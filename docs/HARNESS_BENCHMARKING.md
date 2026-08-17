# Subscription harness benchmarking

VulcanBench can run a task through a product's own coding-agent CLI while
keeping task preparation, the final diff, hidden verification, and scoring in
VulcanBench. These results measure a **model plus product harness**, not a raw
model API.

Release A supports:

| Harness | Spec | Subscription authentication | Execution boundary |
|---|---|---|---|
| Claude Code | `claude-code:<model>` | Claude Pro/Max login | Claude permission auto mode; `--sandbox local` currently required |
| Codex CLI | `codex:<model>` | Sign in with ChatGPT | Codex `workspace-write`; Vulcan setup/verifier may still use Docker |
| Cursor CLI | `cursor:<model>` | `cursor-agent login` (Cursor account/credits) | Cursor sandbox enabled + force-allow; Vulcan setup/verifier may use Docker |
| Grok Build | `grok-build:<model>` | `grok login` (grok.com OIDC) | custom kernel profile: workspace writes + repo reads denied (Seatbelt/Landlock); Vulcan setup/verifier may use Docker |

Cursor-specific limits: `cursor-agent` streams no token usage or cost, so
token counts are recorded as zero and the economics receipt marks the
API-equivalent value **unavailable** — Cursor's own usage dashboard is the
only ledger of what a run consumed. `--max-run-cost` is rejected (nothing to
enforce it against) and `--effort low|medium|high` travels via Cursor's
`model[effort=...]` bracket syntax — though Cursor's Grok family bakes effort
into the model id instead (`cursor-grok-4.6-low` … `-xhigh`), so sweep those by
model id without `--effort`. Run with `--sandbox docker` so hidden-test
verification uses the sandbox image toolchains; `--sandbox local` puts the
verifier on the host, where missing toolchains fail Python tasks. Preflight
fails closed when signed out or when `CURSOR_API_KEY` is set (API-key auth
bills metered usage, not the plan).

Grok Build-specific notes (verified on grok 0.2.69 and 1.0.5, both alpha —
the surface moves fast; re-verify these on every CLI update before a sweep):

- **The effort knob.** The adapter sends `--reasoning-effort` (accepted:
  none/minimal/low/medium/high/xhigh) and proves each run's level by copying
  the session summary's `reasoning_effort` into the outcome as
  `reported_effort`. On 0.2.69 the separate `--effort` flag parsed and was
  silently ignored (every level ran at the default `high`); 1.0.5 makes it
  an alias of `--reasoning-effort`. The adapter never uses `--effort`.
- **Usage and tool calls stream on 1.0+.** `streaming-json` emits
  `tool_call`/`tool_call_update`/`usage` events plus an `end` event with the
  full token split (input/output/cache-read/reasoning; grok's
  `output_tokens` already includes reasoning, unlike the raw xAI API),
  `num_turns`, and the CLI's own `total_cost_usd` (recorded as
  `cli_reported_cost_usd`; it is far below list price and is Grok's internal
  accounting, not a bill). Token receipts and a live `--max-run-cost`
  API-equivalent cap both work; `grok-build:` prices via the `xai:` table.
  The session trace (`~/.grok/sessions/**/<id>/`) is still harvested into
  the run dir — the session id is pre-assigned with `-s` so timeouts keep
  their trace. On 0.2.69, where the stream carried none of this, the trace
  was the only source; the harvest also guards against future stream
  regressions.
- **Web denial is by tool removal.** `--disallowed-tools web_search,web_fetch`
  deletes the tools outright (with `--deny WebFetch` as a second layer), so a
  grok run shows `no_web` rather than Cursor-style `web_blocked` attempt
  counts — the model cannot reach for a tool that does not exist.
