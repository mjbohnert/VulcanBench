# VulcanCyber v1 candidate pool

Target: 10–15 admitted tasks across **Python / Rust / TypeScript / JavaScript / Go**,
roughly balanced between **(A) vulnerability fixes** and **(B) security-tooling PRs**.
All tasks: real merged PRs **merged ≥ 2026-06-01** (post current model cutoffs),
sliced at base commit, graded by ≥3 deterministic `fail_to_pass` tests. See
[CHARTER.md](CHARTER.md) for the discipline. Defensive posture only.

## How this pool is sourced
1. `python scripts/mine_security_prs.py --lang <lang> [--tools]` → read-only `gh`
   search over a curated repo list; prints a table of merged, test-bearing,
   security-signal PRs since 2026-06-01.
2. Triage each into the tables below (status = `candidate`).
3. Build with the recipe in the charter; flip to `building` → `admitted`/`rejected`.

## Toolchain notes (network-off sandbox is the binding constraint)
- Base image ships bandit (Python), Go 1.23, Node 22; Rust via `:rust`/`:rust-2024`;
  extensionless-import TS via `:node-ts` (tsx). gosec / npm-audit are NOT on the
  base image (the `security` metric reports `None` for Go/JS there — expected).
- Vendoring recipes proven in v3: `cargo vendor` + `.cargo/config.toml`
  replace-source; `go mod vendor` + `go test -mod=vendor`; `tsx --test`. Zero-dep
  libs need no vendoring.
- We write our OWN hidden tests (as for the SWE suites), asserting via public APIs.
  NET-NEW-symbol tasks put `pass_to_pass` in a separate module that only imports
  pre-existing names, so it compiles/passes at base.

## Status legend
`candidate` → triaged, not built · `building` → slicing/tests in progress ·
`admitted` → validated + measured, in suite.json · `rejected-easy` (aced by both) ·
`rejected-bad` (flaky/ambiguous/base-doesn't-reproduce/deps-won't-install).
`***` = top pick (net-new symbol or clean-testable defense).

---

## Python (target ~3–4) — family A vuln fixes + family B tools (bandit, pip-audit)
| PR | merged | repo | vuln class / change | family | prov. diff. | status |
|----|--------|------|---------------------|--------|-------------|--------|
| yaml/pyyaml #937 | 2026-06-17 | pyyaml | merge-key amplification DoS — dedup merge nodes in flatten_mapping | A | hard | **admitted** ✓ `oss-pyyaml-merge-key-dos` (gold=1.0, base=0.0, det×3; base=1024 keys→4) |
| tornadoweb/tornado #3704 | 2026-08-07 | tornado | "Security 6.5.8" release | A | ? | candidate (investigate the CVE) |
| django/django #21752 | 2026-08-14 | django | html-safe string rendering in form media | A | ? | candidate (django hard to slice) |

## JavaScript (target ~2–3) — validator.js, express ecosystem, semver ReDoS history
| PR | merged | repo | vuln class / change | family | prov. diff. | status |
|----|--------|------|---------------------|--------|-------------|--------|
| nodejs/undici #5579 | 2026-07-22 | undici | CRLF header injection — validate coerced (non-string) header values | A | medium | **admitted** ✓ `oss-undici-header-crlf-coercion` (gold=1.0, base=0.0, det×3) |

## TypeScript (target ~2–3) — hono, fastify, zod input-hardening
| PR | merged | repo | vuln class / change | family | prov. diff. | status |
|----|--------|------|---------------------|--------|-------------|--------|
| honojs/hono #5161 | 2026-07-24 | hono | prototype pollution — `Object.create(null)` at 3 parse sites (query/accept/header) | A | medium | **admitted** ✓ `oss-hono-proto-pollution-parsers` (gold=1.0, base=0.0, det×3) |
| colinhacks/zod #6346 | 2026-08-09 | zod | prototype pollution — keep `__proto__` as own prop in JSON-schema conv (assignProp at 3 sites) | A | medium | **admitted** ✓ `oss-zod-jsonschema-proto-pollution` (gold=1.0, base=0.0, det×3) |
| colinhacks/zod #6347 | 2026-08-09 | zod | ReDoS — emoji regex exponential backtracking | A | — | **rejected-bad** (only gradable via a timing assertion; flaky, esp. under emulation) |
| colinhacks/zod #6402 | 2026-08-14 | zod | JSON Pointer unescape when resolving `$ref` | A | low-med | candidate |

