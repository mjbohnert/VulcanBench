# VulcanBench Technical Report No. 10, Claude Opus 5 across the effort knob

**July 26, 2026 · VulcanBench v3 · 23 tasks · 69 runs · 3 effort levels · 5 languages · $81.76**

First measurement of Claude Opus 5 on the full v3 suite. Twenty-three real merged post-cutoff
PRs (Python 9, Rust 4, TypeScript 4, JavaScript 3, Go 3), graded by hidden deterministic tests
in a network-isolated Docker sandbox. One attempt per task per effort level.

## Results

| Effort | Score | pass@1 | Solved | Wrong | Timed out | Cost | Tokens/task | Time/task | $/task | $/solved |
|---|---|---|---|---|---|---|---|---|---|---|
| **low** | **20/23** | **87.0%** | 20 | 3 | **0** | $14.07 | 53 K | 5.2 min | $0.61 | $0.70 |
| medium | 19/23 | 82.6% | 19 | 3 | 1 | $24.09 | 93 K | 7.6 min | $1.05 | $1.27 |
| high | 18/23 | 78.3% | 18 | **1** | **4** | $43.60 | 157 K | 13.6 min | $1.90 | $2.42 |

High produces the *fewest wrong answers* of any setting and the most budget cutoffs. Read the
score column together with the last two: its deficit is unfinished work, not bad work.

## Findings

1. **Low is never worse than high, and costs a third as much.** Measured, low leads 20 to 18.
   Two of high's three regressions are budget cutoffs on tasks it solves at low, so grant it
   unlimited time on both and it reaches 20/23, a tie, at 3.1× the cost. There is no reading
   of this sweep where paying for effort wins.

2. **Effort trades wrong answers for unfinished runs.** Wrong answers *fall* (3 → 3 → 1);
   runs that never finish climb (0 → 1 → 4). High effort spends 3× the tokens and 2.6× the
   clock per task, then times out on the biggest repos, `networkx-leiden` was cut off at 60
   minutes after solving in 11.6 at low, and `aiohttp` at 45 after solving in 3.9. The one
   regression the clock does *not* explain is `flask-teardown-robust`: it finished, and
   returned a worse patch (0.67) than it did at low.

3. **One task the knob actually buys.** `itertools-strip-prefix` is wrong at low and medium,
   solved at high. GPT-5.6 Sol went 0-for-3 on it in Report No. 07.

4. **The effort-discriminator inverts.** Report No. 07 called `flask-teardown-robust` the one
   task needing high effort. Opus 5 solves it at *low* and drops to 0.67 at high.

5. **First crack in a wall.** `pennylane-trotter-fragmented` has never been solved by any model
   on v3. At low effort Opus 5 finishes it with a **0.40 partial**: the first non-zero score
   recorded on it. At medium and high it runs the full 60 minutes and scores nothing.

## Failure map

Seven tasks moved. The other sixteen passed at all three settings.

| Task | low | medium | high |
|---|---|---|---|
| aiohttp-upgrade-deferred | ✓ | ✓ | **✗ 45 min** |
| networkx-leiden-communities | ✓ | ✓ | **✗ 60 min** |
| flask-teardown-robust | ✓ | ✓ | 0.67 |
| sqlglot-iso8601-nanos | ✓ | 0.67 | ✓ |
| itertools-strip-prefix | ✗ wrong | ✗ wrong | **✓** |
| sqlglot-canonicalize-internal-names | 0.50 | 0.50 | ✗ 45 min |
| pennylane-trotter-fragmented | **0.40** | ✗ 60 min | ✗ 60 min |

Minutes = hit the wall-clock budget (45 min large / 60 min xlarge, `harness/task_metadata.py`).
All five DNFs hit it to the second; none was step-limited. Scored 0.0, but not a wrong answer.

## The 16 K output cap

A first pass at the high column returned 17/23. It was an artifact: five of six unfinished runs
died on a hardcoded 16,000-token output cap (`harness/agent/providers.py`), returning no content
and no tool calls. Thinking bills against `max_tokens`, so raising effort raised the truncation
rate, and the harness scored the empty patch as a failed attempt.

Fixed two ways: `max_tokens` now scales with effort (32 K → 128 K), and a truncated response
raises instead of failing silently. Every run in this report was produced under the fix. Exactly
three runs across the whole sweep had ever hit the cap, the high column, plus `pennylane` at
low and medium, both re-run. The other 21 tasks at low and medium never came within 3 K of the
ceiling, so raising it could not change them.

**This reaches past this report.** Every prior VulcanBench result ran under the 16 K cap, and any
run that hit it was scored as a wrong answer. Reports No. 07 and No. 08 can't be re-checked, 
their raw runs have rotated out of `runs/`.

## Caveats

- **Single attempts.** One run per task per effort; a one-task difference is within noise.
- **Time budgets bound the high column.** Four of its five failures are wall-clock cutoffs, so
  high effort's ceiling here is partly the 45/60-minute budget, not the model. An extended-budget
  ablation would separate the two.

## Reproducibility

Traces, patches, and replay HTML under `runs/` (suite `v3`). Reported high column is batch
`suite-bb35bfc8`, all 23 tasks in one run; two earlier high batches predate the cap fix and are
retained but not reported. Opus 5 pricing $5/$25 per million tokens.

```
vulcanbench run --suite v3 --model anthropic:claude-opus-5 --effort <low|medium|high> --no-judges
```
