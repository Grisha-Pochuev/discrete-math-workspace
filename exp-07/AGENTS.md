# Agent guide

`exp-07/` is the single canonical project root for this track.

All problem-specific implementation, launch scripts, specs, reports, and public key material belong under this directory. Do not create new task-specific files elsewhere in the repository.

The only allowed external file is `.github/workflows/exp-07.yml`, because GitHub requires executable Actions workflow files under `.github/workflows/`. Keep that file as a thin orchestration wrapper; scientific/search logic must remain under `exp-07/`.

Before changing or launching compute, read the local README, control file, active spec, and latest accepted run summary.

- Use exact checks for acceptance.
- Approximate values may rank or prefilter records only.
- Do not infer global conclusions from finite coverage.
- Do not repeat archived searches without a documented reason.
- Independently verify accepted records.
- Preserve explicit shard/coverage information.
- Failed or timed-out shards are missing/partial coverage, not negative results.

Before a large matrix launch, inspect queued and in-progress workflows across the repository. Do not overlap large matrices.

A full run requires committed implementation, self-tests, a successful smoke run, explicit manual launch, and encrypted detail artifacts when the repository is public.

Known audit issue in the current scientific code: `src/w0.cpp` counts exact multiplicative ratio hits but only persists records after the floating near-gap filter. Fix this in a separate scientific-code change before treating a future null run as a strong computational certificate.

Historical launch definitions belong in `exp-07/history/workflows/` and must not be copied back into `.github/workflows/`.
