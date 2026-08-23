# VulcanBench Technical Report No. 13, GLM 5.3: model versus harness

**August 22, 2026 · VulcanBench v3 · 23 tasks · 138 runs · 2 harnesses · 3 effort levels · 5 languages · $35.48 cash + subscription**

First measurement of Z.ai's GLM 5.3, run two ways against the same suite: through
VulcanBench's uniform agent loop on the raw `zai` API (metered cash), and through
**ZCode**, Z.ai's own coding harness, billed to a GLM Coding Plan subscription.
Same model, same twenty-three real merged post-cutoff PRs (Python 9, TypeScript 4,
Rust 4, Go 3, JavaScript 3), same hidden deterministic tests in a network-isolated
Docker verifier, same effort levels (low, high, max). One attempt per task per
effort per harness. The question is not how good GLM 5.3 is, it is how much the
product harness around it changes the answer.

## Results

**Raw API (`zai:glm-5.3`), VulcanBench uniform loop, metered:**

| Effort | pass@1 | Solved | Wrong | Unfinished | Cost | Tokens/task | Time/task | $/solved |
|---|---|---|---|---|---|---|---|---|
| low | **78.3%** | 18/23 | 0 | 5 | $7.29 | 190 K | 8.4 min | $0.41 |
| high | 73.9% | 17/23 | 0 | 6 | $10.23 | 267 K | 13.5 min | $0.60 |
| max *(default)* | 65.2% | 15/23 | 1 | **7** | $17.96 | 437 K | 22.8 min | $1.20 |

**ZCode (`zcode:glm-5.3`), Z.ai's harness, subscription:**

| Effort | pass@1 | Solved | Wrong | Unfinished | Cost basis | Tokens/task | Time/task | $/solved |
|---|---|---|---|---|---|---|---|---|
| low | **82.6%** | 19/23 | 4 | **0** | $0 cash | 1.39 M | 4.8 min | api-equiv $1.45 |
| high | 82.6% | 19/23 | 4 | **0** | $0 cash | 1.33 M | 4.6 min | api-equiv $1.39 |
| max *(default)* | **87.0%** | 20/23 | 3 | **0** | $0 cash | 1.66 M | 5.3 min | api-equiv $1.64 |

pass@1 is the per-task success rate at one attempt. Both harnesses ran the identical
23-task suite; the raw API total was **$35.48** in metered cash, ZCode consumed GLM
Coding Plan quota at **$0 marginal cash** (API-equivalent value of the harvested
tokens is ~$87). Every run in both tracks was verified running `zai/glm-5.3`, not the
5.2 ZCode ships as its default, and the integrity audit flagged zero contaminated
runs on either side.

## Findings

1. **Same model, and the harness is worth up to 22 points.** At matched `max` effort,
   ZCode scores 87.0% against the raw API's 65.2%, a 21.8-point gap from scaffolding
   alone. It is not a max-effort artifact: ZCode's *worst* column (82.6%) still beats
   the raw API's *best* (78.3% at low). Judged only by its default raw-API setting, GLM
   5.3 looks like a 65% model; judged through its own product, it is an 87% model.

2. **The effort knob runs in opposite directions on the two harnesses.** On the raw API
   it inverts, 78.3 to 73.9 to 65.2, more reasoning steadily worse, echoing the backward
   knob Report No. 12 found for Qwen3.8-Max and Report No. 10 for Opus 5. In ZCode the
   same knob is flat then up, 82.6 to 82.6 to 87.0. The model's `reasoning_effort` is the
   same enum in both; the harness is what decides whether spending it helps.

3. **The gap is unfinished work, not worse work.** Almost every raw-API failure is a
   wall-clock timeout, not a wrong answer: 5, 6, then 7 unfinished runs as effort climbs
   against just 0, 0, 1 incorrect completions, while the solved count erodes 18 to 17 to
   15 and time per task climbs 8.4 to 22.8 minutes. ZCode is the mirror image: zero
   timeouts at any level and every failure a returned wrong answer (4, 4, 3), finishing
   in about five minutes flat regardless of effort. The raw loop reasons until it runs
   out of budget, and more effort makes that worse; the product harness drives every run
   to a finished answer. This is the same "deficit is unfinished, not bad" pattern Report
   No. 12 documented, but here a second harness on the identical model removes it entirely.

4. **Three tasks the raw API never finishes, ZCode completes.** `networkx-leiden-communities`,
   `sqlglot-canonicalize-internal-names`, and `pennylane-trotter-fragmented` time out at
   all three effort levels on the raw API (the same three `pennylane`, `networkx` cluster
   that defeated Qwen). ZCode finishes all three every time, solves two of them
   (`networkx-leiden` at low and high, `pennylane-trotter-fragmented` at max), and even on
   the one it misses (`sqlglot-canonicalize`) it fails as a wrong answer rather than a
   hang. `pennylane-trotter-fragmented` was "never solved at any setting" for Qwen in
   Report No. 12; GLM 5.3 in ZCode cracks it.

