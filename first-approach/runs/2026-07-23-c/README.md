# Batch run 29984144124

Source run: https://github.com/Grisha-Pochuev/discrete-math-workspace/actions/runs/29984144124

The archive was rebuilt from all twenty original GitHub artifact ZIP files. Every recorded or unstarted task was checked against the exact source task list used by the run.

## Search outcome

- source tasks: 65795
- recorded tasks: 30724
- complete tasks: 29029
- incomplete bounded tasks: 1695
- unstarted tasks: 35071
- nodes: 175,004,444,642
- states: 167,227,076,524
- engine seconds: 1533871.441

## Exact support checks

- support occurrences: 864
- unique closed supports: 164
- exact obstruction counts: `{"inconsistent_signs": 26, "mixed_monomial": 45, "target_zero": 93}`
- unresolved exact checks: 0

## Resources

- peak combined RSS on one runner: 7,243,382,784 bytes
- minimum observed MemAvailable: 8,488,321,024 bytes
- maximum observed swap use: 0 bytes

## Successor frontier

`next_tasks.json` contains 127,727 exact tasks:

1. 27,120 refined children of recorded incomplete tasks;
2. 35,071 exact source tasks that were never started;
3. 65,536 reserve tasks from support-size layer 31.

Completed tasks are not repeated. Refined child indices satisfy `child mod parent_shards = parent_shard`, so each refinement is an exact partition of only its unresolved parent.
