# Fifth approach

This directory is the isolated workspace for the next experiment track.

Public documentation here is intentionally operational rather than descriptive. Scientific context should be supplied separately to the agent working on the track.

## Layout

- `control.json` — durable state and launch guardrails.
- `sources.json` — upstream repository locations that may be read but not rewritten.
- `data/` — compact prepared inputs derived from upstream evidence.
- `runs/` — accepted, immutable run archives.
- `reports/` — compact technical/scientific summaries.
- `specs/` — immutable specifications for individual runs.

Executable GitHub Actions workflows remain under `.github/workflows/` and should use a `fifth-approach-` prefix.

## Operating rule

Do not launch a long matrix merely because this directory exists. New execution code must pass static validation and a real-path smoke test first. Full runs are explicitly enabled one at a time.

## Storage rule

Per-job/shard artifacts are temporary transport. Any scientifically unique information must be collected, verified, compressed, checksummed, and preserved in a compact accepted archive under `runs/`. Do not rely on a long-lived Actions artifact as the only copy of a result.
