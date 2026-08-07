# Repository-level agent guide

This repository contains several distinct computational research tracks plus a reserved area for unrelated experiments.

## Scope

- Do not mix state, archives, control files, or conclusions between approach folders.
- Read the local README / AGENTS / control files inside an approach before changing it.
- `first-approach/` contains the original exact frontier infrastructure that historically lived at repository root. Its detailed historical operating memory is `first-approach/AGENTS.md`.
- Files under `other-experiments/` are outside the main experiment sequence unless explicitly documented otherwise.

## Compute safety

Before launching any large GitHub Actions matrix, inspect all queued, pending, waiting, requested, and in-progress runs across every workflow and branch. Do not launch a large matrix on top of another large matrix. Preserve completed artifacts and prefer collection or rescue to recomputation.

A green workflow means only that the requested computation ran as specified. Interpret scientific significance separately from technical execution status.

## Workflows

GitHub requires executable Actions workflows to remain in `.github/workflows/`. Their filenames should identify the approach they belong to. Historical First-approach workflow definitions are stored under `first-approach/workflows/legacy/` so repository reorganization cannot accidentally retrigger old computations.
