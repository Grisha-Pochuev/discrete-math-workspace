# Batch run 30007794848

Source run: https://github.com/Grisha-Pochuev/discrete-math-workspace/actions/runs/30007794848

The archive was rebuilt from all twenty original GitHub artifact ZIP files. Every recorded or unstarted task was checked against the exact source task list used by the run.

## Search outcome

- source tasks: 127727
- recorded tasks: 32385
- complete tasks: 30561
- incomplete bounded tasks: 1824
- unstarted tasks: 95342
- nodes: 175,132,055,789
- states: 167,458,919,959
- engine seconds: 1527061.456

## Exact support checks

- support occurrences: 812
- unique closed supports: 233
- exact obstruction counts: `{"inconsistent_signs": 36, "mixed_monomial": 79, "target_zero": 118}`
- unresolved exact checks: 0

## Resources

- peak combined RSS on one runner: 7,233,945,600 bytes
- minimum observed MemAvailable: 8,448,053,248 bytes
- maximum observed swap use: 0 bytes

## Successor frontier

`next_tasks.json` contains 255,598 exact tasks:

1. 29,184 refined children of recorded incomplete tasks;
2. 95,342 exact source tasks that were never started;
3. 131,072 reserve tasks from support-size layer 32.

Completed tasks are not repeated. Refined child indices satisfy `child mod parent_shards = parent_shard`, so each refinement is an exact partition of only its unresolved parent.
