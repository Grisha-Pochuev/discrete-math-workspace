# Batch run 30104322098

Source run: https://github.com/Grisha-Pochuev/discrete-math-workspace/actions/runs/30104322098

The archive was rebuilt from all twenty original GitHub artifact ZIP files. Every recorded or unstarted task was checked against the exact source task list used by the run.

## Search outcome

- source tasks: 1034753
- recorded tasks: 30061
- complete tasks: 26756
- incomplete bounded tasks: 1273
- technical-failure tasks preserved for exact retry: 2032
- unstarted tasks: 1004692
- nodes: 164,592,809,347
- states: 157,112,935,904
- engine seconds: 1539268.098

## Exact support checks

- support occurrences: 554
- unique closed supports: 244
- exact obstruction counts: `{"inconsistent_signs": 46, "mixed_monomial": 91, "target_zero": 107}`
- unresolved exact checks: 0

## Resources

- peak combined RSS on one runner: 7,351,181,312 bytes
- minimum observed MemAvailable: 7,848,148,992 bytes
- maximum observed swap use: 0 bytes

## Successor frontier

`next_tasks.json.gz` contains 2,075,668 exact tasks:

1. 20,368 refined children of bounded incomplete tasks;
2. 2,032 exact source tasks preserved after technical failure;
3. 1,004,692 exact source tasks that were never started;
4. 1,048,576 reserve tasks from support-size layer 35.

Completed tasks are not repeated. Refined child indices satisfy `child mod parent_shards = parent_shard`, so each refinement is an exact partition of only its unresolved parent.

## Archive format

Large exact task queues and the record stream are stored as deterministic gzip files. Use `gzip -cd` or Python's `gzip` module. The verifier checks their integrity and the exact successor-task count.
