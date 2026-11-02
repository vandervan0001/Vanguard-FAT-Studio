# HistorianSim valve model

- Upstream: https://github.com/ScottDuncanAI/HistorianSim
- Commit: `14e616c382a9db8026cbb4ab86bdd803d56ca72e`
- Original path: `src/historiansim/core/valve.py`
- Local file: `valve.py`, byte-for-byte unchanged.
- SHA-256: `f3cac33ddec0fa788e01a74d47660086982221a3cf70b1a28cfc4f50a7a2e5dc`
- Licence: MIT, full notice in `LICENSE`.
- Reviewed: 2026-11-02.

Only standard-library code is vendored. FAT Studio uses the three flow
characteristics, not HistorianSim's controller or historian generator. The
application separately imposes tight shutoff at zero opening; the upstream
equal-percentage function deliberately returns `1 / rangeability` at zero.
The Stiction helper is retained to keep the source byte-identical but is not
used by the current FAT model. Updates require reviewing upstream changes and
rerunning the valve and mass-balance tests.
