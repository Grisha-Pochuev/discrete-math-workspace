# Sixth approach

Neutral, reproducible C++ experiments for exact small-instance classification
and larger frontier searches.

The first series has two purposes:

1. independently regenerate and exactly partition the size-10 factor systems;
2. search larger sizes for records below, or close to, the linear safety
   threshold declared in the immutable run specification.

The worker writes atomic JSON checkpoints. `driver.py` validates individual
shards and collects a run only after exact shard and orbit coverage checks pass.

## Local interface

```text
g++ -std=c++20 -O3 -DNDEBUG -pthread run000_worker.cpp -o run000_worker
./run000_worker self-test
./run000_worker worker --worker-id 0 --worker-count 1 --seconds 60 --output worker-000.json
python driver.py verify-worker worker-000.json --worker-count 1
```

The public repository intentionally contains no statement of the surrounding
research problem.

## Durable results

Large worker and layer artifacts are temporary transport. A strict collector
may automatically commit a compact immutable archive under `runs/` after full
coverage is accepted. The archive keeps the specification, summary, compact
exceptional samples, provenance, and checksums; bulk raw layers stay outside
Git history.

## Two compute providers

The same C++20 worker and immutable JSON specifications are used on both
providers. GitHub Actions is reserved for long-running batches and audits of
existing GitHub artifacts. CircleCI is reserved for fine power-of-two shard
partitions that finish, audit, and checkpoint within a one-hour job boundary.

CircleCI computation is inert on ordinary commits. A run is enabled only by
the exact neutral tag recorded in its immutable specification. Fine shards are
audited independently before aggregation, so large raw layers do not need to
be copied into Git or onto a local workstation.

