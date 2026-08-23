# Metrics (v1)

VulcanBench scores each run on five metrics plus a weighted **total**. Any metric
may be `null` with a `reason` when its analyzer or judge is unavailable — scores
are never fabricated.

## functional

Hidden verifier tests (`fail_to_pass` / `pass_to_pass` in task metadata) run
after the agent finishes. Score is `1.0` when all required tests pass, else
proportional to pass rate.

## quality

Static analysis over changed files:

- **Python**: ruff lint + radon complexity/maintainability
- **Rust**: `cargo fmt` + `cargo clippy`
- **Go / TypeScript / Java**: toolchain-dependent; `null` when tools absent

## security

Static security analysis:

- **Python**: bandit
- **Rust**: `cargo audit` + unsafe-delta penalty
- **Go**: gosec (when installed)
- **JS/TS**: npm audit (when applicable)

## efficiency

Derived from token usage and agent steps (lower is better, normalized to 0–1).

## human_like

3-judge LLM ensemble (on by default, reusing the run model unless
`--judge-model` is set). Use `--no-judges` for functional-only runs.

## total

Weighted combination of the five metrics (see `harness/evaluator/scorer.py`).
Functional failures dominate; ancillary metrics refine ranking among passes.

## cost

Per-run USD estimate from the built-in pricing table (`VULCANBENCH_PRICING` to
override). Unknown models report `cost_usd: null`.

## Task × model cells

Published suite snapshots (v1 three-model, v2 repeats, v3 effort sweeps) ranked
**models** on pass@1, avg total, cost, and latency — but the per-task table only
stored `solved/attempts`. That hid the stories those runs actually produced:

- **Partial credit.** pass@1 is binary (`functional == 1.0`). Opus 5's 0.40
  PennyLane attempt scored as a miss; `avg_total` / `avg_functional` keep it.
- **Price of a pass.** Fable 5 and Grok 4.5 can post the same 21/23 with a 3×
  cost gap. Cost belongs on the cell, not only the model roll-up.
- **Time.** Kimi K3's v3 column was ~5× slower than Sol at similar pass@1.
- **Effort pooling.** Flask teardown on v3 is a high-only solve. Pooling
  low/medium/high into `2/3` looks like flaky pass@1. Cells stay pooled at
  `(task, model)` for cross-model comparison; `efforts[]` splits the same
  attempts when `--effort` was recorded.

`vulcanbench report` therefore emits, for every `(task, model)`:

| Field | Meaning |
|---|---|
| `solved` / `failed` / `attempts` | Succeed/fail counts (`functional >= 1.0` vs not) |
| `solve_rate` | pass@1 on that cell (mean over repeats) |
| `pass_at_k` | 1 if any attempt solved the task |
| `avg_total`, `avg_functional`, … | Mean of the five metrics + weighted total |
| `total_cost_usd` / `avg_cost_usd` | Sum and mean USD; `cost_known` is false if any run is missing a price |
| `avg_duration_s` | Mean sandbox wall-clock |
| `total_tokens` / `avg_tokens` | Prompt+completion tokens |
| `efforts` | Same fields, one entry per recorded effort (omitted when none) |

Markdown renders three matrices (pass@1, total cost, avg time) plus a Cells
table with every field. Reproduce from `./runs`:

```bash
vulcanbench report --suite v3 -o report.md
vulcanbench report --suite v3 -f json -o report.json
```
