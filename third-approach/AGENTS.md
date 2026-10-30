# Third-approach operating rules

These rules are mandatory for automated ChatGPT tracking and for manual maintenance.

## Scientific interpretation

- The search produces numerical Nullstellensatz-style certificate candidates for restricted `n=6, d=3` support families.
- A small residual is not a proof. Call a result a proof only after exact coefficient reconstruction and symbolic verification of the complete polynomial identity.

## One-run state machine

1. Never launch a second `Third approach proof search` while one is queued or in progress.
2. A completed run must be collected, verified, committed under `third-approach/runs/`, and recorded in `control.json` before a successor is launched.
3. A successor is launched only by changing `third-approach/launch.json` once. There is no GitHub watchdog and no self-dispatch from the collector.
4. Never launch when `control.json` has `enabled=false` or `completed_runs >= target_runs`.
5. Do not repeat an accepted archived run.

## Adaptive search policy

Every successor launch may set `search_policy` in `launch.json`.

Default after a non-empty bank exists:

- `fresh_fraction = 0.45`
- `elite_mutation_fraction = 0.35`
- `diverse_mutation_fraction = 0.20`

Hard guardrails enforced by code:

- fresh search is never below `0.35`;
- elite-parent mutation is never above `0.45`;
- structurally diverse parent mutation is never below `0.15` while the bank is non-empty;
- an empty or unreadable bank falls back to `fresh_fraction = 1.0` rather than failing the run.

Use recent accepted summaries to adapt within these bounds:

- clear continued improvement: at most `0.40 fresh / 0.40 elite / 0.20 diverse`;
- ordinary progress or insufficient history: `0.45 / 0.35 / 0.20`;
- less than 2% best-score improvement across three accepted runs: `0.60 / 0.20 / 0.20`;
- severe structural collapse or one parent family dominating the saved leaders: `0.65 / 0.15 / 0.20`.

Do not rewrite the algorithm after every run. Change executable code only for a confirmed technical defect or a sustained, evidence-backed search-design problem. Any executable-code change must pass `Third approach smoke test` before another long run is launched.

## Failure handling

- The collector is authoritative. A run is accepted with at least 16 readable job manifests and at least one candidate.
- Individual shard failures are tolerated and archived; systematic failures must remain visible.
- Retry dependency installation and Git pushes as implemented in the workflow.
- If a run is externally cancelled or suffers a transient runner failure and no accepted archive exists, inspect logs and artifacts first. Retry failed jobs at most once for the same workflow run.
- If an accepted archive exists, do not repeat computation merely because the overall GitHub display is red or cancelled.
- Preserve partial artifacts before making any repair.
