# Measuring a model family

VulcanBench today scores **one model, at one reasoning effort, in one
harness**, on one task. That is the right atomic measurement. It is not the
question people actually ask about a *family* such as Grok 4.6 + Composer 2.5,
or Sol + Terra + Luna:

1. **Which workflow** should the family use — vendor agent, uniform loop, a
   cheap-then-escalate cascade, a planner/worker orchestrator?
2. **Which member and reasoning level** should handle each task?

Those are two nested searches. Collapsing them into a single “family pass@1”
hides the decision that operators need. This document is the design for
answering them without breaking the honesty rules the rest of the harness
already enforces (don’t mix vendor CLIs with the uniform loop silently; don’t
pretend an unsupported effort was sent; don’t score infrastructure errors as
model failures).

`vulcanbench family-report` (v0.10) is **phase 1**: routing over cached
single-model columns. Live in-task topologies are phase 2+.

## What the harness already measures

A run is identified by `(task, model, effort, harness)`:

| Axis | Where it lives | What it is |
|---|---|---|
| Task | `tasks/<suite>/` | Frozen by `task_hash` / `suite_version` |
| Model | `--model provider:name` | One API or CLI spec |
| Effort | `--effort` / `effort-sweep` | Provider-mapped reasoning level; unsupported levels are recorded-but-not-sent |
| Harness | uniform loop vs `cursor:` / `claude-code:` / `codex:` | The runtime that called tools |

Downstream scoring (hidden tests, quality, security, judges) does not care
which engine produced the patch. Leaderboard and `compare` then roll runs up
by **model string** (and, for `compare`, by model × effort). There is no
first-class family identity, no routing policy, and no workflow field.

Useful pieces to reuse rather than rebuild:

- **Effort sensitivity** (`report`) already classifies strata as “low
  sufficient” vs “effort sensitive” per model × language × scale ×
  difficulty × complexity. That is the feature space a metadata router
  should use.
- **Discrimination** tells you which tasks actually separate members. A
  family router that only ever sees floor/ceiling tasks cannot be
  calibrated.
- **`--only-missing` + `compare`** already treat new columns as fill-the-gaps
  queries over `./runs`. A family measurement should be the same: run each
  member once, then *query* policies.
- Task metadata already carries `repo_scale`, `task_complexity`,
  `difficulty`, `languages`, and stamped `agent_hints` budgets.

## Unit of evaluation for a family

A family is a roster plus a **policy**:

```text
family   = { members: [(id, model, allowed efforts, role)], allowed workflows }
policy   = (workflow, route)
route    = task features (and optional live signals) → (member, effort)
score    = (pass@1, expected USD, latency) under that policy on a frozen suite
```

Roles (`driver` / `planner` / `worker`) are documented on the roster so a
later orchestrator can bind them. Phase 1 ignores role except as metadata:
every member is evaluated as a whole-task driver.

Two scores must never be mixed:

| Score | Meaning | Deployable? |
|---|---|---|
| **Oracle** | Per task, peek at that task’s outcomes and pick the best/cheapest cell | No — label leak; upper bound |
| **Deployable** | Routing that could have been chosen *before* seeing that task’s hidden tests | Yes — this is the product claim |

`family-report` labels oracle policies `leaks_labels: true`. The metadata
router is leave-one-task-out on the metadata stratum, so it is a deployable
baseline.

## Two nested questions

```text
                    ┌─ single driver (always member M @ effort E)
                    │
 family ─ workflow ─┼─ cascade (try cheap, restart or hand off on fail)
                    │
                    └─ orchestrator (planner delegates to workers)
                              │
                              └─ then, given that workflow:
                                   route: task → (member, effort)
```

**Do not start with an orchestrator.** If a deployable single-driver router
already matches “always the strongest member” on pass@1 at much lower cost,
the orchestrator has nothing to prove on those tasks. Spend live multi-model
budget only on the residual: tasks no cheap member solves, or
architecture/system tasks where decomposition is the hypothesis.

## Workflow topologies

### 1. Single driver (already implemented)

One member runs the whole task, either in the uniform loop
(`harness/agent/loop.py`) or a vendor CLI (`cursor:`, `claude-code:`,
`codex:`). The family question reduces to **which column to use per task**.
That is exactly what cached `family-report` computes.

This is the correct default. Cursor’s Composer 2.5 column is already “model +
Cursor harness”; Grok 4.6 via `xai:` is “model + VulcanBench loop”. Pinning
one member per task does not require a new runner.

### 2. Vendor-default family (probe, not yet wired)

Many product families already have an in-house router. For Cursor, that would
be “don’t pin `--model`” (or a dedicated `cursor:auto` spec) and let the
CLI pick Composer vs Grok vs Sol/Terra/Luna. That column measures **the
vendor’s policy**, which is a legitimate product benchmark and a different
claim from “our metadata router over pinned members.”

Honesty: `cursor:auto` is not comparable to `cursor:composer-2.5`. Record the
harness and the fact that member choice was endogenous.

