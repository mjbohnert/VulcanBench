# Python Suite v1 — candidate sourcing & measurement worksheet

Target: **23 admitted** Python tasks matching the CHARTER band table
(≈3 anchor / ≈14 mid discriminator / ≈6 hard tail). Source ~30 candidates,
measure each (frontier panel, repeat ≥ 3), admit down to 23.

Status legend: 🔲 to source · 🔬 sourced, needs measurement · ✅ admitted ·
❌ rejected (reason) · ⏸ hold

Admission needs: gold=1.0, base=0.0 on ≥3 fail_to_pass, deterministic ×3, then
repeat ≥ 3 on the panel with per-config pass@1 recorded here.

---

## Carry-over review from v3 (9 Python tasks)

Decisions from the v3 run data (Reports No. 4 / No. 10). Carrying a task over
means re-slicing its repo under `tasks/python-1/` and re-validating — the task
dirs currently live under `tasks/v3/`.

| v3 task | domain | v3 behavior | band | decision |
|---|---|---|---|---|
| oss-flask-teardown-robust | web-async | both-fail at low, solved only at high; cleanest discriminator | mid→tail | ✅ **keep** |
| oss-sqlglot-iso8601-nanos | data-orm | Fable flipped it across effort (borderline) | mid | ✅ **keep** |
| oss-sqlglot-canonicalize-internal-names | data-orm | 0-for-27; 0.50 partials → hard but approachable | tail | ✅ **keep as ceiling** — verified 2026-08-17 (gold=1.0, base=0.0, det ×3, docker) |
| oss-pennylane-trotter-fragmented | scientific | 0-for-all; one 0.40 partial (Opus 5 low) | tail | ✅ **keep as ceiling** — verified 2026-08-17 (gold=1.0, base=0.0, det ×3, docker) |
| oss-networkx-leiden-communities | scientific | solved at low, DNF (60-min timeout) at high — mostly harness | — | ⏸ re-scope budget, then re-measure; else drop |
| oss-aiohttp-upgrade-deferred | web-async | solved by all at low/med; DNF at high | anchor? | ⏸ candidate easy anchor only |
| oss-sqlglot-qualify-lateral-star | data-orm | all-pass floor | floor | ❌ drop (dead-weight) |
| oss-packaging-range-prerelease-policy | cli-tooling | all-pass floor | floor | ❌ drop (dead-weight) |
| oss-more-itertools-interleave-empty | stdlib-utility | all-pass floor, "easy" | floor | ❌ drop (dead-weight) |

Net carry-over: **2 confirmed keeps** (flask-teardown, sqlglot-iso8601-nanos) +
**2 verified ceilings** (canonicalize, pennylane) = 4 solid, **2 re-measure**,
**3 dropped**. So we need roughly **17 net-new** sourced Python tasks (mostly mid).

✅ Ceiling-task check DONE (2026-08-17): both `sqlglot-canonicalize-internal-names`
and `pennylane-trotter-fragmented` validate clean in the Docker sandbox — gold=1.0,
pre-patch=0.0, deterministic over 3 runs. They are **fair, solvable ceilings**, not
broken tasks. This also answers the reviewer directly: v3's 91.3% ceiling was two
genuinely-hard tasks, not grading bugs — a fair ceiling that simply stopped
discriminating once every frontier model failed it.

---

## Net-new sourcing (fill toward 23)

Harvested 2026-08-17 by `scripts/mine_oss_prs.py --per-repo 20` (119 raw hits →
shortlist below). Filters applied: dropped dependency/CI bumps, version-drop PRs,
typing-only (`TYP:`) PRs, release rollups/backports, docs-only, and
`sympy#30133` (**AI-authored — contamination risk, excluded**). All ≥ 2026-02-01.
Shortlist = 22 net-new; measure each (repeat ≥ 3) and admit toward the band.

Legend: band guess is pre-measurement (E=easy/anchor, M=mid, H=hard/tail).

### web-async
- 🔬 flask#5917 (02-12, 11/86, 7f) — fix `provide_automatic_options` override · M
- 🔬 tornado#3634 (06-08, 26/12, 4f) — curl_httpclient: reset curl obj before pooling · M

### data-orm  (≤3/repo — sqlglot already has 2 carried, room for 1)
- 🔬 pandas#66794 (08-15, 39/5, 3f) — `isin` false matches above 2**53 (mixed int/float) · M
- 🔬 pandas#66753 (08-13, 73/24, 5f) — UTC→local conversion wrapped int64 silently · MH
- 🔬 pandas#66791 (08-15, 10/1, 4f) — `convert_dtypes` OverflowError on out-of-range · EM
- 🔬 sqlglot#8161 (08-14, 91/35, 9f) — optimizer: don't normalize identifiers needing quoting · MH
- 🔬 polars#28799 (08-14, 33/42, 2f) — merge join with coalesce + empty suffix · M

### parsing
- 🔬 pydantic#13659 (08-16, 23/22, 2f) — fix application of other constraints in pipeline · M
- 🔬 lark#1592 (07-18, 351/17, 14f) — add `Lark.scan()` for grammar matches in text · H
- ✅ marshmallow#2994 (07-22, 11/0, 4f) — Enum allow None default · EM

### scientific  (pennylane/networkx each already have 1 carried)
- 🔬 networkx#8813 (08-04, 23/365, 3f) — BUG: reverse the map returned by vf2pp functions · M
- 🔬 numpy#32292 (08-14, 41/41, 2f) — don't assume strides are a multiple of itemsize · H
- 🔬 sympy#30144 (07-27, 24/3, 2f) — manualintegrate: ratint fallback for rational fns · MH