## Go (target ~2–3) — chi/gin middleware, gosec, oauth2, net/http-adjacent
| PR | merged | repo | vuln class / change | family | prov. diff. | status |
|----|--------|------|---------------------|--------|-------------|--------|
| labstack/echo #3009 | 2026-06-14 | echo | encoded path separator (%2F/%5C) bypasses route-level auth (GHSA-vfp3-v2gw-7wfq) | A | hard | **admitted** ✓ `oss-echo-encoded-path-separator` (gold=1.0, base=0.0, det×3; needs go-1.26 image) |
| labstack/echo #3006 | 2026-06-13 | echo | double-unescape of already-decoded path | A | — | **rejected** (traversal already blocked at base; % filename fix, weak security signal) |
| labstack/echo #3011 | — | echo | v4 backport of #3009 | A | — | skipped (v4 dup of #3009) |
| securego/gosec #1694 | 2026-06-15 | gosec | **Family B** — G404 scanner false negative: flag rand.Perm/Shuffle/ExpFloat64 | B | medium | **admitted** ✓ `oss-gosec-g404-weak-random-coverage` (gold=1.0, base=0.0, det×3; go-1.26, deps vendored) |

## Rust (target ~2–3) — url/regex parsing DoS, rustls, `ring`, cargo-audit
| PR | merged | repo | vuln class / change | family | prov. diff. | status |
|----|--------|------|---------------------|--------|-------------|--------|
| tafia/quick-xml #1001 | 2026-08-15 | quick-xml | serialization control-char escaping (`\r`/`\n`/`\t` → numeric refs) prevents round-trip corruption / attribute smuggling | A | medium | **admitted** ✓ `oss-quick-xml-serialize-control-escape` (gold=1.0, base=0.0, det×3; `:rust`, memchr vendored) |
| rustsec/rustsec #1664 | 2026-07-31 | rustsec | CVSS v2 scoring | B | — | **rejected-bad** (test-only PR, +42/-1, no behavioral fix) |
| Keats/jsonwebtoken #521 | 2026-06-20 | jsonwebtoken | remove insecure_disable_signature_validation | A | — | skipped (removal, no clean fail_to_pass) |
| GitoxideLabs/gitoxide #2918 | 2026-08-14 | gitoxide | reject overflowing cache-tree entry counts (int overflow DoS) | A | — | candidate (big workspace; deferred) |

> **NOTE — base-commit derivation:** quick-xml #1001 was *rebase-merged*, so the
> merge commit's first parent was an intermediate PR commit that already had the
> fix. The correct base is the parent of the PR's FIRST commit. `mine_security_prs.py`
> now resolves this via `pulls/<n>/commits[0].parents[0]`; always re-confirm the
> base is vulnerable (validator `pre-patch=0.0`) before trusting it.

---

## STATUS 2026-08-15 — 7 admitted, all validated (gold=1.0, base=0.0, deterministic ×3, Docker)
| # | task | lang | family | vuln class |
|---|------|------|--------|------------|
| 1 | oss-hono-proto-pollution-parsers | TS | A | prototype pollution |
| 2 | oss-undici-header-crlf-coercion | JS | A | CRLF header injection |
| 3 | oss-echo-encoded-path-separator | Go | A | encoded-separator auth bypass |
| 4 | oss-pyyaml-merge-key-dos | Python | A | merge-key amplification DoS |
| 5 | oss-quick-xml-serialize-control-escape | Rust | A | unescaped control chars |
| 6 | oss-gosec-g404-weak-random-coverage | Go | B | scanner false-negative (weak-random) |
| 7 | oss-zod-jsonschema-proto-pollution | TS | A | prototype pollution (JSON-schema) |

Languages: TS 2, Go 2, JS 1, Python 1, Rust 1. Families: A 6, B 1.

## Mapped path to 10–12 (next builds — all heavier offline builds)
These candidates are triaged and buildable but each needs a heavier offline setup
than the fast zero-/low-dep tasks above (workspace slicing, jsdom, or large Go
monorepos). Recipe is unchanged; budget ~30–45 min each.
- **GitoxideLabs/gitoxide #2918** (Rust, int-overflow DoS, new class) — edition-2024
  crate in a big workspace; needs `cargo-prune` to the gix-index closure + a binary
  fuzz fixture. Test asserts the crafted index is rejected without panicking (no
  error-text match).
- **cure53/DOMPurify #1555 / #1577** (TS/JS, XSS + DoS, **Family B**) — needs jsdom
  in the sandbox (heavy dep tree) to sanitize a DOM; would add a 2nd Family-B + the
  XSS class.
- **aquasecurity/trivy #10980 / #11066** or **google/osv-scanner #2915** (Go,
  **Family B**) — vuln-scanner matching-logic fixes; large Go monorepos, deps
  vendored offline.
- **tornadoweb/tornado #3704** (Python) — a bundled "Security 6.5.8" release; would
  need one of its fixes (auth/escape/httputil) isolated into a focused task.

## Measurement log (Phase 5 — deferred until the corpus is final)
Record per-task pass@1 here after the Haiku screen and the Sonnet 5 / Opus 5
repeat-3 sweep; compose the final set for a hard tail. (empty — deferred.)
