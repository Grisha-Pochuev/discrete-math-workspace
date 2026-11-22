# GPT-5.6 Sol handoff

This directory contains the compact reasoning package produced by the Fourth approach.

The primary handoff must be small enough to inspect as a coherent mathematical argument. Bulk archives may be linked as appendices but must not replace the curated core.

## Required core documents

```text
sol-handoff/
├── 00-exact-problem-and-scope.md
├── 01-known-results.md
├── 02-obstruction-taxonomy.md
├── 03-minimal-certificates.md
├── 04-contrast-pairs.md
├── 05-second-approach-bridge.md
├── 06-hard-survivors.md
├── 07-transfer-tests.md
├── 08-candidate-lemmas.md
├── 09-falsification-suite.md
└── MANIFEST.json
```

## Selection policy

The curated core should emphasize:

- the simplest exact representative of each obstruction mechanism;
- structurally diverse examples rather than many low-score copies;
- one-edit pairs that isolate causal changes;
- the strongest old-basin and independent candidates;
- unresolved supports with explicit tested limits;
- examples that falsify tempting but incorrect generalizations;
- any exact pattern shared by more than one value of `n`.

## Candidate lemma format

Every proposed lemma must include:

1. precise quantified statement;
2. intended scope;
3. supporting exact classes;
4. supporting contrast pairs;
5. known counterexamples outside the scope;
6. falsification tests;
7. relation to the full Krenn--Gu conjecture;
8. confidence label: observation, conjectural pattern, proved restricted lemma, or proved general lemma.

## Sol task

GPT-5.6 Sol should be asked to alternate between synthesis and attack:

1. infer a compact structural explanation;
2. test it against the falsification suite;
3. inspect the smallest failure;
4. refine or split the lemma;
5. request a new exact experiment only when it distinguishes concrete alternatives;
6. attempt a proof for arbitrary even `n` only after the restricted statement survives the exact suite.

## Trust boundary

Exact restricted certificates, numerical candidates, and general mathematical claims must remain visibly distinct. The handoff must never imply that a support-restricted identity solves the full prize problem.