### 3. Independent-restart cascade (phase 1: simulated)

Try the cheapest member; if that attempt fails, start over with a stronger
member. **No patch is handed off.** Expected pass and cost can be computed
from cached solve rates:

```text
P(solve) = s1 + (1-s1)s2 + (1-s1)(1-s2)s3 + …
E(cost)  = c1 + (1-s1)c2 + (1-s1)(1-s2)c3 + …
```

`family-report` emits this as `cascade_restart`. It is a lower bound on a
handoff cascade (the expensive model does not see the failed patch) and an
upper bound on waste (you always pay the cheap attempt). It is **not** a
live topology.

### 4. Patch-handoff cascade (phase 2)

Same order, but the next member receives the previous patch, test output, and
trace. This *cannot* be reconstructed from independent runs. It needs a new
runner that keeps the workspace and calls `run_agent` / the CLI again with a
continuation prompt. Record a per-member cost breakdown on the same
`summary.json`.

### 5. Orchestrator / planner–worker (phase 3)

A planner (e.g. Grok 4.6 extra-high, or Sol) decomposes the issue and
spawns workers (Composer 2.5, Terra, Luna) with the existing tool contract.
This is a new loop, not a CLI flag. Minimum viable design:

- Planner-only tools: `spawn_worker(member, prompt, files?)`, `review_patch`,
  plus the current file/search tools for orientation.
- Workers are ordinary single-driver runs in the same workspace, with their
  own step/cost budgets.
- Summary records `workflow: orchestrator`, `family_id`, and a list of
  `{member, tokens, cost, steps}` attributions.
- Same hidden-test scorer as today.

Do **not** implement this until phase 1 shows residual failures on
`system` / `architecture` tasks that a router cannot close.

## Honesty rules (non-negotiable)

These already exist for CLI agents; families inherit them.

1. **Harness is part of the identity.** `cursor:composer-2.5` and
   `xai:grok-4.6` are a *product stack*, not a uniform-loop family.
   `family-report` sets `mixed_harness: true` and warns. Prefer
   `cursor:composer-2.5` + `cursor:grok-4.6` (same CLI) or
   `xai:grok-4.6` + an API sibling (same loop).
2. **Cost bases must not silently mix.** Cursor list-price tokens
   (`cli_agent.billing = cursor-usage`) plus xAI API tokens in one policy
   cost are still comparable as USD, but the summary must keep the split.
   Subscription hypothetical API cost (`claude-code:`) is not spend.
3. **Unsupported effort is not a level.** Composer’s Fast vs standard is a
   *model id*, not `--effort`. Grok maps `low|medium|high`; `extra-high` is
   recorded-but-not-sent. A router that “picks extra-high on Composer” is a
   spec error.
4. **Oracle is not a product claim.** Publish deployable (metadata router,
   vendor-auto, live cascade) next to oracle, never instead of it.
5. **Infrastructure errors stay errors.** A family policy that could not
   obtain a member run is uncovered, not a zero.

## Scoring

All comparative policies are evaluated on the **fair task set**: suite tasks
for which *every* family cell has a fresh (non-stale) cached run. Incomplete
members do not get a free pass@1 on a subset. Static policies still report
on that set when it is non-empty, so they are comparable to the router.

For each policy, on that set:

- **pass@1** — mean over tasks of the chosen cell’s per-task solve rate
  (repeats already averaged inside the cell), with stderr across tasks.
- **policy cost** — USD to run the policy **once per task** (sum of per-task
  mean cell costs, or expected cascade cost). This is not the measurement
  spend already sitting in `./runs`.
- **latency** — mean wall-clock of the chosen cell (cascade: expected sum).

Pareto: a family is interesting when some deployable policy sits on the
pass@1-vs-cost front of the static members. If “always strongest @ high”
dominates on pass@1 and the router does not recover most of that at lower
cost, the family is not earning its routing complexity.

## Experimental order (what to actually run)

For Grok 4.6 + Composer 2.5, or Sol + Terra + Luna:

1. **Fill single-driver columns.** Each member, each supported effort, on
   the frozen suite (`--repeat 3`, `--no-judges` unless you need
   `human_like`, `--only-missing`). Composer via `cursor:` needs
   `--sandbox local`. Grok via `xai:` can use Docker. Sol/Terra/Luna via
   `openai:` (or `cursor:` if that is how you serve them) — pick **one**
   harness for the roster.
2. **`vulcanbench family-report --suite <suite> --family families/….json`.**
   Read static vs metadata router vs cascade-sim vs oracle.
3. **Stop if the router is enough.** If metadata routing matches oracle
   pass@1 within noise at a fraction of always-max cost, ship that routing
   table. No orchestrator required.
4. **Live cascade only on the residual.** Tasks the cheap member never
   solves, where oracle says the expensive member does. Measure handoff vs
   restart; if handoff does not beat restart, skip it.
