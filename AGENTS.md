# Failure Memory, Good-Run Template, and Anti-Regression Guide

This file is the mandatory persistent operating memory for this repository.

It has two equal purposes:

1. preserve failed, fragile, misleading, or noisy attempts so they are not repeated;
2. preserve a positive reference architecture for preparing, running, collecting, and publishing a large computation correctly.

Read this file completely before changing a workflow, retrying a run, collecting results, publishing an archive, creating a marker, or launching a successor.

Do not store rapidly changing state here. Current run ids, current frontier contents, completed shards, and exact next tasks belong in the newest `runs/` archive, the current marker, and GitHub Actions.

## 1. Scientific purpose

The computation is not required to produce pleasant numbers. It must produce objective, exact, reproducible evidence.

A result that weakens a hoped-for pattern is still useful and must be preserved without cherry-picking. Continue from what the evidence actually says.

The computational programme should provide GPT-5.6 Thinking or another strong reasoning system with trustworthy material for solving the Krenn–Gu problem:

- exact task definitions and exact coverage;
- complete, incomplete, timed-out, stopped, and unstarted classifications;
- exact closed supports found by the search;
- exact algebraic obstruction classifications;
- representative raw artifacts and checksums;
- resource and performance measurements;
- a verifier that can independently reproduce all important claims.

The AI should reason from these objective records. Do not alter the experiment to obtain more attractive-looking statistics.

## 2. Sources of truth

Inspect these in order before any write action:

1. this file;
2. the newest dated directory under `runs/`;
3. its `summary.json`, task payload, checksums, verifier, records, and raw artifacts;
4. the newest run marker and its `parent_run` / `retry_of` relation;
5. every active file under `.github/workflows/` and the paths that trigger it;
6. the public Actions API and the newest relevant run, jobs, steps, logs, annotations, and artifacts;
7. `frontier3.py`, `batch.py`, `search.cpp`, `collect_run.py`, and archive-packaging code.

Never infer the current frontier from an old chat description when repository data is available.

## 3. Positive template: how to prepare a good large run

This section describes technical success. It does not prescribe desired mathematical outcomes.

### 3.1 Resolve the exact input

- Load the exact task file from the immediately preceding verified archive.
- Accept both plain JSON and deterministic gzip JSON.
- Record `parent_run`, source commit, stage, task count, and task-file checksum.
- Prove task names are unique.
- Prove the 20 job slices are balanced and cover the exact queue once.
- Never regenerate an old queue from a historical helper function when an explicit saved queue exists.

### 3.2 Static validation before a large launch

Before triggering 20 long jobs:

- parse all YAML, Python, and shell syntax;
- compile the exact committed C++ source;
- verify all referenced files and paths exist;
- confirm exactly one workflow matches the marker path;
- confirm no matching run or successor already exists;
- run the exact task loader in `--dry-run` mode;
- verify output directories and artifact names;
- calculate expected artifact and generated-file sizes;
- reject any future Git blob at or above 95 MiB before attempting a push;
- test changed collector or archive code against a real saved artifact set.

A long run must not be the first test of new orchestration code.

### 3.3 Independent per-job preflight

Do not create one central validation job on which all compute jobs depend.

Each of the 20 matrix jobs must independently:

1. check out the reviewed commit;
2. record OS, CPU, memory, swap, disk, and limits;
3. compile;
4. execute a short exact smoke test through the real wrapper;
5. validate its assigned queue slice;
6. start its computation only after those checks pass;
7. upload its artifact with `if: always()`.

Failure to acquire or initialize one runner must not cancel the other 19 jobs.

### 3.4 Safe full-run baseline

Unless measured evidence justifies a change:

- 20 independent GitHub-hosted jobs;
- 4 workers per job;
- `runtime_seconds = 21000`;
- job timeout of 360 minutes;
- preferred combined RSS at most 10–11 GiB;
- warning near 11.5 GiB;
- keep `MemAvailable` above about 2.5 GiB;
- no sustained swap;
- preserve controlled `capacity`, `timeout`, `stopped`, `deadline_kill`, and memory-guard outcomes as valid bounded-search results.

Record the actual CPU model and full process-tree resource use for every job.

### 3.5 Good compute reference

Run `30069271698` is a reference for the compute architecture, not for desired mathematics:

- all 20 independent jobs completed technically;
- per-job compile and preflight succeeded;
- all 20 artifacts were present and readable;
- exact aggregation against the saved source queue succeeded;
- the generated verifier passed;
- peak memory stayed safe and swap remained zero.

Future large runs should match this technical discipline even when their mathematical statistics are disappointing.

## 4. Positive template: collection, archive, publication, and successor

