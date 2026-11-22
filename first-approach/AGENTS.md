# First-approach operating guide

This file is the persistent technical memory for the original exact-search track. It intentionally describes execution and verification only, not the subject of the experiment.

## Sources of truth

Before any write or launch action inspect, in order:

1. this file;
2. the newest verified directory under `runs/`;
3. its summary, checksums, verifier, records, and task payloads;
4. the newest marker and its parent/retry chain;
5. every active workflow and trigger path;
6. current GitHub Actions runs, jobs, logs, annotations, and artifacts;
7. `frontier3.py`, `batch.py`, `search.cpp`, `collect_run.py`, and archive-packaging code.

Never reconstruct current state from an old chat description when repository data is available.

## Large-run baseline

Unless measured evidence justifies a change:

- at most 20 independent GitHub-hosted jobs;
- four workers per job;
- `runtime_seconds = 21000`;
- job timeout of 360 minutes;
- independent preflight inside every matrix job;
- `fail-fast: false`;
- preserve artifacts with `if: always()`;
- record CPU, memory, swap, disk, and process limits;
- do not overlap another large matrix.

A long run must never be the first test of new orchestration code.

## Before launching

- inspect every queued, waiting, pending, requested, and in-progress Actions run across all workflows and branches;
- parse changed YAML, Python, and shell code;
- compile the exact committed C++ source;
- run a short real-path smoke test;
- verify all referenced paths exist;
- verify task uniqueness and balanced job slices;
- verify output and artifact names;
- reject future Git blobs at or above 95 MiB;
- test collector/archive changes against saved artifacts before recomputation.

## Collection and publication

After computation:

1. download exactly the expected artifacts;
2. verify artifact count, ZIP integrity, and recorded digests;
3. load the exact source task payload used by the run;
4. prove every source task is accounted for exactly once;
5. reject duplicates, missing tasks, unexpected tasks, corrupt files, and schema mismatches;
6. preserve bounded outcomes and partial valid work;
7. independently verify important exact outputs;
8. construct successors only from unresolved work plus explicitly documented reserve work;
9. run the final verifier before publication;
10. separate verification, publication, and successor launch into distinct steps.

Do not recompute successful work merely to repair packaging or publication.

## Failure memory

Important historical incidents that must not be repeated:

- Run `29959775981`: a central validation dependency blocked the entire matrix. Keep preflight inside each independent job.
- Run `29978540008`: collector assumed an obsolete schema. Validate against real artifacts and explicit versioned formats.
- Runs `29978849985` / `29983731567`: verification was coupled to fragile publication. Keep verification and publication separate.
- Run `30100288436`: an uncompressed successor queue exceeded GitHub blob limits. Use deterministic compression and a pre-push size guard.
- Run `30103121289`: workflow selected a historical marker. Bind marker selection to the triggering commit range.
- Run `30103838995`: push-event commit objects lacked changed-file arrays. Derive marker paths from `git diff before after` instead.
- Run `30104322098`: 32-bit parsing failed at shard count `2^32`. Use 64-bit shard identifiers and test the largest real boundary in preflight.

A red overall workflow status is not automatically loss of all computational output. Preserve successful matrix parts and classify technical failures separately from valid bounded outcomes.

## Current status rule

Historical workflows are stored under `workflows/legacy/` and are not active. Do not reactivate them by simple relocation. Any future reproduction requires explicit path adaptation, a fresh short smoke test, inspection of all active Actions capacity, and a newly named workflow under `.github/workflows/`.
