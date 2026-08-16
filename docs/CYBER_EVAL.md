# VulcanCyber v1 — the cybersecurity suite

VulcanCyber v1 measures whether models can do **defensive security engineering**
in real, unfamiliar codebases: given a vulnerable or insufficiently-hardened
piece of code, produce the fix that closes the gap — graded by the upstream
project's own security regression tests.

Every task is sourced from a **real merged open-source PR whose fix merged after
current model training cutoffs** (`>= 2026-06-01`), so the specific fix is not in
the evaluated models' training data. Each task records `upstream_merged` so the
clean subset stays a query as cutoffs move. See the suite
[charter](../tasks/vulcancyber-v1/CHARTER.md) for the full curation discipline and
the [candidates log](../tasks/vulcancyber-v1/CANDIDATES.md) for the sourcing
worklog.

## Posture: defensive only

Every task is "here is vulnerable/insufficient code — produce the fix." The grade
comes from a regression test that goes from **failing** (the weakness is present)
to **passing** (the weakness is closed). VulcanCyber does not contain offensive
tooling or tasks whose deliverable is a working attack. Where a test exercises an
exploit vector, it exists only to prove the defense holds — a standard security
regression test, exactly as the upstream project ships it.

## What it measures

Two task families (the suite aims for a mix as it grows):

- **(A) Vulnerability fixes** — real merged PRs that patch a security weakness:
  prototype pollution, header/CRLF injection, path-traversal / auth bypass,
  algorithmic denial-of-service, injection via unescaped output, and similar.
- **(B) Security-tooling PRs** — fixes/features in scanners, detectors, and
  advisory tooling (planned expansion; see the charter).

Grading is **deterministic** (`grader: "tests"`, no LLM judge): `fail_to_pass` are
the PR's security regression tests (weakness present → fixed), `pass_to_pass` are
existing behaviours that must not regress. Every admitted task carries **≥ 3
`fail_to_pass`** tests, each independently verified to fail at the base commit,
and is validated to be deterministic over 3 runs.

## v1 tasks (validated)

Ten tasks across five languages and eight distinct vulnerability classes, one a
Family-B security-tooling fix. Each is gold-solved (`functional == 1.0`), genuinely
fails pre-patch (`pre-patch == 0.0`), and is deterministic over three runs in the
Docker sandbox.

| Task | Lang | Family | Class | Upstream (merged) |
|------|------|--------|-------|-------------------|
| `oss-hono-proto-pollution-parsers` | TypeScript | A | Prototype pollution | [honojs/hono#5161](https://github.com/honojs/hono/pull/5161) (2026-07-24) |
| `oss-undici-header-crlf-coercion` | JavaScript | A | CRLF header injection | [nodejs/undici#5579](https://github.com/nodejs/undici/pull/5579) (2026-07-22) |
| `oss-echo-encoded-path-separator` | Go | A | Encoded-separator auth bypass (GHSA-vfp3-v2gw-7wfq) | [labstack/echo#3009](https://github.com/labstack/echo/pull/3009) (2026-06-14) |
| `oss-pyyaml-merge-key-dos` | Python | A | Merge-key amplification DoS | [yaml/pyyaml#937](https://github.com/yaml/pyyaml/pull/937) (2026-06-17) |
| `oss-quick-xml-serialize-control-escape` | Rust | A | Unescaped control chars (round-trip corruption) | [tafia/quick-xml#1001](https://github.com/tafia/quick-xml/pull/1001) (2026-08-15) |
| `oss-gosec-g404-weak-random-coverage` | Go | **B** | Scanner false-negative (weak randomness) | [securego/gosec#1694](https://github.com/securego/gosec/pull/1694) (2026-06-15) |
| `oss-zod-jsonschema-proto-pollution` | TypeScript | A | Prototype pollution (JSON-schema conversion) | [colinhacks/zod#6346](https://github.com/colinhacks/zod/pull/6346) (2026-08-09) |
| `oss-tornado-urlencoded-field-limit` | Python | A | Urlencoded field-count DoS | [tornadoweb/tornado#3704](https://github.com/tornadoweb/tornado/pull/3704) (2026-08-07) |
| `oss-werkzeug-host-port-validation` | Python | A | Host-header port validation | [pallets/werkzeug#3236](https://github.com/pallets/werkzeug/pull/3236) (2026-08-12) |
| `oss-werkzeug-etag-strict-parse` | Python | A | Strict ETag parsing | [pallets/werkzeug#3234](https://github.com/pallets/werkzeug/pull/3234) (2026-08-10) |

Language mix: Python 4, TypeScript 2, Go 2, JavaScript 1, Rust 1. A 2nd Family-B
task and a broader family balance are mapped in
[the candidates log](../tasks/vulcancyber-v1/CANDIDATES.md).

## Running it

```bash
# Build the sandbox images the suite needs (base + Rust + Go 1.26):
make sandbox-image-all

# Validate the corpus (gold-solves, fail-to-pass real, deterministic x3):
make validate-cyber

# Deterministic, no-API smoke that the suite loads and runs end to end:
vulcanbench run --suite vulcancyber-v1 --model mock:synthetic --sandbox local

# A real run (bring your own key). Use a judge model different from the model
# under test is unnecessary here — grading is deterministic tests, not a judge:
vulcanbench run --suite vulcancyber-v1 --model anthropic:claude-opus-5 --sandbox docker

# Leaderboard / report must point --tasks-root at the suite directory:
vulcanbench leaderboard --suite vulcancyber-v1 --tasks-root tasks/vulcancyber-v1
vulcanbench report --suite vulcancyber-v1 --tasks-root tasks/vulcancyber-v1
```

Two tasks need non-default sandbox images (declared per-task via `metadata.image`):
`oss-echo-encoded-path-separator` uses `vulcanbench/sandbox:go-1.26` (echo v5's
`go.mod` requires Go ≥ 1.25; the base image ships 1.23), and
`oss-quick-xml-serialize-control-escape` uses `vulcanbench/sandbox:rust`. Both
are built by `make sandbox-image-all`.

## Sourcing your own tasks

`scripts/mine_security_prs.py` is a read-only `gh` helper that finds merged,
test-bearing, security-signal PRs since a cutoff date across a curated per-language
repo list:

```bash
python scripts/mine_security_prs.py --lang all --tools --since 2026-06-01 --json out.json
```

Then follow the per-task build recipe in the charter: `scripts/slice_repo.py` to
pin the repo at the PR base commit, write a terse `issue.md` and hidden `tests/`,
generate `gold_patch.diff`, and gate with
`python scripts/validate_tasks.py tasks/vulcancyber-v1/<id> --sandbox docker`.

> The base commit is the **parent of the PR's first commit** — for a rebase- or
> squash-merged PR the merge commit's first parent is an intermediate PR commit
> that may already contain the fix. Always confirm the base is vulnerable
> (validator `pre-patch = 0.0`) before trusting a task.

## Note on the `security` metric

VulcanBench's 15%-weight `security` metric runs static analyzers
(bandit/gosec/npm-audit/cargo-audit) on the *agent's changed files*. On a security
fix a scanner can fire on the correct patch and depress `total`/`avg_security`
even at `functional == 1.0`. **pass@1 is functional-based, so it is unaffected**;
when publishing, inspect the `security` sub-scores on the gold patches and
footnote any that flag.
