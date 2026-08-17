# Experiment agent guide

## Scope

Keep this track isolated from other repository work.

Before changing or launching compute, read the local README, control file, active spec, and latest accepted run summary.

## Guardrails

- Acceptance conditions use exact arithmetic.
- Approximate values may rank candidates only.
- Do not infer a global conclusion from finite coverage.
- Do not repeat archived searches without a documented reason.
- Independently verify every accepted candidate.

## Compute safety

Before a large matrix launch, inspect all queued and in-progress workflows in the repository. Do not overlap large matrices.

A full run requires committed implementation, exact self-tests, a successful smoke run, explicit enablement in `control.json`, and manual launch.

## Artifacts

Preserve compact checksummed coverage and candidate records. Failed shards must be reported as missing coverage, not as negative results.
