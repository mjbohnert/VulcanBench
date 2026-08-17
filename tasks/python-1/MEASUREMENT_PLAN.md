# Python Suite v1 — measuring the band without spending a fortune

The expensive part of this suite isn't building it, it's **measuring** it: placing
each task in the difficulty band (anchor / mid / tail) needs the frontier panel,
and the CHARTER mandates repeat ≥ 3 so scores carry error bars. Done naively that's

```
23 tasks × 4 models × 3 efforts × 3 repeats = 828 runs
```

At the v3 blended rate (~$0.47/run, from Report No. 4: 207 runs / $96.72) that's
**~$390 per full measurement pass** — and you'll want several passes as the suite
changes. Below is how to get the same signal for a fraction of that.

## The core idea: a cheap funnel, not a uniform sweep

Most tasks don't need the full panel. A task that a *cheap* model already aces is
an anchor; one that even a *strong* model can't touch is tail. You only need the
expensive panel on the **ambiguous middle**. So spend in three widening tiers and
stop early wherever a task is already decided.

### Tier 0 — free / already done
Gold-solvability, base-fails, determinism ×3 are checked by
`scripts/validate_tasks.py` with **no LLM** (deterministic Docker). Every task here
already passes it. This is the correctness gate; it costs nothing.

### Tier 1 — cheap triage (one frugal model, repeat 1)
Run the whole suite once on the **cheapest capable** model at one effort:

```bash
vulcanbench run --suite python-1 --model openai:grok-4.5 --effort low --no-judges \
  --max-concurrency 4 --max-cost 10
```

Grok-4.5-low cost the whole v3 suite **$3.39** (Report No. 4). For ~23 tasks expect
**$3–5**. Read the result:
- **Solved** by grok-low → provisional **anchor/easy** (floor candidate — likely cut).
- **Failed** by grok-low → provisional **mid or tail**; promote to Tier 2.
- This single pass already bins roughly half the suite for the price of a sandwich.

### Tier 2 — the frontier bracket on survivors only (repeat 3)
For the tasks Tier 1 left ambiguous, run a **2-model bracket** — one frontier +
one frugal reference — at **one effort**, repeat 3:

```bash
vulcanbench run --suite python-1 --model anthropic:claude-opus-5 --effort medium \
  --repeat 3 --no-judges --only-missing --max-cost 40
```

`--only-missing` skips tasks already recorded, so you're not re-paying for Tier 1's
decided tasks. Two models × ~12 survivors × 3 repeats ≈ 72 runs ≈ **$25–40**.
This is where the band placement and the error bars actually get earned.

### Tier 3 — the published leaderboard (full panel, only when releasing)
The 4-model × 3-effort sweep is a **reporting** artifact, not a band-building tool.
Run it once, at the end, on the frozen 23 — not on every candidate mid-iteration.

## Five knobs that cut cost with zero loss of signal

1. **`--only-missing` + `--max-cost`** — resume instead of restart, and fail-closed
   at a hard spend cap. Already in the harness (`run_suite`). Never re-pay for a run
   you already have.
2. **Prompt caching is on** — the reports bill "prompt-cache reads discounted." The
   sliced repo + system prompt are identical across a task's repeats, so run a
   task's repeats **back-to-back** (don't interleave models) to maximize cache hits.
3. **One effort for band-building.** Effort sweeps answer "does effort help *this
   model*" — a leaderboard question. For *placing a task in the band* you need one
   representative effort (medium). That's a 3× cut on its own.
4. **Adaptive repeats (sequential stopping).** Don't run a fixed 3 everywhere. Run
   1; if it's a decisive pass or decisive fail, stop. Only spend the full 3–5 on
   tasks whose first run lands *near a band boundary* (the ones where variance
   actually changes the conclusion). Most tasks are decided in 1.
5. **Per-scale step/token budgets.** v3's runaway cost was timeouts on big repos
   (pennylane/networkx hit the 60-min wall). Cap `max_steps`/wall-clock per
   `repo_scale` so a stuck run can't burn budget — and report DNF separately so a
   cap never gets misread as a capability failure (a CHARTER rule already).

## Measure variance *once*, then trust it

The reason for repeat ≥ 3 is to separate a real score gap from run-to-run noise.
You don't need to re-establish that variance on all 23 forever:

- Pick ~5 representative tasks spanning the band, run **repeat 5** on the frontier
  bracket, and compute per-task pass@1 stderr.
- If variance is empirically small for a class of tasks (e.g. deterministic-bug
  fixes), drop those to repeat 2–3 and reserve repeat 5 for the genuinely flaky
  borderline tasks. Spend repeats where they change the answer.

## A concrete first move (~$5, tonight)

```bash
vulcanbench run --suite python-1 --model openai:grok-4.5 --effort low \
  --no-judges --max-concurrency 4 --max-cost 8
```

That single Tier-1 pass on the tasks built so far tells you which are floor
(cut them), which look mid (keep), and which are already tail — turning every
"band guess" in CANDIDATES.md into a measured provisional bin, before you spend a
dollar on the frontier panel.

## Rough budget for a full band-building cycle
| Tier | What | Runs | Est. $ |
|---|---|---|---|
| 0 | validate_tasks (determinism) | — | $0 |
| 1 | grok-low, all tasks, r1 | ~23 | $3–5 |
| 2 | opus5+frugal, survivors, r3, 1 effort | ~70 | $25–40 |
| 3 | full panel leaderboard (release only) | ~280 | ~$130 |

Band-building (Tiers 0–2) lands around **$30–45** instead of ~$390 — an order of
magnitude cheaper — with the full-panel leaderboard reserved for the one-time
public release.
