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
PUBLIC = runpy.run_path(str(CHECKER.parents[1] / "public_distribution.py"))
PORTABLE = runpy.run_path(str(CHECKER.with_name("check-portable.py")))


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


def public_source(root):
    (root / "fat_studio").mkdir()
    (root / "integrations").mkdir()
    (root / "fat_studio/__init__.py").write_text("# public FAT runtime\n")
    policy = {"schema": 1, "wheel_files": ["fat_studio/__init__.py"], "wheel_patterns": [],
              "source_files": ["fat_studio/__init__.py"], "source_patterns": []}
    (root / "public-distribution.json").write_text(json.dumps(policy))
    return policy


def make_public_wheel(path, extra=None):
    import zipfile
    entries = {"fat_studio/__init__.py": "# public runtime\n",
               "vanguard_fat_studio-0.2.1.dist-info/METADATA": "Name: vanguard-fat-studio\nVersion: 0.2.1\n",
               "vanguard_fat_studio-0.2.1.dist-info/WHEEL": "Wheel-Version: 1.0\n"}
    entries.update(extra or {})
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return path


def test_public_source_is_explicit_even_when_private_file_is_gitignored(tmp_path):
    public_source(tmp_path)
    assert PUBLIC["selected_files"](tmp_path, "source") == ["fat_studio/__init__.py"]
    (tmp_path / ".gitignore").write_text("fat_studio/house.py\n")
    (tmp_path / "fat_studio/house.py").write_text("# private programming material\n")
    with pytest.raises(ValueError, match="Unexpected file"):
        PUBLIC["selected_files"](tmp_path, "source")