### stdlib-utility
- ✅ more-itertools#1211 (07-13, 22/14, 2f) — fix stability in `running_min`/`running_max` · M
  — **BUILT + validated 2026-08-17** as `oss-more-itertools-running-minmax-stable`
  (gold=1.0, base=0.0, det ×3, base image, `PYTHONPATH=.`). 4 fail_to_pass (bounded
  tie windows) + 4 pass_to_pass. Band still a guess until measured.
- ✅ more-itertools#1182 (06-17, 13/0, 3f) — support negative start/stop in `iter_index` · M
- ✅ attrs#1571 (08-01, 42/13, 5f) — add `ne` validator · EM

### cli-tooling
- ✅ click#3678 (07-10, 53/4, 6f) — fix parsing when a parameter is named `help` · M
  — **BUILT + validated 2026-08-17** as `oss-click-param-named-help` (gold=1.0,
  base=0.0, det ×3, base image, `PYTHONPATH=src`). Band still a guess until measured.
- ✅ click#3677 (07-08, 29/15, 3f) — validate `style()` color arguments · EM
- 🔬 poetry#10987 (08-01, 17/1, 3f) — solver: resolve extra deps missing from ... · MH

### concurrency
- 🔬 anyio#1218 (07-11, 12/2, 3f) — CapacityLimiter raised trio.WouldBlock incorrectly · M
- 🔬 anyio#1228 (07-20, 64/11, 5f) — add `move_on_at()` / `fail_at()` · M
- 🔬 trio#3474 (08-11, 17/0, 3f) — track max buffer usage in memory channel stats · EM

Full raw harvest JSON: scratchpad `mine_all.json` (119 rows, all domains).

### Repo-set maintenance (for next mining run)
- `tiangolo/typer` → **`fastapi/typer`** (moved); `tiangolo/fastapi` → **`fastapi/fastapi`**.
  Both returned "cannot be searched" this run — stale paths. Fix in
  `scripts/mine_oss_prs.py DOMAIN_REPOS`.
- `encode/starlette` and `encode/httpx` returned nothing — likely collateral of the
  GitHub 503 storm during this run, not empty. Re-mine web-async when the API settles.

---

## Measurement log (repeat ≥ 3, frontier panel)

Panel: Opus 5, GPT-5.6 Sol, Grok 4.5, + frugal ref (Haiku 4.5 / Kimi K3).

| task | Opus5 p@1 (n) | Sol p@1 (n) | Grok p@1 (n) | ref p@1 (n) | median | band | admit? |
|---|---|---|---|---|---|---|---|
| _(fill as measured)_ | | | | | | | |

## Running band tally (target in parens)

Counts well-formed built tasks (gold=1.0/base=0.0/det ×3, docker); final band
placement pending frontier measurement — see MEASUREMENT_PLAN.md.

## ✅ 23 / 23 built + validated — COMPLETE (2026-08-17)

All gold=1.0/base=0.0/deterministic ×3 in the Docker sandbox. By domain:

- **web-async (2):** oss-flask-teardown-robust (tail, carried), oss-flask-automatic-options-override
- **data-orm (3):** oss-sqlglot-iso8601-nanos (carried), oss-sqlglot-canonicalize-internal-names (ceiling, carried), oss-sqlglot-semistructured-case (7-file)
- **parsing (3):** oss-marshmallow-enum-none-default, oss-lark-scan, oss-lark-earley-ambiguous-ignore
- **scientific (4):** oss-networkx-leiden-communities (carried), oss-networkx-vf2pp-mapping-direction, oss-pennylane-trotter-fragmented (ceiling, carried), oss-sympy-manualintegrate-ratint
- **stdlib-utility (5):** oss-more-itertools-running-minmax-stable, oss-more-itertools-iter-index-negative, oss-more-itertools-numeric-range-eq, oss-attrs-ne-validator, oss-attrs-generator-on-setattr
- **cli-tooling (3):** oss-click-param-named-help, oss-click-style-validate-color, oss-click-progressbar-final-position
- **concurrency (3):** oss-anyio-trio-wouldblock, oss-anyio-fail-at-deadline, oss-trio-memory-channel-peak-buffer

18 net-new + 5 carried from v3. New per-task images: anyio-1191, trio-3474, sympy-29877.
Repo cap (≤3/repo) respected everywhere. **Next: measure per MEASUREMENT_PLAN.md.**

### Notes / lessons for future suites
- ⚠️ **oss-aiohttp-upgrade-deferred EXCLUDED** (gold scored 0.0 in the rebuilt
  aiohttp-13016 image — env drift vs v3). Not counted; re-mined web-async instead.
- **Compiled-package constraint:** the grader overlays workspace source via
  `PYTHONPATH`, so only **pure-Python** *packages under test* work. Ruled out
  pandas/numpy/polars/pydantic-core candidates (compiled cores). A package with
  compiled *dependencies* is still fine (deps are pip-installed in the image).
- **pip#14220 skipped** — the bug is Python-3.15+ specific; the base sandbox runs
  3.12, so it doesn't reproduce.
- **git apply is strict:** `gh pr diff` context can drift from the sliced base
  (passes `patch -p1` but fails the validator's `git apply`). Fix: regenerate the
  gold patch via `git diff` in a throwaway git repo of the slice (see
  oss-attrs-generator-on-setattr).
- **Image tasks** run pytest with `-c /dev/null` to bypass the sliced repo's own
  pytest plugins/config (e.g. anyio_mode, filterwarnings=error).
- **click#3728 dropped** — it fixes output *nondeterminism*, which conflicts with
  the validator's "base deterministic ×3" gate.
