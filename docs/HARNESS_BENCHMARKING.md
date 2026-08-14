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

## Web access and solution leakage

VulcanBench's own loop has no web tools and its sandbox runs network-off, but
external harnesses can browse. For suites built from real merged PRs that is a
solved-answer oracle: the fix exists at a known public URL. (Terminal-Bench,
which allows internet by design, asks users to "remain vigilant" about agents
locating solutions; VulcanBench automates that vigilance.)

Three layers:

1. **Prevention.** The Cursor adapter writes a workspace permissions file
   denying `WebFetch(*)` and `WebSearch` unless `--network` is passed; denies
   survive Cursor's `--force`. Claude Code gets `--disallowedTools
   WebSearch,WebFetch`; Codex network access stays off in its sandbox config.
2. **Detection.** Every CLI-harness run's summary carries a `web_audit` block:
   web searches/fetches extracted from the captured stream, matched against
   the task's `metadata.upstream` provenance. Verdicts escalate: `no_web`,
   `web_used`, `upstream_access` (fetched the task's upstream repo, whose
   post-fix sources contain the solution), `solution_retrieval` (fetched the
   exact PR, fix commit, or a raw diff/patch). `contaminated: true` on the top
   two. The audit annotates; it never rescores.
3. **Retro-audit.** `vulcanbench audit-web runs/` re-annotates existing runs
   and prints verdict counts, flagging solved-but-contaminated runs to exclude
   or asterisk in reports.

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
