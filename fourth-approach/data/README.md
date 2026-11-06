# Fourth approach data

This directory stores normalized derived datasets used by the Fourth approach. It is not a dumping ground for complete upstream archives.

## Source discipline

Every dataset must include a manifest recording:

- source repository commit;
- source paths;
- source run identifiers;
- cryptographic hashes where practical;
- extraction script version;
- creation timestamp;
- schema version;
- exact meaning of every status field.

First, Second, and Third approach archives remain immutable in their original directories. Fourth approach data references them and stores only normalized objects required for canonicalization, comparison, exact checking, or the GPT-5.6 Sol handoff.

## Required separations

Never merge these categories before reporting them separately:

- old-basin Second approach candidates;
- independently originated Second approach candidates;
- exact closed supports;
- unresolved supports;
- technically untested supports;
- technical failures;
- numerical leads without exact status.

## Planned datasets

- `source-manifest.json`: immutable source inventory;
- `canonical-supports.jsonl.gz`: canonical support representatives and symmetry maps;
- `canonical-certificates.jsonl.gz`: normalized exact certificates;
- `obstruction-classes.json`: class taxonomy and representatives;
- `contrast-pairs.jsonl.gz`: one-edit exact and numerical contrasts;
- `old-basin-bridge.jsonl.gz`: bridge records for historical Second approach lineages;
- `independent-bridge.jsonl.gz`: bridge records for independent lineages;
- `hard-survivors.jsonl.gz`: unresolved canonical supports with tested search bounds;
- `transfer-tests.jsonl.gz`: hypothesis-driven larger-`n` tests.

## Counting rules

Always report:

1. raw object count;
2. valid parsed count;
3. exact production-verified count;
4. independently verified count;
5. canonical support count;
6. canonical certificate-structure count;
7. unresolved count;
8. technically incomplete count.

Do not use raw certificate count as a proxy for mathematical diversity.