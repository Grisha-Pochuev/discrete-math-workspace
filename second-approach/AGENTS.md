# Second-approach agent instructions

Before changing or restarting this track, read:

1. `second-approach/README.md`;
2. `second-approach/plans/INITIAL_PLAN.md`;
3. `second-approach/OPERATIONS.md`;
4. `second-approach/control.json`;
5. the most recent `second-approach/runs/*/summary.json`.

Rules:

- Keep all second-approach results inside `second-approach/`.
- Do not mix sparse-frontier counts with direct nonlinear-search metrics.
- Preserve partial artifacts before repairing a red workflow.
- Never delete an unsuccessful run; mark whether it was accepted and why.
- Do not report a small residual as an exact counterexample.
- Promote candidates using complete residual profiles and normalized complex weights.
- Prefer minimal, verified workflow fixes. Validate Python syntax, a short numerical preflight, archive checksums, and successor-dispatch logic before launching a long run.
- The GitHub-native collector and watchdog are the primary automatic chain. The external hourly ChatGPT watcher is a supervisory backup, not the sole scheduler.
