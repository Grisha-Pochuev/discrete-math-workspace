# First approach

This directory contains the original exact-search track for the Krenn–Gu problem. These files historically lived at repository root before the later approaches were split into dedicated directories.

## Purpose

The First approach performs exact support/frontier exploration and records exact obstruction evidence. It produced closed supports and obstruction classifications such as `inconsistent_signs`, `mixed_monomial`, and `target_zero`, together with large exact task frontiers and verified run archives.

This is exact restricted evidence. It is not, by itself, a proof of the full Krenn–Gu conjecture for every even `n >= 6`.

## Main code

- `core.py` — core combinatorial/model helpers.
- `search.cpp` — exact low-level search engine.
- `batch.py` — sharded frontier/batch driver.
- `frontier3.py` — later isolated frontier driver within the same First approach.
- `collect_run.py` — run aggregation and verification support.
- `compact_archive.py` — compact deterministic archive packaging.
- `requirements.txt` — runtime dependencies.
- `AGENTS.md` — detailed historical operating memory, successful-run template, and incident log.

## Preserved state and evidence

- `runs/` — verified dated run archives from the original exact-search campaign.
- `.runs/`, `.runs3/` — historical launch/marker state.
- `.archive/`, `.collect/`, `.collect-v2/`, `.diagnose/`, `.inspect/`, `.query/` — historical orchestration and diagnostic state.
- `diagnostics/` — preserved diagnostic material.

These directories were moved as Git trees without rewriting their scientific contents.

## Historical workflows

The old workflow definitions are preserved under `workflows/legacy/`. They are intentionally no longer under `.github/workflows/`, so reorganizing old markers cannot accidentally relaunch the original long computations. Treat them as historical definitions, not active workflows.

## Relation to later approaches

Second approach switched to numerical near-solutions. Third approach searched proof certificates. Fourth approach combines the exact obstruction evidence from this track with the later numerical/proof-search evidence for structural synthesis.
