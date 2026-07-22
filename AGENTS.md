# Agent Operations Guide

This file is the persistent operating memory for automated work in this repository.
Read it before changing the search, launching GitHub Actions, collecting results, or choosing the next computational frontier.

## 1. Purpose

Use this repository as a reproducible computational research workspace.
The main objectives are:

- preserve every completed search result;
- avoid repeating closed search regions;
- use GitHub-hosted CPU capacity efficiently;
- prevent memory, disk, and workflow failures;
- distinguish mathematical outcomes from infrastructure failures;
- continue the search through one successor run at a time.

Keep public-facing wording neutral. Do not add unnecessary problem names, bounty details, or explanatory material that makes the repository easier to discover through search engines.

## 2. Sources of truth

Before doing new work, inspect these in order:

1. `AGENTS.md`;
2. the newest dated directory under `runs/`;
3. summaries, manifests, checksums, and verification scripts in that directory;
4. the newest marker under `.runs/`;
5. `.github/workflows/run.yml`;
6. `batch.py` and `search.cpp`;
7. the newest GitHub Actions `batch` run.

Never infer the current frontier from an old chat description when repository data is available.

## 3. GitHub-hosted runner model

Assume only the following safe baseline for each standard public Linux runner:

- 4 virtual CPU cores;
- about 16 GB RAM, normally about 15.6 GiB visible;
- about 14 GB usable disk;
- maximum job duration of 6 hours;
- processor model may vary between AMD EPYC and Intel Xeon;
- up to 20 jobs may run concurrently for this account class.

The normal full-run target is therefore:

- 20 matrix jobs;
- 4 local workers per job;
- up to 80 virtual CPU cores in total;
- `runtime_seconds = 21000` per job, equal to 5 h 50 min of useful computation;
- `timeout-minutes = 360`, leaving time for shutdown and artifact upload.

Do not tune the algorithm for a specific CPU model. Record the actual model in every artifact.

## 4. Memory and disk safety

The objective is full CPU use without swap or runner termination, not maximum RAM occupation.

Per runner:

- preferred combined resident memory: at most 10–11 GiB;
- warning threshold: about 11.5 GiB combined RSS;
- keep `MemAvailable` above about 2.5 GiB;
- avoid sustained swap use;
- treat swap use above about 1 GiB as dangerous;
- stop or reduce the largest worker after repeated dangerous readings;
- reserve several GiB for the operating system, file cache, Python driver, compiler, and artifact packaging.

Monitor the full process tree, not only the parent process.

Always record:

- `uname -a`;
- `nproc`;
- `lscpu`;
- `free -h`;
- `swapon --show`;
- `df -h`;
- `ulimit -a`;
- relevant lines from `/proc/meminfo`;
- peak combined RSS;
- minimum `MemAvailable`;
- maximum swap use.

Avoid tens of thousands of individual artifact files. Store compact `records.jsonl`, manifests, summaries, and only logs needed for diagnosing failures.

## 5. Required launch architecture

### No central validation dependency

Do not create a single `validate` job that all matrix jobs depend on.
A hosted-runner allocation failure in that one job can cancel the entire computation before any worker starts.

Each matrix job must instead perform its own short preflight:

1. checkout;
2. record system information;
3. compile;
4. run a very small exact smoke test;
5. verify the task queue with `batch.py --dry-run`;
6. start its assigned computation;
7. upload artifacts with `if: always()`.

A failure to allocate one runner must not destroy the other 19 jobs.

### One active workflow

Keep one active computational workflow, currently `.github/workflows/run.yml`.
Do not leave many legacy workflow files triggered by the same push. Multiple workflows can cause duplicate computation and large volumes of failure emails.

Start a new full run by creating one unique marker in `.runs/`.
Do not modify unrelated files merely to trigger a run.

## 6. Marker format and duplicate prevention

Every new marker should contain enough information to reconstruct the chain, for example:

```text
parent_run=<previous successful run id>
stage=<stage name>
runtime_seconds=21000
max_seen=<state-table limit>
jobs=20
workers_per_job=4
frontier=<short neutral description>
```

For infrastructure retries, add:

```text
retry_of=<failed run id>
retry_attempt=<integer>
reason=<confirmed infrastructure reason>
```

Before creating a marker, check that no matching successor or retry is already queued, running, or recorded.
Never create two successors for the same parent run.

## 7. Failure classification

A red or cancelled GitHub status is not automatically a mathematical or program failure.
Classify it using job steps, annotations, runner assignment, billable duration, logs, resource data, and artifacts.

### A. Hosted runner was not acquired

Confirmed indicators include:

- zero executed steps;
- empty `runner_name` or runner id 0;
- zero billable compute duration;
- no artifacts;
- annotation similar to:
  `The job was not acquired by Runner of type hosted even after multiple attempts`.

Action:

