"""Real backend and process engine, temporary evidence store, isolated test port."""

from pathlib import Path
from tempfile import TemporaryDirectory
import sys

import uvicorn

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from fat_studio.app import create_app  # noqa: E402


if __name__ == "__main__":
    if not (ROOT / "fat_studio" / "web" / "index.html").exists():
        raise SystemExit("Construire la distribution puis exécuter python scripts/build-web.py avant les tests UI.")
    with TemporaryDirectory(prefix="fat-studio-e2e-") as data:
        uvicorn.run(create_app(Path(data)), host="127.0.0.1", port=8766, log_level="warning")