### 4.1 Collection

After a technically completed compute run:

1. download exactly the expected 20 artifacts;
2. verify names, count, ZIP integrity, and recorded artifact digests;
3. read `manifest.json` and `records.jsonl` according to the committed schema;
4. load the exact source task file used by the run;
5. prove every source task appears exactly once as recorded or unstarted;
6. reject duplicates, missing tasks, unexpected tasks, corrupt files, and schema mismatches;
7. classify every record objectively;
8. aggregate nodes, states, seconds, supports, CPU models, memory, and swap;
9. exactly verify every newly found closed support;
10. construct the successor only from incomplete and unstarted work, plus an explicit reserve layer.

Never claim a layer is closed while any exact part is missing, unstarted, capacity-limited, timed out, corrupt, or unverified.

### 4.2 Scalable archive contract

Large queues are expected to grow. The archive format must scale before publication.

- `source_tasks.json.gz` stores the exact source queue.
- `next_tasks.json.gz` stores the exact successor queue.
- `records.jsonl.gz` may store the record stream when compacted.
- `summary.json` contains counts and compact aggregates, not millions of duplicated task names.
- raw job ZIPs, `checksums.sha256`, `archive-checksums.sha256`, `README.md`, and `verify.py` remain in the archive.
- gzip output must be deterministic so repeated packaging is reproducible.
- the final verifier must read the compressed payloads, verify their checksums, and prove the exact next-task count and uniqueness.
- before `git add`, enumerate file sizes and abort if any blob is at or above 95 MiB.

Do not use Git LFS for a task queue that compresses from hundreds of megabytes to a few megabytes.

### 4.3 Separate phases

Verification, publication, and launch are separate phases:

1. **Verification:** build the final archive and run its verifier without changing `main`.
2. **Transport:** preserve the complete verified archive as an Actions artifact; when necessary, publish it to one deterministic isolated branch.
3. **Publication:** an authorized external controller verifies the branch descends from current `main` and fast-forwards or otherwise publishes the archive.
4. **Launch:** only after the archive is confirmed on `main`, create one unique successor marker in a separate commit.
5. **Confirmation:** use the public Actions API to confirm exactly one intended compute run appeared.

GitHub Actions must not edit `.github/workflows/` or directly update `main`. It may prepare an isolated candidate branch when the external controller needs binary transport.

### 4.4 Safe commit discipline

Before every write to `main`:

- re-read the latest `main`;
- confirm the target archive and marker do not already exist;
- ensure there is only one publisher;
- keep each commit single-purpose;
- do not force-push;
- verify the resulting commit after writing;
- query Actions through the API, never through a status-only commit.

Recommended commit roles:

- `save batch run <run_id>` — verified result archive only;
- `launch successor after <run_id>` — one marker only;
- `fix <confirmed failure>` — code or workflow correction only;
- `record incident <run_id>` — this file only when practical.

## 5. Failure classification

A red status is not automatically a mathematical failure.

### 5.1 Hosted runner not acquired

Indicators include zero executed steps, no runner name, zero billable compute, no artifacts, or an annotation equivalent to `The job was not acquired by Runner of type hosted even after multiple attempts`.

Action:

- classify as GitHub infrastructure failure;
- do not record a mathematical result;
- do not advance the frontier;
- preserve successful matrix parts;
- retry only missing work, at most once after confirming no retry already exists.

### 5.2 Valid bounded-search outcomes

`complete`, `capacity`, `timeout`, `stopped`, `deadline_kill`, and a controlled memory guard can all be technically valid outcomes. Preserve and analyze them.

### 5.3 Real technical failures

Examples:

- compile or syntax error;
- invalid option or missing source file;
- parser/schema/source-task mismatch;
- missing or corrupt artifact;
- assertion failure or segmentation fault;
- OOM, sustained swap, or disk exhaustion;
- publication or transport failure after successful verification;
- a Git blob that exceeds the publication-size guard.

Diagnose from evidence, test the correction on saved data, and make one corrected attempt. Do not recompute a successful mathematical run to repair publication.

## 6. Failure recording format

Every meaningful new failure must be appended. Preserve old incidents after fixing them.

Record:

```text
Date and run id:
Intended goal:
What actually happened:
Evidence:
Classification:
Root cause:
Consequences:
Permanent fix:
Forbidden repetition:
Validated replacement:
```

Separate confirmed facts from inference. When the exact low-level cause is unknown, say so.

## 7. Incident history

### 2026-07-23 — run 29959775981: central validation blocked the matrix

