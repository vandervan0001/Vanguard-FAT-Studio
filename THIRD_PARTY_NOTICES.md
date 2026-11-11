# Third-party components

Vanguard FAT Studio's original code is supplied under the MIT licence in `LICENSE`. A component's own licence continues to apply to that component. This file records the technical provenance; it does not replace the upstream licence texts.

## Code included in source

**HistorianSim**, ScottDuncanAI, MIT, commit `14e616c382a9db8026cbb4ab86bdd803d56ca72e`.

The unmodified `src/historiansim/core/valve.py` is included as `fat_studio/vendor/historiansim/valve.py`. Its copyright notice and full licence are preserved alongside it. `PROVENANCE.md` identifies the exact source and SHA-256. Vanguard FAT Studio adds its tight-shutoff condition in its own engine without modifying the upstream file.

Source: https://github.com/ScottDuncanAI/HistorianSim

## P&ID catalogue and interchange references

**Scott Duncan / ScottDuncanAI, PID-to-Knowledge-Graph**, MIT, reference commit `7ee3a82e655c13c11aa26ee25bdc2c0c01bd58f1`.

The ontology and `KnowledgeGraph` JSON schema inform the local readers and graph interchange. Vanguard FAT Studio implements its own parsers and exporters; it does not include the upstream Python code or execute the Claude extraction workflow. The upstream reference does not establish process parameters, PLC logic or a human FAT verdict.