def test_public_selection_does_not_copy_unlisted_notes_or_sources(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    public_source(source)
    private = source / ".local"
    private.mkdir()
    (private / "engineering.scl").write_text("private supplied engineering\n")
    (source / "internal-log.md").write_text("private working notes\n")
    destination = tmp_path / "public-copy"
    assert PUBLIC["copy_source"](source, destination) == 1
    assert sorted(p.relative_to(destination).as_posix() for p in destination.rglob("*") if p.is_file()) == [
        "fat_studio/__init__.py"]


def test_public_output_boundary_uses_resolved_path_and_asset_globs_do_not_cross_directories(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    public_source(source)
    with pytest.raises(ValueError, match="outside"):
        PUBLIC["copy_source"](source, tmp_path / "other" / ".." / "source" / "inside")
    assert PUBLIC["is_allowed"]("fat_studio/web/assets/index-abc.js", [], ["fat_studio/web/assets/index-*.js"])
    assert not PUBLIC["is_allowed"]("fat_studio/web/assets/index-private/extra.js", [],
                                    ["fat_studio/web/assets/index-*.js"])


@pytest.mark.parametrize("name", ["fat_studio/house.py", "integrations/private.scl", ".local/backup.json",
                                  "vanguard_fat_studio-0.2.1.dist-info/private.txt", "../escape.py"])
def test_public_wheel_rejects_unlisted_modules_resources_and_metadata(tmp_path, name):
    public_source(tmp_path)
    wheel = make_public_wheel(tmp_path / "app.whl", {name: "private material\n"})
    with pytest.raises(ValueError):
        PUBLIC["validate_wheel"](wheel, policy_root=tmp_path)


@pytest.mark.parametrize("private", ["Nouvelle" + "-Caledonie", "Nouvelle" + " Calédonie",
                                     "NOUVELLE" + "-CALÉDONIE", "FB_" + "VG_Command", "DB_" + "VG_State",
                                     "DB_" + "Pilot_IO", "standard_" + "objects_v1", "vanguard-" + "pilot-v1",
                                     "Cycle" + "Engineering.exe", "-----BEGIN " + "PRIVATE KEY-----"],
                         ids=["private-location", "private-location-accent", "private-location-uppercase",
                              "private-block", "private-db", "private-exchange-db",
                              "private-controller", "private-project", "private-helper", "private-key"])
def test_private_content_refused_even_under_an_allowed_filename(tmp_path, private):
    public_source(tmp_path)
    wheel = make_public_wheel(tmp_path / "app.whl", {"fat_studio/__init__.py": private})
    with pytest.raises(ValueError, match="refused"):
        PUBLIC["validate_wheel"](wheel, policy_root=tmp_path)


def test_key_scan_distinguishes_codec_header_constants_from_embedded_key_material():
    marker = b"-----BEGIN " + b"OPENSSH PRIVATE KEY-----"
    PUBLIC["check_content"]("codec.py", b'HEADER = b"' + marker + b'"\n')
    with pytest.raises(ValueError, match="Private key"):
        PUBLIC["check_content"]("data.txt", marker + b"\n")
    with pytest.raises(ValueError, match="Private key"):
        PUBLIC["check_content"]("embedded.py", b'KEY = """' + marker + b"\nYWJjZGVm\nYWJjZGVm\n")
    with pytest.raises(ValueError, match="Private key"):
        encoded = b'{"key":"' + marker + b"\\n" + b"A" * 64 + b"\\n-----END OPENSSH " + b'PRIVATE KEY-----"}'
        PUBLIC["check_content"]("configuration.json", encoded)


def test_public_wheel_accepts_only_reviewed_payload(tmp_path):
    public_source(tmp_path)
    wheel = make_public_wheel(tmp_path / "app.whl")
    assert PUBLIC["validate_wheel"](wheel, policy_root=tmp_path) == 3


def test_public_brand_and_official_font_licence_are_allowed_without_admitting_private_plc_code(tmp_path):
    public_source(tmp_path)
    content = "Vanguard FAT Studio\nCopyright 2024 The Geist Project Authors\nSIL Open Font License 1.1\n"
    wheel = make_public_wheel(tmp_path / "app.whl", {"fat_studio/__init__.py": content})
    assert PUBLIC["validate_wheel"](wheel, policy_root=tmp_path) == 3
    with pytest.raises(ValueError, match="Private engineering"):
        PUBLIC["check_content"]("brand-note.md", content.encode() + b'FUNCTION_BLOCK "FB_' + b'VG_Command"')


def test_portable_lock_reads_top_level_wheel_metadata_with_vendored_distributions(tmp_path):
    import zipfile
    builder = runpy.run_path(str(CHECKER.with_name("build-portable.py")))
    wheelhouse = tmp_path / "wheels"
    wheelhouse.mkdir()
    lock = tmp_path / "requirements.lock"
    lock.write_text("setuptools==84.2.1\n")
    wheel = wheelhouse / "setuptools-84.2.1-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("setuptools-84.2.1.dist-info/METADATA", "Name: setuptools\nVersion: 84.2.1\n")
        archive.writestr("setuptools/_vendor/other-1.0.dist-info/METADATA", "Name: other\nVersion: 1.0\n")
    assert builder["locked_wheels"](wheelhouse, lock) == [wheel.resolve()]
    (wheelhouse / "unexpected.txt").write_text("not a locked wheel")
    with pytest.raises(ValueError, match="Unexpected"):
        builder["locked_wheels"](wheelhouse, lock)


def test_actual_wheel_and_sdist_use_public_list_without_old_egg_info(tmp_path):
    import tarfile
    import zipfile
    public_source(tmp_path)
    (tmp_path / "README.md").write_text("Public FAT example\n")
    for name in ("public_distribution.py", "build_public.py"):
        (tmp_path / name).write_bytes((CHECKER.parents[1] / name).read_bytes())
    (tmp_path / "pyproject.toml").write_text('''[build-system]
requires=["setuptools==84.2.1","wheel==0.48.0"]
build-backend="setuptools.build_meta"
[project]
name="vanguard-fat-studio"
version="0.2.1"
readme="README.md"
[tool.setuptools]
packages=["fat_studio"]
include-package-data=false
[tool.setuptools.cmdclass]
build_py="build_public.PublicBuildPy"
sdist="build_public.PublicSdist"
''')
    policy_path = tmp_path / "public-distribution.json"
    policy = json.loads(policy_path.read_text())
    policy["source_files"] += ["README.md", "pyproject.toml", "public_distribution.py", "build_public.py",
                               "public-distribution.json"]
    policy_path.write_text(json.dumps(policy))
    private = tmp_path / "internal-standards.txt"
    private.write_text("private user working material\n")
    egg = tmp_path / "local_fat_studio.egg-info"
    egg.mkdir()
    (egg / "SOURCES.txt").write_text("internal-standards.txt\n")
    result = subprocess.run([sys.executable, "-m", "build", "--no-isolation"], cwd=tmp_path,
                            capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert result.returncode == 0, result.stderr + result.stdout
    wheel = next((tmp_path / "dist").glob("*.whl"))
    assert PUBLIC["validate_wheel"](wheel, policy_root=tmp_path) >= 3
    with zipfile.ZipFile(wheel) as archive:
        assert not any("internal-standards" in name for name in archive.namelist())
    with tarfile.open(next((tmp_path / "dist").glob("*.tar.gz"))) as archive:
        names = archive.getnames()
        assert any(name.endswith("/build_public.py") for name in names)
        assert not any("internal-standards" in name for name in names)


@pytest.mark.parametrize("damage", ["content", "extra", "traversal"])
def test_portable_manifest_rejects_changed_extra_or_escaping_files(tmp_path, damage):
    file = tmp_path / "runtime.txt"
    file.write_text("pinned runtime\n")
    manifest = {"schema": 1, "platform": "Windows-x64", "python": "3.12.10",
                "files": PUBLIC["file_manifest"](tmp_path)}
    path = tmp_path / "portable-manifest.json"
    path.write_text(json.dumps(manifest))
    assert PORTABLE["validate_portable"](tmp_path) == 1
    if damage == "content":
        file.write_text("changed runtime\n")
    elif damage == "extra":
        (tmp_path / "not-listed.py").write_text("unreviewed code\n")
    else:
        manifest["files"][0]["path"] = "../runtime.txt"
        path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        PORTABLE["validate_portable"](tmp_path)


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
