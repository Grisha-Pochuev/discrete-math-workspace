# Run 005 final-status incident

Run `31034878944` was shown by GitHub Actions as `cancelled`, but its mathematical result was preserved and accepted.

Confirmed facts:

- all 80 worker checkpoints were present in the collector input;
- the collector produced and committed `fourth-approach/runs/run-005-31034878944`;
- the committed summary has `accepted: true`, full coverage of 1300 candidates, and zero worker errors;
- the overall cancellation marker came from compute jobs reaching the six-hour job boundary after slow bank checkout; at least one job uploaded its checkpoint before the final validation step was skipped.

Run 006 prevents recurrence by reading the two large numerical banks once in a preparation job, packaging only 60 selected candidates, and giving the 15 long compute jobs a compact artifact. Its internal runtime is 20,400 seconds, leaving setup and upload reserve inside GitHub's six-hour job limit.
