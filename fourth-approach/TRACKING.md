# Hourly tracking contract for Fourth approach

This file is the operational contract for the scheduled ChatGPT task named `Fourth Approach Tracking`.

## Purpose

Advance the Fourth approach one safe, evidence-based transition at a time so that its outputs become compact, exact, contrastive material for GPT-5.6 Sol.

## Mandatory order on every activation

1. Read `fourth-approach/AGENTS.md`, `ROADMAP.md`, `control.json`, `launch.json`, `watchdog-state.json`, and the active run specification.
2. Inspect every GitHub Actions run with `queued`, `pending`, `waiting`, `requested`, or `in_progress` status across all branches and workflows.
3. Treat another large matrix as using the same account concurrency allowance. Never launch a 20-job matrix while another large matrix is active or queued.
4. Inspect the latest Fourth approach smoke, compute, collection, and rescue outcomes and the latest relevant commits.
5. Perform no more than one meaningful transition per activation.

## Healthy active computation

If a healthy smoke, compute, collection, or rescue run is queued or active:

- do not cancel it;
- do not edit its launch configuration;
- do not create a duplicate run;
- do not start a successor;
- record or report the status only when meaningful.

## Before any full run

A full run may be launched only when all conditions hold:

- no conflicting large workflow is active or queued;
- the run index equals `control.json.next_run_index`;
- the specification exists and passes validation;
- the real-path smoke workflow passed on the current execution code;
- `control.json.smoke_required` is false or the verified code SHA matches the code to be launched;
- the previous accepted run, if any, has a committed immutable archive;
- launch is not a duplicate of an existing run ID, run index, nonce, or source SHA;
- the launch answers one stated scientific question.

To launch, update only `fourth-approach/launch.json` with `enabled=true` and a unique nonce. Do not edit another approach's launch file.

## Failure handling

Distinguish:

- controlled mathematical or scientific non-result;
- technical failure before useful computation;
- technical failure after useful artifacts were produced;
- collection or push failure after computation completed.

On technical failure:

1. inspect job steps and logs;
2. preserve all available artifacts;
3. identify a confirmed defect rather than guessing;
4. fix the smallest confirmed cause;
5. run the real-path smoke test on the corrected code;
6. relaunch the same run index only after smoke passes and only with a new nonce;
7. never advance the scientific stage after a rejected run.

If computation completed but collection failed, prefer the rescue collector. Do not recompute merely to obtain the same artifacts again.

## After an accepted run

- verify that the archive commit exists;
- independently reproduce the summary from immutable artifacts;
- compare the primary scientific metrics with the registered criteria;
- update `control.json` and `watchdog-state.json`;
- prepare the next specification disabled;
- launch the next run only if its code path is implemented, smoked, scientifically justified, and no stopping rule applies.

Do not continue merely because a floating-point residual improved.

## Notifications

Notify the user only for:

- accepted scientific results;
- a technical failure requiring intervention or a code repair;
- a rescue collection;
- a stage transition;
- a stopping or pivot decision;
- inability to read or write the repository.

Do not send hourly messages when nothing meaningful changed.
