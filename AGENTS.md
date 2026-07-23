# Failure Memory and Anti-Regression Guide

This file is the persistent memory of failed, fragile, misleading, or unnecessarily noisy attempts in this repository.

Its primary purpose is **not** to describe the current run. Its purpose is to prevent the same mistakes from being repeated by a later agent, chat, automation, or maintainer.

Read this file before:

- creating or editing a GitHub Actions workflow;
- retrying a failed run;
- collecting or publishing results;
- choosing a successor frontier;
- changing the artifact format;
- creating a new marker or automatic continuation mechanism;
- committing generated results to `main`.

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

A failed service workflow is still important even when the mathematical computation succeeded. Publication failures, duplicate retries, notification storms, corrupted artifacts, stale assumptions, and unsafe commit patterns must all be recorded.

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

Do not create `collect-v2`, `collect-v3`, or similar replacement workflows as a reflex. Fix and validate one implementation outside GitHub Actions first.

### 3.3 Do not retry before diagnosis

A red run is not permission to create another run immediately.

Before retrying:

1. identify the failing job and step;
2. read the log or check-run annotation;
3. determine whether computation started;
4. inspect runner assignment, billable duration, and artifacts;
5. reproduce the failing parser, collector, or publisher against already downloaded artifacts;
6. run one short end-to-end validation of the corrected path;
7. create at most one retry.

Never create multiple retry markers while another retry is queued or running.

### 3.4 Keep the artifact contract explicit and versioned

The compact artifact format stores task records in `records.jsonl`. `manifest.json` contains metadata and counts and is not required to duplicate the full records list.

Collectors must validate the actual committed schema. They must not assume an older schema because a previous script did.

If the schema changes:

- update the producer and consumer together;
- record a format version;
- test the collector on a real saved artifact set before activating a workflow;
- keep backward compatibility where practical;
- never patch the collector at runtime with `sed`, ad-hoc deletion, or other mutation.

### 3.5 Do not modify tracked source code inside a collection run

A workflow must execute committed code exactly as reviewed.

Forbidden patterns include:

```bash
sed -i ... collect_run.py
cp temporary-version over tracked source
modify batch.py during the job
modify a workflow file during the job
```

If a parser or collector needs correction, update it in a normal commit, test it, then run it.

### 3.6 GitHub Actions must not publish workflow-file changes

The normal `GITHUB_TOKEN` is intentionally restricted. A workflow that attempts to push `.github/workflows/*.yml` may be rejected even when result aggregation and exact verification succeeded.

Therefore:

- do not ask a collector workflow to create, edit, delete, or publish workflow files;
- do not bundle result publication with workflow creation;
- prepare workflow changes in a normal reviewed commit through the connected GitHub tool or another authorized publisher;
- treat a workflow permission failure as a publication failure, not a mathematical failure.

### 3.7 Separate verification, publication, and launch

These are three distinct phases:

1. **Verification** — download artifacts, check integrity, aggregate records, verify supports and summaries.
2. **Publication** — commit the verified archive to `main`.
3. **Launch** — after confirming publication, create one successor marker.

Do not couple all three phases inside an untested workflow.

Preferred sequence:

1. verify against downloaded artifacts without changing the repository;
2. commit the dated `runs/` archive;
3. re-read `main` and confirm the archive commit exists;
4. check that no successor is queued, running, or already recorded;
5. create one unique successor marker in a separate single-purpose commit;
6. confirm exactly one intended workflow was created.

### 3.8 One publisher only

Only one actor may publish a given completed run.

Before publishing, check:

- whether `runs/` already contains that `run_id`;
- whether a commit message already records that `run_id`;
- whether a marker already has `parent_run=<run_id>`;
- whether another collector, automation, or branch is currently publishing it.

Do not let a GitHub Actions workflow, an hourly automation, and a manual agent all push the same result concurrently.

### 3.9 Safe commit discipline

Before every write to `main`:

1. fetch or re-read the latest `main` state;
2. verify that the target path has not already been created or changed;
3. keep the commit single-purpose;
4. avoid unrelated workflow changes in result commits;
5. after the write, fetch the resulting commit and verify the intended files;
6. do not force-push;
7. do not create a second commit merely to query run status.

Use clear commit roles:

