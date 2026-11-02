"""Offline package validation before installers invoke pip or contact an index."""

import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys

import pytest


CHECKER = Path(__file__).resolve().parents[1] / "scripts" / "check-kit.py"
BUILD_WEB = CHECKER.with_name("build-web.py")
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
    result = subprocess.run([sys.executable, "-X", "utf8", str(CHECKER), "--root", str(tmp_path)],
                            capture_output=True, text=True, encoding="utf-8", timeout=10)
    assert result.returncode == 2
    assert "Kit incomplet" in result.stderr


def make_web_build(root):
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    script = scripts / "build-web.py"
    script.write_bytes(BUILD_WEB.read_bytes())
    frontend = root / "frontend" / "dist"
    (frontend / "assets").mkdir(parents=True)
    (frontend / "index.html").write_text('<script src="/assets/index-new.js"></script>\n')
    (frontend / "assets" / "index-new.js").write_text('window.FAT_BUILD = "new";\n')
    bundled = root / "fat_studio" / "web"
    bundled.mkdir(parents=True)
    (bundled / "old-bundle.txt").write_text("previous bundled interface\n")
    return script, bundled


def run_web_build(script):
    return subprocess.run([sys.executable, "-X", "utf8", str(script)], capture_output=True, text=True,
                          encoding="utf-8", timeout=10)


def test_web_bundle_removes_only_its_generated_setuptools_cache(tmp_path):
    root = tmp_path / "FAT dossier épreuve"
    script, bundled = make_web_build(root)
    cache = root / "build" / "lib" / "fat_studio" / "web"
    (cache / "assets").mkdir(parents=True)
    stale = cache / "assets" / "index-old.js"
    stale.write_text('window.FAT_BUILD = "old";\n')
    sibling = cache.parent / "engine.py"
    sibling.write_text("# unrelated generated Python module\n")
    other_package = root / "build" / "lib" / "other_package" / "keep.py"
    other_package.parent.mkdir()
    other_package.write_text("# another package build output\n")
    assert stale.is_file()

    result = run_web_build(script)

    assert result.returncode == 0, result.stderr
    assert not cache.exists()
    assert (bundled / "assets" / "index-new.js").read_text() == 'window.FAT_BUILD = "new";\n'
    assert not (bundled / "old-bundle.txt").exists()
    assert sibling.read_text() == "# unrelated generated Python module\n"
    assert other_package.read_text() == "# another package build output\n"


@pytest.mark.parametrize("link_path", ["build", "build/lib", "build/lib/fat_studio", "build/lib/fat_studio/web"])
def test_web_bundle_refuses_cache_symlink_or_linked_parent_before_mutation(tmp_path, link_path):
    root = tmp_path / "fat-source"
    script, bundled = make_web_build(root)
    outside = tmp_path / "shared-outside-output"
    outside.mkdir()
    protected = outside / "keep.txt"
    protected.write_text("must remain untouched\n")
    link = root / link_path
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        if sys.platform == "win32":
            pytest.skip(f"Windows account cannot create the symlink required for this check: {exc}")
        raise

    result = run_web_build(script)

    assert result.returncode != 0
    assert "Refus" in result.stderr
    assert link.is_symlink()
    assert protected.read_text() == "must remain untouched\n"
    assert (bundled / "old-bundle.txt").read_text() == "previous bundled interface\n"
    assert not (bundled / "assets" / "index-new.js").exists()


@pytest.mark.skipif(sys.platform != "win32", reason="NTFS junctions are a Windows filesystem boundary")
@pytest.mark.parametrize("link_path", ["build", "build/lib", "build/lib/fat_studio", "build/lib/fat_studio/web"])
@pytest.mark.parametrize("target_in_root", [False, True], ids=["external-target", "shared-in-root-target"])
def test_web_bundle_refuses_real_cache_junction_before_mutation(tmp_path, link_path, target_in_root):
    root = tmp_path / "FAT source épreuve"
    script, bundled = make_web_build(root)
    target = (root if target_in_root else tmp_path) / "shared-generated-output"
    target.mkdir()
    protected = target / "keep.txt"
    protected.write_text("shared output must remain untouched\n")
    link = root / link_path
    link.parent.mkdir(parents=True, exist_ok=True)
    command = (
        "$ErrorActionPreference = 'Stop';"
        "[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false);"
        "New-Item -ItemType Junction -Path $env:FAT_TEST_JUNCTION_LINK "
        "-Target $env:FAT_TEST_JUNCTION_TARGET | Out-Null"
    )
    created = subprocess.run(
        ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command],
        env={**os.environ, "FAT_TEST_JUNCTION_LINK": str(link), "FAT_TEST_JUNCTION_TARGET": str(target)},
        capture_output=True, text=True, encoding="utf-8", timeout=15,
    )
    assert created.returncode == 0, created.stderr
    assert link.is_junction(), "The test must exercise an actual NTFS junction"
    try:
        result = run_web_build(script)

        assert result.returncode != 0
        assert "Refus" in result.stderr
        assert link.is_junction()
        assert protected.read_text() == "shared output must remain untouched\n"
        assert (bundled / "old-bundle.txt").read_text() == "previous bundled interface\n"
        assert not (bundled / "assets" / "index-new.js").exists()
    finally:
        # Remove only this test's junction; never recurse into its shared target.
        if link.is_junction():
            link.rmdir()
