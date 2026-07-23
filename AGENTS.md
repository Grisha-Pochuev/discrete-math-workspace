# Failure Memory and Anti-Regression Guide

This file is the persistent memory of failed, fragile, misleading, or unnecessarily noisy attempts in this repository.

Its primary purpose is **not** to describe the current run. Its purpose is to prevent the same mistakes from being repeated by a later agent, chat, automation, or maintainer.

Read this file before:

- creating or editing a GitHub Actions workflow;
- retrying a failed run;
- collecting or publishing results;
- choosing a successor frontier;
- changing the artifact format;
- creating a new marker or automatic continuation mechanism.

Do not store rapidly changing operational state here. Current run ids, frontier status, completed shards, and exact next tasks belong in the newest directory under `runs/`, the current marker, and GitHub Actions itself.

## 1. How to record a failed attempt

Every meaningful failure must be appended to the incident log. Do not erase old incidents after fixing them.

Use this structure:

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

If the exact low-level cause is not confirmed, say so explicitly. Record confirmed facts separately from inference.

A failed service workflow is still important even when the mathematical computation succeeded. Publication failures, duplicate retries, notification storms, corrupted artifacts, and stale assumptions must all be recorded.

## 2. Sources of truth

Before doing new work, inspect these in order:

1. this file;
2. the newest dated directory under `runs/`;
3. its `summary.json`, checksums, verification script, and raw artifacts;
4. the newest run marker;
5. all currently active files under `.github/workflows/`;
6. the newest relevant GitHub Actions run and its job steps;
7. `batch.py`, the search engine, and the collector code.

Never infer the current frontier from an old chat description when repository data is available.

## 3. Non-negotiable anti-regression rules

### 3.1 No central validation bottleneck

Do not create one `validate` or `prepare` job on which the entire 20-job matrix depends.

Each matrix job must perform its own short preflight:

1. checkout;
2. record machine information;
3. compile;
4. run a small exact smoke test;
5. validate its task assignment;
6. run its computation;
7. upload its artifact with `if: always()`.

Failure to acquire one runner must not cancel all other jobs.

### 3.2 One intended workflow per marker

Before committing a marker, enumerate every workflow whose `push.paths` can match that marker.

Exactly one intended computational workflow should match. Do not leave broad `on: push` workflows or several generations of collectors active at the same time.

### 3.3 Do not retry before diagnosis

After the first red service run:

- inspect the failed step and the end of the log;
- classify the failure;
- reproduce it against saved artifacts without a new long run;
- fix the confirmed cause;
- run a short end-to-end replay;
- only then create one retry.

Do not respond to a failed collector by immediately creating another push-triggered collector workflow. Three unverified retries produce three failures and three emails, but no additional knowledge.

### 3.4 One publisher only

Only one process may publish a completed run to `main`.

Do not allow both an Actions job and an external agent to publish the same `runs/...` directory or successor marker. Do not run two collectors for the same source run.

Before publishing, check whether the target directory and successor marker already exist.

### 3.5 Collection and publication are separate phases

The safe sequence is:

```text
download artifacts
-> verify artifact count and checksums
-> aggregate records
-> exact mathematical verification
-> prepare output in an isolated working directory
-> publish once
-> create exactly one successor marker
```

A collector should preferably be read-only with respect to the repository. Publication should happen only after verification succeeds.

### 3.6 A workflow must not rewrite workflow definitions

Do not make a running GitHub Actions job modify or publish files under `.github/workflows/`.

The standard `GITHUB_TOKEN` may have `contents: write` and `actions: read` while still lacking permission to create or modify workflow definitions. Workflow changes must be prepared, reviewed, and committed outside the running workflow before it is triggered.

### 3.7 Never hot-patch production code inside the workflow

Do not use commands such as `sed -i` to remove assertions or alter collector logic at runtime.

Fix the source file in the repository, test it on a saved artifact fixture, and commit the tested version. The code that is tested must be the code that runs.

## 4. Artifact and collector contract

The artifact schema must be explicit and versioned.

For the compact batch format used by run `29960969740`:

- `records.jsonl` is the canonical source of task records;
- `manifest.json` is a compact per-job summary and does not necessarily duplicate the full record list;
- collectors must not assume `manifest["records"]` exists;
- all 20 artifacts must be present and unexpired;
- artifact names must be exactly `data-0` through `data-19`;
- every ZIP must pass an integrity test;
- the combined record count and unique task names must be checked;
- every newly found support must be verified exactly.

Before a collector workflow is allowed to run, it must pass a replay test against a saved set of 20 real artifacts from a completed run.

The replay test must cover the complete path:

```text
20 ZIP artifacts
-> manifests and records.jsonl
-> aggregation
-> exact verification
-> final runs/ directory
-> successor description
```

## 5. Compute safety retained from earlier runs

Assume per standard public Linux runner:

- 4 virtual CPU cores;
- about 15.6 GiB visible RAM;
- about 14 GB disk;
- maximum job duration of 6 hours;
- CPU model may vary;
- up to 20 jobs can run concurrently.

Normal full-run target:

- 20 jobs;
- 4 workers per job;
- `runtime_seconds = 21000`;
- `timeout-minutes = 360`;
- combined RSS normally below 10-11 GiB;
- warning threshold around 11.5 GiB;
- keep `MemAvailable` above about 2.5 GiB;
- no sustained swap use;
- always reserve time for graceful shutdown and artifact upload.

Normal bounded outcomes such as `complete`, `capacity`, `timeout`, controlled `stopped`, and memory guard are data, not workflow failures.

## 6. Notification hygiene

GitHub sends failure email per failed workflow run, not per mathematical problem.

Therefore:

