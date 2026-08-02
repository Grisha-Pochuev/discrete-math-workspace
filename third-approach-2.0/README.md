# Third approach 2.0

Proof-oriented, multi-basin computational search for the Krenn--Gu conjecture.

This approach develops several independent families of candidate algebraic certificates instead of repeatedly polishing one numerical basin. It works with the support-restricted `n=6, d=3` polynomial system and searches identities

```text
1 = sum_j c_j m_j F_j
```

in polynomial coefficient space. Here `F_j` are selected GHZ equations and `m_j` are multiplier monomials of degree 0--3. A verified exact identity proves impossibility only for the recorded restricted support; numerical scores are research leads, not proofs of the full conjecture.

## What is new relative to Third approach 1.0

- coefficient-space residuals instead of validation on random evaluation points;
- affine, quadratic and cubic multiplier families;
- separate candidate lineages and basin fingerprints;
- global elites are retained without discarding lineage and basin champions;
- six search lanes: fresh, elite refinement, basin refinement, degree expansion, support escape and contrast-focused mutation;
- contrast pairs record what changed between a parent and child;
- plateau detection recommends a different strategy profile;
- rational reconstruction and exact coefficient verification are attempted automatically for near-zero candidates.

## Compute layout

A full run uses 20 GitHub Actions jobs. Each job starts four independent worker processes, giving up to 80 busy virtual CPU cores. The requested runtime is 21,000 seconds (5 h 50 min); the runner reserves three minutes for orderly shutdown and manifest creation. Results are checkpointed, uploaded even after failures, aggregated, verified and committed by GitHub Actions.

## Safety model

The workflow has a separate configuration gate and a real-path smoke test before the 20-job matrix. It uses `fail-fast: false`, does not cancel an existing run, records machine and resource information, uploads artifacts with `if: always()`, accepts a run only with at least 16 complete jobs and at most 5% worker-level errors, and retries pushes after rebasing.

The initial `launch.json` is disabled. Creating this folder does not start a run. The first large run is started only by changing `enabled` to `true`, setting a fresh nonce and committing `launch.json` after the current Second approach 2.0 run has finished and committed its own archive.

## Strategy profiles

The available profiles are:

- `balanced`;
- `multi_basin`;
- `degree_expand`;
- `support_escape`;
- `contrast_focus`.

The collector records `recommended_next_profile`. If a run does not improve the global record, or the best gain across three runs is below 2%, the recommendation rotates to another profile. The hourly ChatGPT monitoring task reviews the evidence before launching the next run; it must not interrupt a healthy running matrix.
