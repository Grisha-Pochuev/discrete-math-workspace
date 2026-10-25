# Incident: accepted run did not prepare its successor

Date: 2026-08-05 (Europe/Moscow)

## Confirmed facts

- Fourth approach run `30954702268` completed successfully and its immutable archive was committed as `ea564afa37336bb3e39d3200854b031082a21095`.
- `control.json` advanced to research index `1` and task `stage1_canonicalize_verify`.
- `launch.json` remained enabled for the already accepted research index `0`.
- `watchdog-state.json` remained at the old `compute_dispatch_requested` transition.
- The run-001 specification still declared `draft_not_supported_by_current_runner`.
- No GitHub Actions run was queued or in progress when the incident was diagnosed.

## Root cause

The stage-0 collector updated only `control.json`. It did not atomically replace the consumed launch with a disabled launch for the next research index, and the next scientific task had not yet been implemented. The repository therefore contained mutually inconsistent control-plane files. The watchdog correctly refused to duplicate accepted run 000, but it had no executable run 001 to start.

## Permanent repair

1. Every accepted non-smoke collection now atomically commits:
   - the immutable run archive;
   - advanced `control.json`;
   - a disabled `launch.json` generated from the next specification;
   - reset `watchdog-state.json`.
2. The watchdog repairs any future `control.json` / `launch.json` mismatch before doing anything else.
3. A completed compute for an enabled launch is never recomputed when successor state failed to advance; collection and rescue must be investigated instead.
4. A next specification marked as a draft cannot be launched. Its code, unit tests, real-path smoke, and independent verifier must be implemented first.
5. Run 001 now implements independent exact verification and symmetry canonicalization of the accepted Third approach 2.0 restricted certificates.

## Forbidden recurrence

Never leave `launch.json.enabled=true` for a research index that already has an accepted archive. Never advance only `control.json` after accepted collection. Never treat changing the run number as implementation of a new scientific stage.
