# Second approach 2.0 — independent-basin counterexample search

This directory is a separate continuation of `second-approach/`. It keeps the same numerical `n=6, d=3` Krenn--Gu counterexample model, but changes the experimental question.

The original second approach found very small numerical residuals, with the best candidates increasingly descended from one preserved seed-bank lineage. Second approach 2.0 tests whether that lineage reflects a genuine route toward a counterexample or only a narrow numerical basin.

## Scientific goal

Produce comparative data for later reasoning by GPT-sol:

- can completely independent supports reach or beat the old record;
- do structurally distant supports converge to the same residual pattern;
- what happens near the exact obstruction boundary discovered by the first approach;
- which mixed colourings remain the largest residuals across unrelated basins;
- whether the old lineage survives higher-effort auditing and perturbation;
- whether several genuinely independent basins produce comparable near-solutions.

A small floating-point residual is not a counterexample. Any promising candidate still requires high-precision reproduction, support simplification, exact reconstruction where possible, and exact verification of all 729 colouring equations.

## Fixed 80-worker lane plan

Each long run uses 20 GitHub Actions jobs and four single-threaded workers per job. The 80 workers are assigned deterministically:

| Lane | Workers | Purpose |
|---|---:|---|
| `fresh_independent` | 30 | Fresh closed supports, never initialized from an old candidate. |
| `obstruction_boundary` | 20 | Supports constructed near exact first-approach obstruction boundaries. |
| `novelty_far` | 16 | Supports selected to maximize structural distance from saved banks. |
| `legacy_control` | 8 | Controlled continuation of the old second-approach lineage. |
| `precision_audit` | 6 | Higher-effort reoptimization and perturbation of strong saved candidates. |

Thus 82.5% of the workers are structurally independent of the legacy lineage, 10% form a direct legacy control, and 7.5% audit promising candidates.

## Execution model

- Long search: 5 hours 50 minutes (`21000` seconds), with an internal reserve for checkpointing and artifact upload.
- No attempt cap in long runs; the deadline is authoritative.
- One long run at a time.
- Matrix shards upload checkpoints even after isolated failure.
- The collector accepts a run with at least 16 readable job manifests and at least one promoted candidate.
- Accepted archives are committed under `second-approach-2.0/runs/`.
- The compact cross-run bank is stored at `second-approach-2.0/candidates/bank.json.gz`.
- `launch.json` is changed only by the external ChatGPT tracking task after the previous run is accepted.
- There is no GitHub watchdog and no collector self-dispatch.

## Files

- `AGENTS.md` — mandatory finite-state operating rules for automated tracking.
- `engine.py` — lane assignment, support generation, parent handling, residual signatures.
- `runner.py` — four checkpointed worker processes per GitHub job.
- `collect.py` — authoritative aggregation, archive creation, bank update, and control-state update.
- `verify_run.py` — offline consistency verification for an archived run.
- `control.json` — durable state; there is intentionally no fixed run-count limit.
- `launch.json` — created or updated only to start exactly one long run.

## Stopping principle

There is no numerical run-count limit. Continuing is controlled by scientific value rather than a counter. The track should be paused when several accepted runs provide no new global record, no new independent basin near the record, no stable cross-basin residual pattern, and no improvement under precision audit—or whenever the user pauses it.
