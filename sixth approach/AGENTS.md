# Sixth approach operating rules

This directory is an isolated computational track. Do not import mutable state
from earlier tracks and do not edit their accepted archives.

Public names, logs, workflow titles, artifact names, and commit messages must
remain neutral. Mathematical motivation belongs only in the private analysis
tree, not in this repository.

## Required run discipline

- `control.json` is the only mutable run-control record.
- Every run is specified by an immutable JSON file under `specs/`.
- Heavy work is C++20. Python is permitted only for validation and collection.
- A smoke run must compile and execute the same worker binary and output path as
  a full run.
- GitHub Actions full runs are manual `workflow_dispatch` jobs only. Never add
  an ordinary branch `push` trigger.
- CircleCI full runs use one immutable, neutral, exact-match tag declared in
  the run specification. Ordinary commits and unrelated tags must run no jobs.
- Use exactly four independent single-threaded workers per 4-vCPU compute job
  on either provider.
- GitHub Actions owns long jobs and cross-run artifact audits. CircleCI owns
  sub-hour fine shards and must reserve time for exact per-shard validation.
- Worker output is checkpointed atomically and is collected with `if: always()`.
- The collector must reject missing/duplicate shards and incomplete exact
  coverage. Scientific counterexamples are data, not technical failures.
- Before a large run, inspect all queued, pending, waiting, requested, and
  in-progress Actions jobs on every branch and workflow.
- Never run an individual local computation for more than 15 minutes.

## Archive contract

An accepted archive contains the immutable spec, a machine-generated summary,
scientifically unique compact records, provenance, and SHA-256 checksums.
Acceptance means only that the declared computation was technically complete.

For matrix runs with a strict collector, automatically commit only the compact
accepted archive under `runs/`. Raw shards and full merged layers remain
temporary transport artifacts. Preserve all compact exceptional samples,
provenance, the immutable spec, the accepted summary, and SHA-256 checksums.
No committed blob may reach 95 MiB and no automatic archive may reach 100 MiB.
Collectors must retry a conflicting push by fetching and rebasing on `main`;
they must never force-push.

CircleCI raw shards are temporary within a pipeline. Each complete shard is
audited before its raw payload is discarded; any scientific survivor retains
its source shard. Only a strict compact provider archive may later enter
`runs/` after independent intake.

