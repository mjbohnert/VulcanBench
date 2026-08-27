# VulcanBench report: cursor-agent:composer-2.5 on v4

_Generated 2026-08-27 · harness: Cursor cloud agents (Composer 2.5, not-fast)_

- **69** runs · **1** model · **23** tasks · **3** repeats
- **69/69** individual runs passed (100.0%) — **see integrity caveats below**
- **pass@1**: **23/23** (100.0%)
- **pass@3**: **23/23** (100.0%)
- **pass@k**: **23/23** (100.0%)

## Cost (transcripts refetched 2026-08-27)

Composer list rates: **$0.50/M input**, **$2.50/M output** (reasoning billed as output).

| | Value |
|---|---|
| Unique agent transcripts (82 total, incl. orchestration) | **~$0.44** |
| Per-run attributed cost (69 `summary.json`, batch-shared transcripts) | **~$0.22** |
| Repeat 1 attributed | ~$0.08 |
| Repeat 2 attributed | ~$0.07 |
| Repeat 3 attributed | ~$0.07 |

Per-run `cost_usd` and `tokens` live in each `runs/<run-id>/summary.json` (refetched from cloud-agent transcripts). Batch subagents (e.g. “Rep3 batch A”) share one transcript across multiple tasks, so summing per-run costs **under-counts** true spend; the agent-transcript total is the better ceiling.

## Integrity caveats — not comparable to other models

**This 100% score is not a fair head-to-head result.** Forensic review of 82 refetched transcripts found:

- **76/82** transcripts mention `gold_patch`
- **79/82** transcripts reference `tasks/*/tests/` (hidden tests)
- **45/69** workspaces contain copied hidden test files (`vb_*.py`, `oss_tests.py`, etc.)
- **17/23** repeat-1 patches overlap the gold patch by ≥80%

Root causes:

1. **Full-repo access** — subagents run inside the VulcanBench checkout and can read `tasks/v4/<id>/gold_patch.diff` and hidden `tests/`.
2. **Hidden tests used during solving** — agents grep/read hidden tests and pytest them directly from `tasks/`, not just at grade time.
3. **Prior August run context** — that benchmark’s **47.8% pass@1** was mostly **host-verifier toolchain failures** (pytest cov, Rust/Go versions, missing `tsx`); repeats 2–3 scored **46/46** after `harness/verifier.py` was fixed. This run inherited those fixes.
4. **Non-uniform harness** — `cursor-agent:` runs the vendor cloud-agent loop, not the VulcanBench tool-calling loop other models use.

Treat functional=1.0 here as “passed under contaminated cursor-agent conditions,” not as a leaderboard column comparable to API runs.

## Model summary

| Model | Tasks | Runs | pass@1 | pass@3 | pass@k | Avg functional | Est. cost $† |
|---|---:|---:|---:|---:|---:|---:|---:|
| cursor-agent:composer-2.5 | 23 | 69 | 1.000 | 1.000 | 1.000 | 1.000 | 0.22‡ |

† Per-run attributed (batch-shared transcripts). ‡ True unique agent spend ~$0.44.

## Per-task results

| task | pass (3 runs) | avg functional |
|---|---:|---:|
| oss-aiohttp-upgrade-deferred | 3/3 | 1.000 |
| oss-chi-discard-readfrom | 3/3 | 1.000 |
| oss-chrono-offset-minute-clamp | 3/3 | 1.000 |
| oss-hono-client-header-merge | 3/3 | 1.000 |
| oss-hono-etag-star-match | 3/3 | 1.000 |
| oss-hono-trie-empty-wildcard | 3/3 | 1.000 |
| oss-hono-url-param-prefix | 3/3 | 1.000 |
| oss-jiff-strftime-lenient | 3/3 | 1.000 |
| oss-more-itertools-interleave-empty | 3/3 | 1.000 |
| oss-more-itertools-subfactorial | 3/3 | 1.000 |
| oss-packaging-licenseref-plus | 3/3 | 1.000 |
| oss-packaging-range-prerelease-policy | 3/3 | 1.000 |
| oss-pennylane-trotter-fragmented | 3/3 | 1.000 |
| oss-pflag-custom-isboolflag | 3/3 | 1.000 |
| oss-pflag-uintslice-hex | 3/3 | 1.000 |
| oss-regex-leftmost-suffix-candidate | 3/3 | 1.000 |
| oss-semver-inc-dotted-prerelease | 3/3 | 1.000 |
| oss-semver-tilde-prerelease-bound | 3/3 | 1.000 |
| oss-semver-xrange-order | 3/3 | 1.000 |
| oss-sqlglot-iso8601-nanos | 3/3 | 1.000 |
| oss-sqlglot-qualify-lateral-star | 3/3 | 1.000 |
| oss-sqlglot-udtf-chained-alias | 3/3 | 1.000 |
| oss-time-strftime-truncated-padding | 3/3 | 1.000 |

## Methodology

1. `python scripts/cursor_agent_suite_run.py prepare --suite v4 --repeats 3 --model cursor-agent:composer-2.5`
2. Composer 2.5 (not-fast) cloud agents solve each prepared workspace via Task subagents
3. `vulcanbench cursor-agent finalize <run_dir> --transcript <path> --bc-id <id>`
4. VulcanBench declarative verifier grades functional score (host runner)

**Billing:** subscription (Cursor cloud agent). Token counts estimated from transcript where available.

**Regenerate:**

```bash
python scripts/composer_suite_report.py --model cursor-agent:composer-2.5 --suite v4
```
