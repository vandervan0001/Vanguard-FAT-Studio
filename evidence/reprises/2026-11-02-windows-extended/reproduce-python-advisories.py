from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.request import urlopen
from packaging.requirements import Requirement

root = Path('C:/FAT_Studio')
requirements = {}
for name in ('requirements.lock', 'requirements-dev.lock', 'requirements-engineering.lock'):
    for line in (root / name).read_text().splitlines():
        if not line or line.startswith('#'):
            continue
        req = Requirement(line)
        if req.marker and not req.marker.evaluate():
            continue
        version = next(iter(req.specifier)).version
        requirements[req.name] = version


def check(item):
    name, version = item
    url = f'https://pypi.org/pypi/{name}/{version}/json'
    try:
        with urlopen(url, timeout=20) as response:
            data = json.load(response)
        return {'name': name, 'version': version, 'url': url,
                'advisories': data.get('vulnerabilities', []), 'status': 'checked'}
    except Exception as exc:
        return {'name': name, 'version': version, 'url': url, 'status': 'error', 'error': str(exc)}


with ThreadPoolExecutor(max_workers=8) as pool:
    checked = list(pool.map(check, sorted(requirements.items())))
result = {'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'source': 'PyPI version JSON advisory metadata',
          'scope': 'Active Windows dependencies in the three lock files; not a code security certification',
          'packages': checked, 'package_count': len(checked),
          'errors': sum(item['status'] != 'checked' for item in checked),
          'packages_with_advisories': sum(bool(item.get('advisories')) for item in checked)}
target = root / 'evidence/reprises/2026-11-02-windows-extended/python-advisories.json'
target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({key: value for key, value in result.items() if key != 'packages'}, indent=2))
if result['errors']:
    raise SystemExit(1)
