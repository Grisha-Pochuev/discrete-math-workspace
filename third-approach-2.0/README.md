# Third approach 2.0

This directory contains a revised proof-oriented multi-basin search track.

It develops several independent candidate families instead of repeatedly refining one numerical basin. The implementation works in coefficient space, keeps lineage and basin metadata, and attempts exact reconstruction for especially strong candidates.

## Compute layout

A full run uses 20 GitHub Actions jobs with four worker processes per job. The normal requested runtime is 21,000 seconds, with reserved time for orderly shutdown, manifest creation, artifact upload, aggregation, and verification.

## Safety model

- separate configuration gate and real-path smoke test before a large matrix;
- `fail-fast: false` for independent jobs;
- resource and machine information recorded per run;
- artifacts uploaded even after isolated failures;
- accepted runs require sufficient readable job output and bounded worker-error rates;
- pushes are retried only after synchronization with current `main`.

## Strategy profiles

Available profiles include balanced search, multi-basin exploration, degree expansion, support escape, and contrast-focused search. The collector records the recommended next profile from observed run behavior.

The initial launch configuration is explicit. Creating or reading this folder must not by itself start a long computation.
