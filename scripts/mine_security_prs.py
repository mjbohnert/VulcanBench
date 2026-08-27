#!/usr/bin/env python3
"""Mine candidate *security* PRs for VulcanCyber v1 (read-only, via ``gh``).

This is a **discovery** helper: it finds real, merged, test-bearing PRs with a
security signal, merged on/after a cutoff date, across a curated set of upstream
repos, and prints a ``CANDIDATES.md``-ready table (plus an optional JSON sidecar).
It never fabricates provenance and never writes into a task, a human triages the
output, then builds each task with ``slice_repo.py`` + ``import_oss_issues.py``.

It shells out to the authenticated ``gh`` CLI only (no tokens handled here) and
makes only read calls (``gh search prs``, ``gh pr view``, ``gh api`` GETs).

Usage::

    # One language, defensive vuln-fix repos:
    python scripts/mine_security_prs.py --lang python

    # Include the security-tooling repo set (scanners/detectors):
    python scripts/mine_security_prs.py --lang go --tools

    # Every language, custom cutoff, JSON sidecar, cap per repo:
    python scripts/mine_security_prs.py --lang all --since 2026-06-01 \\
        --json out.json --per-repo 20

Output columns: repo | PR | merged | +/- LOC | files | tests? | title.
Only PRs that (a) merged on/after ``--since`` and (b) touch a test path are kept
unless ``--include-untested`` is passed. ``base_commit`` for slicing is the parent
of the PR's first commit (correct for rebase/squash merges; the merge commit's
first parent is only used as a fallback), reported in JSON. Always re-confirm the
base is actually vulnerable before building a task from it.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field

# --- Curated repo sets -------------------------------------------------------
# Family A: application/library repos whose security PRs are defensive vuln fixes.
# Family B (``--tools``): security-tooling projects (scanners, detectors, etc.).
# These are seeds, not an exhaustive list, extend freely; discovery is the point.

VULN_REPOS: dict[str, list[str]] = {
    "python": [
        "aio-libs/aiohttp",
        "encode/httpx",
        "encode/starlette",
        "pallets/werkzeug",
        "django/django",
        "urllib3/urllib3",
        "psf/requests",
        "tornadoweb/tornado",
        "getsentry/sentry-python",
        "pyca/cryptography",
        "yaml/pyyaml",
        "lxml/lxml",
        "python-jose/python-jose",
        "jpadilla/pyjwt",
        "aws/aws-sam-cli",
    ],
    "javascript": [
        "expressjs/express",
        "fastify/fastify",
        "validatorjs/validator.js",
        "nodejs/undici",
        "axios/axios",
        "isaacs/node-tar",
        "isaacs/minimatch",
        "jshttp/content-disposition",
        "jshttp/cookie",
        "node-fetch/node-fetch",
        "npm/node-semver",
        "follow-redirects/follow-redirects",
    ],
    "typescript": [
        "honojs/hono",
        "colinhacks/zod",
        "nestjs/nest",
        "trpc/trpc",
        "sinclairzx81/typebox",
        "lucia-auth/lucia",
        "panva/jose",
        "auth0/node-jsonwebtoken",
        "cure53/DOMPurify",
    ],
    "go": [
        "go-chi/chi",
        "gin-gonic/gin",
        "labstack/echo",
        "gofiber/fiber",
        "golang-jwt/jwt",
        "go-jose/go-jose",
        "casbin/casbin",
        "minio/minio",
        "traefik/traefik",
        "golang/oauth2",
        "gorilla/websocket",
        "gorilla/sessions",
    ],
    "rust": [
        "servo/rust-url",
        "rust-lang/regex",
        "hyperium/hyper",
        "rustls/rustls",
        "briansmith/ring",
        "tokio-rs/tokio",
        "actix/actix-web",
        "SergioBenitez/Rocket",
        "Keats/jsonwebtoken",
        "RustCrypto/hashes",
        "rust-lang/backtrace-rs",
        "tower-rs/tower-http",
        "zip-rs/zip2",
        "image-rs/image",
        "hickory-dns/hickory-dns",
        "GitoxideLabs/gitoxide",
        "hyperium/h2",
        "servo/html5ever",
        "rust-lang/git2-rs",
        "seanmonstar/reqwest",
        "tokio-rs/axum",
        "rustls/webpki",
        "unicode-rs/idna",
        "jonhoo/openssl-src-rs",
        "sfackler/rust-openssl",
        "RustCrypto/RSA",
        "rust-lang/flate2-rs",
        "tafia/quick-xml",
        "serde-rs/json",
        "toml-rs/toml",
    ],
}

TOOL_REPOS: dict[str, list[str]] = {
    "python": ["PyCQA/bandit", "pypa/pip-audit", "pyupio/safety", "Yelp/detect-secrets"],
    "javascript": ["retirejs/retire.js", "lirantal/is-website-vulnerable"],
    "typescript": ["ossf/scorecard-action", "aquasecurity/trivy-action"],
    "go": [
        "securego/gosec",
        "aquasecurity/trivy",
        "google/osv-scanner",
        "gitleaks/gitleaks",
        "trufflesecurity/trufflehog",
        "anchore/grype",
    ],
    "rust": ["rustsec/rustsec", "EmbarkStudios/cargo-deny"],
}

# High-precision security terms: a match anywhere (title OR body OR label) counts.
STRONG_KEYWORDS = [
    "cve-",
    "redos",
    "ssrf",
    "xss",
    "crlf",
    "prototype pollution",
    "open redirect",
    "path traversal",
    "zip slip",
    "directory traversal",
    "deserialization",
    "constant-time",
    "constant time",
    "command injection",
    "sql injection",
    "request smuggling",
    "arbitrary file",
    "xxe",
    "code injection",
    "csrf",
    "timing attack",
    "timing-safe",
    "auth bypass",
    "authentication bypass",
    "privilege escalation",
    "insecure",
    "sanitiz",
    "vulnerabilit",
]
# Weak terms: noisy in isolation (match unrelated PR bodies), so they only count
# when they appear in the TITLE or a LABEL, never body-only.
WEAK_KEYWORDS = [
    "security",
    "injection",
    "traversal",
    "escape",
    "smuggling",
    "overflow",
    "spoof",
    "bypass",
    "untrusted",
    "hardening",
    "malicious",
    "exploit",
]
SECURITY_KEYWORDS = STRONG_KEYWORDS + WEAK_KEYWORDS  # for reference/back-compat

TEST_PATH_MARKERS = (
    "test",
    "tests",
    "spec",
    "__tests__",
    "_test.go",
    ".test.",
    ".spec.",
    "test_",
    "/it/",
    "conftest.py",
)


@dataclass
class Candidate:
    repo: str
    number: int
    title: str
    url: str
    merged_at: str
    additions: int = 0
    deletions: int = 0
    changed_files: int = 0
    touches_tests: bool = False
    base_commit: str = ""
    merge_commit: str = ""
    matched_on: list[str] = field(default_factory=list)


def _gh_json(args: list[str]) -> object | None:
    """Run a ``gh`` command expected to emit JSON on stdout; None on failure."""
    try:
        proc = subprocess.run(
            ["gh", *args], capture_output=True, text=True, check=False, timeout=60
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"  ! gh failed ({e}) for: gh {' '.join(args)}", file=sys.stderr)
        return None
    if proc.returncode != 0:
        # Common, non-fatal: repo not found, no results, rate limited.
        msg = proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else "(no stderr)"
        print(f"  ! gh rc={proc.returncode}: {msg}", file=sys.stderr)
        return None
    if not proc.stdout.strip():
        return []
    try:
        parsed: object = json.loads(proc.stdout)
        return parsed
    except json.JSONDecodeError:
        print(f"  ! could not parse gh json for: gh {' '.join(args)}", file=sys.stderr)
        return None


def _search_repo(repo: str, since: str, per_repo: int) -> dict[int, list[str]]:
    """Return {pr_number: [matched signals]} for merged PRs since ``since``.

    GitHub PR search ANDs free-text terms and has no working ``OR``, so instead of
    one query per keyword (which would blow the 30/min search rate limit) we make a
    SINGLE search returning title+body+labels for the recent merged PRs, then match
    the security keyword list **locally**. ``per_repo`` caps how many recent merged
    PRs we scan, raise it for busy repos where security PRs sit deeper in history.
    """
    rows = _gh_json(
        [
            "search",
            "prs",
            "--repo",
            repo,
            "--state",
            "closed",
            "--merged-at",
            f">={since}",
            "--limit",
            str(per_repo),
            "--json",
            "number,title,labels,body",
        ]
    )
    hits: dict[int, list[str]] = {}
    if not isinstance(rows, list):
        return hits
    for row in rows:
        num = row.get("number")
        if not isinstance(num, int):
            continue
        title = (row.get("title") or "").lower()
        body = (row.get("body") or "").lower()
        label_names = [lbl.get("name", "").lower() for lbl in (row.get("labels") or [])]
        title_and_labels = " ".join([title, *label_names])
        matched: list[str] = []
        # Strong terms count anywhere.
        matched += [
            kw
            for kw in STRONG_KEYWORDS
            if kw in title or kw in body or any(kw in n for n in label_names)
        ]
        # Weak terms only count in the title or a label (body-only is too noisy).
        matched += [kw for kw in WEAK_KEYWORDS if kw in title_and_labels]
        if any("security" in n or "vuln" in n for n in label_names):
            matched.append("label:security")
        if matched:
            hits[num] = sorted(set(matched))
    return hits


def _enrich(repo: str, number: int, matched: list[str]) -> Candidate | None:
    """Fetch PR details; classify test-touching; resolve the slice base commit."""
    data = _gh_json(
        [
            "pr",
            "view",
            str(number),
            "--repo",
            repo,
            "--json",
            "title,url,mergedAt,additions,deletions,files,mergeCommit",
        ]
    )
    if not isinstance(data, dict) or not data.get("mergedAt"):
        return None
    files = data.get("files") or []
    paths = [f.get("path", "") for f in files]
    touches_tests = any(any(m in p.lower() for m in TEST_PATH_MARKERS) for p in paths)
    merge_oid = (data.get("mergeCommit") or {}).get("oid", "") or ""
    # The reliable slice base is the parent of the PR's FIRST commit. The merge
    # commit's first parent is only correct for merge-commit merges; for a
    # rebase- or squash-merge it points at an intermediate PR commit that already
    # contains the fix, so ALWAYS verify the base is still vulnerable before use.
    base_commit = _pr_base(repo, number) or _first_parent(repo, merge_oid)
    return Candidate(
        repo=repo,
        number=number,
        title=(data.get("title") or "").strip(),
        url=data.get("url", ""),
        merged_at=(data.get("mergedAt") or "")[:10],
        additions=int(data.get("additions") or 0),
        deletions=int(data.get("deletions") or 0),
        changed_files=len(files),
        touches_tests=touches_tests,
        base_commit=base_commit,
        merge_commit=merge_oid,
        matched_on=matched,
    )


def _pr_base(repo: str, number: int) -> str:
    """Parent of the PR's first commit, the correct slice base for any merge style."""
    try:
        proc = subprocess.run(
            ["gh", "api", f"repos/{repo}/pulls/{number}/commits", "--jq", ".[0].parents[0].sha"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return proc.stdout.strip() if proc.returncode == 0 else ""


def _first_parent(repo: str, merge_oid: str) -> str:
    """The merge commit's first parent = the base-branch state to slice at.

    ``gh api --jq`` emits the raw (unquoted) SHA, which is not JSON, so this reads
    stdout directly rather than going through the JSON helper.
    """
    try:
        proc = subprocess.run(
            ["gh", "api", f"repos/{repo}/commits/{merge_oid}", "--jq", ".parents[0].sha"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return proc.stdout.strip() if proc.returncode == 0 else ""


def mine(
    langs: list[str],
    *,
    tools: bool,
    since: str,
    per_repo: int,
    include_untested: bool,
    pause: float,
    max_enrich: int,
) -> list[Candidate]:
    repos: list[str] = []
    for lang in langs:
        repos.extend(VULN_REPOS.get(lang, []))
        if tools:
            repos.extend(TOOL_REPOS.get(lang, []))
    seen: set[str] = set()
    deduped: list[str] = []
    for r in repos:
        if r not in seen:
            seen.add(r)
            deduped.append(r)
    repos = deduped

    out: list[Candidate] = []
    for repo in repos:
        hits = _search_repo(repo, since, per_repo)
        time.sleep(pause)  # one search per repo, stay under 30/min
        # Enrich the most-recent signal PRs first, capped so a noisy repo does not
        # dominate the run; strong-signal PRs (label:security / strong keyword) win ties.
        ordered = sorted(
            hits.items(),
            key=lambda kv: (_signal_rank(kv[1]), kv[0]),
            reverse=True,
        )[:max_enrich]
        print(f"· {repo}: {len(hits)} signal PR(s), enriching {len(ordered)}", file=sys.stderr)
        for number, matched in ordered:
            cand = _enrich(repo, number, matched)
            if cand is None:
                continue
            if not cand.touches_tests and not include_untested:
                continue
            out.append(cand)
    out.sort(key=lambda c: (c.merged_at, c.repo), reverse=True)
    return out


def _signal_rank(matched: list[str]) -> int:
    """Higher = stronger security signal (prioritise which PRs to enrich)."""
    rank = 0
    if "label:security" in matched:
        rank += 10
    rank += sum(2 for m in matched if m in STRONG_KEYWORDS)
    rank += sum(1 for m in matched if m in WEAK_KEYWORDS)
    return rank


def _markdown(cands: list[Candidate]) -> str:
    lines = [
        "| repo | PR | merged | +/- LOC | files | tests? | title |",
        "|------|----|--------|---------|-------|--------|-------|",
    ]
    for c in cands:
        pr = f"[#{c.number}]({c.url})"
        loc = f"+{c.additions}/-{c.deletions}"
        tests = "yes" if c.touches_tests else "no"
        title = c.title.replace("|", "\\|")[:70]
        lines.append(
            f"| {c.repo} | {pr} | {c.merged_at} | {loc} | {c.changed_files} | {tests} | {title} |"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Mine candidate security PRs for VulcanCyber v1")
    p.add_argument(
        "--lang",
        default="all",
        help="python|javascript|typescript|go|rust|all (comma-separated ok)",
    )
    p.add_argument("--tools", action="store_true", help="also search security-tooling repos")
    p.add_argument("--since", default="2026-06-01", help="only PRs merged on/after this date")
    p.add_argument("--per-repo", type=int, default=25, help="max PRs per search query")
    p.add_argument(
        "--include-untested",
        action="store_true",
        help="keep PRs that do not touch a test path (default: drop them)",
    )
    p.add_argument("--pause", type=float, default=2.2, help="seconds between searches (rate limit)")
    p.add_argument(
        "--max-enrich",
        type=int,
        default=12,
        help="max PRs to enrich per repo (strongest-signal, newest first)",
    )
    p.add_argument("--json", type=str, default="", help="also write results to this JSON file")
    args = p.parse_args(argv)

    all_langs = ["python", "javascript", "typescript", "go", "rust"]
    requested = [s.strip() for s in args.lang.split(",") if s.strip()]
    langs = all_langs if "all" in requested else [r for r in requested if r in all_langs]
    if not langs:
        print(f"error: no valid languages in {args.lang!r}", file=sys.stderr)
        return 2

    cands = mine(
        langs,
        tools=args.tools,
        since=args.since,
        per_repo=args.per_repo,
        include_untested=args.include_untested,
        pause=args.pause,
        max_enrich=args.max_enrich,
    )
    print(f"\n# {len(cands)} candidate(s), merged >= {args.since}\n")
    print(_markdown(cands))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump([asdict(c) for c in cands], fh, indent=2)
        print(f"\n(json → {args.json})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
