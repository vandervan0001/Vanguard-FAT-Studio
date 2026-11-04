"""Local project directories and staged archive restoration, independent of target policy."""
from __future__ import annotations

import json
from pathlib import Path
import re
import tempfile
import uuid

from .archive import restore_archive
from .security import atomic_json, safe_id
from .storage import Store


def workspace_path(root: Path, id: str) -> Path:
    root = root.resolve()
    if id == "default":
        return root
    if not re.fullmatch(r"w-[0-9a-f]{32}", id):
        raise ValueError("Identifiant d'espace local invalide.")
    parent = root / "workspaces"
    path = parent / id
    if parent.is_symlink() or parent.is_junction() or path.is_symlink() or path.is_junction():
        raise ValueError("Les liens de dossier ne sont pas acceptés pour un espace restauré.")
    if not path.resolve().is_relative_to(root):
        raise ValueError("Espace hors du répertoire de données.")
    return path


def active_workspace(root: Path) -> str:
    pointer = root / "active-workspace.json"
    if not pointer.exists():
        return "default"
    value = json.loads(pointer.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or set(value) != {"version", "id"} or type(value["version"]) is not int or value["version"] != 1:
        raise ValueError("Pointeur d'espace local invalide ; les dossiers sont conservés.")
    path = workspace_path(root, value["id"])
    if not path.is_dir():
        raise ValueError("Espace local absent ; les autres dossiers sont conservés.")
    return value["id"]


def select_workspace(root: Path, id: str) -> None:
    if not workspace_path(root, id).is_dir():
        raise ValueError("Espace local absent.")
    atomic_json(root / "active-workspace.json", dict(version=1, id=id))


def workspace_summary(root: Path, id: str, active_id: str) -> dict:
    path = workspace_path(root, id)
    pointer = json.loads((path / "last-project.json").read_text(encoding="utf-8"))
    project_id = safe_id(pointer["id"])
    project_path = path / "projects" / (project_id + ".json")
    if project_path.is_symlink() or project_path.is_junction():
        raise ValueError("Lien de projet refusé.")
    project = json.loads(project_path.read_text(encoding="utf-8"))
    return dict(id=id, name=project["name"], path=str(path), active=id == active_id, project_id=project_id)


def list_workspaces(root: Path, active_id: str) -> list[dict]:
    ids = ["default"]
    parent = root / "workspaces"
    if parent.is_symlink() or parent.is_junction():
        raise ValueError("Répertoire d'espaces lié refusé.")
    if parent.is_dir():
        ids.extend(path.name for path in sorted(parent.iterdir()) if re.fullmatch(r"w-[0-9a-f]{32}", path.name) and path.is_dir())
    results = []
    for id in ids:
        try:
            results.append(workspace_summary(root, id, active_id))
        except (ValueError, OSError, KeyError):
            # A corrupt inactive directory does not replace or hide the active one.
            results.append(dict(id=id, name="Espace à vérifier", path=str(workspace_path(root, id)), active=id == active_id,
                                project_id=None, error="Dossier illisible ; conservé intact."))
    return results


def restore_workspace(root: Path, plan) -> tuple[str, Path]:
    parent = root / "workspaces"
    workspace_path(root, "w-" + "0" * 32)  # Validate parent boundaries before mkdir/staging.
    parent.mkdir(parents=True, exist_ok=True)
    id = "w-" + uuid.uuid4().hex
    destination = workspace_path(root, id)
    with tempfile.TemporaryDirectory(prefix=".fat-stage-", dir=parent) as staging:
        staged = Path(staging) / "project"
        store = Store(staged)
        try:
            restore_archive(store, plan)
        finally:
            store.close()
        if destination.exists():
            raise ValueError("Un espace existe déjà à cette destination.")
        staged.rename(destination)
    return id, destination
