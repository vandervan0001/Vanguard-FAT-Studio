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
from .models import PreparedAction, Project, prepared_value, validate_project
from .security import MachinePolicy
from .storage import Store, utc_now


class RunConflict(ValueError):
    pass


class Runtime:
    def __init__(self, store: Store, project: Project, policy: MachinePolicy, adapter_factory=None, *, context_scope=""):
        self.store = store
        self.policy = policy
        self.adapter_factory = adapter_factory
        self.context_scope = context_scope
        self.lock = asyncio.Lock()
        self._task: asyncio.Task | None = None
        self.adapter = None
        self.set_project(project)

    def set_project(self, project: Project) -> None:
        if getattr(self, "status", "idle") in ("running", "paused"):
            raise RunConflict("Arrêter l'essai avant de modifier le projet.")
        self.project = project.model_copy(deep=True)
        serialized = json.dumps(
            self.project.model_dump(mode="json"), sort_keys=True, ensure_ascii=False,
            separators=(",", ":"), allow_nan=False,
        )
        self.project_revision = hashlib.sha256((self.context_scope + "\0" + serialized if self.context_scope else serialized).encode("utf-8")).hexdigest()
        self.engine = ProcessEngine(self.project)
        self.status = "idle"
        self.run_id = None
        self.error = None
        self.connection = self._new_connection()
        self.series = deque(maxlen=600)
        self.events = deque(maxlen=300)
        self.scenario = None
        self.completed_steps: set[int] = set()
        self.pulses: dict[str, dict] = {}
        self.guided_results: list[dict] = []
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

    async def replace_project(self, project: Project) -> Project:
        """Commit a builder draft; a paused run is finished before its revision changes."""
        async with self.lock:
            if self.status == "running":
                raise RunConflict("Mettre l'essai en pause avant de modifier le projet.")
            try:
                if self.adapter:
                    await self.adapter.disconnect()
                if self.status == "paused":
                    self._expire_pulses(self.engine.time_s, all_pending=True)
                    if self.run_id and not self._run_finished:
                        self.event("project_edit", "Modification du projet en pause : essai conservé, nouveau départ requis.",
                                   {"project_revision": self.project_revision})
                        self.store.set_status(self.run_id, "stopped", ended=True)
                        self._run_finished = True
                await self._cancel_loop()
                self.store.save_project(project)
                self.status = "stopped"
                self.set_project(project)
                self.adapter = None
                return self.project
            except asyncio.CancelledError:
                await self._fail(RuntimeError("Modification du projet annulée ; l'essai reste arrêté."))
                raise
            except Exception as exc:
                if self.status == "paused":
                    await self._fail(exc)
                raise

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
            self.pulses.clear()
            self.guided_results.clear()
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
                self._expire_pulses(self.engine.time_s)
                self._due_actions(self.engine.time_s)
                dt = self.project.simulation.step_ms / 1000
                if self.scenario and self.scenario.execution_mode == "timed":
                    dt = min(dt, self.scenario.duration_s - self.engine.time_s)
                if dt <= 1e-9:
                    await self._complete_scenario()
                    return
                commands = await self.adapter.read(self.engine.values, dt)
                inputs = self.engine.step(commands, dt)
                await self.adapter.write(inputs)
                self.write_count = self.adapter.write_count
                timestamp = self.store.sample(self.run_id, self.engine.time_s, self.engine.values, self.engine.qualities)
                self._guided_applied(inputs)
                self.connection.update(connected=True, quality="good", last_update=timestamp, error=None)
                # UI history is sampled at 2 Hz; the evidence store retains every model cycle.
                if not self.series or self.engine.time_s - self.series[-1]["time_s"] >= 0.5 - 1e-9:
                    self.series.append({"time_s": round(self.engine.time_s, 6), "values": dict(self.engine.values)})
                self._due_assertions(self.engine.time_s)
                if self.scenario and self.scenario.execution_mode == "timed" and self.engine.time_s >= self.scenario.duration_s - 1e-9:
                    # Boundary actions at the final timestamp are recorded but no additional PLC write occurs.
                    self._due_actions(self.engine.time_s)
                    await self._complete_scenario()
            except asyncio.CancelledError:
                await self._fail(RuntimeError("Cycle d'échange annulé ; le dernier lot peut être partiel."))
                raise
            except Exception as exc:
                await self._fail(exc)

    def _due_actions(self, now: float) -> None:
        if not self.scenario or self.scenario.execution_mode != "timed":
            return
        for index, step in enumerate(self.scenario.steps):
            if index in self.completed_steps or step.action == "expect" or step.at_s > now + 1e-9:
                continue
            if step.action == "force":
                self.pulses.pop(step.target, None)
                self.engine.force(step.target, step.value)
            elif step.action == "release":
                self.pulses.pop(step.target, None)
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
        if not self.scenario or self.scenario.execution_mode != "timed":
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
        self._expire_pulses(self.engine.time_s, all_pending=True)
        self.status = "paused"
        self.scenario_state = "completed"
        await self.adapter.disconnect()
        self.connection.update(connected=False, quality="paused")
        self.store.set_status(self.run_id, "completed", ended=True)
        self._run_finished = True
        self.event("scenario_completed", "Scénario terminé ; écritures arrêtées. Verdict humain à renseigner.",
                   {"assertions_passed": sum(result["passed"] for result in self.assertions),
                    "assertions_total": len(self.assertions), "guided_steps_reviewed": len(self.guided_results)})

    async def _fail(self, exc: Exception) -> None:
        previously_finished = self._run_finished
        self.error = f"{type(exc).__name__}: {exc}"
        self.status = "error"
        self.scenario_state = "error"
        if self.guided_results and self.guided_results[-1]["state"] == "queued":
            self.guided_results[-1]["state"] = "error"
        self.connection.update(connected=False, quality="bad", error=self.error)
        self.engine.qualities = {key: "bad" for key in self.engine.values}
        if self.adapter:
            self.write_count = self.adapter.write_count
            try:
                await self.adapter.disconnect()
            except Exception as disconnect_error:
                self.error += f" ; fermeture: {disconnect_error}"
        storage_errors = []
        if self.run_id and not previously_finished:
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
            if previously_finished:
                # An editing/export error is not a new PLC sample or a failure
                # of an already completed run. Keep that evidence untouched.
                self.events.append({"id": "e-" + uuid.uuid4().hex[:10], "timestamp": utc_now(),
                                    "sim_time_s": self.engine.time_s, "kind": "error", "message": message,
                                    "details": {**details, "persisted": False, "outside_finished_run": True}})
            else:
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
                self._expire_pulses(self.engine.time_s, all_pending=True)
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
                self._expire_pulses(self.engine.time_s, all_pending=True)
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
        guided = self.scenario is not None and self.scenario.execution_mode == "guided"
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
                             "completed_steps": sum(step["state"] == "reviewed" for step in self.guided_results) if guided else len(self.completed_steps),
                             "completed_step_indices": [step["index"] for step in self.guided_results if step["state"] == "reviewed"] if guided else sorted(self.completed_steps),
                             "total_steps": len(self.scenario.fat_steps) if guided else len(self.scenario.steps) if self.scenario else 0,
                             "assertions": list(self.assertions)},
                "guided_steps": copy.deepcopy(self.guided_results),
                "pulses": {tag_id: {"expires_s": pulse["expires_s"]} for tag_id, pulse in self.pulses.items()},
                "error": self.error, "write_count": self.write_count, "lag_ms": round(self.lag_ms, 3),
                "model_warnings": self._warnings}

    def require_active(self, *, allow_queued: bool = False) -> None:
        if self.status not in ("running", "paused") or self.scenario_state == "completed":
            raise RunConflict("Démarrer un essai avant d'injecter des valeurs ou des défauts.")
        if not allow_queued and self.guided_results and self.guided_results[-1]["state"] == "queued":
            raise RunConflict("Attendre l'application du STEP au prochain échange avant de modifier les entrées ou les défauts.")

    def _guided_step(self, step_id: str):
        self.require_active(allow_queued=True)
        if not self.scenario or self.scenario.execution_mode != "guided":
            raise RunConflict("L'essai actif n'est pas une FAT pas à pas.")
        step = next((step for step in self.scenario.fat_steps if step.id == step_id), None)
        if step is None:
            raise RunConflict("Cette étape n'appartient pas à la FAT active.")
        return step

    async def execute_fat_step(self, step_id: str) -> dict:
        async with self.lock:
            step = self._guided_step(step_id)
            if self.status != "running":
                raise RunConflict("Reprendre l'essai avant de déclencher une étape.")
            index = len(self.guided_results)
            if self.guided_results and self.guided_results[-1]["state"] != "reviewed":
                raise RunConflict("Consignez l'observation de l'étape en cours avant de poursuivre.")
            if index >= len(self.scenario.fat_steps) or self.scenario.fat_steps[index].id != step_id:
                raise RunConflict("Les étapes FAT se déclenchent une seule fois, dans l'ordre préparé.")
            tags = {tag.id: tag for tag in self.project.tags}
            # Validate the entire image before replacing any input force.
            staged = copy.deepcopy(self.engine)
            actions = []
            for action in step.actions:
                value = prepared_value(tags[action.target], action)
                if action.action == "release":
                    staged.release(action.target)
                else:
                    staged.force(action.target, value, enforce_limits=not action.diagnostic)
                actions.append(dict(**action.model_dump(), raw_value=value))
            entry = dict(id=step.id, index=index, name=step.name, expected_result=step.expected_result,
                         state="queued", requested_s=self.engine.time_s, actions=actions,
                         checks=[], verdict="not_evaluated", observation="")
            await self._record_action("fat_step_requested", f"STEP {index + 1} demandé : {step.name}. Résultat attendu : {step.expected_result}", copy.deepcopy(entry))
            self.engine = staged
            for action in step.actions:
                self.pulses.pop(action.target, None)
            self.guided_results.append(entry)
            return self.snapshot()

    def _guided_applied(self, inputs: dict) -> None:
        if self.guided_results and self.guided_results[-1]["state"] == "queued":
            entry = self.guided_results[-1]
            for action in entry["actions"]:
                tag_id = action["target"]
                actual = inputs.get(tag_id)
                if (tag_id not in inputs or action["action"] == "force" and actual != action["raw_value"]
                        or action["action"] == "release" and tag_id in self.engine.forces):
                    self.event("fat_step_not_applied", "L'image échangée ne confirme pas toutes les actions du STEP.",
                               dict(step_id=entry["id"], target=tag_id, expected=action["raw_value"], actual_wire_value=actual))
                    raise RunConflict("Le STEP préparé ne correspond pas à l'image réellement écrite ; essai interrompu.")
                action["actual_wire_value"] = actual
            entry.update(state="applied", applied_s=self.engine.time_s)
            self.event("fat_step_applied", f"STEP {entry['index'] + 1} : écritures appliquées, observation attendue.", copy.deepcopy(entry))

    def _guided_checks(self, step) -> list[dict]:
        results = []
        for index, check in enumerate(step.checks):
            actual = self.engine.values[check.target]
            if check.operator in ("eq", "ne"):
                equal = actual == check.value if type(actual) is bool else math.isclose(actual, check.value, rel_tol=0, abs_tol=check.tolerance)
                passed = equal if check.operator == "eq" else not equal
            else:
                passed = {"gt": operator.gt, "ge": operator.ge, "lt": operator.lt, "le": operator.le}[check.operator](actual, check.value)
            quality = self.engine.qualities.get(check.target, "unknown")
            results.append(dict(index=index, target=check.target, operator=check.operator, expected=check.value,
                                actual=actual, passed=passed and quality in ("good", "forced", "out_of_range", "fault"),
                                evaluated_s=self.engine.time_s, quality=quality))
        return results

    async def observe_fat_step(self, step_id: str, verdict: str, observation: str) -> dict:
        async with self.lock:
            step = self._guided_step(step_id)
            if self.status != "running" or not self.guided_results or self.guided_results[-1]["id"] != step_id or self.guided_results[-1]["state"] != "applied":
                raise RunConflict("Attendre l'application de cette étape sur un essai en cours avant de l'observer.")
            if verdict not in ("pass", "fail"):
                raise ValueError("Indiquez explicitement conforme ou écart pour cette étape.")
            results = self._guided_checks(step)
            if verdict == "pass" and any(not result["passed"] for result in results):
                raise RunConflict("Un contrôle mesuré présente un écart ; corrigez le procédé ou consignez l'échec de cette étape.")
            entry = dict(self.guided_results[-1], state="reviewed", verdict=verdict, observation=observation,
                         checks=results, observed_s=self.engine.time_s)
            await self._record_action("fat_step_observed", f"STEP {entry['index'] + 1} : {'conforme' if verdict == 'pass' else 'écart constaté'}. {observation}", entry)
            self.guided_results[-1] = entry
            if len(self.guided_results) == len(self.scenario.fat_steps):
                try:
                    await self._complete_scenario()
                except Exception as exc:
                    await self._fail(exc)
                    raise ValueError(self.error) from exc
            return self.snapshot()

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
            self.pulses.pop(tag_id, None)
            await self._record_action("force", f"Forçage de {tag_id} à {value}.", {"tag_id": tag_id, "value": value})
            return self.snapshot()

    async def release(self, tag_id: str) -> dict:
        async with self.lock:
            self.require_active()
            self.engine.release(tag_id)
            self.pulses.pop(tag_id, None)
            await self._record_action("release", f"Libération du forçage {tag_id}.")
            return self.snapshot()

    async def pulse(self, tag_id: str, value: bool, duration_ms: int = 300) -> dict:
        """The server owns the return edge, even when the browser closes."""
        async with self.lock:
            self.require_active()
            tag = next((tag for tag in self.project.tags if tag.id == tag_id), None)
            if self.status != "running" or tag is None or tag.data_type != "BOOL":
                raise RunConflict("Un poussoir exige une entrée BOOL et un essai en cours.")
            if type(value) is not bool or type(duration_ms) is not int or not 100 <= duration_ms <= 2000:
                raise ValueError("Impulsion BOOL attendue, durée entre 100 et 2000 ms simulées.")
            if tag_id in self.pulses:
                raise RunConflict("Une impulsion est déjà en cours sur cette entrée.")
            previous = dict(had_force=tag_id in self.engine.forces, value=self.engine.forces.get(tag_id))
            self.engine.force(tag_id, value)
            self.pulses[tag_id] = dict(**previous, expires_s=self.engine.time_s + duration_ms / 1000)
            await self._record_action("pulse", f"Poussoir {tag.name} à {value} pendant {duration_ms} ms simulées.",
                                      dict(tag_id=tag_id, value=value, duration_ms=duration_ms))
            return self.snapshot()

    async def stimulus(self, tag_id: str, action: PreparedAction) -> dict:
        async with self.lock:
            self.require_active()
            tag = next((tag for tag in self.project.tags if tag.id == tag_id), None)
            if tag is None:
                raise ValueError("Entrée analogique inconnue.")
            if tag.data_type == "BOOL":
                raise ValueError("La conversion de stimulus concerne une entrée analogique.")
            value = prepared_value(tag, action)
            # Store the command before applying it; persistence failure cannot leave a new force active.
            await self._record_action("stimulus", f"Stimulus {tag.name} : {action.value} {action.unit}, valeur PLC {value}.",
                                      dict(tag_id=tag_id, raw_value=value, **action.model_dump()))
            self.engine.force(tag_id, value, enforce_limits=not action.diagnostic)
            self.pulses.pop(tag_id, None)
            return self.snapshot()

    def _expire_pulses(self, now: float, *, all_pending: bool = False) -> None:
        for tag_id, pulse in list(self.pulses.items()):
            if all_pending or now + 1e-9 >= pulse["expires_s"]:
                if pulse["had_force"]:
                    self.engine.force(tag_id, pulse["value"])
                else:
                    self.engine.release(tag_id)
                del self.pulses[tag_id]
                self.event("pulse_release", f"Retour du poussoir {tag_id} à son état précédent.", {"tag_id": tag_id})

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
