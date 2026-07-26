# Second-approach operations

This research track is designed to run as an automatic chain of approximately six-hour GitHub Actions experiments.

## Workflows

- `Second approach compute` runs 20 GitHub-hosted machines with four independent numerical workers per machine.
- `Second approach collect` runs after every compute workflow, downloads every available artifact, preserves partial checkpoints, verifies the archive, commits it under `second-approach/runs/`, updates the evolutionary seed bank, and dispatches the next compute run.
- `Second approach watchdog` runs hourly. It leaves an active chain alone, recovers a completed run whose collector did not archive it, or dispatches the next compute run if the chain stopped after a verified commit.

## Failure policy

A red compute workflow is not automatically treated as lost research.

1. Every worker appends one durable JSON record after each attempt.
2. Every worker maintains a small set of its best complete weight vectors.
3. The matrix uses `fail-fast: false`.
4. Artifact upload uses `if: always()`.
5. The collector accepts a run when at least 16 of 20 job manifests and at least one numerical attempt are present.
6. A smaller partial run is still archived, but it does not advance the accepted-run index; the same index is retried with a slightly changed deterministic seed.
7. Attempt streams are split into compressed parts so no single GitHub blob approaches the 100 MB limit.

## Automatic stopping

Edit `second-approach/control.json`:

- set `enabled` to `false` to stop new dispatches;
- change `target_runs` to alter the number of accepted runs;
- do not decrease `next_run_index` unless intentionally repeating an accepted experiment.

The default target is 30 accepted runs. Failed or severely incomplete attempts do not count toward this target.

## Scientific interpretation

The numerical search deliberately targets dense supports and direct complex-weight fitting. It is adversarial to the three sparse-support certificates, but it does not assume that evading those certificates implies a solution. Numerical near-solutions are evidence for follow-up, not proofs or counterexamples, until independently reconstructed and checked exactly.
