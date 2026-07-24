# Batch run 30041615382

Source run: https://github.com/Grisha-Pochuev/discrete-math-workspace/actions/runs/30041615382

The archive was rebuilt from all twenty original GitHub artifact ZIP files. Every recorded or unstarted task was checked against the exact source task list used by the run.

## Search outcome

- source tasks: 255598
- recorded tasks: 31730
- complete tasks: 30233
- incomplete bounded tasks: 1497
- unstarted tasks: 223868
- nodes: 166,918,924,968
- states: 159,378,285,163
- engine seconds: 1532581.886

## Exact support checks

- support occurrences: 613
- unique closed supports: 219
- exact obstruction counts: `{"inconsistent_signs": 41, "mixed_monomial": 73, "target_zero": 105}`
- unresolved exact checks: 0

## Resources

- peak combined RSS on one runner: 7,209,349,120 bytes
- minimum observed MemAvailable: 8,436,027,392 bytes
- maximum observed swap use: 0 bytes

## Successor frontier

`next_tasks.json` contains 509,964 exact tasks:

1. 23,952 refined children of recorded incomplete tasks;
2. 223,868 exact source tasks that were never started;
3. 262,144 reserve tasks from support-size layer 33.

Completed tasks are not repeated. Refined child indices satisfy `child mod parent_shards = parent_shard`, so each refinement is an exact partition of only its unresolved parent.
