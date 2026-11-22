# Batch run 30069271698

Source run: https://github.com/Grisha-Pochuev/discrete-math-workspace/actions/runs/30069271698

The archive was rebuilt from all twenty original GitHub artifact ZIP files. Every recorded or unstarted task was checked against the exact source task list used by the run.

## Search outcome

- source tasks: 509964
- recorded tasks: 27035
- complete tasks: 25314
- incomplete bounded tasks: 1721
- unstarted tasks: 482929
- nodes: 163,719,562,469
- states: 156,390,011,145
- engine seconds: 1551384.855

## Exact support checks

- support occurrences: 485
- unique closed supports: 218
- exact obstruction counts: `{"inconsistent_signs": 34, "mixed_monomial": 85, "target_zero": 99}`
- unresolved exact checks: 0

## Resources

- peak combined RSS on one runner: 7,245,660,160 bytes
- minimum observed MemAvailable: 8,204,972,032 bytes
- maximum observed swap use: 0 bytes

## Successor frontier

`next_tasks.json.gz` contains 1,034,753 exact tasks:

1. 27,536 refined children of recorded incomplete tasks;
2. 482,929 exact source tasks that were never started;
3. 524,288 reserve tasks from support-size layer 34.

Completed tasks are not repeated. Refined child indices satisfy `child mod parent_shards = parent_shard`, so each refinement is an exact partition of only its unresolved parent.

## Archive format

Large exact task queues and the record stream are stored as deterministic gzip files. Use `gzip -cd` or Python's `gzip` module. The verifier checks their integrity and the exact successor-task count.
