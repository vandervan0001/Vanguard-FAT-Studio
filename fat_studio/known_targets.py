"""Read-only selection of identities already authorized on this machine."""

from __future__ import annotations

import asyncio
from collections import Counter
import hashlib
import json
import re

from asyncua import ua

from .adapters.opcua import MappingError
from .models import PLCConfig, Project
from .opcua_browser import MetadataBrowser
from .security import MachinePolicy, TargetDenied


IDENTITY_FIELDS = ("endpoint", "expected_application_uri", "approved_virtual_target", "server_certificate_sha256")
AUTH_FIELDS = ("username_env", "password_env", "client_certificate", "client_private_key")


def _target_id(entry: dict) -> str:
    # The opaque identifier expires if any authorized setting changes. Private
    # references participate in the fingerprint but are never sent to the UI.
    canonical = {key: entry.get(key, "") for key in (*IDENTITY_FIELDS, *AUTH_FIELDS)}
    canonical.update({key: entry.get(key, False) for key in ("allow_insecure", "isolated_virtual_adapter_confirmed")})
    return hashlib.sha256(json.dumps(canonical, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _config(entry: dict) -> PLCConfig:
    return PLCConfig(mode="opcua", **{key: entry.get(key, "") for key in (*IDENTITY_FIELDS, *AUTH_FIELDS)},
                     security_policy="None" if entry.get("allow_insecure") is True else "Basic256Sha256")


def known_targets(policy: MachinePolicy) -> dict:
    entries = policy.entries()
    counts = Counter(entry["endpoint"] for entry in entries)
    targets = []
    for entry in entries:
        reason = ""
        try:
            config = _config(entry)
            if counts[config.endpoint] != 1:
                raise ValueError("Plusieurs autorisations utilisent cette adresse. Corrigez la politique locale.")
            if entry.get("isolated_virtual_adapter_confirmed") is not True:
                raise ValueError("L’adaptateur virtuel isolé doit être confirmé dans la politique locale.")
            if config.security_policy == "Basic256Sha256":
                if not re.fullmatch(r"[0-9a-fA-F:]{64,95}", config.server_certificate_sha256) or len(config.server_certificate_sha256.replace(":", "")) != 64:
                    raise ValueError("L’empreinte serveur SHA-256 de la politique est incomplète.")
                if not config.client_certificate or not config.client_private_key:
                    raise ValueError("Les références du certificat client doivent être configurées dans la politique locale.")
            elif config.username_env or config.password_env:
                raise ValueError("Les identifiants utilisateur exigent une cible avec chiffrement.")
        except ValueError:
            # Validation exceptions can contain private field values. Keep the
            # public error generic, without reflecting policy contents.
            reason = "Autorisation locale incomplète ou ambiguë. Vérifiez sa configuration avec le CLI."
        targets.append({"id": _target_id(entry), "name": entry["approved_virtual_target"],
                        **{key: entry.get(key, "") for key in IDENTITY_FIELDS},
                        "security_policy": "None" if entry.get("allow_insecure") is True else "Basic256Sha256",
                        "authentication_required": any(entry.get(key) for key in AUTH_FIELDS),
                        "selectable": not reason, "reason": reason})
    return {"targets": targets, "editable_from_browser": False}


def preview_known_target(project: Project, policy: MachinePolicy, target_id: str) -> dict:
    current = next((target for target in known_targets(policy)["targets"] if target["id"] == target_id), None)
    if not current or not current["selectable"]:
        raise TargetDenied("Cette cible a changé ou n’est plus autorisée. Actualisez la liste avant de choisir.")
    # Re-read the policy for this explicit selection; no imported project can
    # create a remembered target, even with a plausible opaque identifier.
    entries = [entry for entry in policy.entries() if _target_id(entry) == target_id]
    if len(entries) != 1:
        raise TargetDenied("Cette cible a changé. Actualisez la liste avant de choisir.")
    entry = entries[0]
    authorized = _config(entry)
    policy.authorize(authorized)
    same_identity = (project.plc.mode == "opcua" and project.plc.security_policy == authorized.security_policy
                     and all(getattr(project.plc, key) == getattr(authorized, key) for key in IDENTITY_FIELDS))
    keep_auth = same_identity and all(getattr(project.plc, key) == entry.get(key, "") for key in AUTH_FIELDS)
    result = project.model_copy(deep=True)
    result.plc.mode = "opcua"
    for key in IDENTITY_FIELDS:
        setattr(result.plc, key, getattr(authorized, key))
    result.plc.security_policy = authorized.security_policy
    if not same_identity:
        result.plc.namespace_uri = ""
    if not keep_auth:
        for key in AUTH_FIELDS:
            setattr(result.plc, key, "")
    result.simulation.speed = 1.0
    return {"project": result.model_dump(mode="json"), "target": current,
            "authentication_required": current["authentication_required"] and not keep_auth,
            "notice": "La cible est préparée dans le brouillon. Les NodeId existants sont conservés et restent à vérifier. "
                      "Aucune connexion ni nouvelle autorisation n’a été créée."}


async def check_known_target(project: Project, policy: MachinePolicy, confirmation: str) -> dict:
    if project.plc.mode != "opcua":
        raise MappingError("Choisissez le mode OPC UA pour vérifier la connexion.")
    bounded = project.model_copy(deep=True)
    bounded.plc.timeout_s = min(project.plc.timeout_s, 3.0)
    # The metadata adapter retains certificate/identity checks before session
    # activation and rejects writes. It tolerates incomplete tag mappings.
    adapter = MetadataBrowser(bounded, policy, confirmation)
    try:
        async with asyncio.timeout(20):
            await adapter.connect()
            return {"connected": True, "identity_verified": True, "mapping_checked": False,
                    "namespace_index": adapter.namespace_index, "target": adapter.target,
                    "message": "Connexion et identité vérifiées, puis session fermée. "
                               "Les valeurs et les droits des tags ne sont pas contrôlés par cet essai."}
    except ua.UaError as exc:
        raise MappingError("La vérification OPC UA a été refusée. Aucune écriture effectuée.") from exc
    finally:
        await adapter.disconnect()
