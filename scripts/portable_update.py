"""Explicit GitHub update discovery and verified, side-by-side portable extraction."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
import time
import urllib.parse
import urllib.request
import zipfile

REPOSITORY = "vandervan0001/Vanguard-FAT-Studio"
RELEASES_URL = f"https://api.github.com/repos/{REPOSITORY}/releases?per_page=20"
MAX_ARCHIVE = 300 * 1024 * 1024
MAX_EXPANDED = 1200 * 1024 * 1024
MAX_ENTRIES = 12000


def asset_url(value: str) -> str:
    url = urllib.parse.urlsplit(value)
    prefix = f"/{REPOSITORY}/releases/download/"
    if (url.scheme != "https" or url.netloc != "github.com" or not url.path.startswith(prefix)
            or url.query or url.fragment or ".." in url.path.split("/")):
        raise ValueError("Le téléchargement ne vient pas de la release officielle.")
    return value


def latest_candidate(releases: list[dict]) -> dict:
    choices = []
    for release in releases:
        if release.get("draft"):
            continue
        for asset in release.get("assets", []):
            name = asset.get("name", "")
            digest = asset.get("digest", "")
            if (not re.fullmatch(r"Vanguard-FAT-Studio-Windows-x64-[A-Za-z0-9._-]+\.zip", name)
                    or asset.get("state") != "uploaded"):
                continue
            if not isinstance(digest, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
                continue
            size = asset.get("size")
            if type(size) is not int or not 0 < size <= MAX_ARCHIVE:
                continue
            url = asset_url(asset.get("browser_download_url", ""))
            choices.append({"name": name, "url": url, "sha256": digest[7:], "size": size,
                            "release": str(release.get("tag_name", "")),
                            "published_at": str(release.get("published_at", "")),
                            "created_at": str(asset.get("created_at", ""))})
    if not choices:
        raise ValueError("Aucun portable publié avec une empreinte SHA-256 vérifiable.")
    return max(choices, key=lambda item: (item["published_at"], item["created_at"], item["name"]))


def discover() -> dict:
    request = urllib.request.Request(RELEASES_URL, headers={"Accept": "application/vnd.github+json",
                                                           "User-Agent": "Vanguard-FAT-Studio-portable",
                                                           "X-GitHub-Api-Version": "2022-11-28"})
    with urllib.request.urlopen(request, timeout=20) as response:
        data = response.read(2_000_001)
    if len(data) > 2_000_000:
        raise ValueError("La réponse de GitHub est trop volumineuse.")
    releases = json.loads(data)
    if not isinstance(releases, list):
        raise ValueError("Réponse de GitHub inattendue.")
    return latest_candidate(releases)


def download(candidate: dict, target: Path) -> None:
    url = asset_url(candidate["url"])
    size, expected = candidate["size"], candidate["sha256"]
    if type(size) is not int or not 0 < size <= MAX_ARCHIVE or not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise ValueError("Taille ou empreinte de la release invalide.")
    digest, received = hashlib.sha256(), 0
    deadline = time.monotonic() + 180
    request = urllib.request.Request(url, headers={"User-Agent": "Vanguard-FAT-Studio-portable"})
    with urllib.request.urlopen(request, timeout=45) as response, target.open("xb") as stream:
        while True:
            if time.monotonic() >= deadline:
                raise ValueError("Le téléchargement a dépassé le délai prévu. Réessayez volontairement.")
            # read1 returns after a network read; read(n) can wait indefinitely
            # for a trickling peer to complete n bytes despite socket timeouts.
            block = response.read1(1024 * 1024)
            if time.monotonic() >= deadline:
                raise ValueError("Le téléchargement a dépassé le délai prévu. Réessayez volontairement.")
            if not block:
                break
            received += len(block)
            if received > size:
                raise ValueError("Le téléchargement dépasse la taille publiée.")
            stream.write(block)
            digest.update(block)
    if received != size or digest.hexdigest() != expected:
        raise ValueError("Le téléchargement est incomplet ou son empreinte ne correspond pas.")


def safe_entries(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    entries = archive.infolist()
    if not entries or len(entries) > MAX_ENTRIES or sum(item.file_size for item in entries) > MAX_EXPANDED:
        raise ValueError("L’archive dépasse les limites du portable.")
    seen = set()
    for item in entries:
        name = item.filename.rstrip("/")
        parts = name.split("/")
        if (item.orig_filename != item.filename or not name or "\\" in name or ":" in name or name.startswith("/")
                or any(part in {"", ".", ".."} or part.rstrip(" .") != part
                       or re.match(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)", part, re.I) for part in parts)
                or any(ord(char) < 32 for char in name)
                or name.casefold() in seen
                or (item.external_attr >> 16) & 0o170000 not in {0, 0o100000, 0o040000}
                or item.external_attr & 0x400
                or item.flag_bits & 1):
            raise ValueError("Chemin non autorisé dans le portable : " + name)
        seen.add(name.casefold())
    return entries


def prepare_archive(archive_path: Path, destination: Path, validate_portable) -> Path:
    """Never import or execute code from the update to validate that update."""
    destination = destination.resolve()
    if destination.exists():
        raise ValueError("Le dossier de destination existe déjà. Choisissez un nouveau dossier.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as archive:
        entries = safe_entries(archive)
        manifests = [item.filename for item in entries if item.filename.endswith("/portable-manifest.json")]
        if len(manifests) != 1 or len(manifests[0].split("/")) != 2:
            raise ValueError("Le ZIP doit contenir un seul dossier portable vérifiable.")
        portable_folder = manifests[0].split("/")[0]
        # Extraction only into our new temporary sibling; old delivery/data untouched.
        with tempfile.TemporaryDirectory(prefix=".vanguard-update-", dir=destination.parent) as staging:
            stage = Path(staging)
            for item in entries:
                target = stage / item.filename
                if not target.resolve().is_relative_to(stage.resolve()):
                    raise ValueError("Chemin hors du dossier de mise à jour.")
                if item.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(item) as source, target.open("xb") as output:
                        shutil.copyfileobj(source, output)
            portable = stage / portable_folder
            validate_portable(portable)
            if not (portable / "launch.py").is_file() or not (portable / "runtime/pythonw.exe").is_file():
                raise ValueError("Le lanceur du portable est incomplet.")
            stage.rename(destination)
    return destination / portable_folder


def install(candidate: dict, destination: Path, validate_portable) -> Path:
    if destination.exists():
        raise ValueError("Le dossier de mise à jour existe déjà ; aucune version n’a été remplacée.")
    # Archive temp outside both the sealed runtime and user test data.
    with tempfile.TemporaryDirectory(prefix="vanguard-download-") as temporary:
        archive = Path(temporary) / "portable.zip"
        download(candidate, archive)
        return prepare_archive(archive, destination, validate_portable)
