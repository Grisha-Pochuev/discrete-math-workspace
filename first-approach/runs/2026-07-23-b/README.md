# Batch run 29960969740

Source run: https://github.com/Grisha-Pochuev/discrete-math-workspace/actions/runs/29960969740

The run completed technically on all 20 matrix jobs. The archive was rebuilt from all twenty original GitHub artifact ZIP files and checked independently.

## Search outcome

- recorded tasks: 28205
- complete tasks: 26699
- incomplete bounded tasks: 1506
- unstarted tasks: 8931
- nodes: 179,752,786,545
- states: 171,952,707,000
- engine seconds: 1550628.294

## Exact support checks

- support occurrences: 1102
- unique closed supports: 150
- exact obstruction counts: `{"inconsistent_signs": 21, "mixed_monomial": 39, "target_zero": 90}`
- unresolved exact checks: 0

## Resources

- peak combined RSS on one runner: 6,739,079,168 bytes
- minimum observed MemAvailable: 8,976,343,040 bytes
- maximum observed swap use: 0 bytes

## Successor frontier

`next_tasks.json` contains 65,795 exact tasks. Priority order:

1. sixteen-way refinements of every recorded incomplete task;
2. all tasks from the current queue that were never started;
3. support-size layer 30 as a reserve queue so CPU workers do not become idle.

Completed tasks are not repeated. Child shard indices satisfy `child mod parent_shards = parent_shard`, so the refinement is an exact partition of only the unresolved parent.
