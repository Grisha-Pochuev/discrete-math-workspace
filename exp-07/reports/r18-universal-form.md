# r18 universal semimagic reduction

This note isolates the linear structure behind the repeated-difference search.

Let a 3x3 array of numbers

```
x11 x12 x13
x21 x22 x23
x31 x32 x33
```

have a common row and column sum. No cube assumption is needed for this lemma.

Put

```
b0 = x11,
b1 = x32,
b2 = x23,
A  = x22 - x11,
B  = x33 - x11.
```

The row/column equalities imply exactly

```
x13 - b1 = x31 - b2 = A,
x21 - b1 = x12 - b2 = B.
```

Hence every 3x3 semimagic array has the form

```
b0      b2+B    b1+A
b1+B    b0+A    b2
b2+A    b1      b0+B
```

and conversely every array of this form is semimagic, with common sum

```
b0+b1+b2+A+B.
```

For the cube problem, each displayed entry must itself be a positive cube. Therefore, if A and B are nonzero, each of |A| and |B| must occur as a difference of two positive cubes at least three times: once for each of b0,b1,b2. The sign only decides whether the base cube is the lower or upper endpoint of the corresponding representation.

Thus a solution is equivalent to two signed repeated cube differences whose three chosen base endpoints are the same after a common integer scaling. This is precisely the normalized signed-collision model used by r17. The finite OEIS input used by r17 is therefore a coverage limitation, not a limitation of the structural reduction.

The immediate r18 experiment is to broaden the repeated-difference seed pool by taking the union of:

- A265625, first 10000 terms (more than two representations),
- A333376, first 1000 terms (exactly four representations),
- A333377, first 150 terms (exactly five representations),
- explicit independently replayed high-multiplicity seeds already used in r17.

Every accepted candidate must still be reconstructed from exact positive cube representations and replay all six row/column sums exactly.