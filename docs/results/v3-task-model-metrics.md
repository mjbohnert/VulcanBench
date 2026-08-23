# v3 task × model metrics (compiled)

Compiled from published snapshots. The **23-task suite is v3**. v1 (52 tasks) and v2 (35 tasks) use a different task set — **zero overlap** with these 23.

Sources: `docs/results/v3-kimi-k3-2026-07.md` (pooled), Report 4 (`v3-3way-2026-07/model-card.md`, effort split), Report 10 (`v3-opus5-effort-2026-07/model-card.md`), Report 09 (`v4-contamination-2026-07/results.json`, Opus 5 medium cost/time on 13 tasks).

**How to read n=3:** Grok / Fable / Sol columns in the pooled table are **one run at low + medium + high**, not three repeats of one effort. Haiku and Kimi are a **single** attempt. Opus 4.8 ran only **5 of 23** tasks. Per-task USD and wall-clock were not published except for Opus 5 Report 09.

## Model rollups (suite-level)

| Model | Tasks | Runs | pass@1 | pass@k | Avg total | Cost $ | Avg time |
|---|---|---|---|---|---|---|---|
| openai:grok-4.5 | 23 | 69 | 0.8841 | 0.9130 | 0.8200 | 18.82 | 225 s |
| anthropic:claude-fable-5 | 23 | 69 | 0.8551 | 0.9130 | 0.7711 | 49.33 | 229 s |
| openai:gpt-5.6-sol | 23 | 69 | 0.8261 | 0.8696 | 0.7804 | 28.59 | 169 s |
| anthropic:claude-haiku-4-5 | 23 | 23 | 0.7826 | 0.7826 | 0.7398 | 9.14 | 305 s |
| kimi:kimi-k3 | 23 | 23 | 0.7391 | 0.7391 | 0.6566 | 16.84 | 1087 s |
| anthropic:claude-opus-4-8 | **5** | 5 | 0.6000 | 0.6000 | 0.5765 | 5.44 | 306 s |
| anthropic:claude-opus-5 low | 23 | 23 | 0.870 | — | — | 14.07 | 5.2 min |
| anthropic:claude-opus-5 medium | 23 | 23 | 0.826 | — | — | 24.09 | 7.6 min |
| anthropic:claude-opus-5 high | 23 | 23 | 0.783 | — | — | 43.60 | 13.6 min |

## Pooled pass@1 (solved/attempts)

| Task | Grok 4.5 | Fable 5 | Sol | Haiku 4.5 | Kimi K3 | Opus 4.8 |
|---|---|---|---|---|---|---|
| flask-teardown-robust | 2/3 | 2/3 | 1/3 | 1/1 | 1/1 | — |
| aiohttp-upgrade-deferred | 2/3 | 3/3 | 2/3 | 1/1 | 0/1 | — |
| sqlglot-qualify-lateral-star | 3/3 | 3/3 | 3/3 | 1/1 | 1/1 | — |
| sqlglot-iso8601-nanos | 3/3 | 2/3 | 3/3 | 1/1 | 0/1 | — |
| packaging-range-prerelease-policy | 3/3 | 3/3 | 3/3 | 1/1 | 1/1 | — |
| more-itertools-interleave-empty | 3/3 | 3/3 | 3/3 | 1/1 | 1/1 | — |
| networkx-leiden-communities | 3/3 | 1/3 | 3/3 | 0/1 | 0/1 | 1/1 |
| sqlglot-canonicalize-internal-names | 0/3 | 0/3 | 0/3 | 0/1 | 0/1 | 0/1 |
| pennylane-trotter-fragmented | 0/3 | 0/3 | 0/3 | 0/1 | 0/1 | 0/1 |
| itertools-strip-prefix | 3/3 | 3/3 | 0/3 | 0/1 | 1/1 | 1/1 |
| jiff-signdur-panic | 3/3 | 3/3 | 3/3 | 1/1 | 1/1 | — |
| jiff-date-day-lt1 | 3/3 | 3/3 | 3/3 | 1/1 | 1/1 | — |
| jiff-strftime-negpad | 3/3 | 3/3 | 3/3 | 1/1 | 0/1 | — |
| zod-invert-codec | 3/3 | 3/3 | 3/3 | 1/1 | 1/1 | — |
| zod-proto-catchall | 3/3 | 3/3 | 3/3 | 1/1 | 1/1 | — |
| hono-request-bytes | 3/3 | 3/3 | 3/3 | 1/1 | 1/1 | — |
| hono-client-header-merge | 3/3 | 3/3 | 3/3 | 1/1 | 1/1 | — |
| semver-truncate | 3/3 | 3/3 | 3/3 | 0/1 | 1/1 | 1/1 |
| semver-inc-dotted-prerelease | 3/3 | 3/3 | 3/3 | 1/1 | 1/1 | — |
| semver-xrange-order | 3/3 | 3/3 | 3/3 | 1/1 | 1/1 | — |
| chi-readfrom-tee-doublecount | 3/3 | 3/3 | 3/3 | 1/1 | 1/1 | — |
| cobra-noduplicateargs | 3/3 | 3/3 | 3/3 | 1/1 | 1/1 | — |
| pflag-uintslice-hex | 3/3 | 3/3 | 3/3 | 1/1 | 1/1 | — |

