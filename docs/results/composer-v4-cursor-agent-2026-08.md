# VulcanBench report: cursor-agent:composer-2.5 on v4

_Generated 2026-08-23 · harness: Cursor cloud agents (first-party Task subagents, no API key)_

- **69** runs · **1** model · **23** tasks · **3** repeats
- **57/69** individual runs passed (82.6%)
- **pass@1** (repeat 1 only): **11/23** (47.8%)
- **pass@3** (3/3 on all repeats): **11/23** (47.8%)
- **pass@k** (≥1 pass across 3 tries): **23/23** (100%)

> ⚠️ **12 repeat-1 failures** were caused by host-verifier toolchain mismatches (pytest inheriting parent coverage settings, wrong Rust/Go versions, missing `tsx` for Hono). Repeats 2–3 went **46/46** after `harness/verifier.py` was fixed. Treat repeat-1 scores as environment artifacts, not model capability.

> ⚠️ **Token estimates cover repeat 1 only.** Repeats 2–3 were finalized without cloud-agent transcripts (`steps: 0`). Multiply repeat-1 per-run averages by 3 for a rough full-suite cost band.

## Model summary

| Model | Tasks | Runs | pass@1 | pass@3 | pass@k | Avg functional | Est. cost $† | Avg time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| cursor-agent:composer-2.5 | 23 | 69 | 0.478 | 0.478 | 1.000 | 0.826 | 0.069‡ | 1489 |

† Composer list rates: $0.50/M input, $2.50/M output (reasoning billed as output).  
‡ Repeat-1 transcripts only; true 3× cost likely **~$0.21** if per-run token use is similar.

### Repeat-1 token totals (for API cost estimation)

| | Tokens |
|---|---:|
| Input | 1,574 |
| Reasoning (inference) | 20,370 |
| Output | 7,022 |
| **Total** | **28,966** |

```
est_cost ≈ (input × $0.50 + (reasoning + output) × $2.50) / 1_000_000
repeat 1 ≈ $0.069
```

## Per-task results

| task | pass (3 runs) | avg functional | avg time (s) | input† | reasoning† | output† | est. cost $† |
|---|---:|---:|---:|---:|---:|---:|---:|
| oss-aiohttp-upgrade-deferred | 3/3 | 1.000 | 1287 | 37 | 423 | 105 | 0.0013 |
| oss-chi-discard-readfrom | 2/3 | 0.667 | 1647 | 12 | 276 | 109 | 0.0010 |
| oss-chrono-offset-minute-clamp | 3/3 | 1.000 | 1504 | 13 | 329 | 108 | 0.0011 |
| oss-hono-client-header-merge | 2/3 | 0.667 | 1613 | 15 | 453 | 168 | 0.0016 |
| oss-hono-etag-star-match | 2/3 | 0.667 | 1614 | 13 | 320 | 103 | 0.0011 |
| oss-hono-trie-empty-wildcard | 2/3 | 0.667 | 1615 | 14 | 441 | 88 | 0.0013 |
| oss-hono-url-param-prefix | 2/3 | 0.667 | 1616 | 13 | 293 | 87 | 0.0010 |
| oss-jiff-strftime-lenient | 3/3 | 1.000 | 1504 | 13 | 361 | 74 | 0.0011 |
| oss-more-itertools-interleave-empty | 2/3 | 0.667 | 1289 | 38 | 95 | 58 | 0.0004 |
| oss-more-itertools-subfactorial | 2/3 | 0.667 | 1359 | 37 | 113 | 70 | 0.0005 |
| oss-packaging-licenseref-plus | 2/3 | 0.667 | 1361 | 37 | 195 | 66 | 0.0007 |
| oss-packaging-range-prerelease-policy | 2/3 | 0.667 | 1368 | 42 | 105 | 81 | 0.0005 |
| oss-pennylane-trotter-fragmented | 3/3 | 1.000 | 1369 | 41 | 121 | 118 | 0.0006 |
| oss-pflag-custom-isboolflag | 3/3 | 1.000 | 1652 | 12 | 207 | 96 | 0.0008 |
| oss-pflag-uintslice-hex | 3/3 | 1.000 | 1296 | 53 | 166 | 72 | 0.0006 |
| oss-regex-leftmost-suffix-candidate | 3/3 | 1.000 | 1505 | 14 | 839 | 120 | 0.0024 |
| oss-semver-inc-dotted-prerelease | 3/3 | 1.000 | 1646 | 13 | 440 | 89 | 0.0013 |
| oss-semver-tilde-prerelease-bound | 3/3 | 1.000 | 1646 | 13 | 158 | 132 | 0.0007 |
| oss-semver-xrange-order | 3/3 | 1.000 | 1647 | 12 | 236 | 71 | 0.0008 |
| oss-sqlglot-iso8601-nanos | 2/3 | 0.667 | 1420 | 26 | 283 | 150 | 0.0011 |
| oss-sqlglot-qualify-lateral-star | 2/3 | 0.667 | 1422 | 26 | 357 | 162 | 0.0013 |
| oss-sqlglot-udtf-chained-alias | 2/3 | 0.667 | 1502 | 14 | 378 | 122 | 0.0013 |
| oss-time-strftime-truncated-padding | 3/3 | 1.000 | 1648 | 16 | 201 | 94 | 0.0007 |

† Per-task token columns are averaged across all 3 repeats; only repeat 1 has non-zero values.

## Per-repeat breakdown

| repeat | runs | pass | fail |
|---:|---:|---:|---:|
| 1 | 23 | 11 | 12 |
| 2 | 23 | 23 | 0 |
| 3 | 23 | 23 | 0 |

### Tasks at 3/3 (pass@3)

oss-aiohttp-upgrade-deferred, oss-chrono-offset-minute-clamp, oss-jiff-strftime-lenient, oss-pennylane-trotter-fragmented, oss-pflag-custom-isboolflag, oss-pflag-uintslice-hex, oss-regex-leftmost-suffix-candidate, oss-semver-inc-dotted-prerelease, oss-semver-tilde-prerelease-bound, oss-semver-xrange-order, oss-time-strftime-truncated-padding

### Tasks at 2/3 (repeat-1 environment failure)

oss-chi-discard-readfrom, oss-hono-client-header-merge, oss-hono-etag-star-match, oss-hono-trie-empty-wildcard, oss-hono-url-param-prefix, oss-more-itertools-interleave-empty, oss-more-itertools-subfactorial, oss-packaging-licenseref-plus, oss-packaging-range-prerelease-policy, oss-sqlglot-iso8601-nanos, oss-sqlglot-qualify-lateral-star, oss-sqlglot-udtf-chained-alias

## Methodology

1. `vulcanbench cursor-agent prepare --task <id> --suite v4 --repeat <n>`
2. Composer 2.5 cloud agent solves task in prepared workspace (first-party Task subagent)
3. Transcript fetched via `cursor-cloud batch-fetch-details`
4. `vulcanbench cursor-agent finalize <run_dir> --transcript <path> --bc-id <id>`
5. VulcanBench declarative verifier grades functional score (0.0–1.0)

**Billing:** subscription (Cursor cloud agent). Token counts estimated from transcript (`chars/4`); not provider-reported.

**Raw data:** `runs/<task-id>-<uuid>/summary.json` (gitignored; 69 files on benchmark VM).

**Regenerate:**

```bash
python scripts/composer_suite_report.py --model cursor-agent:composer-2.5 --suite v4
```