- classify as GitHub infrastructure failure;
- do not record it as a search result;
- do not advance to a new mathematical frontier;
- retry the same frontier once;
- prefer rerunning only failed or cancelled matrix jobs when successful jobs exist;
- if the whole run never started, create one retry marker with `retry_of` and the same parameters;
- never create a retry when one is already queued or running.

### B. Partial runner allocation failure

If some matrix jobs completed and others never obtained runners:

- preserve all successful artifacts;
- identify exactly which job ids are missing;
- rerun only missing or infrastructure-cancelled jobs;
- do not repeat successful search portions;
- do not advance the frontier until the run is reconstructed or the missing portions are explicitly tracked as pending.

### C. Normal bounded-search outcomes

The following are normally valid technical outcomes, not workflow failures:

- `complete`;
- `capacity`;
- `timeout`;
- `stopped` after controlled shutdown;
- controlled memory guard;
- no new support found.

Store and analyze them. A green workflow only means technical success, not that the mathematical problem is solved.

### D. Real technical failures

Treat these as actionable failures:

- compile error;
- invalid option;
- malformed input;
- missing required source data;
- missing mandatory manifest or records file;
- segmentation fault or assertion failure;
- unexplained nonzero exit after computation begins;
- OOM or sustained swap;
- disk exhaustion;
- corrupt artifact.

Fix the confirmed cause, run a short end-to-end test, then retry the same frontier once.

Do not hide real errors with unconditional `exit 0`.

## 8. Result collection

After a technically completed run:

1. download all available artifacts;
2. verify artifact count and checksums;
3. combine manifests and `records.jsonl`;
4. identify missing job ids;
5. classify every task as complete, capacity, timeout, stopped, memory, or technical failure;
6. aggregate nodes, states, engine seconds, supports, and resource peaks;
7. verify every newly found support exactly;
8. write a concise machine-readable summary;
9. save raw artifacts, checksums, summary, verification script, and frontier notes in a new dated `runs/` directory;
10. commit the result to `main` before launching the successor.

Recommended directory shape:

```text
runs/YYYY-MM-DD-short-name/
  README.md
  summary.json
  checksums.sha256
  verify.py
  raw/
```

Never claim a layer is closed when any shard is missing, capacity-limited, timed out, corrupt, or technically unverified.

## 9. Choosing the next frontier

Use this priority order:

1. missing or infrastructure-failed jobs;
2. capacity-limited or timed-out pieces from the current frontier;
3. deeper subdivision of only unresolved pieces;
4. the next support-size layer;
5. a stronger search invariant or exact obstruction test when repeated subdivision becomes inefficient.

Do not repeat complete shards.
When refining a parent shard, preserve a mathematically exact relation between parent and child shard indices so completed siblings remain excluded.

Keep reserve tasks after the main queue so CPU cores do not become idle if the primary frontier completes early.

## 10. Continuous-run protocol

The monitoring process should check the newest `batch` run hourly.

- If queued or running: do nothing.
- If it failed before obtaining runners: retry the same frontier according to Section 7.
- If only some jobs failed to obtain runners: preserve successes and rerun only the missing jobs.
- If it failed after computation began: diagnose and repair before retrying the same frontier.
- If it completed technically: collect, verify, commit, select the next frontier, and launch exactly one successor full run.

The monitor must use the newest run dynamically. It must never be permanently tied to one run id.

## 11. Notification hygiene

To avoid large volumes of GitHub email:

- maintain one active workflow instead of many legacy workflows;
- use one matrix run rather than separate workflows for each shard;
- keep normal bounded-search outcomes green;
- reserve red status for genuine technical failures;
- do not create repeated marker commits while a run is queued or active.

Do not disable security, access, recovery, or account-change notifications merely to silence workflow mail.

## 12. Incident log

### 2026-07-23 — run 29959775981

Observed:

- the central `validate` job waited about 15 minutes;
- no runner was assigned;
- no workflow step executed;
- billable compute time was zero;
- the matrix job was skipped because it depended on `validate`;
- GitHub annotation: `The job was not acquired by Runner of type hosted even after multiple attempts`.

Classification:

- GitHub-hosted runner allocation failure;
- no computation took place;
- no mathematical result was produced.

Permanent fix:

- removed the central `validate` dependency;
- changed the workflow to 20 independent matrix jobs;
- each job performs its own preflight before computation;
- switched runner label to `ubuntu-latest` to avoid unnecessary image-specific allocation pressure;
- retry launched as run 29960969740.

Do not reintroduce a central validation bottleneck.

## 13. Current operational state

At the time this file was created:

- active retry run: `29960969740`;
- frontier stage: `frontier2`;
- useful runtime: `21000` seconds;
- matrix: 20 jobs;
- workers per job: 4;
- the independent preflight steps were passing and computation had started on assigned runners.

Always replace this understanding with newer repository and Actions data when available.
