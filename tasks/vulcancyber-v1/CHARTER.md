# VulcanCyber v1: the cybersecurity tier

## Goal
A small suite of **cybersecurity** tasks that represent real work a security-
minded engineering team would hand an agentic coding tool: close a vulnerability,
harden an input path, or fix/extend a security tool — each sourced from a **real
merged open-source PR that post-dates current model training cutoffs**, and each
graded by the PR's own deterministic tests. Tasks span difficulty and are composed
so frontier models (Claude Sonnet 5, Claude Opus 5) land a meaningful aggregate
pass@1 **with a genuine hard tail** (at least one task both frontier models fail).
This suite exists to measure whether models can do *defensive security
engineering* in unfamiliar codebases, not to memorise CVE writeups.

## Posture: defensive only
Every task is framed as **"here is vulnerable or insufficient code — produce the
fix that closes the gap."** The grade comes from a regression test that goes from
*failing* (the weakness is present) to *passing* (the weakness is closed). We do
**not** author offensive tooling, exploit kits, or tasks whose deliverable is a
working attack. Where a `fail_to_pass` test exercises an exploit vector, it exists
only to prove the defense holds after the fix — a standard security regression
test, exactly as the upstream project ships it.

## Two hard truths (carried from the v2 charter, and they hold here)
1. **Hand-authoring cannot produce frontier difficulty.** Synthetic "spot the
   vuln" prompts do not trip strong models no matter how cleverly worded.
   Difficulty lives in real, unfamiliar codebases and real subtle security bugs.
   We curate and MEASURE real PRs; we never invent the vulnerability.
2. **Toy one-liners are not enough.** A single-line `shell=True` → `shell=False`
   swap reads like a lint fix, not security engineering, and never reaches a hard
   tail. Prefer fixes with real logic: a parser that must reject a malformed input
   class, a normalizer that must canonicalise before a security check, a
   comparison that must be constant-time, a detection rule that must catch a new
   evasion.

## What counts as a task (the "mix of both")
Two families, roughly balanced across the admitted set:

- **(A) Vulnerability fixes (defensive).** A real merged PR that patches a
  security weakness in an application or library: path/zip-slip traversal, SSRF,
  ReDoS, header/CRLF injection, SQL/command/template injection, XXE, unsafe
  deserialization (pickle/yaml/marshal), prototype pollution, open redirect,
  auth/authorization bypass, cookie/session handling, TLS/cert validation,
  timing-unsafe comparisons, integer-overflow-to-panic DoS.
- **(B) Security-tooling PRs.** A real merged PR to a *security tool* — a scanner,
  linter, secret detector, SBOM/vuln database, policy engine, or fuzz harness
  (e.g. semgrep, bandit, gosec, trivy, osv-scanner, gitleaks/trufflehog,
  detect-secrets, checkov, pip-audit, cargo-audit, rustls/`ring` hardening).
  The codebase *is* a security tool; the task looks like normal SWE work in that
  domain (add a detection, fix a false negative, parse a new advisory format).

## Realism bar (every task)
- Reads like a security ticket: "endpoint X is vulnerable to Y", "the scanner
  misses Z", "comparison W is timing-unsafe" — state the symptom or desired
  behavior, **never the fix**.
- Terse, ticket-style `issue.md`. No gold-mimicry (grade the stated security
  requirement plus genuine no-regression, never incidental things the gold PR
  happened to touch).
- Keep a realistic navigation surface. Do not over-slice to hand the agent the
  vulnerable line; locating it is part of the task.

