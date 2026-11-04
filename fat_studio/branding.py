"""Product identity and local, unchanged Vanguard assets for standalone reports."""

from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path


APP_NAME = "Vanguard FAT Studio"
REPOSITORY_URL = "https://github.com/vandervan0001/Vanguard-FAT-Studio"
BRAND_BLUE = "#0055dd"


@lru_cache(maxsize=8)
def _asset_uri(path: Path, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def report_identity() -> tuple[str, str]:
    """Embed packaged assets; an API-only installation can use system fonts."""
    root = Path(__file__).parent / "web" / "brand"
    rules = []
    for filename, family, weight in (("Geist-Regular.ttf", "Geist", "400"),
                                      ("Geist-Bold.ttf", "Geist", "700"),
                                      ("GeistMono-Regular.ttf", "Geist Mono", "400")):
        path = root / filename
        if path.is_file():
            rules.append(f"@font-face{{font-family:'{family}';font-style:normal;font-weight:{weight};"
                         f"src:url('{_asset_uri(path, 'font/ttf')}') format('truetype')}}")
    logo = root / "logo_vanguard.png"
    mark = (f'<img class="brand-mark" src="{_asset_uri(logo, "image/png")}" alt="Vanguard" width="42" height="42">'
            if logo.is_file() else "")
    return "".join(rules), mark
