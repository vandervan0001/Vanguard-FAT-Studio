"""Offline package validation before installers invoke pip or contact an index."""

import hashlib
import json
from pathlib import Path
import runpy
import subprocess
import sys

import pytest


CHECKER = Path(__file__).resolve().parents[1] / "scripts" / "check-kit.py"
validate_kit = runpy.run_path(str(CHECKER))["validate_kit"]


def test_windows_kit_uses_python_architecture_even_on_an_arm_host(monkeypatch):
    namespace = runpy.run_path(str(CHECKER))
    with monkeypatch.context() as patch:
        patch.setattr(namespace["sys"], "platform", "win32")
        patch.setattr(namespace["platform"], "machine", lambda: "ARM64")
        patch.setattr(namespace["sysconfig"], "get_platform", lambda: "win-amd64")
        assert namespace["platform_name"]() == "Windows-x64"


def make_kit(root, *, target="Windows-x64", engineering=False):
    wheelhouse = root / "wheelhouse"
    wheelhouse.mkdir()
    wheel = wheelhouse / "test-1.0-py3-none-any.whl"
    wheel.write_bytes(b"opaque package bytes; this test validates transfer integrity, not wheel contents")
    manifest = {"schema": 1, "python": "3.12", "platform": target, "engineering": engineering,
                "files": [{"path": wheel.relative_to(root).as_posix(),
                           "sha256": hashlib.sha256(wheel.read_bytes()).hexdigest()}]}
    path = root / "offline-manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8-sig")
    return path, manifest, wheel


def test_valid_offline_kit_accepts_powershell_bom_and_paths_with_spaces(tmp_path):
    root = tmp_path / "FAT dossier épreuve"
    root.mkdir()
    make_kit(root)
    assert validate_kit(root, "Windows-x64") == 1


def test_source_checkout_without_wheels_is_allowed(tmp_path):
    assert validate_kit(tmp_path, "Linux-x64") == 0


def test_wrong_platform_is_rejected_without_falling_back_to_an_index(tmp_path):
    make_kit(tmp_path)
    with pytest.raises(ValueError, match="Windows-x64.*Linux-x64"):
        validate_kit(tmp_path, "Linux-x64")


def test_optional_engineering_requires_prepared_engineering_dependencies(tmp_path):
    make_kit(tmp_path)
    with pytest.raises(ValueError, match="Engineering"):
        validate_kit(tmp_path, "Windows-x64", engineering=True)


@pytest.mark.parametrize("damage", ["modified", "unlisted", "missing_manifest", "missing_wheelhouse"])
def test_damaged_or_incomplete_kit_fails_before_install(tmp_path, damage):
    manifest, _, wheel = make_kit(tmp_path)
    if damage == "modified":
        wheel.write_bytes(wheel.read_bytes() + b"corruption")
    elif damage == "unlisted":
        (wheel.parent / "unexpected.whl").write_bytes(b"not in manifest")
    elif damage == "missing_manifest":
        manifest.unlink()
    else:
        wheel.unlink()
        wheel.parent.rmdir()
    with pytest.raises(ValueError):
        validate_kit(tmp_path, "Windows-x64")


@pytest.mark.parametrize("invalid", ["../escape.whl", "/absolute.whl", "C:/file.whl", r"wheelhouse\file.whl", "wheelhouse//file.whl"])
def test_manifest_paths_cannot_escape_or_change_meaning_between_platforms(tmp_path, invalid):
    path, manifest, _ = make_kit(tmp_path)
    manifest["files"][0]["path"] = invalid
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="Chemin invalide"):
        validate_kit(tmp_path, "Windows-x64")


def test_manifest_rejects_case_collisions_on_windows(tmp_path):
    path, manifest, _ = make_kit(tmp_path)
    alias = {**manifest["files"][0], "path": manifest["files"][0]["path"].upper()}
    manifest["files"].append(alias)
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="dupliqué"):
        validate_kit(tmp_path, "Windows-x64")


def test_checker_cli_reports_incomplete_kit_as_nonzero(tmp_path):
    (tmp_path / "wheelhouse").mkdir()
    result = subprocess.run([sys.executable, str(CHECKER), "--root", str(tmp_path)],
                            capture_output=True, text=True, encoding="utf-8", timeout=10)
    assert result.returncode == 2
    assert "Kit incomplet" in result.stderr