## Sourcing
- **Real merged PRs, merged ≥ 2026-06-01** (post current model cutoffs, incl.
  Opus 5's May 2026 cutoff — so the specific fix is novel and not in the evaluated
  models' training data: `decontaminated: true`, with `upstream_merged` recorded
  as proof, exactly as v4's post-cutoff tasks do). Prefer the most recent months.
  When a future model's cutoff moves past these dates, relabel the affected tasks
  `decontaminated: false` — the `upstream_merged` field makes that a query.
- The PR **must ship tests** (so a deterministic `fail_to_pass` exists) and carry
  a **permissive license** (MIT/BSD/Apache) so the slice can vendor it.
- Substantial, real projects — not abandoned repos. Run with the repo's own deps
  and test runner in a per-task Docker image (`sandbox/task.Dockerfile.template`),
  network-off.
- Language mix matches v4: **Python, Rust, TypeScript, JavaScript, Go.**
- Candidate discovery is seeded by `scripts/mine_security_prs.py` (a read-only
  `gh` search), then hand-triaged in `CANDIDATES.md`.

## Grading (deterministic, no judge)
The repo's own tests, per the v2/v3/v4 discipline. `metadata.json`:
`grader: "tests"`, `fail_to_pass` = the PR's new/changed security tests (the
weakness present → fixed), `pass_to_pass` = existing tests that must not regress,
`test_timeout_s`. **No LLM judge** — rubric grading is too noisy on security code,
where "looks fixed" and "is fixed" diverge. Coverage floor: **≥ 3 `fail_to_pass`
tests**, each independently verified to fail at the base commit; assert behavior
via public APIs, never exact error text; generate acceptance constants from the
gold patch. NET-NEW-symbol tasks put `pass_to_pass` guards in a **separate module**
that imports only pre-existing names (so it compiles/passes at base).

## Difficulty composition (the discipline)
Build ~20–25 candidates across a difficulty range, MEASURE each (Sonnet 5 and
Opus 5, repeat ≥ 3, after a cheap Haiku-first screen), then compose the final
10–15. Per-task decision:
- **Keep** any well-formed task (gold passes, base fails the `fail_to_pass`
  test(s), deterministic over 3 runs, unambiguous), anywhere on the spectrum. **A
  task the frontier scores near 0% on is DESIRABLE if it is fair and well-formed**
  — that is the tail we want.
- **Reject** a task trivially aced by both at low effort (unless kept as a
  deliberate easy anchor), OR flaky / ambiguous / gold-mimicry / whose base env
  does not actually reproduce the weakness / whose deps do not install reliably
  offline.

## Build recipe (per task)
1. `scripts/mine_security_prs.py` (or `gh`) → a qualifying merged security PR
   (post-cutoff, real vuln/hardening or security-tool change, ships tests).
2. `gh pr diff <n>` → separates the gold source change from the PR's tests.
3. `scripts/slice_repo.py` → pin the repo at the PR's **base commit**, preserve
   the LICENSE and a realistic navigation surface; add the per-task Docker env.
4. Write terse `issue.md` (symptom/desired behavior only — no fix leak, no
   gold-mimicry).
5. Write `metadata.json` (`grader: tests`, `fail_to_pass`/`pass_to_pass`,
   `upstream` URL + `upstream_merged`, honest `decontamination_notes`).
6. Validate: gold passes (`functional == 1.0`), base fails the `fail_to_pass`
   test(s), deterministic ×3 (`scripts/validate_tasks.py --sandbox docker`).
7. Measure: metered run of Sonnet 5 + Opus 5; record pass@1; admit or reject.

## Target
10–15 admitted tasks across the five languages, roughly balanced between the two
task families, with a genuine hard tail (≥ 1 task both frontier models fail).
Quality over volume.

## Scope: what this suite measures, and what it does not
Measures: issue-driven **defensive** security fixes and security-tool changes
(patches up to ~200 lines) in real, mature, unfamiliar OSS codebases, graded by
deterministic hidden tests; plus cost, steps, tokens, latency. This is the "here
is a security ticket, go close it in a codebase you have never seen" slice.

Does not measure: offensive capability, red-team operations, multi-day or
cross-service work, greenfield secure design, threat modeling requiring
conversation, or operating on proprietary code. Composition is deliberately
difficulty-weighted (tasks that discriminate frontier models are over-represented
relative to a uniform sample of a real security backlog); the score is a
discrimination instrument, not a survey of security-engineering labor.

## Note on the `security` metric
VulcanBench's 15%-weight `security` metric runs bandit/gosec/npm-audit/cargo-audit
on the *agent's changed files*. On a security fix, a scanner can fire on the
correct patch (e.g. the regression test itself invokes a flagged API) and depress
`total`/`avg_security` even at `functional == 1.0`. **pass@1 is functional-based,
so it is unaffected**; when publishing this suite, inspect the `security`
sub-scores on the gold patches and footnote any that flag, so `total` is read
correctly.
