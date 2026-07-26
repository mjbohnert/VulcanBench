# VulcanBench Technical Report No. 09 — Does training-data contamination move Claude Opus 5's score?

**July 25, 2026 · 26 runs · 1 model · 1 effort level · 5 languages · total spend $20.94**

A controlled A/B on contamination. Both arms are 13 tasks graded by deterministic hidden tests
in a network-isolated Docker sandbox, run back-to-back with identical settings. They differ in
exactly one property: whether the upstream fix merged **before** Claude Opus 5's May 2026
training cutoff (so the model may have memorised it) or **after** (so it cannot have).

- **Contaminated arm** — the 13 VulcanBench v3 tasks whose upstream PRs merged 2026-02-12
  through 2026-05-21.
- **Clean arm** — the 13 tasks newly built for v4, from PRs merged 2026-06-10 through
  2026-07-19.

Every task pre-validated: gold patch = 1.0, unpatched = 0.0, deterministic over 3 runs.

## Results

| Arm | Score | pass@1 | Genuine misses | Hit wall-clock | Suite cost | Tokens/task | Time/task | $/task | $/solved |
|---|---|---|---|---|---|---|---|---|---|
| Clean (post-cutoff) | 12/13 | 92.3% | 1 | 0 | $4.58 | 38 K | 4.7 min | $0.35 | $0.38 |
| Contaminated (pre-cutoff) | 11/13 | 84.6% | 1 | 1 | $16.36 | 121 K | 9.4 min | $1.26 | $1.49 |

Claude Opus 5, `--effort medium`, one attempt per task, judges disabled. Zero stalls, zero
infrastructure errors, zero retries needed on either arm.

**Genuine misses** are runs that completed and produced a wrong patch. **Hit wall-clock** are
runs still working productively when the budget expired — a different failure mode, and not a
statement about capability.

## Findings

1. **No detectable contamination effect.** Genuine capability misses are **1 versus 1**. The
   headline gap is a single task (7.7 pp), inside the noise floor at n=13. Memorisation of the
   upstream fix did not measurably help.

2. **The visible gap is repo-scale composition, not memorisation.** The contaminated arm carries
   11/13 large-or-xlarge repos against the clean arm's 8/13. Bigger repos cost more per step —
   context-heavy model round trips, slower test runs — which is why the same 13-task shape cost
   **3.6× more** ($16.36 vs $4.58) and ran **2× longer** per task. The one wall-clock loss landed
   there for the same reason. Any cross-suite comparison must report scale mix alongside score.

3. **This is evidence against a large effect, not proof of none.** At 11–12 of 13 the model is
   near ceiling, and a ceiling leaves memorisation little room to show itself. A sharper test
   would need harder tasks or a weaker model, not more tasks at this difficulty.

4. **The frontier-hard tail behaved as designed.** Both surviving misses are the tasks these
   suites deliberately contain: `sqlglot-canonicalize-internal-names` (ran to completion, wrong
   answer) and `regex-leftmost-suffix-candidate` (v4's `veryhard` entry, ~1618-line gold patch).
   `networkx-leiden-communities` remains unsolved at a 3600 s budget while doing real work —
   issuing its own `timeout 600` sub-commands — so a larger budget would buy patience, not
   capability.

5. **Most of the apparent signal was harness bugs.** Before the fixes below, the same comparison
   read 7/13 vs 12/13 — a large gap pointing the *wrong* way for contamination. It was five
   stalled HTTP requests. Each fix moved the contaminated arm up and the arms closer together:

   | Run | Conditions | Contaminated | Clean |
   |---|---|---|---|
   | 1 | high effort, all bugs live | 7/13 | 12/13 |
   | 2 | medium, request ceiling + retry fixed | 10/13 | 12/13 |
   | 3 | medium, all four fixed | **11/13** | **12/13** |

## Harness defects found and fixed for this report

These changed scoring behaviour. Results published before them — including Reports No. 4 and
No. 08 — were produced under the old semantics and are not comparable to this one.

| Defect | Effect on scores |
|---|---|
| Run budget passed as the per-request socket timeout, which also disabled retries | One stalled request consumed a whole task and scored it 0. Six of 13 tasks in the first run died this way; one spent 21 s working and 1785 s blocked. |
| Request ceiling initially set from a pooled latency distribution | 300 s sat below a response that had legitimately completed in 333 s, aborting real work. Round-trip time grows with context, so the tail is per-task, not pooled. Now 600 s. |
| Infrastructure errors dropped the task instead of retrying | The suite reported a tidy pass@1 over a silently smaller denominator, with a different task dropping each run. Two consecutive runs both printed "over 12 tasks" for different reasons. |
| `large` and `xlarge` shared an 1800 s budget despite xlarge allowing 33 % more steps | Neither tier could spend its step allowance at the 10–15 s/step measured on large repos. Runs were cut off mid-work, penalising whichever arm carried more big repos. Now 2700 s / 3600 s. |

## Failure map

| Task | Arm | Scale | Outcome |
|---|---|---|---|
| sqlglot-canonicalize-internal-names | contaminated | large | ✗ completed, wrong patch (1744 s, 298 steps) |
| networkx-leiden-communities | contaminated | xlarge | ✗ still working at the 3600 s budget (274 steps) |
| regex-leftmost-suffix-candidate | clean | xlarge | ✗ completed, wrong patch (1257 s, 104 steps) |
| (remaining 23 tasks) | both | — | ✓ |

## Caveats

- **Wall-clock is not comparable to earlier reports.** These runs executed amd64 sandbox images
  on an arm64 host (~2× emulation overhead on tool calls). Scores are unaffected; time/task and
  $/solved are inflated relative to native runs.
- **n=13 per arm.** One task is 7.7 pp. Only multi-task gaps are meaningful.
- **Single attempt per task.** No pass@k; borderline tasks may flip between runs.
- **One model.** Contamination sensitivity is not necessarily uniform across model families.

## Reproducibility

The two arms are subsets recorded in the committed suite manifests: `pre-2026-05` in
`tasks/v3/suite.json` and `new_in_v4` in `tasks/v4/suite.json`. Materialise them as scratch
suites of symlinks, then run:

```python
import json, os, shutil
for name, src, key in (("v3-pre", "v3", "pre-2026-05"), ("v4-new", "v4", "new_in_v4")):
    ids = json.load(open(f"tasks/{src}/suite.json"))[key]
    root = f"tasks/{name}"; shutil.rmtree(root, ignore_errors=True); os.makedirs(root)
    for t in ids:
        os.symlink(os.path.abspath(f"tasks/{src}/{t}"), os.path.join(root, t))
    json.dump({"tasks": ids, "full": ids}, open(f"{root}/suite.json", "w"), indent=2)
```

```bash
vulcanbench run --suite v3-pre --model anthropic:claude-opus-5 --effort medium --no-judges \
  --repeat 1 --max-concurrency 4 --max-cost 30.00
vulcanbench run --suite v4-new --model anthropic:claude-opus-5 --effort medium --no-judges \
  --repeat 1 --max-concurrency 4 --max-cost 30.00
```

Requires the fixes above (branch `v4-suite`). Pricing: Claude Opus 5 $5/$25 per million tokens.
Run records with full traces, final patches and replay HTML are under `runs/`.

Every task in both arms records `upstream_merged`, so the clean/contaminated split can be
recomputed against any future model's cutoff rather than re-derived by hand. **v4 is clean for a
May 2026 cutoff specifically — not indefinitely.**
