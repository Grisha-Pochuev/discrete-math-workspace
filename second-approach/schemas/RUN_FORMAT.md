# Run data format

Each substantial experiment should use a directory such as:

`second-approach/runs/YYYY-MM-DD-<method>-<run-id>/`

Required files:

- `config.json` — method, support family, ranges, precision, budgets, seeds, code commit;
- `summary.json` — counts, best residuals, promoted candidates, failure modes, resource use;
- `candidates.jsonl.gz` — one complete machine-readable candidate per line;
- `promoted/` — compact records for the strongest near-solutions;
- `logs/` — worker and optimizer logs;
- `checksums.sha256` — checksums of preserved artifacts;
- `README.md` — short human-readable interpretation.

A candidate record should contain at least:

- candidate identifier;
- support mask and support size;
- generation method and seed;
- normalized real and imaginary parts of all active weights;
- maximum and aggregate mixed residuals;
- three monochromatic amplitudes;
- normalization and gauge choices;
- numerical precision;
- status under each existing exact obstruction check;
- convergence status;
- parent candidate, if mutated or refined.

Near-solutions must be preserved even when exact verification fails. Exact certificates and numerical evidence must be stored in separate fields.
