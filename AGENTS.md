# Repository-level agent guide

This repository contains several distinct computational research tracks for the Krenn–Gu problem plus a reserved area for unrelated experiments.

## Scope

- Do not mix state, archives, control files, or conclusions between approach folders.
- Read the local README / AGENTS / control files inside an approach before changing it.
- `first-approach/` contains the original exact frontier search that historically lived at repository root. Its historical operating memory is now `first-approach/AGENTS.md`.
- Files under `other-experiments/` are not Krenn–Gu evidence unless explicitly documented otherwise.

## Compute safety

Before launching any large GitHub Actions matrix, inspect all queued, pending, waiting, requested, and in-progress runs across every workflow and branch. Do not launch a large matrix on top of another large matrix. Preserve completed artifacts and prefer collection/rescue to recomputation.

A green workflow means the computation ran as specified; it does not by itself prove the Krenn–Gu conjecture or establish a counterexample.

## Workflows

GitHub requires executable Actions workflows to remain in `.github/workflows/`. Their filenames should identify the approach they belong to. Historical First-approach workflow definitions are stored under `first-approach/workflows/legacy/` so repository reorganization cannot accidentally retrigger old frontier computations.
