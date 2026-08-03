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
9. A profile recommended by `collect.py` must be accepted by the compute workflow and exercised by the independent smoke workflow before it is written to `launch.json`.
10. After changing execution code or workflow logic, do not launch a long matrix until `Third approach 2.0 smoke test` succeeds on the exact commit containing the fix.

## Hourly monitoring cycle

On each hourly wake-up:

1. Inspect all queued, pending and in-progress repository Actions runs across every workflow and branch.
2. If Second approach 2.0 is still running, leave it untouched and do not launch this approach.
3. If its compute finished, wait for its own collector/archive commit; investigate only if the collector failed or the commit did not appear.
4. If a Third approach 2.0 compute, rescue or smoke run is active and healthy, do nothing and do not create a duplicate.
5. If a job failed, inspect the failed job logs and distinguish a technical failure from a normal mathematical non-result. Patch only confirmed defects and preserve completed artifacts.
6. If execution code or workflow logic changed, require a successful independent same-path smoke run before changing `launch.json` or `rescue.json`.
7. After a fix passes smoke, trigger exactly one appropriate transition with a new nonce and confirm through the Actions API that the new run actually appeared and passed its prepare stage.
8. If a run completed, verify that the collector committed an archive, that `summary.json` is accepted, and that `control.json` advanced exactly once.
9. Compare the global frontier, median score, parent-improvement fraction, distinct lineages, distinct basins, degree distribution, exact candidates and contrast pairs.
10. Choose the next profile from evidence. Follow `recommended_next_profile` only after compatibility and smoke validation.
11. Launch the next run by updating only `launch.json`: use `control.next_run_index` and `control.next_seed`, keep 21,000 seconds and no attempt cap, set the selected profile, and use a unique nonce.
12. Notify the user only for a completed/accepted run, a meaningful record, an exact restricted certificate, a strategy change, a confirmed fix, or a failure requiring attention.

## Plateau response

A plateau is not a reason to repeat the same search indefinitely. When the collector flags a plateau:

- `balanced` -> `multi_basin` to strengthen several unrelated lineages;
- `multi_basin` -> `degree_expand` to leave the old certificate degree;
- `degree_expand` -> `support_escape` to move to more distant supports;
- `support_escape` -> `contrast_focus` to make small interpretable changes near boundaries;
- `contrast_focus` -> `balanced` with the enlarged bank.

When exact restricted certificates are abundant, `exact_reconstruction` is permitted as a focused profile. It must retain at least 15% fresh search and must never be interpreted as a proof of the full conjecture.

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
- Use sparse checkout for preparation, validation, compute and collection; this repository is large enough that a full checkout can consume most of a short-stage timeout.
- Do not duplicate profile allow-lists without checking their compatibility. The failure of run `30858625970` was caused by `collect.py` recommending `exact_reconstruction` while the workflow rejected that profile before smoke or compute began.
- A completed rescue must be disabled after its archive is accepted so an old source run is not accidentally rescued again.
