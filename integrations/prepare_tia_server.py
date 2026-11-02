"""Prepare the pinned Czarnak source for a native V20 build.

This edits a dedicated clean checkout only. It does not compile, install or
qualify Siemens software. The Windows installer must build against real V20
assemblies and reject an incompatible API rather than using reference stubs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


UPSTREAM_COMMIT = "10c5de2eb44c0362792cd141370b3f42f92f6ecd"
PRODUCT_DIRECTORIES = frozenset({
    "TiaMcpServer", "TiaMcpServer.Contracts", "TiaMcpServer.OpennessWorker",
})
_RESOLVER = "TiaMcpServer.OpennessWorker/Openness/Infrastructure/AssemblyResolver.cs"
_STRICT_IDENTITY = "requestedName.FullName, loadedAssembly.GetName().FullName"
_TOKENS = {
    "TiaPortalV21": "TiaPortalV20",
    "tiaPortalV21": "tiaPortalV20",
    ".ap21": ".ap20", ".amc21": ".amc20", ".als21": ".als20", ".zap21": ".zap20",
    "V21": "V20", "v21": "v20", "21.0.0.0": "20.0.0.0",
}
_TOKEN_PATTERN = re.compile("|".join(re.escape(token) for token in _TOKENS))


def _git(source: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(source), *arguments], capture_output=True, text=True, check=False,
    )
    if completed.returncode:
        raise ValueError("Cannot inspect the source checkout: " + completed.stderr.strip())
    return completed.stdout


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _product_file(relative: str) -> bool:
    path = Path(relative)
    return relative == "Directory.Build.props" or (
        path.parts[0] in PRODUCT_DIRECTORIES and path.suffix in {".cs", ".csproj", ".xml"}
    )


def _rewrite(text: str, relative: str) -> str:
    """Replace version tokens once; retain upstream historical comment lines."""
    replacements = dict(_TOKENS)
    if relative == "Directory.Build.props":
        if text.count("<PropertyGroup>") != 1 or "UseTiaPortalReferenceStubs" in text:
            raise ValueError("The pinned build-properties anchor differs; no source was changed.")
        newline = "\r\n" if "\r\n" in text else "\n"
        replacements["<PropertyGroup>"] = (
            "<PropertyGroup>" + newline
            + "    <UseTiaPortalReferenceStubs>false</UseTiaPortalReferenceStubs>"
        )
    pattern = re.compile("|".join(re.escape(token) for token in replacements))
    lines = []
    for line in text.splitlines(keepends=True):
        # The pinned source keeps its provenance notes on comment-only lines.
        # Do not relabel a native V21 observation as a V20 test.
        stripped = line.lstrip()
        if relative.endswith(".cs") and stripped.startswith(("//", "/*", "*")):
            lines.append(line)
        else:
            lines.append(pattern.sub(lambda match: replacements[match.group()], line))
    return "".join(lines)


def prepare_source(source: Path, version: str = "V20") -> dict:
    if version != "V20":
        raise ValueError("Only V20 needs a source retarget; V21 uses the unmodified pinned package.")
    source = source.resolve(strict=True)
    if not source.is_dir() or Path(_git(source, "rev-parse", "--show-toplevel").strip()).resolve() != source:
        raise ValueError("Use the root of a dedicated source checkout.")
    if _git(source, "rev-parse", "HEAD").strip() != UPSTREAM_COMMIT:
        raise ValueError("The source checkout must be exactly Czarnak commit " + UPSTREAM_COMMIT + ".")
    if _git(source, "status", "--porcelain=v1", "--untracked-files=all").strip():
        raise ValueError("The source checkout is not clean; use a new dedicated clone without discarding changes.")

    tracked = sorted(name for name in _git(source, "ls-files", "-z").split("\0") if name)
    license_path = source / "LICENSE"
    if "MIT License" not in license_path.read_text(encoding="utf-8-sig"):
        raise ValueError("The pinned upstream MIT license is missing.")
    resolver = (source / _RESOLVER).read_text(encoding="utf-8")
    if _STRICT_IDENTITY not in resolver:
        raise ValueError("The strict assembly-identity guard is missing.")

    plan = []
    found_tokens: set[str] = set()
    untouched = {}
    for relative in tracked:
        path = source / relative
        if path.is_symlink() or not path.resolve(strict=True).is_relative_to(source):
            raise ValueError("Source symlinks are not accepted: " + relative)
        if not path.is_file():
            raise ValueError("Tracked source file is missing: " + relative)
        before = path.read_bytes()
        if not _product_file(relative):
            untouched[relative] = _sha256(before)
            continue
        text = before.decode("utf-8")
        found_tokens.update(match.group() for match in _TOKEN_PATTERN.finditer(text))
        after = _rewrite(text, relative).encode("utf-8")
        if before != after:
            plan.append((relative, before, after))

    if not {"V21", ".ap21", ".amc21", ".als21", ".zap21"}.issubset(found_tokens):
        raise ValueError("The pinned source version anchors are incomplete; no source was changed.")
    properties = next((after for relative, _, after in plan if relative == "Directory.Build.props"), b"")
    if b"<UseTiaPortalReferenceStubs>false</UseTiaPortalReferenceStubs>" not in properties:
        raise ValueError("Real Siemens references were not enforced; no source was changed.")
    rewritten_resolver = next((after.decode("utf-8") for relative, _, after in plan if relative == _RESOLVER), "")
    if _STRICT_IDENTITY not in rewritten_resolver:
        raise ValueError("The assembly-identity guard would change; no source was changed.")

    # Every transformation is planned before the first write. Outputs are never
    # used as the input of another replacement.
    changes = []
    for relative, before, after in plan:
        path = source / relative
        if path.read_bytes() != before:
            raise ValueError("Source changed during preparation: " + relative)
        path.write_bytes(after)
        changes.append({"path": relative, "before_sha256": _sha256(before), "after_sha256": _sha256(after)})
    if any(_sha256((source / relative).read_bytes()) != digest for relative, digest in untouched.items()):
        raise ValueError("An excluded upstream file changed during preparation; inspect the dedicated clone.")
    patch = _sha256(json.dumps(changes, sort_keys=True, separators=(",", ":")).encode())
    return {
        "source_commit": UPSTREAM_COMMIT, "target_version": "V20", "transformed_files": changes,
        "patch_sha256": patch, "no_stubs": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare-source")
    prepare.add_argument("--source", type=Path, required=True)
    prepare.add_argument("--tia-version", choices=["V20"], default="V20")
    prepare.add_argument("--report", type=Path, required=True)
    arguments = parser.parse_args(argv)
    try:
        report = arguments.report.absolute()
        if report.exists() or report.is_relative_to(arguments.source.resolve(strict=True)):
            raise ValueError("Use a new report path outside the dedicated source checkout.")
        document = prepare_source(arguments.source, arguments.tia_version)
        report.parent.mkdir(parents=True, exist_ok=True)
        with report.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(document, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        print(f"Prepared {len(document['transformed_files'])} source files for a native V20 build: {report}")
        return 0
    except (OSError, ValueError) as exc:
        print("Source preparation refused: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
