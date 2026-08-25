# Exact search for Zhang's 1029-prime Williams-number challenge

This branch contains an independently reconstructed exact modular model of
Zhenxiang Zhang's stronger sufficient system.  A selected subset is accepted
only after direct integer verification of

- `p - 1 | N - 1`, and
- `p + 1 | N + 1`

for every selected prime `p`, where `N` is their product.

The workflow runs several equivalent CP-SAT formulations in parallel:
original cyclic rows, prime-power split rows with native XOR constraints, a
hybrid formulation, and an incremental prime-base formulation.  `UNKNOWN`
means only that the time limit expired; it is not a nonexistence result.