- **Observed:** one `validate` job acquired no runner and executed no steps; all compute jobs were skipped through dependency.
- **Root cause:** a single infrastructure allocation was a global point of failure.
- **Fix:** independent preflight inside every matrix job.
- **Do not repeat:** no central `validate` / `prepare` dependency for all 20 compute jobs.
- **Validated by:** successful run `29960969740`.

### 2026-07-23 — run 29978540008: collector assumed an old artifact schema

- **Observed:** collector expected records in `manifest.json`; producer stored them in `records.jsonl`.
- **Root cause:** collector was not tested against real current artifacts.
- **Fix:** explicit versioned contract and real-artifact test.
- **Do not repeat:** never infer the schema from an older script.

### 2026-07-23 — run 29978849985: verification coupled to unauthorized publication

- **Observed:** download, aggregation, exact verification, and successor preparation succeeded; final push failed.
- **Root cause:** one workflow coupled verified results to repository/workflow mutation requiring unavailable permissions.
- **Fix:** separate verification, external publication, and launch.
- **Do not repeat:** do not ask an Actions collector to edit workflow files or treat a publication failure as a reason to recompute.

### 2026-07-23 — run 29983731567: `collect-v2` repeated the same architecture

- **Observed:** exact verification again succeeded and final publication again failed.
- **Root cause:** a second collector copied the same fragile publication design.
- **Fix:** delete replacement collectors and keep one publishing path.
- **Do not repeat:** no `collect-v2`, `collect-v3`, or concurrent publishers.

### 2026-07-23 — pre-publication audit of run 29984144124

- **Observed:** static audit found old-schema access, reconstruction from `batch.frontier2_tasks()`, silent reserve-layer reuse, and attempts to rewrite tracked code/workflows.
- **Fix:** data-only collector with explicit source queue and explicit reserve parameters.
- **Do not repeat:** never derive the current generation from a historical generator when an exact saved queue exists.

### 2026-07-24 — run 30098487026: verified archive was not recoverable before branch push

- **Observed:** all 20 artifacts, aggregation, and verifier succeeded; branch-publication step failed.
- **Design weakness:** the complete verified archive existed only in the ephemeral workspace before the push.
- **Fix:** upload the complete verified candidate before transport and capture the full publication transcript.
- **Do not repeat:** never discard or recompute a verified archive because transport failed.

### 2026-07-24 — run 30099623792: diagnostic pipeline aborted publication

- **Observed:** verified archive was preserved; isolated-branch step stopped before Git commands.
- **Root cause:** `find | sort | head` under `set -euo pipefail` allowed SIGPIPE from `head` to abort the gate.
- **Fix:** write the complete sorted listing to a file and display it with `sed -n`.
- **Do not repeat:** no truncating `head` pipeline inside a strict publication gate.

### 2026-07-24 — run 30100288436: GitHub rejected an oversized exact queue

- **Observed:** all 20 compute artifacts downloaded; exact aggregation and verifier passed; the archive was preserved; `git commit` succeeded locally; `git push` was rejected.
- **Evidence:** `next_tasks.json` was 159,107,694 bytes (151.74 MiB), above GitHub's 100 MiB hard file limit. `source_tasks.json` was 78,340,818 bytes and `summary.json` was 15,420,690 bytes because it duplicated long name lists.
- **Classification:** publication-format failure after successful mathematical verification.
- **Consequences:** no result loss and no need to rerun compute run `30069271698`; archive publication and successor launch remain pending.
- **Permanent fix:** deterministic gzip task queues, compact summary without duplicated name lists, final compressed-payload verifier, and a 95 MiB pre-push guard.
- **Forbidden repetition:** do not retry the same uncompressed archive; do not use Git LFS as a substitute for compact machine-readable queues; do not launch a successor before the verified archive reaches `main`.
- **Validated replacement:** the saved archive was compacted offline; the largest resulting payload was about 3 MiB and the final verifier passed. A corrected end-to-end publication run is still required.

## 8. Mandatory startup checklist

Before any write action:

1. read this file completely and treat the incidents as examples to avoid;
2. inspect the newest verified archive and its exact `run_id`;
3. inspect the newest marker and parent/retry chain;
4. enumerate active workflows and trigger paths;
5. query the public Actions API dynamically;
6. determine whether the newest relevant run is active, failed, complete, or already processed;
7. check existing archive branches, published archives, successors, and retries;
8. ensure one publisher and one intended workflow;
9. perform static and saved-data tests for changed orchestration code;
10. re-read `main` immediately before committing;
11. after committing, verify the commit and exactly one resulting run through the API.

If a check cannot be completed, do not make multiple speculative retries. Preserve the current state, record the uncertainty, and make the smallest reversible correction.
