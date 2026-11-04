"""Public PLC bundle boundaries; native Siemens execution is separate evidence."""
import csv
import json

import pytest

from fat_studio.demo_contract import DB_NAME, DEMO_TAGS
from integrations.demo_plc import build, db_source, main_source, verify


def test_bundle_is_public_passive_and_disabled(tmp_path):
    destination = tmp_path / "public-plc"
    assert build(destination) == {"verified": True, "files": 7, "mapped_tags": 75,
                                  "canonical_enable_demo": False}
    source = (destination / "plc/Program_All.scl").read_text()
    assert source.count("DATA_BLOCK ") == 1
    assert source.count("ORGANIZATION_BLOCK ") == 1
    assert 'ORGANIZATION_BLOCK "Main"\n{ S7_Optimized_Access := \'TRUE\' }' in source
    assert "FUNCTION_BLOCK" not in source and "UDT" not in source
    assert "Bool := FALSE; // isolated virtual copy only" in source
    assert source.count("NORM_X(") == source.count("SCALE_X(") == 3
    assert source.count("LIMIT(") == 5
    rows = list(csv.DictReader((destination / "tags.csv").open(encoding="utf-8", newline="")))
    assert len(rows) == len(DEMO_TAGS) == 75
    assert all(not row["observed_address"] and not row["observed_node_id"] for row in rows)
    for row in rows:
        assert row["symbol"] == f'"{DB_NAME}"."{DEMO_TAGS[row["tag_id"]][0]}"'


def test_only_plc_outputs_are_assigned():
    assigned = {line.split('"DB_FAT_Demo".', 1)[1].split(" := ", 1)[0]
                for line in main_source().splitlines() if " := " in line and line.lstrip().startswith('"DB_')}
    outputs = {field for field, direction, *_ in DEMO_TAGS.values() if direction == "output"}
    assert assigned == outputs
    db = db_source()
    for field, direction, *_ in DEMO_TAGS.values():
        declaration = next(line for line in db.splitlines() if line.lstrip().startswith(field + " "))
        assert f"ExternalWritable := '{'True' if direction == 'input' else 'False'}'" in declaration


def test_build_refuses_overwrite_and_verify_detects_mutation(tmp_path):
    destination = tmp_path / "public-plc"
    build(destination)
    original = (destination / "manifest.json").read_bytes()
    with pytest.raises(FileExistsError):
        build(destination)
    assert (destination / "manifest.json").read_bytes() == original
    (destination / "plc/Main.scl").write_text("altered", encoding="utf-8")
    with pytest.raises(ValueError, match="Integrity mismatch"):
        verify(destination)


@pytest.mark.parametrize("unsafe_path", ["../outside", "/outside", "C:/outside", "\\outside"])
def test_verify_rejects_extra_files_and_traversal(tmp_path, unsafe_path):
    destination = tmp_path / "public-plc"
    build(destination)
    extra = destination / "unexpected.txt"
    extra.write_text("unexpected")
    with pytest.raises(ValueError, match="Unexpected"):
        verify(destination)
    extra.unlink()
    manifest_path = destination / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["files"][0]["path"] = unsafe_path
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="Unsafe"):
        verify(destination)


def test_verify_rejects_symbolic_link(tmp_path):
    destination = tmp_path / "public-plc"
    build(destination)
    link = tmp_path / "link"
    try:
        link.symlink_to(destination, target_is_directory=True)
    except OSError:
        pytest.skip("Creating symlinks is not allowed for this Windows account")
    with pytest.raises(ValueError, match="Link/reparse"):
        verify(link)
