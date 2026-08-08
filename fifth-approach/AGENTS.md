# Fifth-approach agent instructions

These rules are mandatory for work under `fifth-approach/`.

## Scope

- Treat earlier approach archives as immutable upstream evidence.
- Read `control.json`, `sources.json`, the active run specification, and the newest accepted archive before changing this track.
- Keep new outputs inside `fifth-approach/` unless a GitHub Actions workflow must live in `.github/workflows/`.
- Keep public names/descriptions operational and neutral; do not expand the public repository landing page with scientific context.

## Before any large Actions run

1. Inspect all queued, pending, waiting, requested, and in-progress Actions runs across every workflow and branch.
2. Account for known large runs in other repositories when account concurrency is shared.
3. Confirm the previous accepted archive is committed and independently verifiable.
4. Validate Python/shell/YAML, paths, matrix size, task count, artifact paths, and projected Git blob sizes.
5. Run a short real-path smoke through the same runner -> outputs -> collector -> verifier path as the full run.
6. Inspect smoke logs and artifacts; a green icon alone is insufficient.
7. Only then enable one explicitly specified full run.

## Hosted-runner assumptions

Use these as operating assumptions, not permanent guarantees:

- Ubuntu x86-64 standard runner;
- 4 vCPU per job;
- about 16 GB RAM;
- about 14 GB disk;
- maximum job duration about 6 hours;
- up to about 20 simultaneous standard jobs observed for this account;
- common full-load pattern: 20 jobs x 4 single-threaded workers;
- common useful long-run budget: 21000 seconds, leaving shutdown/upload reserve.

Aim to keep process-tree RSS around 10-11 GiB or lower and preserve several GiB for the system. Measure the whole process tree, not only the parent.

## Artifact/storage policy

- Raw shard artifacts are temporary transport, not the canonical scientific record.
- Every accepted run must produce a consolidated archive containing all scientifically unique records needed for later analysis.
- Compress large structured data deterministically and store checksums.
- Prefer short retention for redundant shard artifacts after a collector has verified them.
- Preserve unique failure diagnostics until the cause is understood.
- Do not commit prospective Git blobs near the hard size limit; project practice is to stop around 95 MiB and redesign/compress.
- If compute completed but collection failed, rescue from artifacts instead of recomputing.

## Evidence discipline

Distinguish exact results, numerical leads, and technical workflow outcomes. A successful workflow is not by itself a mathematical result.

## Launch state

`control.json` is authoritative. `enabled=false` and `full_run_auto_launch_allowed=false` mean no large run may be started automatically.
