# Second approach 2.0 operating rules

These rules are mandatory for automated ChatGPT tracking and manual maintenance.

## Scientific interpretation

- This track searches numerically for `n=6, d=3` Krenn--Gu counterexample candidates.
- A small residual is not a counterexample. Never report a numerical candidate as a solution without independent high-precision and exact verification of all 729 equations.
- “Old basin” means candidates whose lineage originates in the original `second-approach` bank.
- “Independent candidates” or “new basins” means candidates whose lineage originated in Second approach 2.0 without an old-basin parent. Once such a candidate is inherited and refined, it remains an independent lineage; inheritance does not turn it into an old-basin candidate.
- The main experimental questions are: whether several independent lineages can be developed substantially; whether any becomes competitive with the old basin; and which tactic continues to yield scientifically meaningful progress in each population.

## One-run finite-state machine

1. Read this file, `control.json`, `launch.json` when it exists, recent accepted `summary.json` files, and workflow states before any action.
2. Never launch a second `Second approach 2.0 independent basin search` while one is queued or in progress.
3. Do not alter or cancel a healthy active long run because a new algorithm version was committed. The run must finish on the exact commit that launched it.
4. A completed long run must be collected, verified, committed under `second-approach-2.0/runs/`, recorded in `control.json`, and merged into the compact candidate bank before a successor is launched.
5. The collector archive is authoritative. Accept a run with at least 16 readable job manifests and at least one promoted candidate, even if an isolated tolerable shard makes the GitHub display red.
6. Never repeat an accepted archived run.
7. A successor is launched only by changing `second-approach-2.0/launch.json` once with the exact `next_run_index` and `next_seed` from `control.json`, `runtime_seconds=21000`, `max_attempts=0`, `lane_plan_version=2`, one allowed `legacy_strategy`, one allowed `independent_strategy`, and a new unique nonce.
8. Never launch when `control.json` has `enabled=false`.
9. There is no fixed target-run limit. Scientific value and explicit user instruction determine when to pause.
10. There is no GitHub watchdog and no self-dispatch from the collector. The hourly ChatGPT tracking task is the only successor controller.

## Lane allocation version 2

Long runs use exactly 80 workers:

- 12 `fresh_independent`: new supports and new weights from scratch;
- 8 `obstruction_boundary`: fresh supports near exact obstruction boundaries;
- 8 `novelty_far`: fresh supports deliberately far from the current banks;
- 20 `independent_precision`: continue several strong, structurally distinct independent lineages on the same support;
- 16 `independent_mutation`: continue several independent lineages while cautiously changing their supports;
- 8 `legacy_adaptive`: develop old-basin lineages with the selected run tactic;
- 4 `legacy_escape`: apply a complementary escape tactic to old-basin lineages;
- 4 `legacy_precision`: retain a high-precision old-basin control.

The 36 inherited-independent workers are not allowed to collapse onto one parent. Parent selection must preserve multiple lineage roots and residual basins. The bank must reserve the majority of its capacity for independent candidates while retaining enough old-basin candidates for controls and tactic changes.

Fresh exploration remains mandatory. It is a guardrail against turning the whole search into repeated polishing of a few local minima.

## Allowed tactics

### Old-basin tactics

- `micro_polish`: same support, very small perturbations, high evaluation budget;
- `support_mutation`: inherited weights plus moderate closed-support mutation;
- `wide_restart`: nearby support but restart weights instead of inheriting the local point;
- `bound_expansion`: same support and inherited weights with wider numerical bounds;
- `residual_escape`: stronger support mutation and larger perturbation to leave the current local valley.

### Independent-lineage tactics

- `balanced`: equal emphasis on precise continuation and moderate support mutation;
- `precision_heavy`: more effort on the same or minimally changed supports;
- `mutation_heavy`: more support changes while preserving inherited weights;
- `escape_heavy`: stronger mutations and occasional weight restarts.

## Adaptive tactic selection after each accepted run

The tracking task must compare at least the latest three accepted runs, not just the last number.

For the old basin, inspect:

