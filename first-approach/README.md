# First approach

This directory contains the original exact-search track. These files historically lived at repository root before later tracks were split into dedicated directories.

## Main code

- `core.py` — core model helpers.
- `search.cpp` — low-level exact search engine.
- `batch.py` — sharded frontier/batch driver.
- `frontier3.py` — later isolated frontier driver.
- `collect_run.py` — run aggregation and verification support.
- `compact_archive.py` — compact deterministic archive packaging.
- `requirements.txt` — runtime dependencies.
- `AGENTS.md` — detailed historical operating memory, successful-run template, and incident log.

## Preserved state

- `runs/` — verified dated run archives.
- `.runs/`, `.runs3/` — historical launch/marker state.
- `.archive/` — compact historical source/run markers.

Temporary collector/query/inspection markers and tail-only diagnostic logs were pruned after the corresponding runs and durable archives had been preserved. Scientific run archives, exact verification inputs, checksums, task queues, certificates, and candidate data are retained.

## Historical workflows

Old workflow definitions are preserved under `workflows/legacy/`. They are intentionally outside `.github/workflows/`, so reorganizing historical markers cannot accidentally relaunch the old computations. Treat them as reference material, not active workflows.

## Relation to later tracks

Later approach directories use different search and verification strategies. Keep their state and archives separate unless a current task explicitly compares them.
