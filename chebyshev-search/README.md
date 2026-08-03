# Search for a counterexample to the Chebyshev primality criterion

This directory performs an exhaustive check of the published table of all
49,679,870 Carmichael numbers below `10^22`.

For every number `n` it computes the prescribed smallest odd prime `r` with
`r ∤ n` and `n^2 != 1 (mod r)`.  Since Carmichael numbers are squarefree, for
each prime divisor `p | n` the original congruence modulo `p` is equivalent to

`T_(n/p)(x) = x^(n/p) in F_p[x]/(x^r-1)`.

The scanner factors `n`, checks this local congruence for every prime divisor,
and performs a direct calculation modulo `n` for every survivor.  The special
closed formula for `r=5` and `p=2 or 3 (mod 5)` is used as a fast exact path.

`test.cpp` contains regression tests for the known fixed-`r=5` false positives
`35,626,501` and `107,357,041`; both must fail when their prescribed values
`r=11` and `r=19` are used.

A complete negative result excludes this finite Carmichael table only. It does
not prove that no non-Carmichael composite number, or no larger Carmichael
number, can be a counterexample.