Source and licence: [PID-to-Knowledge-Graph at the referenced commit](https://github.com/ScottDuncanAI/PID-to-Knowledge-Graph/tree/7ee3a82e655c13c11aa26ee25bdc2c0c01bd58f1), [MIT licence](https://github.com/ScottDuncanAI/PID-to-Knowledge-Graph/blob/7ee3a82e655c13c11aa26ee25bdc2c0c01bd58f1/LICENSE).

**Scott Duncan / ScottDuncanAI, Public Chemical Manufacturing Datasets**, reference commit `3f21a8540cac027489d22ebc7af757b0b5299880`, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

The P&ID and time-series catalogue links and descriptions are adapted and translated into French in `fat_studio/pid_catalog.py`. The original attribution, source links, reference commit and a notice of adaptation accompany the catalogue. The full licence is retained in [fat_studio/pid_catalog_LICENSE.txt](fat_studio/pid_catalog_LICENSE.txt). External documents and datasets retain their authors' terms; they are linked, not redistributed with FAT Studio.

Source: [Public Chemical Manufacturing Datasets at the referenced commit](https://github.com/ScottDuncanAI/public-chemical-manufacturing-datasets/tree/3f21a8540cac027489d22ebc7af757b0b5299880).

## P&ID drawing representations

Four general representations (pump, valve, heat exchanger and compressor) adapt drawing formulae from **pyflowsheet**, Copyright (c) 2020 **Jochen Steimel**, MIT licence, pinned commit `8a68f2569a9a977079ece242aa7771b9d53448a8`. Body geometry is normalised to the local canvas, drawing terminals and French labels are added. No upstream module, router or process model is executed. These freely licensed PFD representations do not certify ISO/ISA conformity.

The [provenance record](fat_studio/pid_symbols_PROVENANCE.md) identifies immutable source paths and SHA-256 values. The [full upstream MIT licence](fat_studio/pid_symbols_pyflowsheet_LICENSE.txt) is retained in source and installed packages. Source: [pyflowsheet at the pinned commit](https://github.com/nukleon84/pyflowsheet/tree/8a68f2569a9a977079ece242aa7771b9d53448a8).

Sixteen instrument-function examples use original local circle/terminal geometry and public functional-code explanations, with ISA references. No paywalled standards table, normative drawing library or certification is redistributed. The service palette is a Vanguard project convention, not a universal ISO/ISA colour assignment.

## Bundled browser assets

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
| pypdfium2 / PDFium | 5.15.2 | BSD-3-Clause / Apache-2.0 and bundled dependency notices, [source](https://github.com/pypdfium2-team/pypdfium2) |
| pypdf | 7.0.1 | BSD-3-Clause, [source](https://github.com/py-pdf/pypdf) |
| Pillow | 13.0.0 | MIT-CMU, [source](https://github.com/python-pillow/Pillow) |
| ezdxf | 1.4.5 | MIT, [source](https://github.com/mozman/ezdxf) |
| defusedxml | 0.7.1 | Python Software Foundation License v2, [source and licence](https://github.com/tiran/defusedxml) |
| ReportLab | 5.1.0 | BSD-3-Clause, [source](https://hg.reportlab.com/hg-public/reportlab/) |
| RapidOCR (`rapidocr-onnxruntime`) | 1.4.4 | Apache-2.0, [source](https://github.com/RapidAI/RapidOCR) |
| ONNX Runtime | 1.31.1 | MIT and bundled dependency notices, [source](https://github.com/microsoft/onnxruntime) |

The P&ID readers use PDFium for local PDF geometry/rendering, pypdf for PDF structure and embedded documents, Pillow for images, ezdxf for CAD entities and defusedxml for bounded XML reading. ReportLab produces vector PDF exports with the local Geist font. RapidOCR uses the CPU ONNX models supplied with its installed package; the FAT runtime does not request a hosted model or download an OCR model. This pinned OCR dependency is installed on Python 3.12; Python 3.13/3.14 retain the other local readers.

The locked support dependencies include OpenCV 5.0.0.93 (Apache-2.0 and binary dependency notices), NumPy 2.5.4 (BSD-3-Clause and bundled notices), fontTools 4.68.0 (MIT), pyparsing 3.3.3 (MIT), pyclipper 1.4.0 (MIT), Shapely 2.2.0 (BSD-3-Clause; binary GEOS notices also apply), PyYAML 6.0.3 (MIT), FlatBuffers 25.12.19 (Apache-2.0), protobuf 7.36.2 (BSD-3-Clause) and tqdm 4.70.1 (MPL-2.0 and MIT). The exact platform-specific binaries and full licence/notice files remain in their installed packages and wheel metadata. Retain those notices when constructing an offline or portable distribution, including PDFium, ONNX Runtime, OpenCV and other compiled dependencies.

`asyncua` is a replaceable, dynamically imported Python dependency. If distributing an offline wheelhouse or a modified version, retain its original licence and the corresponding source obligations applicable to that distribution. The independent dependency remains replaceable; no frozen single-file executable is supplied.

## Optional engineering components

- **GNU LibreDWG 0.14**, GPL-3.0-or-later, commit `d9468ae948b8f07a08efa756c19f8916052358c0`. The optional local `dwg2dxf` / `dxf2dwg` executables run as separate processes. No LibreDWG code or DLL is linked into FAT Studio or included in its public Python package, source kit or portable. [GNU project and licence](https://www.gnu.org/software/libredwg/), [official release](https://github.com/LibreDWG/libredwg/releases/tag/0.14), [program contract](https://www.gnu.org/software/libredwg/manual/html_node/Programs.html). The Windows setup script downloads the upstream x64 binary archive and matching source archive into `.tools/pid-cad/`, verifies their SHA-256 and records provenance. It does not change the global PATH. DWG writing is experimental; the application selects R2000 and does not claim acceptance by AutoCAD or another recipient CAD system.

LibreDWG's pinned binary archive is [`libredwg-0.14-win64.zip`](https://github.com/LibreDWG/libredwg/releases/download/0.14/libredwg-0.14-win64.zip), SHA-256 `1ad7e15344d20b3426c3435b078d82fb84b35062815946b2cca9c5fc9810fea8`. Its corresponding source is [`libredwg-0.14.tar.gz`](https://github.com/LibreDWG/libredwg/releases/download/0.14/libredwg-0.14.tar.gz), SHA-256 `cb6ee0b078c6d9e0f09d66f1feac33ba6342df88ae544e9f9335fab475218351`. A separate redistribution of the optional executables must preserve their GPL notices and provide corresponding source under that licence. The FAT public file selection excludes the local installation.

- **Czarnak/TiaMcpServer 4.3.0**, MIT. V21 installs the pinned NuGet package. The optional V20 profile prepares a modified checkout of the same pinned source and builds it locally against the installed Siemens V20 assemblies; its transformation report records every changed file. The upstream licence and provenance are retained. This repository does not redistribute Siemens assemblies. Exact revision and contracts: `integrations/upstream.lock.json`. Source: https://github.com/Czarnak/tia-portal-mcp.
- **Official Python MCP SDK 2.3.0**, MIT, optional dependency in `requirements-engineering.lock`. Source: https://github.com/modelcontextprotocol/python-sdk.
- **TIA Portal, TIA Portal Openness and S7-PLCSIM Advanced** are Siemens products. No Siemens installers, DLLs or licence files are redistributed here.

## Examined but not incorporated

- HistorianRCA (CC BY 4.0): documentary reference only; no dataset, diagram or content asset is copied.
- heilingbrunner/tiaportal-mcp (MIT): compared, not installed or incorporated.
- Czarnak/totally-integrated-claude: studied as an optional workflow; not a runtime dependency.

The detailed reuse decisions are in `docs/UPSTREAM_REVIEW.md`.