- one failed collector retry equals one additional email;
- several temporary collector workflows can multiply emails;
- skipped or empty jobs may also generate mail;
- red status should be reserved for genuine technical failure;
- do not create repeated trigger commits while a run or retry is active;
- remove obsolete temporary workflows after their purpose is complete;
- never disable security or account notifications merely to silence Actions mail.

The correct solution to notification noise is fewer, better-tested workflows, not hiding the email.

## 7. Incident log

### 2026-07-23 — run 29959775981: central validator never acquired a runner

**Intended goal:** validate the new frontier and then start a 20-job computation.

**What happened:**

- the single central `validate` job waited about 15 minutes;
- no runner was assigned;
- no step executed;
- billable compute duration was zero;
- the matrix was skipped because it depended on `validate`;
- GitHub reported: `The job was not acquired by Runner of type hosted even after multiple attempts`.

**Classification:** GitHub-hosted runner allocation failure. No computation and no mathematical result.

**Root cause:** the workflow architecture made one hosted runner a single point of failure for all 20 jobs.

**Permanent fix:** remove the dependency and give every matrix job its own preflight. Use `ubuntu-latest` unless a fixed image is materially required.

**Forbidden repetition:** never restore a central validation job that gates the whole matrix.

**Validated replacement:** run `29960969740`, where independent jobs acquired runners, passed preflight, computed, and uploaded 20 artifacts.

### 2026-07-23 — run 29978540008: collector assumed the old artifact schema

**Intended goal:** collect and exactly verify the successful computation `29960969740`, save it, and prepare its successor.

**What happened:**

- checkout, dependency installation, and download of all original artifacts succeeded;
- the job failed in `Aggregate, exactly verify, and prepare successor`;
- the collector expected full task records inside `manifest.json`;
- the compact artifacts stored the canonical records in `records.jsonl` instead.

**Classification:** collector compatibility failure. The mathematical computation remained valid and its artifacts were intact.

**Root cause:** the collector was written against an older artifact layout and was not replay-tested against the real compact artifact set before being triggered.

**Permanent fix:** treat `records.jsonl` as canonical, version the artifact schema, and test collectors on saved real artifacts before running them in Actions.

**Forbidden repetition:** do not assume `manifest["records"]`; do not patch the assertion at runtime with `sed -i`.

**Validated replacement:** the final external collection successfully produced and verified `runs/2026-07-23-b/`.

### 2026-07-23 — run 29978849985: verification succeeded but publication was coupled to workflow changes

**Intended goal:** retry the collector after correcting the schema assumption.

**What happened:**

- artifact download succeeded;
- aggregation and exact verification succeeded;
- a successor marker was created;
- the final `Commit verified archive and launch successor` step failed;
- the workflow attempted to publish repository changes that included workflow-related files while its token permissions were only `contents: write` and `actions: read`.

**Classification:** publication-layer failure, not mathematical or aggregation failure.

**Root cause:** collection, workflow modification, publication, and successor launch were combined in one Actions job. The job tried to use its own workflow token for a class of repository changes that should have been made outside the running workflow.

**Permanent fix:** a collector must not modify `.github/workflows/`. Prepare workflow definitions before launch. Publish verified results and the successor marker through one authorized external publisher.

**Forbidden repetition:** do not give a result-collection workflow responsibility for rewriting or introducing the next workflow.

### 2026-07-23 — run 29983731567: second collector verified the same result but failed at the same publication boundary

**Intended goal:** isolate the collector and publish the already verified result.

**What happened:**

- all 20 artifacts were downloaded;
- aggregation and exact verification succeeded;
- the isolated successor marker was created;
- only the final commit/push step failed;
- during the same period, several external and automated commits were also targeting `main` and the same result/continuation chain.

**Classification:** publication race / multiple-writer architecture failure. The exact mathematical result was not affected.

**Root cause:** more than one mechanism was permitted to publish or repair the same completed run. A new collector was launched before the publication architecture had been simplified to one writer.

**Permanent fix:** only one publisher may write the result directory and successor marker. If an external agent is publishing, Actions collection must remain read-only. If publication has already succeeded externally, do not retry the collector.

**Forbidden repetition:** do not create `collect-v2`, `collect-v3`, or another temporary push-triggered collector after a publish-step failure without first proving the full publication path in isolation.

**Cleanup:** obsolete `collect.yml` and `collect-v2.yml` were removed after the verified results had already been saved.

### 2026-07-23 — three collector failure emails

**Observed:** three emails from this repository were generated by the three failed service runs above.

**Root cause:** each retry was a separate red GitHub Actions workflow run. The emails were a consequence of repeated unverified service retries, not of the successful 20-job mathematical run.

**Permanent fix:** after the first collector failure, stop. Diagnose once, replay locally or against saved artifacts, and publish through one tested path. Do not create another Actions retry merely to test a new idea.

## 8. Checklist before any future retry

Before creating a retry marker or workflow, answer all of the following:

- Is the failed run computational, infrastructural, collection, verification, or publication failure?
- Did the mathematical workers actually run?
- Are all successful artifacts preserved?
- Is the exact final error known?
- Has the proposed fix been tested against saved artifacts?
- Does exactly one workflow match the new marker?
- Is there exactly one publisher?
- Will the workflow attempt to modify `.github/workflows/`?
- Does the target result directory already exist?
- Does a successor marker already exist?
- Is another retry queued or active?
- Will this new run create another failure email without adding new information?

If any answer is unknown, do not launch the retry yet.

## 9. Where current state belongs

Do not keep an `active run` section in this file. It becomes stale and can mislead later work.

Use instead:

- the newest dated directory under `runs/` for verified completed state;
- the newest unique marker for intended successor state;
- GitHub Actions for queued and running state;
- `summary.json` and verification output for mathematical state.

This file should change mainly when a new failure mode, misleading assumption, or durable prevention rule is discovered.
