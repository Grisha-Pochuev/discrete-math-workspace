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

