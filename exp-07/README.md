# exp-07

This directory is the canonical root for this compute track.

All problem-specific code, run scripts, specifications, reports, public encryption material, and historical workflow definitions must live under `exp-07/`.

The only intentional exception is `.github/workflows/exp-07.yml`: GitHub requires executable Actions workflow files to live under `.github/workflows/`. That file is only a thin launcher and must not contain scientific logic. It calls scripts from this directory.

## Layout

- `AGENTS.md` — operating and verification guardrails.
- `control.json` — current launch state and latest run metadata.
- `src/` — mathematical/search implementation.
- `run/` — canonical smoke, worker, packaging, and collection scripts.
- `specs/` — run specifications.
- `reports/` — accepted operational/mathematical summaries.
- `history/workflows/` — archived old launch workflows; not executable by GitHub Actions from this location.
- `k0.pub` — public key used to encrypt detailed result artifacts.

The matching private key is deliberately not committed because this repository is public.

## GitHub Actions

Use the single workflow named `exp-07` in the Actions UI. It is manual-only and delegates execution to `exp-07/run/`.

Default long-run parameters are currently:

- 20 GitHub-hosted jobs;
- one native worker per runner (hosted runners were observed as `nproc=1`);
- parameter ceiling 2350;
- up to 19,800 seconds search time per worker;
- smoke must pass before the matrix starts.

Before launching anything large, read `AGENTS.md`, `control.json`, the active spec, and the latest report, and confirm no other large matrix is queued or running.