- `save batch run <run_id>` — verified result archive only;
- `launch successor after <run_id>` — one marker only;
- `fix <confirmed failure>` — source or workflow correction only;
- `record incident <run_id>` — this file only when possible.

Do not generate status-query commits. Query GitHub Actions through the API instead.

### 3.10 Safe compute baseline

For standard public Linux runners use this safe baseline unless measured evidence justifies a change:

- 20 independent jobs;
- 4 workers per job;
- `runtime_seconds = 21000`;
- job timeout of 360 minutes;
- preferred combined RSS at most 10–11 GiB;
- warning around 11.5 GiB;
- keep `MemAvailable` above about 2.5 GiB;
- no sustained swap;
- always record CPU, memory, disk, and process-tree data.

A controlled `capacity`, `timeout`, `stopped`, or memory-guard result is not automatically a workflow failure.

### 3.11 Failure classification

#### Runner was not acquired

Indicators:

- zero executed steps;
- empty runner name or runner id zero;
- zero billable compute time;
- no artifacts;
- annotation equivalent to `The job was not acquired by Runner of type hosted even after multiple attempts`.

Action:

- classify as GitHub infrastructure failure;
- do not record it as a mathematical result;
- do not advance the frontier;
- retry the same frontier once;
- if only some matrix jobs were affected, preserve successful artifacts and repeat only missing work.

#### Real technical failure

Examples:

- compile error;
- invalid option;
- malformed input;
- missing mandatory file;
- parser/schema mismatch;
- corrupt artifact;
- assertion failure;
- segmentation fault;
- OOM or sustained swap;
- disk exhaustion;
- failed publication after successful verification.

Fix the confirmed cause, test the corrected path, then retry once.

### 3.12 Notification hygiene

Every red workflow can generate email. Avoid creating noise by architecture, not by disabling security mail.

Rules:

- keep only necessary active workflows;
- delete obsolete collector workflows after their purpose is complete;
- do not leave workflows that trigger on every push but skip all jobs through an internal `if`;
- do not create a new workflow for each retry;
- reserve red status for genuine technical failures;
- do not make repeated marker commits while a run is active;
- after a noisy incident, inspect all active workflows, not only the one named in the email.

## 4. Required result-collection protocol

After a technically completed computation:

1. download all expected artifacts;
2. verify artifact names, count, ZIP integrity, and checksums;
3. read `manifest.json` and `records.jsonl` according to the committed schema;
4. identify missing, duplicate, corrupt, and unstarted tasks;
5. classify all records as `complete`, `capacity`, `timeout`, `stopped`, memory guard, or technical failure;
6. aggregate nodes, states, engine seconds, supports, CPU models, peak RSS, minimum available memory, and swap;
7. exactly verify every new support;
8. write a dated archive containing raw artifacts, checksums, summary, verifier, and next-frontier description;
9. execute the verifier from the finished archive;
10. publish the archive in one result commit;
11. only after publication, create one successor marker in a separate commit.

Never claim a layer is closed while any shard is missing, capacity-limited, timed out, corrupt, unverified, or never started.

## 5. Incident log

### 2026-07-23 — run 29959775981: central validation blocked the whole matrix

**Intended goal:** launch the full `frontier2` matrix.

**What actually happened:** the single `validate` job waited for a hosted runner, never received one, executed no steps, and the entire compute matrix was skipped because it depended on that job.

**Evidence:** zero executed steps, zero billable compute, no artifacts, and the annotation `The job was not acquired by Runner of type hosted even after multiple attempts`.

**Classification:** GitHub infrastructure allocation failure; no mathematical computation occurred.

**Root cause:** one central job was a single point of failure for all 20 machines.

**Consequences:** the full run produced no result and required a retry.

**Permanent fix:** remove the central dependency; each matrix job performs its own preflight and then computes independently.

**Forbidden repetition:** never reintroduce one `validate`/`prepare` job required by the full matrix.

**Validated replacement:** run 29960969740 used independent per-job preflight and completed successfully.

### 2026-07-23 — run 29978540008: collector assumed the old artifact schema

**Intended goal:** aggregate and publish completed run 29960969740.

**What actually happened:** all artifacts were downloaded, but the collector expected the full task record list inside `manifest.json`. The current compact format stores records in `records.jsonl`.

