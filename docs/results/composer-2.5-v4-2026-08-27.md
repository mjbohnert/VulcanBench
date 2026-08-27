# VulcanBench report: cursor-agent:composer-2.5 on v4

_Generated 2026-08-27 · harness: Cursor cloud agents (Composer 2.5, not-fast)_

- **69** runs · **1** model · **23** tasks · **3** repeats
- **69/69** individual runs passed (100.0%)
- **pass@1**: **23/23** (100.0%)
- **pass@3**: **23/23** (100.0%)
- **pass@k**: **23/23** (100.0%)

## Model summary

| Model | Tasks | Runs | pass@1 | pass@3 | pass@k | Avg functional |
|---|---:|---:|---:|---:|---:|---:|
| cursor-agent:composer-2.5 | 23 | 69 | 1.000 | 1.000 | 1.000 | 1.000 |

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
