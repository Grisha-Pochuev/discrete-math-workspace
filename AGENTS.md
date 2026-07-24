# Failure Memory, Good-Run Template, and Anti-Regression Guide

This file is the mandatory persistent operating memory for this repository.

It has two equal purposes:

1. preserve failed, fragile, misleading, or noisy attempts so they are not repeated;
2. preserve a positive technical reference for preparing, launching, collecting, and publishing a large computation correctly.

Read this file completely before changing a workflow, retrying a run, collecting results, publishing an archive, creating a marker, or launching a successor.

Do not store rapidly changing state here. Current run ids, frontier contents, completed shards, and exact next tasks belong in the newest `runs/` archive, current markers, and GitHub Actions.

## 1. Scientific purpose

The computation is not required to produce pleasant numbers. It must produce objective, exact, reproducible evidence.

A result that weakens a hoped-for pattern is still useful and must be preserved without cherry-picking. Continue from what the evidence actually says.

The computational programme should give GPT-5.6 Thinking or another strong reasoning system trustworthy material for solving the Krenn–Gu problem:

- exact task definitions and exact coverage;
- complete, incomplete, timed-out, stopped, and unstarted classifications;
- exact closed supports found by the search;
- exact algebraic obstruction classifications;
- raw artifacts and checksums;
- resource and performance measurements;
- a verifier that independently reproduces every important claim.

Do not modify an experiment merely to obtain more attractive statistics.

## 2. Sources of truth

Inspect these in order before any write action:

1. this file;
2. the newest dated directory under `runs/`;
3. its `summary.json`, task payload, checksums, verifier, records, and raw artifacts;
4. the newest marker and its `parent_run` / `retry_of` chain;
5. every active workflow and its trigger paths;
6. the public Actions API and the newest relevant run, jobs, steps, logs, annotations, and artifacts;
7. `frontier3.py`, `batch.py`, `search.cpp`, `collect_run.py`, and archive-packaging code.

Never infer the current frontier from an old chat description when repository data is available.

## 3. Positive template: preparing a good large run

This section describes technical success. It does not prescribe desired mathematical outcomes.

### 3.1 Resolve the exact input

- Load the exact task payload from the immediately preceding verified archive.
- Accept plain JSON and deterministic gzip JSON.
- Record `parent_run`, source commit, stage, task count, and task-file checksum.
- Prove task names are unique.
- Prove all 20 job slices are balanced and cover the queue exactly once.
- Never reconstruct the current generation from a historical helper when an explicit saved queue exists.

### 3.2 Marker discipline

- Every launch or archive request uses one new, unique marker file.
- Before committing a marker, prove exactly one workflow trigger matches its path.
- A push-triggered workflow must read `before` and `after` from `GITHUB_EVENT_PATH`, then derive the changed marker through `git diff --name-status before after -- <marker-directory>`.
- Require exactly one added or modified marker in that triggering commit range; zero or multiple markers are a technical error.
- Record the push range, diff, and selected marker path in diagnostics.
- Do not assume `commits[].added` or `commits[].modified` is present: pushes created through repository APIs can contain minimal commit objects.
- Never choose a marker by filesystem `mtime`, lexical order, directory name, or scanning all historical markers.

### 3.3 Static validation before a large launch

Before triggering 20 long jobs:

- parse YAML, Python, and shell syntax;
- compile the exact committed C++ source;
- verify every referenced path exists;
- confirm one intended workflow matches the marker;
- confirm no matching run, archive, successor, or retry already exists;
- run the exact task loader in `--dry-run` mode;
- verify output directories and artifact names;
- estimate generated file sizes;
- reject any future Git blob at or above 95 MiB before attempting a push;
- test changed collector or archive code against real saved artifacts.

A long run must not be the first test of new orchestration code.

### 3.4 Independent per-job preflight

Do not create one central validation job on which all compute jobs depend.

Each of the 20 matrix jobs must independently:

1. check out the reviewed commit;
2. record OS, CPU, memory, swap, disk, and limits;
3. compile;
4. execute a short exact smoke test through the real wrapper;
5. validate its assigned queue slice;
6. start computation only after those checks pass;
7. upload its artifact with `if: always()`.

Failure to acquire or initialize one runner must not cancel the other 19 jobs.

