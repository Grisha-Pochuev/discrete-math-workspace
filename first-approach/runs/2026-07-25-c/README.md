# Batch run 30146741216

Source run: https://github.com/Grisha-Pochuev/discrete-math-workspace/actions/runs/30146741216

The archive was rebuilt from all twenty original GitHub artifact ZIP files. Every recorded or unstarted task was checked against the exact source task list used by the run.

## Search outcome

- source tasks: 4177182
- recorded tasks: 32823
- complete tasks: 31306
- incomplete bounded tasks: 1517
- technical-failure tasks preserved for exact retry: 0
- unstarted tasks: 4144359
- nodes: 178,198,488,294
- states: 170,024,410,551
- engine seconds: 1528512.039

## Exact support checks

- support occurrences: 730
- unique closed supports: 234
- exact obstruction counts: `{"inconsistent_signs": 39, "mixed_monomial": 102, "target_zero": 93}`
- unresolved exact checks: 0

## Resources

- peak combined RSS on one runner: 7,044,444,160 bytes
- minimum observed MemAvailable: 6,648,348,672 bytes
- maximum observed swap use: 0 bytes

## Successor frontier

`next_tasks.json.gz` contains 8,362,935 exact tasks:

1. 24,272 refined children of bounded incomplete tasks;
2. 0 exact source tasks preserved after technical failure;
3. 4,144,359 exact source tasks that were never started;
4. 4,194,304 reserve tasks from support-size layer 37.

Completed tasks are not repeated. Refined child indices satisfy `child mod parent_shards = parent_shard`, so each refinement is an exact partition of only its unresolved parent.

## Archive format

Large exact task queues and the record stream are stored as deterministic gzip files. Use `gzip -cd` or Python's `gzip` module. The verifier checks their integrity and the exact successor-task count.
