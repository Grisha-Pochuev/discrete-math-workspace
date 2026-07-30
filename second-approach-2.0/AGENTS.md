# Second approach 2.0 operating rules

These rules are mandatory for automated ChatGPT tracking and manual maintenance.

## Scientific interpretation

- This track searches numerically for `n=6, d=3` Krenn--Gu counterexample candidates.
- A small residual is not a counterexample. Never report a numerical candidate as a solution without independent high-precision and exact verification of all equations.
- The main experimental question is whether strong candidates arise in multiple independent structural basins or only in the old second-approach lineage.

## One-run finite-state machine

1. Read this file, `control.json`, `launch.json` when it exists, recent accepted `summary.json` files, and the workflow states before any action.
2. Never launch a second `Second approach 2.0 independent basin search` while one is queued or in progress.
3. A completed long run must be collected, verified, committed under `second-approach-2.0/runs/`, recorded in `control.json`, and merged into the compact candidate bank before a successor is launched.
4. The collector archive is authoritative. Accept a run with at least 16 readable job manifests and at least one promoted candidate, even if an isolated tolerable shard makes the GitHub display red.
5. Never repeat an accepted archived run.
6. A successor is launched only by creating or changing `second-approach-2.0/launch.json` once with the exact `next_run_index` and `next_seed` from `control.json`, `runtime_seconds=21000`, `max_attempts=0`, and a new unique nonce.
7. Never launch when `control.json` has `enabled=false`.
8. There is no fixed target-run limit. Scientific value and explicit user instruction determine when to pause.
9. There is no GitHub watchdog and no self-dispatch from the collector.

## Fixed lane allocation

Long runs use exactly 80 workers:

- global workers 0–29: `fresh_independent`;
- global workers 30–49: `obstruction_boundary`;
- global workers 50–65: `novelty_far`;
- global workers 66–73: `legacy_control`;
- global workers 74–79: `precision_audit`.

Do not silently increase legacy exploitation. At least 66 of 80 workers must remain independent of the old lineage unless a multi-run, evidence-backed design change is explicitly committed and smoke-tested.

## What to evaluate after each accepted run

Read and compare:

- global best `max_error` and best score by lane;
- best independent score excluding `legacy_control` and legacy-rooted audits;
- number of distinct support fingerprints and residual-basin fingerprints;
- lane attempt and promotion counts;
- count and fraction of promoted candidates rooted in the old bank;
- parent-based improvement counts;
- repeated top residual colouring rows across independent candidates;
- whether precision auditing materially improves or destabilizes old records;
- whether a new candidate survives cleaning and high-effort reoptimization.

A lower global score alone is not enough. Prefer results that are independently reproduced, structurally distinct, stable under perturbation, or mathematically interpretable.

## Failure handling

- Individual shard failures are tolerated and archived; systematic failures must remain visible.
- Dependency installation and Git pushes may use the bounded retries implemented in the workflow.
- If a run is externally cancelled or suffers a transient runner failure and no accepted archive exists, inspect jobs, steps, logs, and artifacts first. Retry failed jobs at most once for that same workflow run; do not create a new run.
- If executable code is wrong, preserve partial artifacts, make the smallest justified repair, and do not launch another long run until `Second approach 2.0 smoke test` succeeds for the latest executable code.
- Do not convert parse errors, missing files, invalid arguments, corrupt artifacts, or repeated worker crashes into a false green status.
- If an accepted archive exists, do not repeat computation merely because the overall GitHub conclusion is red or cancelled.

## Code-change discipline

Do not rewrite the algorithm after every run. Change executable code only for:

- a confirmed technical defect; or
- a sustained, evidence-backed design problem visible across several accepted runs.

Every executable-code or workflow change must pass the smoke test before the next long run.

## Notification discipline

Notify the user only when:

- a result is accepted and saved;
- a successor run is launched;
- a technical repair is committed;
- a systematic repeated failure is found; or
- an especially strong, independent, stable candidate appears.

When a long run is healthy and nothing significant changed, make no repository change and send no notification.
