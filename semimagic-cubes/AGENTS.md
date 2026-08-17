# Semimagic-cubes agent guide

## Scope

This directory is a separate research track. Do not mix its state, run archives, or conclusions with the older `first-approach` through `sixth approach` tracks.

Before editing or launching compute, read:

1. this file;
2. `README.md`;
3. `control.json`;
4. the active file under `specs/`;
5. the latest accepted report under `reports/`, when present.

## Scientific guardrails

- Exact arithmetic decides all equalities.
- Floating point may only rank near misses.
- A finite negative search is not a proof that the original problem has no solution.
- Do not repeat the already completed general base search through 50,000 merely with a nearby bound.
- Do not repeat the two Morgenstern searches through 50,000 as if they covered the general problem.
- Do not repeat the old Euler four-cycle search through parameter limit 400 without a new mathematical reason.
- The additive-base class, affine-rank-one class, simultaneous first/third-power semimagic class, and the two homogeneous orientations of the special one-parameter Euler family are already excluded by proofs; do not reopen them without identifying an error in those proofs.
- Any solution candidate must be independently reconstructed from the original equations and checked for positivity, pairwise distinctness, and all six equal sums.

## Compute safety

Before a large GitHub Actions launch, inspect all queued, pending, waiting, requested, and in-progress workflows in the repository. Never launch this 20-job matrix on top of another large matrix.

A full run requires:

- implementation committed under `semimagic-cubes/src/`;
- exact branch-generation/certificate tests;
- a successful real-path smoke run;
- `control.json` explicitly enabled for that run;
- manual launch only.

## Artifact policy

Per-job artifacts are transport only. The collector must preserve compact, checksummed summaries under `semimagic-cubes/runs/`, including exact coverage, source SHA, branch identifiers, completed denominator blocks, candidate records, and technical failures. Never infer scientific absence from missing or failed shards.
