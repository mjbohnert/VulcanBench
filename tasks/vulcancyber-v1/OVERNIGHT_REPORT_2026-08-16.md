# Overnight report — 2026-08-16 (VulcanCyber v1)

_Autonomous run while you were asleep. Nothing was committed or pushed; PR #45
is untouched. This file is untracked — read, act, then delete it._

## TL;DR

- **Full-suite Docker re-validation: all 17/17 tasks are functionally sound** —
  every task grades `gold=1.0, pre-patch=0.0, deterministic over 3 runs`.
- Getting there surfaced **one real, must-fix suite defect** (below) and one
  benign local-Windows artifact.
- **Next-task mining was thin**: mostly dependabot CI-bump noise. No clean
  slam-dunk to build; one Go lead worth a look, details below. I did **not**
  build a new task — none cleared the bar to build unattended.

---

## 1. Suite health (Docker ×3, this machine)

First pass: **13 pass, 4 fail**. All 4 failures were in `setup`/patch-apply, not
in the tests. Root-caused to two independent issues:

### Issue A — REAL DEFECT: Go tasks' `vendor/` is gitignored, never committed

`oss-echo-encoded-path-separator` and `oss-gosec-g404-weak-random-coverage` both
carry `vendor` in their sliced `repo/.gitignore`, so **0 vendor files are tracked
in git**:

```
oss-echo-encoded-path-separator:  0 tracked vendor files
oss-gosec-g404-weak-random-coverage: 0 tracked vendor files
```

Their `setup` is `go build -mod=vendor ./...`, which requires `vendor/` to be
present. So **a fresh `git clone` of this repo cannot build these two tasks
offline** — the original ×3 admission only passed because the author's machine
had a local, uncommitted `vendor/` sitting in the working tree. This contradicts
`suite.json`'s "all validated" claim for anyone starting from a clean checkout
(CI included, unless CI regenerates vendor).

By contrast the Rust tasks commit their vendor correctly (`gix` 359 files,
`quick-xml` 55; `toml` is zero-dep so needs none). So this is specifically a
**Go-slice gap** — the slicer (or a manual step) vendored the deps but never
force-added them past the upstream repo's `.gitignore vendor` line.

**Proof the tasks themselves are fine:** I regenerated both vendor trees with
`go mod vendor` (echo → 140 files, gosec → 2391 files) and both then pass the
×3 gate cleanly.

**Recommended fix (your call — a repo change, so I did not commit it):**
force-add the vendor trees so clones are reproducible, matching the Rust tasks:

```bash
# from repo root, after regenerating vendor (go mod vendor in each repo/)
git add -f tasks/vulcancyber-v1/oss-echo-encoded-path-separator/repo/vendor
git add -f tasks/vulcancyber-v1/oss-gosec-g404-weak-random-coverage/repo/vendor
```

Consider auditing `scripts/slice_repo.py` so future Go slices force-add vendor
(or strip `vendor` from the slice `.gitignore`) automatically. gosec adds ~2400
files — large but consistent with how vendored tasks ship here.

### Issue B — BENIGN: local Windows CRLF (not a repo problem)

This box had `core.autocrlf=true`. On checkout that rewrote LF→CRLF in the
working tree, which:
- broke `cargo`'s vendored-source **checksum** verification (Rust: `gix`,
  `quick-xml`), and
- corrupted `gold_patch.diff` so `git apply` failed.

The **committed blobs are LF** (`git ls-files --eol` → `i/lf`), so CI/Linux was
never affected. Fixed for this working tree with repo-local config + re-checkout:

```bash
git config --local core.autocrlf false
git config --local core.eol lf
# then re-materialize affected trees so the working copy is LF
```

I've already applied this locally (it's in `.git/config`, repo-local, not global).
**Optional durable defense:** a root `.gitattributes` pinning task sources to LF
so no future Windows checkout can corrupt vendored/patched files, e.g.
`tasks/** text=auto eol=lf` (verify it doesn't fight the sliced repos' own
`.gitattributes`).

### Final state after both fixes: **17/17 PASS**

```
✓ content-disposition-ext-value   ✓ dompurify-ownerdocument-clobber
✓ echo-encoded-path-separator*    ✓ gix-validate-lone-at-refname
✓ gosec-g404-weak-random*         ✓ hono-proto-pollution-parsers
✓ pyyaml-merge-key-dos            ✓ quick-xml-serialize-control-escape
✓ toml-writer-quote-count         ✓ tornado-urlencoded-field-limit
✓ undici-header-crlf-coercion     ✓ urllib3-host-injection-validation
✓ validator-bytelength-surrogate  ✓ werkzeug-etag-strict-parse
✓ werkzeug-host-port-validation   ✓ werkzeug-int-converter-dos
✓ zod-jsonschema-proto-pollution
```
`*` = passes locally only after `go mod vendor` regeneration; see Issue A.

All 5 sandbox images are now built locally: `base`, `go-1.26`, `rust`,
`node-ts`, `node-dompurify`.

---

## 2. Next-task candidate triage (mining since 2026-06-01, all langs + tools)

The miner returned ~30 test-bearing PRs, but the large majority are dependabot
CI-workflow bumps (`chore(deps): bump actions/... group`) with a "security"
label — **noise, not fixes**. Genuine security-relevant PRs and my read:

| PR | Lang | Verdict |
|----|------|---------|
| **gofiber/fiber #4568** — combine repeated proxy headers for client-IP extraction | Go | **Best real lead.** Small (+74/-9, 3 files incl. `ctx_test.go`), genuine security angle (X-Forwarded-For spoofing). Risk: fiber is a framework — vendor/build closure may be heavy. Worth a feasibility slice. |
| rustsec/rustsec #1664 — check all three CVSS v2 scores | Rust | **Reject.** Diff is test-only (a new `#[test]` + test-harness rework); no production change → no deterministic `fail_to_pass`. Same reason we rejected DOMPurify #1555. |
| Keats/jsonwebtoken #521 — remove deprecated `insecure_disable_signature_validation` | Rust | **Low priority.** The "fix" is deleting an API; awkward to frame as a fail-at-base security task. |
| gofiber/fiber #4570 — log-injection / cookie-jar / CSRF fixes | Go | Real but **big** (+2620/-185, 38 files), multi-concern — hard to slice cleanly. |

**Recommendation:** this window is genuinely quiet for clean, buildable security
fixes in the charter's repo list. Rather than build a weak task, either (a) let
me do a feasibility slice of **fiber #4568** to check dep weight, or (b) broaden
the miner (add repos, or pull from an advisory feed like GHSA/RUSTSEC by CVE)
for stronger Family-B leads to fix the A16/B1 imbalance. Family B remains the
gap — and note rustsec-style tooling repos tend to fix via test-only PRs, which
don't qualify.

Full mining table: `scratchpad/mining.log`.

---

## 3. What I changed on disk (all local, uncommitted)

- Built sandbox images `rust`, `node-ts`, `node-dompurify` (node-ts/dompurify
  were needed for PR #45; rust for the suite check).
- Set repo-local `core.autocrlf=false`, `core.eol=lf`; re-checked-out the task
  tree to LF.
- Regenerated `vendor/` for the two Go tasks (gitignored, so not staged).
- `harness/sandbox/docker_executor.py` — the Windows `getuid` guard (already part
  of PR #45).
- This report + memory notes.

Nothing pushed. Your review gates: (1) the Go-vendor fix, (2) whether to slice
fiber #4568 or broaden mining.
