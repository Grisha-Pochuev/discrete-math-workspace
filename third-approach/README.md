# Third approach: proof-oriented numerical certificates

This directory contains the third computational approach to the Krenn--Gu problem.

Unlike `second-approach/`, which searches numerically for counterexamples, this approach searches for low-degree algebraic infeasibility certificates. For the initial frontier (`n=6`, `d=3`) it samples restricted support families and numerically fits affine Nullstellensatz-style identities

```text
1 ~= sum_i q_i(x) F_i(x),
```

where the `F_i` are GHZ polynomial equations and the `q_i` are affine holomorphic multipliers.

A small numerical residual is only a lead. It becomes a proof only after exact coefficient reconstruction and symbolic verification of the polynomial identity. Results in this directory must never be described as a proof solely because the numerical error is small.

## Execution model

- 20 GitHub Actions jobs run in parallel.
- Each job uses four independent Python processes.
- The workflow budget is 21,000 seconds (5 h 50 min).
- The numerical workers stop about eight minutes early so artifacts can be validated, uploaded, aggregated, and committed safely.
- Raw artifacts are retained by GitHub for 14 days.
- Compact summaries and the best numerical certificate candidates are committed under `third-approach/runs/`.
- There is no GitHub watchdog and no self-dispatching collector. The single workflow computes, collects, verifies, and commits its own run. ChatGPT scheduled tracking decides whether to launch the next run.

## Files

- `certificate.py` -- GHZ polynomial evaluation and numerical certificate fitting.
- `runner.py` -- checkpointed four-process worker driver.
- `collect.py` -- aggregation and compact archival.
- `control.json` -- accepted-run state and next-run parameters.
- `launch.json` -- changing this file launches exactly one new workflow run.
- `candidates/bank.json.gz` -- best certificate leads accumulated across accepted runs.
- `runs/` -- committed run summaries.

## Scientific scope

The first implementation studies restricted support families for `n=6`, `d=3`. Closing those families is useful evidence and may expose an exact algebraic obstruction, but it does not by itself prove the full conjecture for all even `n >= 6` and all `d >= 3`.