## Effort split (Report 4: Grok / Fable / Sol at low · medium · high)

`✓` = functional 1.0. Fable `aiohttp` is API-refusal + Opus 4.8 fallback (all three passed). Remaining 16 tasks: `✓ ✓ ✓` for all three models.

| Task | Grok l/m/h | Fable l/m/h | Sol l/m/h |
|---|---|---|---|
| flask-teardown-robust | ✗ ✓ ✓ | ✗ ✓ ✓ | ✗ ✗ ✓ |
| aiohttp-upgrade-deferred | ✗ ✓ ✓ | ✓ ✓ ✓ †fallback | ✗ ✓ ✓ |
| sqlglot-iso8601-nanos | ✓ ✓ ✓ | ✓ ✗ ✓ | ✓ ✓ ✓ |
| networkx-leiden-communities | ✓ ✓ ✓ | ✓ ✗ ✗ | ✓ ✓ ✓ |
| sqlglot-canonicalize-internal-names | ✗ ✗ ✗ | ✗ ✗ ✗ | ✗ ✗ ✗ |
| pennylane-trotter-fragmented | ✗ ✗ ✗ | ✗ ✗ ✗ | ✗ ✗ ✗ |
| itertools-strip-prefix | ✓ ✓ ✓ | ✓ ✓ ✓ | ✗ ✗ ✗ |
| *(other 16)* | ✓ ✓ ✓ | ✓ ✓ ✓ | ✓ ✓ ✓ |

## Opus 5 (Report 10) — score at low / medium / high

16 tasks are `1.0 / 1.0 / 1.0`. The seven that moved:

| Task | low | medium | high |
|---|---|---|---|
| flask-teardown-robust | 1.0 | 1.0 | 0.67 |
| aiohttp-upgrade-deferred | 1.0 | 1.0 | 0.0 (DNF 45min (solved 3.9min at low)) |
| sqlglot-iso8601-nanos | 1.0 | 0.67 | 1.0 |
| networkx-leiden-communities | 1.0 | 1.0 | 0.0 (DNF 60min (solved 11.6min at low)) |
| sqlglot-canonicalize-internal-names | 0.5 | 0.5 | 0.0 (DNF 45min) |
| pennylane-trotter-fragmented | 0.4 | 0.0 (DNF 60min) | 0.0 (DNF 60min) |
| itertools-strip-prefix | 0.0 | 0.0 | 1.0 |

## Opus 5 medium — cost and time (Report 09, 13 of 23 tasks)

Only published per-task USD / duration. Times inflated (~2×) because amd64 images ran on arm64.

| Task | functional | outcome | duration_s | steps | cost_usd |
|---|---|---|---|---|---|
| flask-teardown-robust | 1.0 | solved | 431.7 | 200 | 1.5499 |
| networkx-leiden-communities | 0.0 | wall_clock | 3606.0 | 274 | 7.6818 |
| sqlglot-canonicalize-internal-names | 0.5 | genuine_miss | 1743.9 | 298 | 4.9048 |
| itertools-strip-prefix | 1.0 | solved | 315.8 | 104 | 0.4224 |
| jiff-signdur-panic | 1.0 | solved | 59.8 | 58 | 0.1201 |
| jiff-date-day-lt1 | 1.0 | solved | 80.9 | 74 | 0.1259 |
| jiff-strftime-negpad | 1.0 | solved | 192.9 | 142 | 0.5108 |
| zod-invert-codec | 1.0 | solved | 229.7 | 130 | 0.5267 |
| zod-proto-catchall | 1.0 | solved | 61.5 | 62 | 0.1404 |
| hono-request-bytes | 1.0 | solved | 115.2 | 42 | 0.0732 |
| semver-truncate | 1.0 | solved | 178.5 | 52 | 0.1158 |
| chi-readfrom-tee-doublecount | 1.0 | solved | 185.4 | 42 | 0.1142 |
| cobra-noduplicateargs | 1.0 | solved | 95.7 | 42 | 0.0693 |

## v1 / v2 (not these 23 tasks)

| Suite | Tasks | Models | GPT-5.5 pass@1 | Opus 4.8 pass@1 | GLM 5.2 pass@1 | Source |
|---|---|---|---|---|---|---|
| v1 | 52 | 3 | 0.7885 | 0.7885 | 0.7115 | `docs/results/v1-compare-2026-06.json` |
| v2 | 35 | 3 | 1.0000 | 0.9714 | 0.9048 | `docs/results/v2-results.json` |

Per-task solve rates for v1/v2 live in those JSON files under `tasks[]` (`solved` / `attempts` only).

