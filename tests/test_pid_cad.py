"""LibreDWG boundary tests and an actual optional Windows DWG roundtrip."""

import io
from pathlib import Path
import subprocess

import ezdxf
import pytest

from fat_studio.demo import demo_project
from fat_studio import pid_cad
from fat_studio.pid_export import export_pid, project_document
from fat_studio.pid_models import PidDocument


def test_missing_converter_and_relative_configuration_are_explicit(tmp_path, monkeypatch):
    monkeypatch.setenv("FAT_STUDIO_PID_CAD_DIR", str(tmp_path))
    capabilities = pid_cad.cad_capabilities()
    assert capabilities["read_available"] is False and capabilities["write_available"] is False
    assert capabilities["experimental_write"] is True
    with pytest.raises(ValueError, match="LibreDWG local absent"):
        pid_cad.dwg_to_dxf(b"AC1015" + b"0" * 100)
    monkeypatch.setenv("FAT_STUDIO_PID_CAD_DIR", "relative-path")
    with pytest.raises(ValueError, match="absolu"):
        pid_cad.dwg_to_dxf(b"AC1015")


@pytest.mark.parametrize("data", [b"", b"<script>", b"AC1015" + b"0" * (20 * 1024 * 1024)])
def test_invalid_dwg_rejected_before_process(data, monkeypatch):
    def fail(*args, **kwargs):
        pytest.fail("Invalid data reached subprocess")
    monkeypatch.setattr(pid_cad.subprocess, "run", fail)
    with pytest.raises(ValueError):
        pid_cad.dwg_to_dxf(data)


def test_timeout_uses_fixed_arguments_and_cleans_temporary_files(tmp_path, monkeypatch):
    monkeypatch.setattr(pid_cad, "_tool", lambda name: tmp_path / "local-converter.exe")
    seen = {}

    def timeout(arguments, **kwargs):
        seen.update(kwargs)
        assert Path(arguments[-1]).name == "input.dwg"
        assert arguments[1:4] == ["-v0", "--as", "r2000"]
        assert kwargs["shell"] is False and kwargs["timeout"] == 30
        assert kwargs["stdout"] == subprocess.DEVNULL
        raise subprocess.TimeoutExpired(arguments, 30)

    monkeypatch.setattr(pid_cad.subprocess, "run", timeout)
    with pytest.raises(ValueError, match="30 secondes"):
        pid_cad.dwg_to_dxf(b"AC1015test")
    assert not seen["cwd"].exists()


def test_invalid_converter_output_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(pid_cad, "_tool", lambda name: tmp_path / "local-converter.exe")

    def convert(arguments, **kwargs):
        Path(arguments[5]).write_bytes(b"not-a-dxf")
        return subprocess.CompletedProcess(arguments, 0)

    monkeypatch.setattr(pid_cad.subprocess, "run", convert)
    with pytest.raises(ValueError, match="Signature DXF"):
        pid_cad.dwg_to_dxf(b"AC1015test")


def test_libredwg_empty_preview_and_null_handle_normalization():
    data = b"  0\r\nSECTION\r\n  2\r\nENTITIES\r\n  5\r\nFF\r\n310\r\n\r\n  5\r\n0\r\n  0\r\nENDSEC\r\n  0\r\nEOF\r\n"
    result = pid_cad._normalize_libredwg_dxf(data)
    assert b"310\n\n" not in result and b"  5\n100\n" in result
    assert b"\r" not in result and b"FF\n" in result


@pytest.mark.skipif(not pid_cad.cad_capabilities()["available"], reason="Optional local LibreDWG not installed")
def test_actual_dwg_r2000_roundtrip_geometry_and_metadata():
    project = demo_project()
    source = ezdxf.read(io.StringIO(export_pid(project, "dxf")[0].decode("cp1252")))
    dwg = export_pid(project, "dwg")[0]
    assert dwg.startswith(b"AC1015")  # Genuine binary DWG R2000, not a renamed DXF.
    roundtrip = pid_cad.dwg_to_dxf(dwg)
    drawing = ezdxf.read(io.StringIO(roundtrip.decode("cp1252")))
    assert len(drawing.modelspace()) == len(source.modelspace()) > 50
    for kind in ("TEXT", "CIRCLE", "ELLIPSE", "LWPOLYLINE"):
        assert len(drawing.modelspace().query(kind)) == len(source.modelspace().query(kind))
    record = "".join(value for code, value in drawing.rootdict["FAT_STUDIO_PID"].tags if code == 1)
    assert PidDocument.model_validate_json(record) == project_document(project)
