# Third approach 2.0 operating notes

## Purpose

Search for exact or near-exact algebraic certificates that rule out support-restricted Krenn--Gu systems, while preserving several genuinely different candidate basins for later mathematical analysis by GPT Sol.

## Non-negotiable rules

1. Never describe a numerical candidate as a proof.
2. `exact_verified=true` proves only the recorded support-restricted `n=6,d=3` system, not the full conjecture.
3. Never cancel a healthy running GitHub Actions matrix to apply a later improvement.
4. Do not launch Third approach 2.0 while the current Second approach 2.0 run is still active.
5. Second approach 2.0 commits its own results. The web monitoring task only confirms that its archive commit appeared.
6. A new long run must use 20 jobs, four workers per job, `runtime_seconds=21000`, and `max_attempts=0`.
7. Long runs are triggered only by an intentional change to `third-approach-2.0/launch.json`.
8. Preserve raw artifacts and rejected-run diagnostics. A green workflow means technical success, not mathematical success.

## Hourly monitoring cycle

On each hourly wake-up:

1. Inspect the latest repository commits and Actions state.
2. If Second approach 2.0 is still running, leave it untouched and do not launch this approach.
3. If its compute finished, wait for its own collector/archive commit; investigate only if the collector failed or the commit did not appear.
4. If a Third approach 2.0 run is active and healthy, do nothing.
5. If a job failed, inspect the failed job logs and distinguish a technical failure from a normal mathematical non-result. Patch only confirmed defects, preserve completed artifacts, run the same-path smoke test, then relaunch if needed.
6. If a run completed, verify that the collector committed an archive, that `summary.json` is accepted, and that `control.json` advanced exactly once.
7. Compare the global frontier, median score, parent-improvement fraction, distinct lineages, distinct basins, degree distribution, exact candidates and contrast pairs.
8. Choose the next profile from evidence. Follow `recommended_next_profile` unless the detailed metrics give a clear reason not to.
9. Launch the next run by updating only `launch.json`: increment run index, use `control.next_seed`, keep 21,000 seconds and no attempt cap, set the selected profile, and use a unique nonce.
10. Notify the user only for a completed/accepted run, a meaningful record, an exact restricted certificate, a strategy change, or a failure requiring attention.

## Plateau response

A plateau is not a reason to repeat the same search indefinitely. When the collector flags a plateau:

- `balanced` -> `multi_basin` to strengthen several unrelated lineages;
- `multi_basin` -> `degree_expand` to leave the old certificate degree;
- `degree_expand` -> `support_escape` to move to more distant supports;
- `support_escape` -> `contrast_focus` to make small interpretable changes near boundaries;
- `contrast_focus` -> `balanced` with the enlarged bank.

Do not discard the old global best when rotating. Preserve it as an elite, but cap concentration by retaining lineage and basin champions.

## Failure prevention learned from earlier projects

- Use a real end-to-end smoke test, not a different simplified command.
- Compile all Python entry points before the matrix.
- Validate every manifest and required artifact.
- Do not whitelist a tiny set of exit codes as the sole failure classifier.
- Keep `fail-fast: false`; one failed shard must not destroy the other 19.
- Always upload artifacts after failure.
- Leave enough time for graceful worker shutdown, manifest creation and upload.
- Retry Git pushes only after fetching and rebasing; never force-push result archives.
- Record CPU, memory, swap, disk and process-tree snapshots for diagnosis.