5. **Orchestrator only if residual is structural.** Hypothesis: `system` /
   `architecture` tasks fail because one driver cannot plan. Test against
   “expensive single driver @ extra-high” on those tasks — an orchestrator
   that loses to that baseline is complexity without capability.

## Phase 1 (shipped): `family-report`

Roster JSON (see `families/`):

```json
{
  "id": "cursor-grok-composer",
  "display_name": "Grok 4.6 + Composer 2.5",
  "members": [
    {"id": "composer", "model": "cursor:composer-2.5", "efforts": [null], "role": "driver"},
    {"id": "grok", "model": "cursor:grok-4.6", "efforts": [null], "role": "driver"}
  ]
}
```

`efforts: [null]` means the unset/`--effort`-not-sent column (vendor CLIs).
Omit `efforts` to discover whatever levels exist in `./runs`. API families
list `["low","medium","high"]`.

```bash
# After each member has a cached column:
vulcanbench family-report --suite v3 --family families/cursor-grok-composer.json
vulcanbench family-report --suite v3 --members xai:grok-4.5,cursor:composer-2.5 --json
```

Policies emitted:

| Policy | Deployable? |
|---|---|
| `static:<member>@<effort>` | Yes — today’s leaderboard column |
| `metadata_router` | Yes — LOO on metadata stratum |
| `cascade_restart` | Yes as a *product* (restart); simulation only until phase 2 |
| `oracle_cheapest_sufficient` | No |
| `oracle_max_pass` | No |

## Phase 2 — live cascade (not built)

- New runner flag, e.g. `--family families/….json --workflow cascade`.
- One `run_id`, one workspace, sequential members, shared `task_hash`.
- `summary.json` grows `family`, `workflow`, `member_attempts[]`.
- Leaderboard grouping key becomes `(family_id, workflow, policy)` rather
  than `model` alone — otherwise a cascade run would look like whichever
  member last touched the tree.
- Cost cap `--max-run-cost` applies to the *sum* of members.

## Phase 3 — orchestrator (not built)

- Planner provider + worker roster; standardized `spawn_worker` tool.
- Trace events for handoff (who spawned whom, with which prompt).
- Same verifier. Judge ensemble must not use a family member as a self-judge
  by default (`--judge-model` stays a third model).
- Budget: planner timeout vs worker timeout must be explicit in
  `agent_hints` or the family spec so large tasks are not planner-starved.

## Work that is *not* required

- New tasks. v3 / CII already vary scale, complexity, language, difficulty.
- New metrics. Functional pass@1 + USD + latency are the family axes;
  quality/security still grade the final patch.
- Dashboard work in phase 1. Markdown/JSON from the CLI is enough to learn
  whether the question is even interesting.
- Changing `effort-sweep`. It remains the way to fill member columns.

## Example: Grok 4.6 + Composer 2.5

Composer is Cursor-only and has no `--effort` mapping (Fast is
`cursor:composer-2.5-fast`). Grok 4.6 has `low|medium|high` on the xAI API
and no extra-high. Fair families:

- **Same harness (preferred):** `cursor:composer-2.5` + `cursor:grok-4.6`
  (if the CLI serves Grok). Effort is unset on both; routing is member-only.
- **Product stack (mixed harness):** `cursor:composer-2.5` + `xai:grok-4.6`
  with Grok effort sweep. `family-report` will flag `mixed_harness`. Useful
  as “what should Cursor do,” but not as a uniform-loop paper table.

Hypothesis to test, not assume: Composer on `micro`/`small`/`localized`,
Grok medium/high on `large`/`xlarge` + `system`/`architecture` and on
effort-sensitive Python strata the v3 report already flags.

## Example: Sol + Terra + Luna

Treat them as three drivers in **one** harness (all `openai:` loop or all
`cursor:`), each with the effort levels that provider actually sends. The
interesting result is a routing table, e.g. Luna-low on micro, Terra-medium
on medium/multi_file, Sol-high on xlarge/system — **if** the metadata router
recovers oracle cost without losing pass@1. If Sol-high dominates every
stratum, the family is a SKU list, not a router.

## Checklist: what it would take (full vision)

| Item | Status |
|---|---|
| Family roster JSON + validation | Phase 1 |
| Cached policy report (static, LOO router, cascade-sim, oracle) | Phase 1 |
| Mixed-harness warning | Phase 1 |
| Fair-set coverage (intersection of member columns) | Phase 1 |
| Same-harness Cursor/API examples | Phase 1 (`families/`) |
| `cursor:auto` / omit `--model` vendor-router column | Not built |
| Live patch-handoff cascade runner | Not built |
| Orchestrator loop + `spawn_worker` | Not built |
| Leaderboard grouping by `(family, workflow, policy)` | Not built |
| Per-member cost attribution on a single `summary.json` | Not built |
| Dashboard family view | Not built |

Phase 1 is enough to decide whether a given roster *should* use an
orchestrator. That is the point of measuring the family.