5. **Cheaper in cash, heavier in tokens, faster on the clock.** The raw API cost $35.48
   to run all three columns and got slower with effort (8.4 to 22.8 min/task). ZCode cost
   no marginal cash (subscription quota) and held ~5 min/task at every level, but moved
   far more context: ~1.3 to 1.7 M tokens/task against the raw loop's 190 K to 437 K,
   roughly 5x, reflecting the product's system prompt, tools, skills, and context
   management. The two cost columns are not comparable: one is metered cash, the other is
   allowance already paid for.

## Failure map

Eight tasks moved between harnesses or across effort. The other fifteen were solved by
both harnesses at all three levels.

| Task | API low/high/max | ZCode low/high/max |
|---|---|---|
| pennylane-trotter-fragmented | timeout / timeout / timeout | wrong / wrong / **solved** |
| networkx-leiden-communities | timeout / timeout / timeout | **solved / solved** / wrong |
| sqlglot-canonicalize-internal-names | timeout / timeout / timeout | wrong / wrong / wrong |
| sqlglot-iso8601-nanos | timeout / timeout / solved | solved / solved / solved |
| aiohttp-upgrade-deferred | solved / solved / timeout | solved / solved / solved |
| flask-teardown-robust | solved / timeout / timeout | solved / wrong / wrong |
| jiff-strftime-negpad | timeout / solved / solved | wrong / wrong / solved |
| semver-inc-dotted-prerelease | solved / solved / timeout | solved / solved / solved |
| semver-xrange-order | solved / solved / timeout | solved / solved / solved |
| semver-truncate | solved / solved / wrong | wrong / solved / solved |

Read the two halves together. Where the raw API degrades, it degrades into `timeout`
(the cell goes blank on the clock, most often at `max`); where ZCode degrades, it
degrades into `wrong` (a finished, incorrect answer). `sqlglot-canonicalize-internal-names`
is the cleanest single illustration: neither harness solves it, but the raw API spends
its whole budget and returns nothing while ZCode returns a wrong patch in minutes.

Of the raw API's 18 unfinished runs across the three columns, all hit the 45-minute
(large) or 60-minute (xlarge) wall-clock boundary in `harness/task_metadata.py`; none
was cost-capped or hit the step ceiling. The clock is what binds, and `max` reasoning is
what spends it.

## Caveats

- **One attempt per cell.** Unlike Report No. 12's repeat-3 debut, this comparison is a
  single attempt per task per effort per harness (138 runs total). At 23 tasks the pass@1
  standard error is roughly plus or minus 8 to 9 points per column, so the within-harness
  effort trends (especially the raw API's 78 to 65) are suggestive rather than tight, and
  a repeat-3 rerun would sharpen them. The headline max-vs-max harness gap (21.8 points)
  is larger than the combined uncertainty; the flat-vs-inverted shape and the
  timeout-vs-wrong split are categorical, not marginal.
- **This measures model plus product harness, not two model APIs.** The ZCode column
  includes Z.ai's system prompt, tools, context management, skills, and any routing
  inside the product. It is not comparable to an `anthropic:` or `openai:` uniform-loop
  column and must never be added to a raw-API leaderboard. The value of the report is
  precisely the delta between the two rows for one fixed model.
- **Fixed budget, not a capability ceiling.** With unlimited wall clock the raw API might
  finish more of what it currently times out on. Budgets (5 to 60 min, scaled by repo
  size) are identical for every model and harness on the board and unchanged since Report
  No. 07; agents in production run under a clock.
- **ZCode token counts are harvested, not streamed.** ZCode's headless mode prints only
  the final text; tokens, tool calls, and the per-request model id come from its SQLite
  session store, and its API-equivalent cost is priced from those tokens at the `zai`
  table rate. Cache-write pricing and any product-side discount are not modeled.

## Reproducibility

Traces, patches, and replay HTML under `runs/` (suite `v3`). Both tracks ran GLM 5.3 at
one attempt across low, high, and max (`extra-high` maps to the API's `max`). The ZCode
harness is `zcode-app-cli` 3.8.1-15 on runtime 0.16.3, signed in with a GLM Coding Plan;
the per-run model and thought level are read back from its session store as proof of what
executed. Judges were off for both (hidden-test grading only, the documented publication
protocol).

```
# Raw API, VulcanBench uniform loop (metered cash)
vulcanbench run --suite v3 --model zai:glm-5.3 --effort <low|high|extra-high> \
  --repeat 1 --no-judges

# ZCode, Z.ai's harness (GLM Coding Plan subscription)
vulcanbench run --suite v3 --model zcode:glm-5.3 --effort <low|high|extra-high> \
  --repeat 1 --no-judges --sandbox docker
```

GLM 5.3 priced at $1.40 input, $0.26 cached input, $4.40 output per million tokens. The
GLM Coding Plan meters usage in rolling 5-hour and weekly windows; the ZCode curve was
run across those windows with `--only-missing` to resume.
