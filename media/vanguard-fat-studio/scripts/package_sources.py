"""Package an explicit set of editable film sources; no tools, caches or private data."""
from hashlib import sha256
from pathlib import Path
import json
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

root = Path(__file__).resolve().parents[1]
files = [
    'README.md', 'STORYBOARD.md', 'LICENSE', 'package.json', 'package-lock.json',
    'brand.mjs', 'config.mjs', 'index.html', 'studio.css',
    'src/player.mjs', 'src/math.mjs', 'src/ads-state.mjs', 'src/ads-scene.mjs',
    'scripts/serve.mjs', 'scripts/render.mjs', 'scripts/check.mjs',
    'scripts/audio.mjs', 'scripts/subtitles.mjs', 'scripts/package_sources.py',
    'scripts/capture-ui.mjs', 'scripts/capture-details.mjs', 'scripts/capture-trends.mjs',
    'assets/brand-logo.png', 'assets/brand-logo-white.png', 'assets/brand-symbol.png',
    'assets/Geist-Regular.ttf', 'assets/Geist-Bold.ttf', 'assets/GeistMono-Regular.ttf',
    'assets/OFL.txt', 'assets/provenance.json', 'assets/historical-proof.json',
    'assets/captures/manifest.json',
]
captures = json.loads((root / 'assets/captures/manifest.json').read_text(encoding='utf8'))
assert captures['status'] == 'ui-frozen-real-demo' and not captures['connected_plc']
for series in captures['shots'].values():
    for frame in series:
        name = frame['file']
        if Path(name).name != name or Path(name).suffix != '.png':
            raise ValueError('Unsafe capture filename')
        path = root / 'assets/captures' / name
        assert sha256(path.read_bytes()).hexdigest() == frame['sha256']
        files.append('assets/captures/' + name)
files = sorted(set(files))
contents = {}
for name in files:
    path = root / name
    if path.is_symlink() or root not in path.resolve().parents:
        raise ValueError('Source outside the editable film')
    contents[name] = path.read_bytes()
index = {'format':'vanguard-film-sources/1', 'files':[
    dict(path=name, bytes=len(contents[name]), sha256=sha256(contents[name]).hexdigest())
    for name in files
]}
contents['source-manifest.json'] = (json.dumps(index, ensure_ascii=False, indent=2) + '\n').encode()
destination = root / 'exports/vanguard-fat-studio-sources.zip'
destination.parent.mkdir(exist_ok=True)
with ZipFile(destination, 'x', compression=ZIP_DEFLATED, compresslevel=9) as archive:
    for name, payload in sorted(contents.items()):
        entry = ZipInfo(name, date_time=(2026, 11, 3, 0, 0, 0))
        entry.compress_type = ZIP_DEFLATED
        entry.external_attr = 0o100644 << 16
        archive.writestr(entry, payload)
with ZipFile(destination) as archive:
    assert archive.testzip() is None
    for item in index['files']:
        assert sha256(archive.read(item['path'])).hexdigest() == item['sha256']
print(json.dumps(dict(file=destination.name, bytes=destination.stat().st_size,
    entries=len(contents), sha256=sha256(destination.read_bytes()).hexdigest())))