### 3.5 Safe full-run baseline

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

### 3.6 Good compute reference

Run `30069271698` is a reference for technical architecture, not for desired mathematics:

- all 20 independent jobs completed;
- per-job compile and preflight succeeded;
- all 20 artifacts were readable;
- exact aggregation against the saved source queue succeeded;
- the generated verifier passed;
- memory stayed safe and swap remained zero.

Future large runs should match this discipline even when their mathematical statistics are disappointing.

## 4. Positive template: collection, archive, publication, and successor

### 4.1 Collection

After a technically completed compute run:

1. download exactly the expected 20 artifacts;
2. verify names, count, ZIP integrity, and recorded digests;
3. read `manifest.json` and `records.jsonl` according to the committed schema;
4. load the exact source task payload used by the run;
5. prove every source task appears exactly once as recorded or unstarted;
6. reject duplicates, missing tasks, unexpected tasks, corrupt files, and schema mismatches;
7. classify every record objectively;
8. aggregate nodes, states, seconds, supports, CPU models, memory, and swap;
9. exactly verify every newly found closed support;
10. construct the successor only from incomplete and unstarted work plus an explicit reserve layer.

Never claim a layer is closed while any exact part is missing, unstarted, capacity-limited, timed out, corrupt, or unverified.

### 4.2 Scalable archive contract

Large queues are expected to grow.

- `source_tasks.json.gz` stores the exact source queue.
- `next_tasks.json.gz` stores the exact successor queue.
- `records.jsonl.gz` stores a compact record stream when needed.
- `summary.json` contains compact counts and aggregates, not duplicated millions of task names.
- raw ZIPs, `checksums.sha256`, `archive-checksums.sha256`, `README.md`, and `verify.py` remain available.
- gzip output must be deterministic.
- the final verifier must read compressed payloads, verify checksums, and prove the exact successor count and uniqueness.
- before `git add`, enumerate file sizes and abort if any blob reaches 95 MiB.

Do not use Git LFS for queues that compress from hundreds of megabytes to a few megabytes.

### 4.3 Separate phases

1. **Verification:** build the final archive and run its verifier without changing `main`.
2. **Transport:** preserve the complete verified archive as an Actions artifact; when necessary, publish one deterministic isolated archive branch.
3. **Publication:** an authorized external controller verifies provenance and publishes the archive to current `main`.
4. **Launch:** only after the archive is confirmed on `main`, create one unique successor marker in a separate commit.
5. **Confirmation:** use the public API to confirm exactly one intended compute run.

GitHub Actions must not edit `.github/workflows/` or directly update `main`.

### 4.4 Safe commit discipline

Before every write to `main`:

- re-read current `main`;
- confirm the target archive and marker do not already exist;
- ensure one publisher;
- keep each commit single-purpose;
- do not force-push;
- verify the resulting commit;
- query Actions through the API, never through a status-only commit.

Recommended commit roles:

- `save batch run <run_id>` — verified archive only;
- `launch successor after <run_id>` — one marker only;
- `fix <confirmed failure>` — code or workflow correction only;
- `record incident <run_id>` — this file only when practical.

## 5. Failure classification

A red status is not automatically a mathematical failure.

### Hosted runner not acquired

Indicators include zero executed steps, no runner, zero billable compute, no artifacts, or an annotation equivalent to `The job was not acquired by Runner of type hosted even after multiple attempts`.

Action: do not advance the frontier; preserve successful matrix parts; retry only missing work, at most once after confirming no retry exists.

### Valid bounded-search outcomes

`complete`, `capacity`, `timeout`, `stopped`, `deadline_kill`, and a controlled memory guard can all be technically valid. Preserve and analyze them.

### Real technical failures

Examples include compile or syntax errors, invalid options, missing files, schema/source mismatches, corrupt artifacts, assertions, crashes, OOM, sustained swap, disk exhaustion, transport failures, wrong-marker selection, and oversized Git blobs.

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

Separate confirmed facts from inference.

## 7. Incident history

### 2026-07-23 — run 29959775981: central validation blocked the matrix

- One `validate` job acquired no runner; all compute jobs were skipped through dependency.
- Fix: independent preflight inside every matrix job.
- Do not repeat: no central validation dependency.
- Validated by successful run `29960969740`.