**Evidence:** the failure occurred in `Aggregate, exactly verify, and prepare successor`; the retry marker recorded `compact manifest stores task records only in records.jsonl`.

**Classification:** collector compatibility failure; the underlying mathematical run was successful.

**Root cause:** the collector was not tested against the exact artifact format produced by the completed run.

**Consequences:** one failed workflow and one email; no result loss.

**Permanent fix:** make the artifact contract explicit, validate `records.jsonl`, and test collectors against saved real artifacts before activation.

**Forbidden repetition:** do not assume duplicated records in `manifest.json`; do not activate an untested collector.

**Validated replacement:** the result was later aggregated and exactly verified from all 20 artifacts.

### 2026-07-23 — run 29978849985: successful verification was coupled to an unauthorized workflow-file publication

**Intended goal:** retry collection, publish the verified archive, and launch the successor.

**What actually happened:** artifact download, aggregation, exact verification, and successor preparation succeeded. The final commit/push step failed.

**Evidence:** steps through `Create one successor marker` succeeded; `Commit verified archive and launch successor` failed.

**Classification:** publication failure after successful verification.

**Root cause:** the workflow attempted to publish changes that included tracked workflow-related files or otherwise required permissions unavailable to the normal `GITHUB_TOKEN`; verification and repository mutation were coupled in one job.

**Consequences:** a second failed service workflow and a second email, despite successful mathematical verification.

**Permanent fix:** workflows may verify and upload diagnostics, but workflow-file changes and publication must be performed by an authorized external publisher. Separate result commit from launch marker.

**Forbidden repetition:** never ask an Actions collector to change `.github/workflows/`; never treat successful verification plus failed publication as a need to recompute.

**Validated replacement:** the archive was ultimately published through an authorized repository write path.

### 2026-07-23 — run 29983731567: a second collector duplicated the same publication architecture

**Intended goal:** use an isolated `collect-v2` workflow to publish the already verified result.

**What actually happened:** download, aggregation, exact verification, and marker creation again succeeded; the final publication step again failed.

**Evidence:** all steps before `Commit verified archive and launch successor` succeeded; that step failed.

**Classification:** repeated publication architecture failure, not a mathematical failure.

**Root cause:** instead of validating one corrected publishing path outside Actions, a second collector workflow was created. Multiple actors and branches were also touching `main`, making publication more fragile.

**Consequences:** a third failed service workflow, a third email, extra branches, diagnostic commits, and unnecessary repository noise.

**Permanent fix:** delete both collector workflows, keep one external publisher, and use a two-commit sequence: verified archive first, successor marker second.

**Forbidden repetition:** do not create `collect-v2`/`collect-v3`; do not retry publication by cloning the same workflow pattern; do not run concurrent publishers.

**Validated replacement:** results were saved in `runs/2026-07-23-b/`; obsolete `collect.yml` and `collect-v2.yml` were removed.

### 2026-07-23 — operational lesson from the three collector emails

**Intended goal:** continue the computational chain automatically with minimal intervention.

**What actually happened:** three separate service workflows failed after the main mathematical run had already succeeded, creating three emails.

**Root cause:** too much failure-handling detail lived in a transient automation prompt while the repository did not yet contain a complete, tested anti-regression record. Each attempted repair introduced another active workflow.

**Permanent fix:** this file is now the canonical failure memory. The hourly automation must read it first and keep only a short portable control loop in its own prompt.

**Forbidden repetition:** do not duplicate incident-specific rules across chat context, automation text, and workflow code. Store durable lessons here and let automation reference them.

## 6. Mandatory startup checklist for any future agent or automation

Before taking any write action:

1. read `AGENTS.md` completely;
2. inspect the newest `runs/` archive and verify its recorded `run_id`;
3. inspect the newest marker and its `parent_run`/`retry_of` relationship;
4. list active workflows and determine which paths trigger each one;
5. find the newest relevant Actions run dynamically;
6. check whether it is queued, running, failed, completed, or already processed;
7. check for existing successor or retry markers;
8. ensure only one publisher and one intended workflow will act;
9. re-read `main` immediately before committing;
10. after committing, verify the resulting commit and created run through the API.

If any of these checks cannot be completed, do not create multiple speculative retries. Preserve the current state, record the uncertainty, and make the smallest reversible correction.