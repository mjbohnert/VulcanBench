"""Runtime web-leakage audit for CLI-harness runs.

VulcanBench's own loop has no web tools and runs its sandbox network-off, but
external harnesses (Cursor, and Claude Code / Codex when ``--network`` is set)
can browse. For a suite built from real merged PRs that is a solved-answer
oracle: the fix exists at a known public URL. Terminal-Bench, which also allows
internet, tells benchmark users to "remain vigilant" about agents locating
solutions; this module is that vigilance, automated.

Every v3 task records its provenance in ``metadata.upstream`` (repo URL, PR,
fix commit). The audit parses a run's captured CLI event stream, extracts every
web search and fetch, and matches them against that provenance. Verdicts
escalate:

- ``no_web``: the stream contains no web tool use.
- ``web_blocked``: the agent attempted web calls and every one was rejected by
  the harness's deny rules. No data reached the model, so this is clean --
  but it is recorded, because an agent reaching for the web on a
  decontaminated task is worth seeing.
- ``web_used``: browsed, but never touched the task's upstream project.
- ``upstream_access``: fetched content from the task's upstream repository.
  Post-fix sources (e.g. the repaired file on ``main``) contain the solution,
  so this is contamination even without the PR itself.
- ``solution_retrieval``: fetched the exact source PR, the fix commit, or a
  raw diff/patch of the upstream repo.

The audit annotates; it never rescores. Reports decide what a contaminated
run is worth.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_WEB_MARKERS = ("webSearchToolCall", "webFetchToolCall", '"WebSearch"', '"WebFetch"')
_URL_RE = re.compile(r"https?://[^\s\"'\\]+")

VERDICTS = ("no_web", "web_blocked", "web_used", "upstream_access", "solution_retrieval")


def upstream_refs(metadata: dict[str, Any]) -> dict[str, str]:
    """Extract the provenance identifiers the tripwire matches against."""
    up = metadata.get("upstream") or {}
    url = str(up.get("url") or "")
    repo_m = re.search(r"github\.com/([\w.-]+/[\w.-]+)", url)
    pr_m = re.search(r"/pull/(\d+)", url)
    return {
        "repo": repo_m.group(1).lower() if repo_m else "",
        "pr": pr_m.group(1) if pr_m else "",
        "commit": str(up.get("commit") or "")[:12].lower(),
    }


def _line_hits(line: str, refs: dict[str, str]) -> tuple[bool, bool]:
    """(upstream_access, solution_retrieval) signals for one stream line."""
    low = line.lower()
    repo = refs["repo"]
    repo_hit = bool(repo) and repo in low
    solution = False
    if repo_hit:
        if refs["pr"] and re.search(rf"/pull/{refs['pr']}\b", line):
            solution = True
        if refs["commit"] and refs["commit"] in low:
            solution = True
        if ".diff" in low or ".patch" in low or "patch-diff" in low:
            solution = True
    return repo_hit, solution


def _line_web_use(line: str) -> tuple[int, int, set[str]]:
    """(searches, fetches, hosts) contributed by one non-rejected stream line."""
    searches = 0
    fetches = 0
    if "webSearchToolCall" in line or '"WebSearch"' in line:
        searches = line.count("searchTerm") or 1
    if "webFetchToolCall" in line or '"WebFetch"' in line:
        fetches = 1
    hosts = set()
    for url in _URL_RE.findall(line):
        host = re.sub(r"^https?://", "", url).split("/", 1)[0]
        if host:
            hosts.add(host.lower())
    return searches, fetches, hosts


def audit_stream(stream_path: Path, metadata: dict[str, Any]) -> dict[str, Any]:
    """Audit one run's CLI event stream. Missing stream -> trivially no_web."""
    refs = upstream_refs(metadata)
    searches = 0
    fetches = 0
    hosts: set[str] = set()
    upstream_access = False
    solution = False

    blocked = 0
    if stream_path.exists():
        with stream_path.open(encoding="utf-8", errors="replace") as f:
            for line in f:
                if not any(m in line for m in _WEB_MARKERS):
                    continue
                # A denied call appears only as a completed event carrying a
                # rejection; it obtained nothing, so it is counted separately
                # and never scores as access.
                if '"rejected"' in line:
                    blocked += 1
                    continue
                # Otherwise count per tool-call start; Cursor re-emits the call
                # on completion and double counting would inflate the totals.
                if '"subtype": "completed"' in line or '"subtype":"completed"' in line:
                    continue
                s_add, f_add, line_hosts = _line_web_use(line)
                searches += s_add
                fetches += f_add
                hosts |= line_hosts
                repo_hit, sol = _line_hits(line, refs)
                upstream_access = upstream_access or repo_hit
                solution = solution or sol

    if solution:
        verdict = "solution_retrieval"
    elif upstream_access:
        verdict = "upstream_access"
    elif searches or fetches:
        verdict = "web_used"
    elif blocked:
        verdict = "web_blocked"
    else:
        verdict = "no_web"
    return {
        "verdict": verdict,
        "web_searches": searches,
        "web_fetches": fetches,
        "web_blocked": blocked,
        "hosts": sorted(hosts)[:40],
        "upstream": refs,
        "contaminated": verdict in ("upstream_access", "solution_retrieval"),
    }
