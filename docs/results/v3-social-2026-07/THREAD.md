# X thread — v3 results drop (ready to paste)

Suggested order: one visual per tweet, each replying to the last.
All figures verified against Reports No. 07, 08, 10 and the corrected Opus 5 sweep.

## Tweet 1 — the leaderboard
*(attach `docs/results/v3-leaderboard-2026-07/vulcanbench-v3-leaderboard-card.png`)*

We've now put 6 models through VulcanBench v3 — 23 real merged PRs, hidden tests, one attempt each.

15 configurations. One frontier.

Grok 4.5 (medium): 21/23 at $0.32 per solved task. Nothing else matches it on accuracy or price.

## Tweet 2 — the effort knob
*(attach `vulcanbench-v3-effort-curves.png`)*

Every provider sells the same knob: pay more, think harder.

Four flagships, four different answers:

Grok: pays, then plateaus
Sol: a task per step
Fable 5: a round trip
Opus 5: runs backwards — 20→19→18 while the bill triples

## Tweet 3 — the difficulty spectrum
*(attach `vulcanbench-v3-difficulty.png`)*

Task-level view: 14 of 23 tasks now fall to every model we run. Seven separate the field.

Two have survived all 15 configurations — PennyLane Trotter fragmentation and SQLGlot identifier canonicalization.

Best mark yet on PennyLane: 0.40 — Opus 5, LOW effort.

## Tweet 4 — the receipts
*(attach `vulcanbench-v3-receipts.png`)*

Same model. Same 23 tasks. Same tests.

Low effort: $14.07 → 20 solved
High effort: $43.60 → 18 solved

The extra $29.53 bought 3× the tokens, 2.6× the clock, and two fewer solved tasks.

Keep the receipt.

---

## Spare stats for replies

- Opus 5 high spent 45 minutes and $6.37 on a task it solves in 3.9 minutes at low effort.
- High effort's failures aren't wrong answers: 1 wrong vs 4 timeouts. It thinks — it just doesn't finish.
- Only one task in the suite is uniquely bought by high effort (itertools-strip-prefix). Effective price of that one task: an extra $29.53.
- Fable 5 low is the cheapest Claude per solved task ($0.61); Opus 5 low is nine cents behind.
- Our Opus 5 sweep alone: 69 runs, $81.76 total.
- We also caught our own harness lying mid-sweep: a 16K output cap was scoring truncated thinking as wrong answers. Fixed, disclosed in Report No. 10, re-run.

## Caveats to keep handy (if pressed)

- One attempt per task per configuration — a one-task gap is within noise.
- Kimi's 2-h row is a budget-override ablation, not a standard config.
- Opus 5 ran under the raised output cap; Reports 07–08 predate it (only runs that hit the cap could differ).
- Opus 4.8 excluded everywhere: only 5 of 23 tasks on record.
