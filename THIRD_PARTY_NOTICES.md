# Third-party components

Vanguard FAT Studio's original code is supplied under the MIT licence in `LICENSE`. A component's own licence continues to apply to that component. This file records the technical provenance; it does not replace the upstream licence texts.

## Code included in source

**HistorianSim**, ScottDuncanAI, MIT, commit `14e616c382a9db8026cbb4ab86bdd803d56ca72e`.

The unmodified `src/historiansim/core/valve.py` is included as `fat_studio/vendor/historiansim/valve.py`. Its copyright notice and full licence are preserved alongside it. `PROVENANCE.md` identifies the exact source and SHA-256. Vanguard FAT Studio adds its tight-shutoff condition in its own engine without modifying the upstream file.

Source: https://github.com/ScottDuncanAI/HistorianSim

## Bundled browser code

The Vanguard logo, horizontal wordmarks and favicon are the assets selected by the project owner from `vandervan0001/vanguard_systems`, revision `b4df8d8ed0942e98ceee643a9be210f00aca9e9f`. They are kept under their original filenames in `frontend/public/brand/` and `fat_studio/web/brand/`. No application code from that site is included.

**Geist Regular/Bold and Geist Mono Regular** accompany those assets. Copyright 2024 The Geist Project Authors, [vercel/geist-font](https://github.com/vercel/geist-font), SIL Open Font License 1.1. The supplied static TTF files are retained unchanged, together with the full `brand/OFL.txt` notice. Reports embed these local files for offline reading; they do not fetch fonts from a remote service.

React, React DOM, React Flow (`@xyflow/react`, `@xyflow/system`), Recharts, Lucide and their runtime dependencies are bundled from the exact `frontend/package-lock.json` versions. Their licences and notices are collected in `fat_studio/web/assets/THIRD_PARTY_LICENSES.txt`; the same file is included by the browser build as `frontend/public/assets/THIRD_PARTY_LICENSES.txt`.

Main sources:

- https://github.com/facebook/react — MIT.
- https://github.com/xyflow/xyflow — MIT.
- https://github.com/recharts/recharts — MIT.
- https://github.com/lucide-icons/lucide — ISC (with inherited icon notices where applicable).

The generated notice file includes all installed non-development package entries from the lock, including a few type-only dependencies that may not contribute executable bytes. They are retained conservatively.

## Python libraries installed separately

Runtime versions and transitive dependencies are locked in `requirements.lock`. The installation keeps their package licence metadata and source distributions separate; Vanguard FAT Studio does not copy or modify their implementation.

| Library | Tested version | Upstream licence / source |
| --- | --- | --- |
| FastAPI | 0.162.0 | MIT — https://github.com/fastapi/fastapi |
| Uvicorn | 0.54.0 | BSD-3-Clause — https://github.com/encode/uvicorn |
| Pydantic | 2.14.2 | MIT — https://github.com/pydantic/pydantic |
| asyncua | 1.1.8 | LGPL-3.0-or-later — https://github.com/FreeOpcUa/opcua-asyncio |

`asyncua` is a replaceable, dynamically imported Python dependency. If distributing an offline wheelhouse or a modified version, retain its original licence and the corresponding source obligations applicable to that distribution. The independent dependency remains replaceable; no frozen single-file executable is supplied.

## Optional engineering components

- **Czarnak/TiaMcpServer 4.3.0**, MIT. V21 installs the pinned NuGet package. The optional V20 profile prepares a modified checkout of the same pinned source and builds it locally against the installed Siemens V20 assemblies; its transformation report records every changed file. The upstream licence and provenance are retained. This repository does not redistribute Siemens assemblies. Exact revision and contracts: `integrations/upstream.lock.json`. Source: https://github.com/Czarnak/tia-portal-mcp.
- **Official Python MCP SDK 2.3.0**, MIT, optional dependency in `requirements-engineering.lock`. Source: https://github.com/modelcontextprotocol/python-sdk.
- **TIA Portal, TIA Portal Openness and S7-PLCSIM Advanced** are Siemens products. No Siemens installers, DLLs or licence files are redistributed here.

## Examined but not incorporated

- HistorianRCA (CC BY 4.0): documentary reference only; no dataset, diagram or content asset is copied.
- heilingbrunner/tiaportal-mcp (MIT): compared, not installed or incorporated.
- Czarnak/totally-integrated-claude: studied as an optional workflow; not a runtime dependency.

The detailed reuse decisions are in `docs/UPSTREAM_REVIEW.md`.
