# Chebyshev criterion: exhaustive Carmichael scan

**No counterexample in the complete published Carmichael table below 10^22**

- Status: `complete`
- Dataset rows processed: `49,679,870` / `49,679,870`
- Result shards: `20` / `20`
- Strict shard boundaries: `True`
- First/last number: `561` / `9999999972168827821201`
- Exact counterexample candidates: `0`
- Malformed source rows: `0`
- Unresolved computational errors: `0`
- Largest prescribed `r` encountered: `59`
- Source URL: `https://blue.butler.edu/~jewebste/cars_table_10to22.txt`
- Source ETag: `"a20de2e2-61ba73e7afd80"`
- Source bytes: `2718819042`
- GitHub Actions run: `30850670035`

For each published Carmichael number the scanner reads its complete prime
factorization, computes the prescribed smallest `r`, checks the Frobenius-
reduced congruence modulo every prime divisor, and independently recomputes the
original congruence modulo `n` for every survivor. A complete negative result
excludes this finite table only; it is not a proof for all composite integers.