### 2026-07-23 — run 29978540008: collector assumed an old schema

- Collector expected records in `manifest.json`; producer stored them in `records.jsonl`.
- Fix: explicit versioned contract and real-artifact tests.
- Do not repeat: never infer schema from older scripts.

### 2026-07-23 — runs 29978849985 and 29983731567: verification coupled to fragile publication

- Download and exact verification succeeded; final publication failed twice, including a copied `collect-v2` architecture.
- Fix: separate verification, external publication, and launch; keep one publisher.
- Do not repeat: no replacement collectors and no workflow-file mutation from Actions.

### 2026-07-23 — pre-publication audit of run 29984144124

- Found old-schema access, reconstruction from `batch.frontier2_tasks()`, silent reserve reuse, and tracked-code mutation.
- Fix: data-only collector with exact source queue and explicit reserve parameters.

### 2026-07-24 — run 30098487026: verified archive not preserved before transport

- All 20 artifacts and verifier succeeded; branch publication failed.
- Fix: preserve the complete candidate before transport and save the full transcript.

### 2026-07-24 — run 30099623792: diagnostic pipeline aborted publication

- `find | sort | head` under `set -euo pipefail` allowed SIGPIPE to stop the gate before Git commands.
- Fix: write the complete listing to a file and display it with `sed -n`.
- Do not repeat: no truncating `head` pipeline in a strict gate.

### 2026-07-24 — run 30100288436: GitHub rejected an oversized queue

- Exact aggregation and verifier passed; push was rejected.
- `next_tasks.json` was 159,107,694 bytes (151.74 MiB), above GitHub's 100 MiB limit; other JSON files also duplicated large lists.
- Fix: deterministic gzip queues, compact summary, final compressed-payload verifier, and 95 MiB pre-push guard.
- Saved-data validation reduced the largest payload to about 3 MiB and passed the verifier.
- Do not repeat: no uncompressed retry and no recomputation of successful run `30069271698`.

### 2026-07-24 — run 30103121289: workflow selected a historical marker

- Intended archive: source `f1a518671b1116647c8be9b04f38148dd8b593fc`, output `runs/2026-07-24-b`.
- Actual request: old source `5f12071830128bc3a8e5a403ae04f8464d935656`, output `runs/2026-07-24-a`.
- Evidence: diagnostic `request.env` from the run.
- Root cause: selection by filesystem `mtime` after checkout.
- Fix: bind marker selection to the triggering commit range.
- No mathematical data was changed.

### 2026-07-24 — run 30103838995: push event contained minimal commit objects

- Intended goal: select the marker from `commits[].added/modified` in `GITHUB_EVENT_PATH`.
- What happened: the push event contained `before`, `after`, and minimal commit metadata, but no `added`, `modified`, or `removed` arrays. The protective step found zero markers and stopped immediately.
- Evidence: saved `work/push-event.json` from run `30103838995`; it records `before=fe710face5bc84ec9bdd9283588c488abf8b2373` and `after=a4a3233e3c64d13ea10d646cade0a231eee38191` but no changed-file arrays.
- Classification: request-resolution failure before source resolution, downloads, aggregation, or publication.
- Root cause: an unsupported assumption about push-event richness for commits created through repository APIs.
- Permanent fix: derive changed paths with `git diff --name-status before after -- .archive/`, require exactly one added/modified marker, and save the range and diff in diagnostics.
- Forbidden repetition: do not rely on `commits[].added/modified` being present; do not fall back to directory-wide scanning.
- No compute result or verified archive was damaged.

## 8. Mandatory startup checklist

Before any write action:

1. read this file completely and treat incidents as examples to avoid;
2. inspect the newest verified archive and exact `run_id`;
3. inspect marker and parent/retry chain;
4. enumerate workflows and trigger paths;
5. query the public Actions API dynamically;
6. determine whether the relevant run is active, failed, complete, or processed;
7. check archive branches, published archives, successors, and retries;
8. ensure one publisher and one intended workflow;
9. test changed orchestration on saved data and simulate or inspect actual event structures;
10. re-read `main` immediately before committing;
11. after committing, verify the commit and exactly one resulting run through the API.

If a check cannot be completed, do not make multiple speculative retries. Preserve state, record uncertainty, and make the smallest reversible correction.
