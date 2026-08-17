# VulcanBench Python Suite v1 — the language-focused discrimination tier

CLI name: `python-1` (`vulcanbench run --suite python-1`). Display name:
**VulcanBench Python Suite v1**. Target size: **23 tasks** (fixed), Python only.

## Why this suite exists (the v3 lesson)

v3 mixed five languages and **saturated**: across 15 configs and 6 model families,
every score landed in a 5-point band (17–23 → 73.9–91.3%). Post-mortem of the v3
run data:

- **16 of 23 tasks** were passed by *every* frontier config → zero signal (floor).
- **2 of 23** were solved by *no* config → zero signal (ceiling); the 91.3% "upper
  bound" a reviewer flagged is exactly `21/23`, i.e. those two never-solved tasks.
- **~5 tasks** did all the discriminating — and several of those flipped for
  *harness* reasons (45/60-min wall-clock DNFs, a 16K output-cap bug) rather than
  capability, so the true capability-discriminating set was ~3 tasks.

Python Suite v1 is a direct response. One language removes the language/capability
confound. The composition is engineered to keep the middle of the distribution
populated so the suite *ranks* frontier models instead of measuring coin-flips.

## The three non-negotiables (all baked in from task #1)

1. **Difficulty band, not a floor.** Compose so the **median frontier model lands
   ~50–70% aggregate pass@1**, with a genuine hard tail. A task that *every*
   measured frontier config solves is **floor dead-weight — reject it** (keep at
   most 3 as deliberate calibration anchors). A task *no* config solves is kept
   only if it is verified fair and solvable (a gold patch passes) — ceiling, capped
   at ~3.
2. **Every score carries error bars.** Admission and all published results are
   **repeat ≥ 3** per task per config. A 1-task margin over a single run is noise;
   v3 never had the repeats to tell a real gap from variance. No task is admitted
   or ranked on `n=1`.
3. **Harness failure ≠ capability failure.** A wall-clock DNF or provider/sandbox
   error is scored and reported **separately** from a wrong answer (see
   `harness.suite.is_infrastructure_error`; DNF surfaces in the `timed_out`
   column). Budgets are set per repo scale so a solvable task is not failed by the
   clock. If a task only "discriminates" because big repos time out, it is a
   harness artifact — fix the budget, do not count it as signal.

## Difficulty composition (the 23-task budget)

Compose ~30 measured candidates down to 23 admitted, targeting this shape (frontier
= the current frontier panel, see Measurement):

| Band | Frontier pass@1 | Count | Role |
|---|---|---|---|
| Anchor (easy) | ~90–100% | ~3 | calibration / floor reference — deliberately few |
| **Discriminator (mid)** | **~40–80%** | **~14** | the workhorses; where the ranking is earned |
| Hard tail | ~0–30% | ~6 | at least 2–3 that a frontier model robustly fails (`0/3`) |

The mid band is the product. If sourcing drifts easy, the suite re-saturates.

## Domain coverage (secondary axis, tags not boundaries)

Every task carries a `domain` tag in `metadata.json`. The suite boundary is the
*language*; domain is a tag so we can publish cross-cutting "views" later without
re-introducing the v3 confound. Aim for spread, not a fixed quota, across:

`web-async` (Flask/FastAPI/aiohttp/httpx) · `data-orm` (SQLGlot/SQLAlchemy/pandas)
· `parsing` (tokenizers, format parsers, serializers) · `scientific` (numpy/
networkx/pennylane-class numeric) · `stdlib-utility` (pure-Python libs,
itertools-class) · `cli-tooling` (click/typer/packaging/build) · `concurrency`
(async/threading correctness).

Guard against a single library dominating discrimination: no more than ~3 admitted
tasks from one upstream repo.

## Sourcing (same rigor as v2/v3)

- Real merged PRs, **merged ≥ 2026-02-01** (post model cutoff → the specific fix is
  novel and decontaminated). Record the PR URL + merge date in
  `decontamination_notes`.
- Prefer feature additions and non-trivial multi-file bug fixes over one-line edge
  fixes; the both-fail tail so far comes only from multi-site behavioral redesigns
  with an explicit contract (v3's `flask-teardown-robust`), not from clever wording.
- Slice the repo at the PR base commit with `scripts/slice_repo.py`, preserving the
  LICENSE and a realistic navigation surface (don't over-slice to the fix site).
- Per-task Docker env from `sandbox/task.Dockerfile.template`; runs are
  network-isolated.

## Grading (deterministic, no judge)

The repo's own tests. `metadata.json`: `grader: "tests"`, `fail_to_pass` = the PR's
new/changed tests (**coverage floor ≥ 3**, each independently verified to fail at
the base commit), `pass_to_pass` = existing regression guard that does **not**
reference the new feature (so it compiles/passes at base). No LLM judge.

## Per-task admission gate

1. Well-formed: gold patch = 1.0; base commit = 0.0 on every `fail_to_pass`;
   deterministic over 3 validation runs (`scripts/validate_tasks.py`).
2. `issue.md` states the symptom / desired behavior with acceptance examples whose
   constants come from the gold patch — **no fix leak, no gold-mimicry** (grade the
   stated requirement + genuine no-regression only).
3. Measured: **repeat ≥ 3** on the frontier panel; record per-config pass@1.
4. Admit to fill the band table above. Reject a task that is floor dead-weight
   (aced by all) unless it's one of the ≤3 anchors, or that is flaky / ambiguous /
   a gotcha / whose base env doesn't reproduce / whose deps don't install reliably.

## Measurement panel

Frontier panel for admission + the launch report (subject to availability at build
time): **Claude Opus 5, GPT-5.6 Sol, Grok 4.5**, plus one frugal reference
(Haiku 4.5 or Kimi K3). Repeat ≥ 3 per task per config. Report DNF/timeout and
wrong-answer separately; publish per-config pass@1 **with ±1 stderr**.

## Target (definition of done)

23 admitted Python tasks matching the band table; median frontier aggregate pass@1
**50–70%** over repeat ≥ 3, a hard tail with ≥2 robust both-fail tasks, and no
single task carrying the ranking. Sourcing/measurement tracked in `CANDIDATES.md`.