- **The sandbox is a custom kernel profile, not `strict`.** The adapter
  writes `<workspace>/.grok/sandbox.toml` (`extends = "workspace"`, `deny =
  [<repo root>]`) and runs `--sandbox vulcanbench`: toolchains stay usable
  (`strict` also kernel-denied `~/.cargo` and homebrew, crippling non-Python
  tasks — observed live) while this checkout's answer keys are read-denied
  by the kernel even if the agent learns the path. That path can leak:
  a live run extracted the repo location from `PATH`'s `.venv/bin` entry and
  ran `find` over it (Seatbelt denied it), so `_subscription_env` now scrubs
  repo-rooted PATH entries for every harness. Grok fails closed if the
  profile cannot be applied. Note the sandbox does not block child-process
  network on macOS — `curl` in a shell works; web tool removal plus the
  audit's command scan remain the check on that.
- **Session hygiene.** `GROK_MEMORY=0` is always set (1.0 dropped the
  `--no-memory` flag): Grok's cross-session memory would let repeat N+1
  remember repeat N's task. `grok trace` uploads remotely by default —
  anything touching it must pass `--local`.
- Preflight fails closed when signed out or when `XAI_API_KEY` is set
  (API-key auth bills console.x.ai metered usage, not the plan).

## Leakage: two channels, both real

External harnesses execute on the host with broad tool access, and a benchmark
built from public merged PRs leaks through two independent channels. Both were
observed in live sweeps, and blocking one does nothing about the other.

**The web.** Every v3 task derives from a public PR, so the fix sits at a known
URL. In the first Cursor sweep 46% of runs fetched their task's exact source PR
or fix commit, and the median patch of those runs matched the gold patch
exactly. (Terminal-Bench, which allows internet by design, asks users to
"remain vigilant" about this; VulcanBench automates the check using provenance
its own tasks record.)

**The filesystem.** Harness agents run on the host, so a workspace inside this
checkout lets an agent walk up into `tasks/` and read `gold_patch.diff` and the
hidden tests -- the grader's answer key, not merely the upstream fix. In a
sweep with the web already blocked, 46 runs read their own task's answer key
and all 46 solved.

Three layers now stand against both:

1. **Containment.** CLI-harness runs get a workspace outside the repo
   (`tempfile.mkdtemp`), so no benchmark data exists anywhere above the
   agent's cwd; the tree is moved back under the run dir after scoring. This
   is the load-bearing defence: enumerating forbidden paths is the same losing
   game as enumerating forbidden URLs.
2. **Prevention.** The Cursor adapter writes a workspace permissions file
   denying `WebFetch(*)` and `WebSearch` (with an explicit allow list for the
   work tools) and runs with `--trust` unless `--network` is passed. The
   mechanism is fussy and was verified live: `--force` approves *denied*
   queries too, so a deny list under `--force` is silently useless; `--trust`
   honours denies but rejects shell calls without an allow list. Claude Code
   gets `--disallowedTools WebSearch,WebFetch`.
3. **Detection.** Every CLI-harness run summary carries an `integrity_audit`
   with both channels. Web verdicts: `no_web`, `web_blocked` (attempts made,
   all denied -- clean, but recorded), `web_used`, `upstream_access`,
   `solution_retrieval`. Filesystem verdicts: `clean`, `out_of_workspace`,
   `benchmark_data_access`, `answer_key_access`. A run is `contaminated` if
   either channel says so. `vulcanbench audit-runs runs/` re-annotates
   existing runs. The audit annotates; it never rescores.

Note what the audit is not: a rejected call is not access, and the audit must
correlate a tool call's `started` and `completed` events before scoring it. An
earlier version scored the `started` event alone and flagged four clean runs as
contaminated, one of them as solution retrieval.

## Preflight

Check installation, CLI version, authentication source, and non-secret plan
metadata without starting a paid model run:

```bash
vulcanbench harness list
vulcanbench harness doctor
vulcanbench harness doctor codex --json
```

Doctor fails closed when the CLI is signed out or authenticated with API
billing. VulcanBench never copies login tokens into run artifacts. External CLI
processes receive a minimal environment rather than the caller's entire shell
environment, and provider API keys are not inherited.