- global best `max_error` and whether the run set a new global record;
- best scores of `legacy_adaptive`, `legacy_escape`, and `legacy_precision`;
- `legacy_parent_improvement_fraction`;
- concentration among old lineage roots and residual fingerprints.

Keep the current old-basin tactic for one further run when it produces a material new record or a clearly improving parent yield. Change it when any of the following is sustained:

- less than 2% global-frontier improvement across three accepted runs;
- two accepted runs without a new global record;
- falling parent-improvement yield combined with lineage concentration;
- clear evidence that the active tactic only reproduces the same residual pattern.

Do not merely alternate names. Choose a tactic that changes the failed mechanism. Typical transitions are:

- `micro_polish` or `bound_expansion` plateau -> `support_mutation` or `residual_escape`;
- mutation plateau with unstable scores -> `micro_polish`;
- inherited starts trapped at numerical boundaries -> `bound_expansion`;
- all inherited starts return to one valley -> `wide_restart`.

For independent lineages, inspect:

- best fresh independent error;
- best inherited independent error;
- global best independent error across all independent origins;
- `independent_parent_improvement_fraction`;
- number of distinct independent lineage roots;
- the best-independent-lineage table and repeated residual signatures.

Change the independent tactic when inherited lineages improve by less than 2% across three accepted runs, parent-improvement yield falls materially, or one lineage dominates without frontier progress. Prefer:

- `balanced` initially;
- `precision_heavy` when several lineages improve reliably on fixed supports;
- `mutation_heavy` when fixed-support refinement plateaus but parent improvements remain common;
- `escape_heavy` when both precision and moderate mutation reproduce the same residual signatures.

A lineage whose depth is high and whose latest parent gain is nearly zero is deprioritized automatically, not permanently deleted. Retain its best representative for later tactics. New lineages may replace exhausted ones when they are both structurally distinct and competitive.

## What to evaluate after each accepted run

Read and compare:

- global best `max_error` and best score by lane;
- best fresh-independent, inherited-independent, and overall-independent errors;
- the best independent and legacy lineage tables;
- number of distinct support, residual-basin, and independent-lineage fingerprints;
- lane attempt and promotion counts;
- counts and fractions of old-rooted and independent promoted candidates;
- parent-based improvement counts and fractions, separately for old and independent lineages;
- repeated top residual colouring rows across independent candidates;
- whether tactics materially improve, destabilize, or merely reproduce prior candidates;
- whether a candidate survives cleaning and high-effort reoptimization.

A lower global score alone is not enough. Prefer results that are independently reproduced, structurally distinct, stable under perturbation, mathematically interpretable, or useful for later SAT/SMT/exact analysis.

## Failure handling

- Individual shard failures are tolerated and archived; systematic failures must remain visible.
- Dependency installation and Git pushes may use the bounded retries implemented in the workflow.
- If a run is externally cancelled or suffers a transient runner failure and no accepted archive exists, inspect jobs, steps, logs, and artifacts first. Retry failed jobs at most once for that same workflow run; do not create a new run.
- If executable code is wrong, preserve partial artifacts, make the smallest justified repair, and do not launch another long run until `Second approach 2.0 smoke test` succeeds for the latest executable code.
- Do not convert parse errors, missing files, invalid arguments, corrupt artifacts, or repeated worker crashes into a false green status.
- If an accepted archive exists, do not repeat computation merely because the overall GitHub conclusion is red or cancelled.

## Code-change discipline

Method changes are now an intended part of this track, but they must remain controlled:

- prefer selecting an already implemented tactic through `launch.json`;
- do not rewrite executable code merely because one run is noisy;
- add or change executable tactics only when existing tactics cannot address a sustained, evidence-backed plateau or a confirmed technical defect;
- every executable-code or workflow change must pass the smoke test before the next long run;
- record the selected tactic in every manifest, summary, control history, and run README.

## Notification discipline

Notify the user only when:

- a result is accepted and saved;
- a successor run is launched;
- a tactic is changed and why;
- a technical repair is committed;
- a systematic repeated failure is found; or
- an especially strong, independent, stable candidate appears.

When a long run is healthy and nothing significant changed, make no repository change and send no notification.
