"""Source-retarget guards; no Siemens DLL or native execution is simulated."""

import hashlib
import json
import os
from pathlib import Path
import subprocess

import pytest

from integrations.prepare_tia_server import UPSTREAM_COMMIT, _rewrite, main, prepare_source


def run_git(directory, *arguments):
    completed = subprocess.run(["git", "-C", str(directory), *arguments], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    return completed.stdout.strip()


def test_retarget_uses_original_tokens_and_keeps_upstream_observation_comments():
    source = (
        '// Native V21 observation; this is not V20 qualification.\r\n'
        'const string TiaPortalV21Dir = @"Portal V21\\PublicAPI\\V21\\net48";\r\n'
        'var tiaPortalV21Dir = ".ap21 .amc21 .als21 .zap21 v21 21.0.0.0";\r\n'
        '/// Verified on V21.\r\n'
    )
    result = _rewrite(source, "TiaMcpServer/Example.cs")
    assert result == (
        '// Native V21 observation; this is not V20 qualification.\r\n'
        'const string TiaPortalV20Dir = @"Portal V20\\PublicAPI\\V20\\net48";\r\n'
        'var tiaPortalV20Dir = ".ap20 .amc20 .als20 .zap20 v20 20.0.0.0";\r\n'
        '/// Verified on V21.\r\n'
    )


def test_build_properties_enforce_real_references_without_changing_encoding_or_line_endings():
    source = '\ufeff<Project>\r\n  <PropertyGroup>\r\n    <TiaPortalV21Dir>Portal V21</TiaPortalV21Dir>\r\n  </PropertyGroup>\r\n</Project>\r\n'
    result = _rewrite(source, "Directory.Build.props")
    assert result.startswith('\ufeff<Project>\r\n')
    assert result.count('<UseTiaPortalReferenceStubs>false</UseTiaPortalReferenceStubs>') == 1
    assert '<TiaPortalV20Dir>Portal V20</TiaPortalV20Dir>' in result
    assert '\n' not in result.replace('\r\n', '')


@pytest.mark.parametrize("source", [
    '<Project><PropertyGroup/><PropertyGroup/></Project>',
    '<Project><PropertyGroup><UseTiaPortalReferenceStubs>true</UseTiaPortalReferenceStubs></PropertyGroup></Project>',
])
def test_unexpected_build_properties_are_refused_before_source_edits(source):
    with pytest.raises(ValueError, match="anchor differs"):
        _rewrite(source, "Directory.Build.props")


def test_v21_never_uses_the_source_retarget(tmp_path):
    with pytest.raises(ValueError, match="unmodified pinned package"):
        prepare_source(tmp_path, "V21")


def test_wrong_checkout_commit_is_refused_without_mutating_its_files(tmp_path):
    source = tmp_path / "unrelated"
    source.mkdir()
    run_git(source, "init")
    example = source / "example.cs"
    example.write_text('var version = "V21";\n')
    run_git(source, "add", "example.cs")
    message = tmp_path / "commit-message.txt"
    message.write_text("Create unrelated test source\n")
    run_git(source, "-c", "user.name=FAT test", "-c", "user.email=fat-test@example.invalid",
            "-c", "commit.gpgsign=false", "commit", "-F", str(message))
    before = example.read_bytes()
    with pytest.raises(ValueError, match="must be exactly Czarnak commit"):
        prepare_source(source)
    assert example.read_bytes() == before
    assert run_git(source, "status", "--porcelain=v1") == ""


def test_cli_refuses_report_inside_checkout_before_modification(tmp_path, capsys):
    assert main(["prepare-source", "--source", str(tmp_path), "--report", str(tmp_path / "report.json")]) == 2
    assert "outside the dedicated source checkout" in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == []


@pytest.fixture
def pinned_checkout(tmp_path):
    configured = os.environ.get("FAT_TIA_UPSTREAM_SOURCE")
    if not configured:
        pytest.skip("Set FAT_TIA_UPSTREAM_SOURCE to the real pinned upstream clone for source integration checks.")
    upstream = Path(configured).resolve(strict=True)
    assert run_git(upstream, "rev-parse", "HEAD") == UPSTREAM_COMMIT
    source = tmp_path / "Czarnak source épreuve"
    result = subprocess.run(["git", "clone", "--no-hardlinks", str(upstream), str(source)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert run_git(source, "rev-parse", "HEAD") == UPSTREAM_COMMIT
    return source


def test_real_pinned_source_retarget_changes_native_profile_and_preserves_excluded_files(pinned_checkout):
    source = pinned_checkout
    excluded = {
        p.relative_to(source).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for name in ("ref", "reference-stubs") for p in (source / name).rglob("*") if p.is_file()
    }
    assert excluded, "The real source must contain reference files to exercise their preservation."
    license_before = (source / "LICENSE").read_bytes()
    report = prepare_source(source)
    assert len(report["transformed_files"]) > 20
    assert report["source_commit"] == UPSTREAM_COMMIT and report["target_version"] == "V20"
    assert report["no_stubs"] is True
    canonical = json.dumps(report["transformed_files"], sort_keys=True, separators=(",", ":")).encode()
    assert report["patch_sha256"] == hashlib.sha256(canonical).hexdigest()
    assert run_git(source, "rev-parse", "HEAD") == UPSTREAM_COMMIT
    assert (source / "LICENSE").read_bytes() == license_before
    assert excluded == {
        relative: hashlib.sha256((source / relative).read_bytes()).hexdigest() for relative in excluded
    }
    assert '<UseTiaPortalReferenceStubs>false</UseTiaPortalReferenceStubs>' in (source / 'Directory.Build.props').read_text()
    resolver = (source / 'TiaMcpServer.OpennessWorker/Openness/Infrastructure/AssemblyResolver.cs').read_text()
    assert 'TiaPortalV20Dir' in resolver and r'PublicAPI\V20\net48' in resolver
    assert 'requestedName.FullName, loadedAssembly.GetName().FullName' in resolver
    assert 'CompressedFileExtension = ".zap20"' in (source / 'TiaMcpServer.Contracts/Project/ArchiveModeNames.cs').read_text()
    assert 'EngineeringVersion = "V20"' in (source / 'TiaMcpServer.OpennessWorker/Openness/Block/BlockSourceGenerator.cs').read_text()
    assert '".ap20"' in (source / 'TiaMcpServer/Cli/ConfiguredProjectPath.cs').read_text()
    assert all(not item['path'].startswith(('ref/', 'reference-stubs/')) for item in report['transformed_files'])
    for item in report['transformed_files']:
        assert hashlib.sha256((source / item['path']).read_bytes()).hexdigest() == item['after_sha256']
    with pytest.raises(ValueError, match="not clean"):
        prepare_source(source)


def test_real_pinned_dirty_checkout_is_refused_without_overwriting_changes(pinned_checkout):
    source = pinned_checkout
    target = source / "TiaMcpServer/Cli/ConfiguredProjectPath.cs"
    changed = target.read_bytes() + b"\n// Local work must survive.\n"
    target.write_bytes(changed)
    with pytest.raises(ValueError, match="not clean"):
        prepare_source(source)
    assert target.read_bytes() == changed
    assert "UseTiaPortalReferenceStubs" not in (source / "Directory.Build.props").read_text()
