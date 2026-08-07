# Fourth approach agent instructions

These instructions are authoritative for work under `fourth-approach/`. They intentionally describe only the workflow and evidence handling, not the subject of the experiment.

## Mission

Prepare compact, exact, contrastive evidence from the earlier approach archives. Optimize for new structural information, not attempt volume, file count, or a smaller numerical score by itself.

## Repository is the source of truth

Read `README.md`, `ROADMAP.md`, `TRACKING.md`, `control.json`, `launch.json`, `watchdog-state.json`, and the active run specification before acting. Do not reconstruct state from chat memory when repository records are available.

Accepted run directories are immutable. Reference upstream approach data by commit and path; do not edit accepted archives in place.

## Non-interference and concurrency

Before any action inspect all GitHub Actions runs with `queued`, `pending`, `waiting`, `requested`, or `in_progress` status across every branch and workflow.

Never cancel, modify, supersede, or duplicate a healthy run. Do not launch a new large matrix while another large matrix is active or queued. Never edit another approach's launch file as part of this track.

## One activation, one transition

A managed activation may perform at most one meaningful transition:

- inspect and report a meaningful status change;
- repair one confirmed technical defect;
- run or trigger one smoke validation;
- rescue one completed artifact set;
- enable one registered run;
- accept and advance one completed stage;
- stop or pivot one stalled family.

A full run may be enabled only when:

1. its run index equals `control.json.next_run_index`;
2. its immutable run specification exists;
3. it answers one registered research question;
4. the real-path smoke workflow passed for current execution code;
5. no conflicting large run is active or queued;
6. the previous accepted run has a committed immutable archive;
7. the run index, nonce, source SHA, and artifact set are not duplicates;
8. all input schemas and source commit requirements validate.

## Required execution sequence

```text
static validation
-> unit tests
-> real-path smoke
-> inspect smoke artifacts
-> full run
-> always-upload artifacts
-> collection
-> independent verification
-> immutable commit
```

A long run must never be the first test of new code.

## Failure handling

Preserve partial artifacts. If computation completed but collection failed, use rescue rather than recomputation.

On technical failure:

1. inspect steps and logs;
2. preserve available artifacts;
3. identify a confirmed cause;
4. apply the smallest repair;
5. rerun the real-path smoke;
6. relaunch the same research index only when appropriate and with a fresh nonce;
7. never advance after a rejected run.

Stop automatic continuation on technical failure, rejected collection, unexpected data shape, inability to read/write the repository, or an explicit stopping condition.

## Run specification contract

Every run specification must state:

- research question;
- immutable source commits and datasets;
- exact transformation or search space;
- control/comparison group where relevant;
- primary metrics;
- acceptance and stopping criteria;
- expected output schema;
- independent verification path;
- which result changes the next decision.

Do not mix several unrelated stages into one inseparable run.

## Evidence discipline

Treat independently checked exact output as stronger than reconstructed, interval, or numerical evidence. A successful workflow establishes only that the configured computation completed. Any broader interpretation must be stated separately and must match the exact scope of the verified data.
