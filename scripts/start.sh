#!/usr/bin/env bash
set -euo pipefail
fat_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$fat_root"
fat_python="$fat_root/.venv/bin/python"
if [[ ! -f "$fat_root/fat_studio/web/index.html" ]]; then
  echo "Interface compilee absente : npm ci && npm run build dans frontend/, puis python scripts/build-web.py." >&2
  exit 1
fi
if [[ ! -x "$fat_python" ]]; then
  fat_system_python="$(command -v python3.12 || command -v python3 || true)"
  if [[ -z "$fat_system_python" ]]; then echo "Installer Python 3.12." >&2; exit 1; fi
  "$fat_system_python" -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3,12) else 1)' || { echo "Python 3.12 est requis par ce lanceur." >&2; exit 1; }
  "$fat_system_python" -m venv .venv
fi
"$fat_python" "$fat_root/scripts/check-kit.py" --root "$fat_root"
if [[ ! -x "$fat_root/.venv/bin/vanguard-fat-studio" ]]; then
  fat_pip_options=(--disable-pip-version-check)
  if [[ -d "$fat_root/wheelhouse" ]]; then
    fat_pip_options+=(--no-index --find-links "$fat_root/wheelhouse")
  fi
  "$fat_python" -m pip install "${fat_pip_options[@]}" -r requirements.lock
  "$fat_python" -m pip install "${fat_pip_options[@]}" --no-deps --no-build-isolation .
fi
exec "$fat_python" -m fat_studio serve --host 127.0.0.1 "$@"
