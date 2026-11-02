"""Single-owner FAT execution, scenario scheduling, communication fail-stop and evidence."""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import math
import operator
import time
import uuid
from collections import deque

from .adapters.demo import DemoAdapter
from .adapters.opcua import OpcUaAdapter
from .engine import ProcessEngine
from .models import Project, validate_project
from .security import MachinePolicy
from .storage import Store, utc_now


class RunConflict(ValueError):
    pass


class Runtime:
    def __init__(self, store: Store, project: Project, policy: MachinePolicy, adapter_factory=None):
        self.store = store
        self.policy = policy
        self.adapter_factory = adapter_factory
        self.lock = asyncio.Lock()
        self._task: asyncio.Task | None = None
        self.adapter = None
        self.set_project(project)

    def set_project(self, project: Project) -> None:
        if getattr(self, "status", "idle") in ("running", "paused"):
            raise RunConflict("Arrêter l'essai avant de modifier le projet.")
        self.project = project.model_copy(deep=True)
        self.project_revision = hashlib.sha256(json.dumps(
            self.project.model_dump(mode="json"), sort_keys=True, ensure_ascii=False,
            separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")).hexdigest()
        self.engine = ProcessEngine(self.project)
        self.status = "idle"
        self.run_id = None
        self.error = None
        self.connection = self._new_connection()
        self.series = deque(maxlen=600)
        self.events = deque(maxlen=300)
        self.scenario = None
        self.completed_steps: set[int] = set()
        self.assertions = []
        self.result = {"verdict": "not_evaluated", "comment": ""}
        self.scenario_state = "idle"
        self.write_count = 0
        self.lag_ms = 0.0
        self._last_overrun_event = -60.0
        self._warnings = [issue["message"] for issue in validate_project(self.project)["warnings"]]
        self._last_confirmation = ""
        self._run_finished = False

    def _new_connection(self) -> dict:
        return {"mode": self.project.plc.mode, "connected": False,
                "target": ("Contrôleur de démonstration local — aucun PLC connecté" if self.project.plc.mode == "demo"
                           else f"{self.project.plc.approved_virtual_target} @ {self.project.plc.endpoint}"),
                "quality": "disconnected", "last_update": None, "error": None}

    def ensure_editable(self) -> None:
        if self.status in ("running", "paused"):
            raise RunConflict("Arrêter l'essai avant de modifier, importer ou charger un projet.")

    def event(self, kind: str, message: str, details=None) -> None:
        if self.run_id:
            entry = self.store.event(self.run_id, self.engine.time_s, kind, message, details)
        else:
            entry = {"id": "e-" + uuid.uuid4().hex[:10], "timestamp": utc_now(),
                     "sim_time_s": self.engine.time_s, "kind": kind, "message": message, "details": details or {}}
        self.events.append(entry)

    async def start(self, scenario_id: str | None = None, confirmation: str = "", background: bool = True) -> dict:
        async with self.lock:
            self.ensure_editable()
            await self._cancel_loop()
            validation = validate_project(self.project)
            if not validation["valid"]:
                raise ValueError("Projet invalide : " + "; ".join(item["message"] for item in validation["errors"]))
            if self.project.plc.mode == "opcua" and self.project.simulation.speed != 1:
                raise ValueError("La vitesse doit rester à 1× avec un PLC externe. L'accélération est réservée à la démo.")
            scenario = None
            if scenario_id:
                scenario = next((item for item in self.project.scenarios if item.id == scenario_id), None)
                if scenario is None:
                    raise ValueError("Scénario introuvable.")
            if self.adapter:
                await self.adapter.disconnect()
            self.engine.reset()
            self.scenario = scenario
            self.completed_steps = set()
            self.assertions = []
            self.result = {"verdict": "not_evaluated", "comment": ""}
            self.scenario_state = "running" if scenario else "manual"
            self.error = None
            self.events.clear()
            self.series.clear()
            self.write_count = 0
            self.lag_ms = 0.0
            self._last_overrun_event = -60.0
            self._last_confirmation = confirmation
            self.connection = self._new_connection()
            self.run_id = "run-" + uuid.uuid4().hex
            self._run_finished = False
            try:
                self.store.start_run(self.run_id, self.project, scenario, self.connection)
                self.event("start_requested", "Démarrage demandé.", {"mode": self.project.plc.mode,
                           "target": self.connection["target"], "step_ms": self.project.simulation.step_ms,
                           "speed": self.project.simulation.speed})
                if self.adapter_factory:
                    self.adapter = self.adapter_factory(self.project)
                elif self.project.plc.mode == "demo":
                    self.adapter = DemoAdapter(self.project)
                else:
                    self.adapter = OpcUaAdapter(self.project, self.policy, confirmation)
                await self.adapter.connect()
                self.connection.update(connected=True, quality="connected", error=None)
                self.status = "running"
                self.event("started", "Essai démarré. Mapping validé avant toute écriture.")
                if self.project.plc.mode == "opcua":
                    self.event("model_boundary", "Le PLC garde seul le contrôle. Pause/reset du banc ne change pas l'état de la CPU.")
                if background:
                    self._task = asyncio.create_task(self._loop(self.run_id), name="fat-studio-runtime")
            except asyncio.CancelledError:
                await self._fail(RuntimeError("Démarrage annulé ; l'essai doit être redémarré explicitement."))
                raise
            except Exception as exc:
                await self._fail(exc)
                raise ValueError(self.error) from exc
            return self.snapshot()

    async def _loop(self, run_id: str) -> None:
        interval = self.project.simulation.step_ms / 1000 / self.project.simulation.speed
        deadline = time.monotonic()
        try:
            while self.status == "running" and self.run_id == run_id:
                await self.tick()
                deadline += interval
                now = time.monotonic()
                self.lag_ms = max(0.0, now - deadline) * 1000
                if now > deadline:
                    if self.engine.time_s - self._last_overrun_event >= 10:
                        self.event("timing_overrun", "Cycle plus lent que le pas demandé ; temps simulé non synchronisé au temps réel.",
                                   {"lag_ms": round(self.lag_ms, 3)})
                        self._last_overrun_event = self.engine.time_s
                    # No unbounded catch-up burst against the PLC.
                    deadline = now
                await asyncio.sleep(max(0.001, deadline - now))
        except asyncio.CancelledError:
            # pause/stop detach the task before cancelling it while owning the
            # lock. An independent cancellation must close the live run too.
            if self._task is asyncio.current_task() and self.status == "running":
                async with self.lock:
                    await self._fail(RuntimeError("Boucle d'essai annulée ; écritures arrêtées."))
            raise
        except Exception as exc:
            async with self.lock:
                await self._fail(exc)
        finally:
            if self._task is asyncio.current_task():
                self._task = None

    async def tick(self) -> None:
        async with self.lock:
            if self.status != "running":
                return
            try:
                self._due_actions(self.engine.time_s)
                dt = self.project.simulation.step_ms / 1000
                if self.scenario:
                    dt = min(dt, self.scenario.duration_s - self.engine.time_s)
                if dt <= 1e-9:
                    await self._complete_scenario()
                    return
                commands = await self.adapter.read(self.engine.values, dt)
                inputs = self.engine.step(commands, dt)
                await self.adapter.write(inputs)
                self.write_count = self.adapter.write_count
                timestamp = self.store.sample(self.run_id, self.engine.time_s, self.engine.values, self.engine.qualities)
                self.connection.update(connected=True, quality="good", last_update=timestamp, error=None)
                # UI history is sampled at 2 Hz; the evidence store retains every model cycle.
                if not self.series or self.engine.time_s - self.series[-1]["time_s"] >= 0.5 - 1e-9:
                    self.series.append({"time_s": round(self.engine.time_s, 6), "values": dict(self.engine.values)})
                self._due_assertions(self.engine.time_s)
                if self.scenario and self.engine.time_s >= self.scenario.duration_s - 1e-9:
                    # Boundary actions at the final timestamp are recorded but no additional PLC write occurs.
                    self._due_actions(self.engine.time_s)
                    await self._complete_scenario()
            except asyncio.CancelledError:
                await self._fail(RuntimeError("Cycle d'échange annulé ; le dernier lot peut être partiel."))
                raise
            except Exception as exc:
                await self._fail(exc)

    def _due_actions(self, now: float) -> None:
        if not self.scenario:
            return
        for index, step in enumerate(self.scenario.steps):
            if index in self.completed_steps or step.action == "expect" or step.at_s > now + 1e-9:
                continue
            if step.action == "force":
                self.engine.force(step.target, step.value)
            elif step.action == "release":
                self.engine.release(step.target)
            elif step.action == "fault":
                self.engine.set_fault(step.target, step.value["kind"], step.value.get("value"))
            elif step.action == "clear_fault":
                self.engine.clear_fault(step.target, step.value.get("kind") if isinstance(step.value, dict) else None)
            self.completed_steps.add(index)
            message = step.message or (step.value if step.action == "marker" and isinstance(step.value, str) else f"{step.action} : {step.target}")
            self.event("scenario_" + step.action, message,
                       {"index": index, "scheduled_s": step.at_s, "target": step.target, "value": step.value})

    def _due_assertions(self, now: float) -> None:
        if not self.scenario:
            return
        comparisons = {"gt": operator.gt, "ge": operator.ge, "lt": operator.lt, "le": operator.le}
        for index, step in enumerate(self.scenario.steps):
            if index in self.completed_steps or step.action != "expect" or step.at_s > now + 1e-9:
                continue
            actual = self.engine.values[step.target]
            if step.operator in ("eq", "ne"):
                equal = actual == step.value if type(actual) is bool else math.isclose(
                    actual, step.value, rel_tol=0, abs_tol=step.tolerance)
                passed = equal if step.operator == "eq" else not equal
            else:
                passed = comparisons[step.operator](actual, step.value)
            result = {"index": index, "target": step.target, "operator": step.operator,
                      "expected": step.value, "actual": actual, "passed": passed,
                      "message": step.message, "scheduled_s": step.at_s, "evaluated_s": now,
                      "quality": self.engine.qualities.get(step.target, "unknown")}
            self.assertions.append(result)
            self.completed_steps.add(index)
            self.event("assertion_pass" if passed else "assertion_fail",
                       step.message or f"{step.target} {step.operator} {step.value} : {'OK' if passed else 'ÉCHEC'}", result)

    async def _complete_scenario(self) -> None:
        self.status = "paused"
        self.scenario_state = "completed"
        await self.adapter.disconnect()
        self.connection.update(connected=False, quality="paused")
        self.store.set_status(self.run_id, "completed", ended=True)
        self._run_finished = True
        self.event("scenario_completed", "Scénario terminé ; écritures arrêtées. Verdict humain à renseigner.",
                   {"assertions_passed": sum(result["passed"] for result in self.assertions),
                    "assertions_total": len(self.assertions)})

    async def _fail(self, exc: Exception) -> None:
        self.error = f"{type(exc).__name__}: {exc}"
        self.status = "error"
        self.scenario_state = "error"
        self.connection.update(connected=False, quality="bad", error=self.error)
        self.engine.qualities = {key: "bad" for key in self.engine.values}
        if self.adapter:
            self.write_count = self.adapter.write_count
            try:
                await self.adapter.disconnect()
            except Exception as disconnect_error:
                self.error += f" ; fermeture: {disconnect_error}"
        storage_errors = []
        if self.run_id:
            # A full/read-only disk must not prevent fail-stop or hide the cause in
            # an unhandled background-task exception. Try each record independently.
            try:
                self.store.sample(self.run_id, self.engine.time_s, self.engine.values, self.engine.qualities)
            except Exception as storage_error:
                storage_errors.append(f"échantillon : {storage_error}")
            try:
                self.store.set_status(self.run_id, "error", ended=True)
            except Exception as storage_error:
                storage_errors.append(f"statut : {storage_error}")
            self._run_finished = True
        if storage_errors:
            self.error += " ; enregistrement impossible (" + "; ".join(storage_errors) + ")"
        details = {"partial_write": getattr(exc, "results", None)}
        message = "Essai interrompu. Les écritures cessent ; aucune reconnexion automatique. " + self.error
        try:
            self.event("error", message, details)
        except Exception as storage_error:
            self.error += f" ; journal non enregistré : {storage_error}"
            self.events.append({"id": "e-" + uuid.uuid4().hex[:10], "timestamp": utc_now(),
                                "sim_time_s": self.engine.time_s, "kind": "error",
                                "message": self.error, "details": {**details, "persisted": False}})
        self.connection["error"] = self.error

    async def storage_failed(self, exc: Exception) -> None:
        """Stop an active run when a user action can no longer be recorded."""
        async with self.lock:
            if self.status in ("running", "paused"):
                await self._fail(exc)
                await self._cancel_loop()

    async def _cancel_loop(self) -> None:
        task, self._task = self._task, None
        if task and task is not asyncio.current_task():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def pause(self) -> dict:
        async with self.lock:
            if self.status != "running":
                raise RunConflict("Seul un essai en cours peut être mis en pause.")
            self.status = "paused"
            self.scenario_state = "paused" if self.scenario else "manual"
            try:
                await self.adapter.disconnect()
                self.connection.update(connected=False, quality="paused")
                self.store.set_status(self.run_id, "paused")
                self.event("pause", "Modèle et échanges en pause. La CPU externe n'est pas mise en STOP.")
            except asyncio.CancelledError:
                await self._fail(RuntimeError("Mise en pause annulée ; l'essai ne peut pas être repris."))
                raise
            except Exception as exc:
                await self._fail(exc)
                raise ValueError(self.error) from exc
            finally:
                await self._cancel_loop()
        return self.snapshot()

    async def resume(self, background: bool = True) -> dict:
        async with self.lock:
            if self.status != "paused" or self.scenario_state == "completed":
                raise RunConflict("Cet essai ne peut pas être repris. Réinitialiser pour un nouvel essai.")
            try:
                await self.adapter.connect()
                self.connection.update(connected=True, quality="connected", error=None)
                self.status = "running"
                self.scenario_state = "running" if self.scenario else "manual"
                self.store.set_status(self.run_id, "running")
                self.event("resume", "Reprise explicite ; identité et mapping revalidés.")
                if background:
                    self._task = asyncio.create_task(self._loop(self.run_id), name="fat-studio-runtime")
            except asyncio.CancelledError:
                await self._fail(RuntimeError("Reprise annulée ; l'essai doit être redémarré explicitement."))
                raise
            except Exception as exc:
                await self._fail(exc)
                raise ValueError(self.error) from exc
        return self.snapshot()

    async def stop(self) -> dict:
        async with self.lock:
            self.status = "stopped"
            try:
                if self.adapter:
                    await self.adapter.disconnect()
                self.connection.update(connected=False, quality="stopped")
                if self.run_id and not self._run_finished:
                    self.store.set_status(self.run_id, "stopped", ended=True)
                    self._run_finished = True
                self.event("stop", "Essai arrêté. Aucune commande de CPU envoyée.")
                self.scenario_state = "stopped"
            except asyncio.CancelledError:
                await self._fail(RuntimeError("Fermeture de l'essai annulée ; écritures arrêtées."))
                raise
            except Exception as exc:
                await self._fail(exc)
            finally:
                await self._cancel_loop()
        return self.snapshot()

    async def reset(self) -> dict:
        async with self.lock:
            if self.status == "running":
                raise RunConflict("Mettre en pause ou arrêter l'essai avant réinitialisation.")
            await self._cancel_loop()
            try:
                if self.adapter:
                    await self.adapter.disconnect()
                if self.run_id and not self._run_finished:
                    self.event("reset", "Fin de l'essai par réinitialisation du modèle.")
                    self.store.set_status(self.run_id, "stopped", ended=True)
                self.status = "stopped"
                project = self.project
                self.set_project(project)
                self.adapter = None
                self.event("reset", "Modèle réinitialisé ; traces précédentes conservées dans l'historique.")
            except asyncio.CancelledError:
                await self._fail(RuntimeError("Réinitialisation annulée ; l'essai ne peut pas être repris."))
                raise
        return self.snapshot()

    async def close(self) -> None:
        await self.stop()

    def snapshot(self) -> dict:
        tags = {}
        for key, value in self.engine.values.items():
            quality = self.engine.qualities.get(key, "unknown")
            if self.status == "error":
                quality = "bad"
            elif self.status in ("paused", "stopped"):
                quality = "paused" if self.status == "paused" else "stale"
            elif self.status == "idle":
                quality = "initial"
            tags[key] = {"value": value, "quality": quality, "forced": key in self.engine.forces}
        return {"project_id": self.project.id, "project_revision": self.project_revision,
                "status": self.status, "sim_time_s": round(self.engine.time_s, 6), "wall_time": utc_now(),
                "run_id": self.run_id, "connection": dict(self.connection), "tags": tags,
                "equipment": copy.deepcopy(self.engine.equipment_state), "faults": copy.deepcopy(self.engine.faults),
                "events": list(self.events), "series": list(self.series),
                "result": dict(self.result),
                "scenario": {"id": self.scenario.id if self.scenario else None, "state": self.scenario_state,
                             "completed_steps": len(self.completed_steps),
                             "total_steps": len(self.scenario.steps) if self.scenario else 0,
                             "assertions": list(self.assertions)},
                "error": self.error, "write_count": self.write_count, "lag_ms": round(self.lag_ms, 3),
                "model_warnings": self._warnings}

    def require_active(self) -> None:
        if self.status not in ("running", "paused") or self.scenario_state == "completed":
            raise RunConflict("Démarrer un essai avant d'injecter des valeurs ou des défauts.")

    async def _record_action(self, kind: str, message: str, details=None) -> None:
        """Fail while still owning the model lock if an operator action is not durable."""
        try:
            self.event(kind, message, details)
        except Exception as exc:
            if self.status in ("running", "paused"):
                await self._fail(exc)
                await self._cancel_loop()
            raise

    async def marker(self, message: str) -> dict:
        async with self.lock:
            if not self.run_id:
                raise ValueError("Aucun essai à annoter.")
            await self._record_action("marker", message)
            return self.snapshot()

    async def set_result(self, verdict: str, comment: str) -> dict:
        async with self.lock:
            if not self.run_id:
                raise ValueError("Aucun essai à évaluer.")
            try:
                entry = self.store.set_result(self.run_id, verdict, comment, sim_time_s=self.engine.time_s)
            except Exception as exc:
                if self.status in ("running", "paused"):
                    await self._fail(exc)
                    await self._cancel_loop()
                raise
            self.result = {"verdict": verdict, "comment": comment}
            self.events.append(entry)
            return self.snapshot()

    async def force(self, tag_id: str, value) -> dict:
        async with self.lock:
            self.require_active()
            self.engine.force(tag_id, value)
            await self._record_action("force", f"Forçage de {tag_id} à {value}.", {"tag_id": tag_id, "value": value})
            return self.snapshot()

    async def release(self, tag_id: str) -> dict:
        async with self.lock:
            self.require_active()
            self.engine.release(tag_id)
            await self._record_action("release", f"Libération du forçage {tag_id}.")
            return self.snapshot()

    async def fault(self, equipment_id: str, kind: str, value=None) -> dict:
        async with self.lock:
            self.require_active()
            self.engine.set_fault(equipment_id, kind, value)
            await self._record_action("fault", f"Défaut {kind} sur {equipment_id}.", {"equipment_id": equipment_id, "kind": kind, "value": value})
            return self.snapshot()

    async def clear_fault(self, equipment_id: str) -> dict:
        async with self.lock:
            self.require_active()
            self.engine.clear_fault(equipment_id)
            await self._record_action("clear_fault", f"Défauts retirés sur {equipment_id}.")
            return self.snapshot()
