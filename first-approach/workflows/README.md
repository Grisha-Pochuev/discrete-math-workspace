# Legacy First-approach workflows

These YAML files are the preserved GitHub Actions definitions used by the original exact-search campaign when its code and markers lived at repository root.

They are intentionally stored outside `.github/workflows/`, so GitHub does not execute them. Their old relative paths are preserved for historical reproducibility and should not be assumed to work from the reorganized tree without adaptation.

If a First-approach computation ever needs to be reproduced, first review `../AGENTS.md`, adapt paths explicitly to `first-approach/`, run a short real-path smoke test, and only then create a new clearly named active workflow under `.github/workflows/`.