## Run with an explicit harness

```bash
# Claude Code through a Claude subscription
vulcanbench run --task hello-world \
  --harness claude-code \
  --billing subscription \
  --model claude-sonnet-5 \
  --sandbox local \
  --no-judges

# Codex through a ChatGPT subscription
vulcanbench run --task hello-world \
  --harness codex \
  --billing subscription \
  --model gpt-5.6-sol \
  --no-judges
```

The old `--model claude-code:<model>` form remains supported. For publication,
use `--no-judges` during execution and grade saved patches with the same fixed,
independent judge. Deterministic task verifiers are unchanged.

## Economics receipt

A subscription run does not claim that included usage cost zero. Each
`summary.json` contains an `economics` object with independent fields:

- `marginal_cash_usd`: cash caused by this run; unknown until the product
  provides an overage receipt.
- `overage_cash_usd`: paid usage beyond the plan allowance, when measurable.
- `allocated_plan_cost_usd`: a modeled share of the plan fee, when supplied.
- `grading_cash_usd`: metered cash for an independent API judge; unknown when
  grading also uses an included subscription.
- `grading_api_equivalent_usd`: counterfactual API value of grading usage.
- `api_equivalent_cost_usd`: counterfactual API cost derived from reported
  tokens.
- `quota`: provider-reported usage-window consumption, when available.
- `measurement_quality`: whether each value is exact, provider-reported,
  estimated, or unavailable.

The legacy top-level `cost_usd` remains an API-equivalent compatibility field
for existing tools. New reports and leaderboards label marginal cash and API
equivalent separately.

When the CLI reports cache reads and the price table has a `cached_input`
rate, VulcanBench subtracts those tokens from full-price input and applies the
cache-read rate separately. The receipt's `measurement_quality` states whether
cache pricing was applied. Cache writes and model-specific long-context tiers
remain unknown unless the CLI exposes enough per-request detail to price them.

```bash
vulcanbench leaderboard --track subscription
vulcanbench leaderboard --track api
```

Never add the two tracks to one model-performance claim. Subscription results
include the product's system prompt, context management, safety layers, tools,
and possible model routing.

## Reproducibility receipt

External-harness summaries record:

- Harness and CLI version
- Authentication mode and non-secret plan label
- Requested and CLI-reported model, when exposed
- Model-identity confidence
- Requested effort and the actual value sent
- Raw, redacted CLI event stream
- Token and cache usage exposed by the CLI
- Economics measurement basis
- Task hash, environment manifest, final patch, and verifier result

If a CLI cannot report a field, VulcanBench records it as unknown rather than
inferring it.

## Limits and recovery

Subscription quota exhaustion is a non-retryable infrastructure outcome, not a
task failure. The suite stops hot-looping that unit and records an error; resume
after the usage window resets:

```bash
vulcanbench run --suite v3 --harness codex --billing subscription \
  --model gpt-5.6-sol --repeat 3 --only-missing --no-judges
```

Codex currently reports token usage when a turn completes, so VulcanBench
rejects `--max-run-cost` for Codex rather than pretending it can enforce a live
cap. Use `--timeout` for a hard per-run boundary. Claude Code streams usage and
can enforce the API-equivalent cap during a run.

## Publication protocol

1. Freeze the task set and CLI versions.
2. Run `harness doctor` and save its non-secret JSON receipt.
3. Run one cheap smoke task.
4. Run a stratified pilot across easy, medium, and difficult tasks.
5. Use concurrency one for the baseline subscription comparison.
6. Complete every task/repeat cell or label the column incomplete.
7. Publish pass@1 with uncertainty, latency, quota/cost basis, and harness
   version.
8. Keep a small raw-API control subset to estimate the harness delta.

Use Docker verification for publication runs. A missing verifier dependency is
an infrastructure error, not a model failure; VulcanBench now surfaces and
retries that condition instead of recording a functional zero.
