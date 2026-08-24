# X thread, GLM 5.3 model-vs-harness (ready to paste)

Suggested order: attach the chart to tweet 1, the rest are text replies.
All figures from Report No. 18 (`docs/results/v3-glm53-2026-08/`).

## Tweet 1, the headline
*(attach `vulcanbench-v3-glm53-harness.png`)*

Same model. Same 23 real merged PRs. Same hidden tests. Two harnesses.

GLM 5.3 through its raw API, vs through Z.ai's own ZCode harness.

At max effort: 65% vs 87%.

The scaffolding around a model is worth 22 points.

## Tweet 2, the mechanism

Why the gap? Not smarts. Finishing.

The raw API fails by timing out: it reasons until the clock runs out, and worse with more effort (78 to 74 to 65).

ZCode fails by getting it wrong: zero timeouts, ~5 min flat, scoring 83 / 83 / 87.

## Tweet 3, the knob runs backwards

The same reasoning knob points opposite directions on the same model.

Raw API: pay more, score less.
ZCode: flat, then up.

Judge GLM 5.3 by its default API setting and you rate it 22 points below what it does inside its own product.

## Tweet 4, the method

VulcanBench v3: 23 post-cutoff merged PRs, hidden tests, Docker-isolated, one attempt per cell.

Raw API is metered ($35, all three effort columns). ZCode runs on a GLM Coding Plan.

Subscription-harness numbers are model + product. Don't mix them into a raw-API leaderboard.

---

## Spare stats for replies

- Even the raw API's best column (low, 78%) trails ZCode's worst (82.6%).
- Across all three raw-API columns: 18 timeouts, 1 wrong answer. Across ZCode: 0 timeouts, 11 wrong answers.
- Three tasks the raw API never finishes (all timeouts), ZCode completes. It even solves pennylane-trotter-fragmented at max, a task no model finished in our Qwen report.
- Time per task: raw API 8 to 23 min and climbing with effort; ZCode ~5 min flat.
- ZCode moves ~5x the tokens per task (product system prompt, tools, context management), at $0 marginal cash on the plan.

## Caveats to keep handy (if pressed)

- One attempt per cell, so within-harness effort trends are suggestive; the max-vs-max harness gap (21.8 pts) is larger than the uncertainty, and the timeout-vs-wrong split is categorical.
- This is model plus product harness, not two model APIs. That is the whole point: the delta is the harness.
- ZCode ran glm-5.3, verified from its own session store, not the 5.2 it ships as default.
