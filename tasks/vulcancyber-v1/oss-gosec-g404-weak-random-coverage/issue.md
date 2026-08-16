# G404 misses several weak `math/rand` functions (false negatives)

The G404 rule reports use of the insecure `math/rand` package for
security-sensitive randomness. Its list of flagged functions is incomplete:
several functions that draw on the same weak generator are **not** reported, so
code that uses them for security decisions passes the scanner clean.

At least these are missed:

- `math/rand.Perm`
- `math/rand.Shuffle`
- `math/rand.ExpFloat64`

(the corresponding `math/rand/v2` functions are missed too).

## Expected behaviour

G404 must flag these additional `math/rand` (and `math/rand/v2`) functions as
weak randomness, so a program using them is reported just like one calling
`rand.Intn` or `rand.Float64`.

Existing behaviour must not change: functions already covered (e.g. `rand.Intn`)
are still flagged, and secure sources such as `crypto/rand` are still **not**
flagged (no false positives).

The rule's function list lives in `rules/rand.go`.
