name: Sixth approach run-000 smoke

on:
  workflow_dispatch:

permissions:
  contents: read

jobs:
  same-path-smoke:
    runs-on: ubuntu-24.04
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4

      - name: Compile optimized worker
        run: >-
          g++ -std=c++20 -O3 -DNDEBUG -pthread
          "sixth approach/run000_worker.cpp"
          -o sixth-run000-worker

      - name: Deterministic catalogue self-test
        run: ./sixth-run000-worker self-test

      - name: Execute one exact shard through the production path
        run: |
          mkdir -p smoke-output
          timeout --signal=TERM --kill-after=30s 600s \
            ./sixth-run000-worker worker \
              --worker-id 0 \
              --worker-count 1108 \
              --seconds 5 \
              --output smoke-output/worker-000.json

      - name: Strictly verify the smoke shard
        run: >-
          python3 "sixth approach/driver.py" verify-worker
          smoke-output/worker-000.json
          --worker-count 1108

      - name: Preserve smoke evidence
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: sixth-run000-smoke-${{ github.run_id }}
          path: smoke-output/
          if-no-files-found: warn
          retention-days: 14
