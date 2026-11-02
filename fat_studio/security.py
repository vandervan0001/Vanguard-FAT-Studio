"""Local machine authorization is deliberately separate from imported FAT projects."""

from __future__ import annotations

import ipaddress
import json
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import urlsplit


class TargetDenied(ValueError):
    pass


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def safe_id(value: str) -> str:
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}", value):
        raise ValueError("Identifiant invalide : lettres, chiffres, _ et - uniquement (80 maximum).")
    return value


def validate_endpoint(endpoint: str) -> str:
    try:
        if not isinstance(endpoint, str) or not endpoint or any(c.isspace() or ord(c) < 32 for c in endpoint):
            raise ValueError
        parsed = urlsplit(endpoint)
        if (parsed.scheme != "opc.tcp" or parsed.username is not None or parsed.password is not None
                or parsed.query or parsed.fragment):
            raise ValueError
        if not parsed.hostname or not parsed.port:
            raise ValueError
        address = ipaddress.ip_address(parsed.hostname)
        if not (address.is_private or address.is_loopback) or address.is_unspecified or address.is_multicast:
            raise ValueError
        if address.is_reserved and not address.is_loopback:
            raise ValueError
        return str(address)
    except ValueError as exc:
        raise TargetDenied(
            "Cible refusée : utiliser opc.tcp://IP_PRIVEE:PORT avec une IP explicite de l'instance "
            "virtuelle locale. Les noms DNS, identifiants dans l'URL et adresses publiques sont interdits."
        ) from exc


class MachinePolicy:
    def __init__(self, path: Path):
        self.path = path

    def entries(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            content = json.loads(self.path.read_text(encoding="utf-8"))
            if (not isinstance(content, dict) or type(content.get("version")) is not int
                    or content.get("version") != 1 or not isinstance(content.get("targets"), list)):
                raise ValueError
            for entry in content["targets"]:
                self._validate_entry(entry)
            return content["targets"]
        except (ValueError, TypeError, KeyError) as exc:
            raise TargetDenied("Politique locale invalide. Corriger machine-policy.json avant connexion.") from exc

    @staticmethod
    def _validate_entry(entry: dict) -> None:
        if not isinstance(entry, dict):
            raise TargetDenied("Chaque cible de la politique doit être un objet JSON.")
        for key in ("endpoint", "expected_application_uri", "approved_virtual_target"):
            if not isinstance(entry.get(key), str) or not entry[key].strip():
                raise TargetDenied(f"Champ obligatoire absent de la politique : {key}.")
        validate_endpoint(entry["endpoint"])
        for key in ("server_certificate_sha256", "username_env", "password_env", "client_certificate", "client_private_key"):
            if not isinstance(entry.get(key, ""), str):
                raise TargetDenied(f"Le champ de politique {key} doit être une chaîne.")
        for key in ("allow_insecure", "isolated_virtual_adapter_confirmed"):
            if type(entry.get(key, False)) is not bool:
                raise TargetDenied(f"Le champ de politique {key} doit être un booléen.")

    def authorize(self, plc, confirmation: str | None = None) -> dict:
        validate_endpoint(plc.endpoint)
        matches = [entry for entry in self.entries() if entry.get("endpoint") == plc.endpoint]
        if len(matches) != 1:
            raise TargetDenied(
                "Cible absente de la politique du poste. Utiliser la commande locale "
                "fat-studio authorize-target après vérification de l'adaptateur PLCSIM isolé."
            )
        entry = matches[0]
        if entry.get("isolated_virtual_adapter_confirmed") is not True:
            raise TargetDenied("L'isolation de l'adaptateur virtuel n'est pas confirmée sur ce poste.")
        for key in ("expected_application_uri", "approved_virtual_target"):
            if not entry.get(key) or entry[key] != getattr(plc, key):
                raise TargetDenied(f"L'identité {key} ne correspond pas à la politique locale.")
        # An imported JSON project must not select arbitrary environment secrets or
        # client private-key files, even when the destination was approved earlier.
        for key in ("username_env", "password_env", "client_certificate", "client_private_key"):
            if getattr(plc, key) != entry.get(key, ""):
                raise TargetDenied(f"Le champ {key} n'est pas autorisé par la politique locale.")
        fingerprint = plc.server_certificate_sha256.lower().replace(":", "")
        if fingerprint != entry.get("server_certificate_sha256", "").lower().replace(":", ""):
            raise TargetDenied("L'empreinte du certificat ne correspond pas à la politique locale.")
        if plc.security_policy == "None" and entry.get("allow_insecure") is not True:
            raise TargetDenied("OPC UA sans chiffrement n'est pas autorisé pour cette cible locale.")
        if plc.security_policy != "None" and not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
            raise TargetDenied("Une empreinte serveur SHA-256 est obligatoire avec SignAndEncrypt.")
        expected = f"{plc.approved_virtual_target} @ {plc.endpoint}"
        if confirmation is not None and confirmation != expected:
            raise TargetDenied(f"Confirmer exactement la cible : {expected}")
        return entry

    def add(self, entry: dict) -> None:
        self._validate_entry(entry)
        entries = [item for item in self.entries() if item.get("endpoint") != entry["endpoint"]]
        entries.append(entry)
        atomic_json(self.path, {"version": 1, "targets": entries})
