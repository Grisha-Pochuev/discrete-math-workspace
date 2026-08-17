# Experiment track

Isolated compute workspace.

## Layout

- `AGENTS.md` — operating guardrails.
- `control.json` — launch state.
- `specs/` — run specifications.
- `reports/` — compact run summaries.
- `runs/` — accepted run archives.
- `src/` — implementation.

Executable GitHub Actions workflow files remain under `.github/workflows/`.

## Rule

Full compute stays disabled until implementation and smoke validation are complete. Exact checks decide acceptance; finite null results must not be overinterpreted.
