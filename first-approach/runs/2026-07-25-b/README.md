# Batch run 30128864444

Source run: https://github.com/Grisha-Pochuev/discrete-math-workspace/actions/runs/30128864444

The archive was rebuilt from all twenty original GitHub artifact ZIP files. Every recorded or unstarted task was checked against the exact source task list used by the run.

## Search outcome

- source tasks: 2075668
- recorded tasks: 26006
- complete tasks: 24108
- incomplete bounded tasks: 1898
- technical-failure tasks preserved for exact retry: 0
- unstarted tasks: 2049662
- nodes: 166,026,151,151
- states: 158,657,484,454
- engine seconds: 1555832.688

## Exact support checks

- support occurrences: 702
- unique closed supports: 252
- exact obstruction counts: `{"inconsistent_signs": 48, "mixed_monomial": 97, "target_zero": 107}`
- unresolved exact checks: 0

## Resources

- peak combined RSS on one runner: 7,323,136,000 bytes
- minimum observed MemAvailable: 7,320,764,416 bytes
- maximum observed swap use: 0 bytes

## Successor frontier

`next_tasks.json.gz` contains 4,177,182 exact tasks:

1. 30,368 refined children of bounded incomplete tasks;
2. 0 exact source tasks preserved after technical failure;
3. 2,049,662 exact source tasks that were never started;
4. 2,097,152 reserve tasks from support-size layer 36.

Completed tasks are not repeated. Refined child indices satisfy `child mod parent_shards = parent_shard`, so each refinement is an exact partition of only its unresolved parent.

## Archive format

Large exact task queues and the record stream are stored as deterministic gzip files. Use `gzip -cd` or Python's `gzip` module. The verifier checks their integrity and the exact successor-task count.
