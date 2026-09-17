"""Score a *model family* from cached single-model runs.

VulcanBench's unit of evaluation is ``(task, model, effort, harness)``. A family
benchmark asks a different question: given a roster of members (e.g. Grok 4.6 +
Composer 2.5, or Sol + Terra + Luna), which **workflow** and which
**(member, effort)** should handle each task?

This module answers the second half from cache: it never launches new runs.
Each family policy (always-this-member, metadata router, simulated cascade,
oracle) is a routing table over cells that ``vulcanbench run`` / ``effort-sweep``
already produced. Live topologies that mix models *inside* one task
(orchestrator, patch-handoff cascade) are specified in ``docs/FAMILY_BENCH.md``
and are not simulated here — independent cached attempts cannot reconstruct
them honestly.
"""

from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from harness.agent.cli_agents import CLI_AGENT_PROVIDERS
from harness.compare import _scan_runs_recursive, suite_version
from harness.effort import normalize_effort
from harness.leaderboard import mark_stale
from harness.suite import DEFAULT_TASKS_BASE, load_suite
from harness.task_metadata import repo_scale, task_complexity, task_difficulty
from harness.tasks import load_task

_EFFORT_SORT = {"low": 0, "medium": 1, "high": 2, "extra-high": 3, "-": 4}
_UNSET_EFFORT = "-"
_ROLES = frozenset({"driver", "planner", "worker"})


class FamilySpecError(ValueError):
    """Raised when a family JSON file or ``--members`` list is invalid."""


class FamilyMember(BaseModel):
    """One model in the family roster."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    model: str = Field(min_length=1)
    efforts: list[str | None] | None = None
    role: str = "driver"

    @field_validator("model")
    @classmethod
    def _model_is_spec(cls, value: str) -> str:
        if ":" not in value.strip():
            raise ValueError(f"member model must be provider:model, got {value!r}")
        return value.strip()

    @field_validator("role")
    @classmethod
    def _role_known(cls, value: str) -> str:
        role = value.strip().lower()
        if role not in _ROLES:
            allowed = ", ".join(sorted(_ROLES))
            raise ValueError(f"role must be one of {allowed}, got {value!r}")
        return role

    @field_validator("efforts")
    @classmethod
    def _efforts_known(cls, value: list[str | None] | None) -> list[str | None] | None:
        if value is None:
            return None
        if not value:
            raise ValueError("efforts must be omitted or a non-empty list")
        out: list[str | None] = []
        seen: set[str] = set()
        for raw in value:
            if raw is None or (isinstance(raw, str) and not raw.strip()):
                label = _UNSET_EFFORT
            else:
                label = normalize_effort(raw) or _UNSET_EFFORT
            if label in seen:
                continue
            seen.add(label)
            out.append(None if label == _UNSET_EFFORT else label)
        return out


class FamilySpec(BaseModel):
    """Roster of models treated as one product family."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    display_name: str | None = None
    description: str = ""
    members: list[FamilyMember] = Field(min_length=1)
    cascade_order: list[str] | None = None

    @model_validator(mode="after")
    def _unique_ids_and_cascade(self) -> FamilySpec:
        ids = [m.id for m in self.members]
        if len(ids) != len(set(ids)):
            raise ValueError("family member ids must be unique")
        if self.cascade_order:
            known = set(ids)
            for token in self.cascade_order:
                member_id = token.split("@", 1)[0].strip()
                if member_id not in known:
                    raise ValueError(f"cascade_order references unknown member {member_id!r}")
        return self


def harness_kind(model: str) -> str:
    """Return the execution harness implied by a ``provider:model`` spec."""
    provider = model.partition(":")[0].strip().lower()
    if provider in CLI_AGENT_PROVIDERS:
        return provider
    return "vulcanbench-loop"


def load_family_spec(path: Path) -> FamilySpec:
    """Load and validate a family roster from JSON."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise FamilySpecError(f"cannot read family spec {path}: {e}") from e
    if not isinstance(raw, dict):
        raise FamilySpecError(f"family spec {path} must be a JSON object")
    try:
        return FamilySpec.model_validate(raw)
    except Exception as e:
        raise FamilySpecError(f"invalid family spec {path}: {e}") from e


def family_from_models(models: list[str], family_id: str = "adhoc") -> FamilySpec:
    """Build a family that discovers effort levels from whatever runs exist."""
    members: list[FamilyMember] = []
    seen_ids: set[str] = set()
    for spec in models:
        trimmed = spec.strip()
        if not trimmed:
            continue
        base = trimmed.replace(":", "-")
        member_id = base
        n = 2
        while member_id in seen_ids:
            member_id = f"{base}-{n}"
            n += 1
        seen_ids.add(member_id)
        try:
            members.append(FamilyMember(id=member_id, model=trimmed, efforts=None))
        except Exception as e:
            raise FamilySpecError(str(e)) from e
    if not members:
        raise FamilySpecError("at least one member model is required")
    return FamilySpec(id=family_id, display_name=family_id, members=members)


def parse_members(raw: str) -> list[str]:
    """Split a comma-separated ``--members`` list."""
    models = [part.strip() for part in raw.split(",") if part.strip()]
    if not models:
        raise FamilySpecError("--members must list at least one provider:model spec")
    return models


def build_family_report(
    spec: FamilySpec,
    suite: str,
    runs_dir: Path = Path("./runs"),
    tasks_base: Path = DEFAULT_TASKS_BASE,
) -> dict[str, Any]:
    """Assemble family-policy scores for ``suite`` from cached runs only."""
    ver = suite_version(suite, tasks_base)
    loaded = load_suite(suite, tasks_base)
    suite_tasks = list(ver["task_ids"])
    suite_task_set = set(suite_tasks)

    rows = [r for r in _scan_runs_recursive(runs_dir) if r.get("task_id") in suite_task_set]
    mark_stale(rows, loaded.tasks_root)
    fresh = [r for r in rows if r.get("task_stale") is not True]
    n_stale_excluded = sum(1 for r in rows if r.get("task_stale") is True)

    grouped = _group_cells(fresh)
    cells, cell_warnings = _resolve_cells(spec, grouped, suite_tasks)
    harnesses = sorted({harness_kind(m.model) for m in spec.members})
    mixed_harness = len(harnesses) > 1

    fair_tasks = _intersection_tasks(cells, suite_tasks)
    warnings = list(cell_warnings)
    if mixed_harness:
        warnings.append(
            "mixed harness: members run under "
            + ", ".join(harnesses)
            + " — a family score that mixes vendor CLIs with the uniform loop "
            "measures a product stack, not a single agent runtime. Prefer "
            "same-harness rosters for apples-to-apples routing."
        )
    if not fair_tasks:
        warnings.append(
            "no common coverage: at least one family cell is missing every suite "
            "task, so comparative policies (oracle, router, cascade) are skipped. "
            "Run the missing members, then re-report."
        )

    policies: list[dict[str, Any]] = []
    for cell in cells:
        policies.append(_static_policy(cell, fair_tasks or _cell_tasks(cell, suite_tasks)))

    eval_tasks = fair_tasks
    if eval_tasks:
        policies.append(_oracle_policy(cells, eval_tasks, mode="cheapest_sufficient"))
        policies.append(_oracle_policy(cells, eval_tasks, mode="max_pass"))
        policies.append(_metadata_router_policy(cells, eval_tasks, loaded.tasks_root))
        policies.append(_cascade_policy(spec, cells, eval_tasks))

    policies.sort(
        key=lambda p: (
            p.get("leaks_labels") is True,
            -(p["pass_at_1"] if p.get("pass_at_1") is not None else -1.0),
            p["policy_cost_usd"] if p.get("policy_cost_usd") is not None else math.inf,
        )
    )

    return {
        **ver,
        "family": spec.model_dump(),
        "runs_dir": str(runs_dir),
        "n_stale_excluded": n_stale_excluded,
        "harnesses": harnesses,
        "mixed_harness": mixed_harness,
        "fair_tasks": fair_tasks,
        "n_fair_tasks": len(fair_tasks),
        "cells": [_cell_summary(c, suite_tasks) for c in cells],
        "policies": policies,
        "warnings": warnings,
        "limitations": [
            "Policies route whole tasks to one (member, effort). They do not "
            "measure in-task orchestrators, planners, or patch-handoff cascades.",
            "cascade_restart is an independent-restart simulation: the expensive "
            "member does not see the cheap member's failed patch.",
            "oracle_cheapest_sufficient and oracle_max_pass peek at that task's "
            "own outcomes (label leak). They are upper bounds, not deployable routers.",
            "metadata_router is leave-one-task-out on (language, scale, difficulty, "
            "complexity). It is the deployable baseline this command can support "
            "without a live multi-model runner.",
        ],
    }


def to_markdown(report: dict[str, Any]) -> str:
    """Render a family report as shareable Markdown."""
    family = report.get("family") or {}
    title = family.get("display_name") or family.get("id") or "family"
    lines = [
        f"# VulcanBench family report — {title}",
        "",
        f"Suite **{report.get('suite')}** frozen @ `{report.get('version')}` "
        f"({report.get('n_tasks')} tasks). Comparative policies use "
        f"**{report.get('n_fair_tasks', 0)}** tasks covered by every family cell.",
    ]
    desc = family.get("description")
    if desc:
        lines += ["", desc]
    if report.get("mixed_harness"):
        lines += [
            "",
            "> **Mixed harness.** Members run under "
            + ", ".join(report.get("harnesses") or [])
            + ". Do not read this column as a uniform-loop comparison.",
        ]
    lines += ["", "## Policies", ""]
    lines += [
        "| Policy | Kind | Pass@1 ± se | Cost (1x suite) | Latency | Tasks | Notes |",
        "|---|---|---|---|---|---|---|",
    ]
    for policy in report.get("policies") or []:
        notes: list[str] = []
        if policy.get("leaks_labels"):
            notes.append("oracle / leaks labels")
        if policy.get("kind") == "cascade":
            notes.append("independent restart; no patch handoff")
        if not policy.get("cost_known", True):
            notes.append("cost incomplete")
        lines.append(
            "| {id} | {kind} | {pass_at_1} ± {se} | {cost} | {lat} | {n}/{n_eval} | {notes} |".format(
                id=policy.get("id"),
                kind=policy.get("kind"),
                pass_at_1=_fmt(policy.get("pass_at_1")),
                se=_fmt(policy.get("pass_at_1_stderr")),
                cost=_fmt_cost(policy.get("policy_cost_usd"), policy.get("cost_known")),
                lat=_fmt_secs(policy.get("avg_duration_s")),
                n=policy.get("n_tasks"),
                n_eval=policy.get("n_eval_tasks"),
                notes="; ".join(notes) or "—",
            )
        )

    lines += ["", "## Cells (cached single-model columns)", ""]
    lines += [
        "| Member | Model | Effort | Coverage | Pass@1 | Mean cost / task |",
        "|---|---|---|---|---|---|",
    ]
    for cell in report.get("cells") or []:
        lines.append(
            "| {mid} | {model} | {effort} | {cov} | {p} | {cost} |".format(
                mid=cell.get("member_id"),
                model=cell.get("model"),
                effort=cell.get("effort"),
                cov=f"{cell.get('n_present')}/{cell.get('n_total')}",
                p=_fmt(cell.get("pass_at_1")),
                cost=_fmt_cost(cell.get("mean_cost_per_task"), cell.get("cost_known")),
            )
        )

    router = next(
        (p for p in report.get("policies") or [] if p.get("kind") == "router"),
        None,
    )
    if router and router.get("routing"):
        lines += [
            "",
            "## Metadata router (leave-one-task-out)",
            "",
            "Deployable routing: pick the (member, effort) that won on *other* "
            "tasks in the same (language, scale, difficulty, complexity) stratum.",
            "",
            "| Task | Stratum | Choice | Pass@1 | Cost |",
            "|---|---|---|---|---|",
        ]
        for row in router["routing"]:
            lines.append(
                "| {task} | {stratum} | {choice} | {p} | {cost} |".format(
                    task=row.get("task_id"),
                    stratum=row.get("stratum") or "—",
                    choice=f"{row.get('member_id')}@{row.get('effort')}",
                    p=_fmt(row.get("solve_rate")),
                    cost=_fmt_cost(row.get("cost_usd"), row.get("cost_usd") is not None),
                )
            )

    warnings = report.get("warnings") or []
    if warnings:
        lines += ["", "## Warnings", ""]
        lines.extend(f"- {w}" for w in warnings)

    limitations = report.get("limitations") or []
    if limitations:
        lines += ["", "## What this does not measure", ""]
        lines.extend(f"- {item}" for item in limitations)
        lines += ["", "See [FAMILY_BENCH.md](FAMILY_BENCH.md) for live topologies."]

    return "\n".join(lines) + "\n"


# --- internals ----------------------------------------------------------------


def _group_cells(
    rows: list[dict[str, Any]],
) -> dict[tuple[str, str], dict[str, list[dict[str, Any]]]]:
    cells: dict[tuple[str, str], dict[str, list[dict[str, Any]]]] = {}
    for row in rows:
        model = str(row.get("model") or "?")
        effort = normalize_effort(row.get("effort_requested")) or _UNSET_EFFORT
        task_id = str(row.get("task_id") or "?")
        cells.setdefault((model, effort), {}).setdefault(task_id, []).append(row)
    return cells


def _resolve_cells(
    spec: FamilySpec,
    grouped: dict[tuple[str, str], dict[str, list[dict[str, Any]]]],
    suite_tasks: list[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    cells: list[dict[str, Any]] = []
    for member in spec.members:
        efforts = _member_efforts(member, grouped)
        if not efforts:
            warnings.append(f"member {member.id} ({member.model}) has no cached runs on this suite")
            efforts = [_UNSET_EFFORT]
        for effort in efforts:
            raw = grouped.get((member.model, effort), {})
            by_task = {tid: _task_stats(runs) for tid, runs in raw.items() if tid in suite_tasks}
            if not by_task:
                warnings.append(f"no fresh runs for {member.id} ({member.model}, effort {effort})")
            cells.append(
                {
                    "member_id": member.id,
                    "model": member.model,
                    "effort": effort,
                    "role": member.role,
                    "by_task": by_task,
                }
            )
    return cells, warnings


def _member_efforts(
    member: FamilyMember,
    grouped: dict[tuple[str, str], dict[str, list[dict[str, Any]]]],
) -> list[str]:
    if member.efforts is not None:
        return [_UNSET_EFFORT if e is None else e for e in member.efforts]
    found = sorted(
        (effort for model, effort in grouped if model == member.model),
        key=lambda e: (_EFFORT_SORT.get(e, 9), e),
    )
    return found


def _task_stats(runs: list[dict[str, Any]]) -> dict[str, Any]:
    solved = sum(1 for row in runs if (row.get("functional") or 0) >= 1.0)
    costs = [row["cost_usd"] for row in runs if isinstance(row.get("cost_usd"), (int, float))]
    durs = [row["duration_s"] for row in runs if isinstance(row.get("duration_s"), (int, float))]
    return {
        "n_runs": len(runs),
        "solve_rate": solved / len(runs) if runs else 0.0,
        "mean_cost": (sum(costs) / len(costs)) if costs else None,
        "cost_known": len(costs) == len(runs) and bool(runs),
        "mean_duration": (sum(durs) / len(durs)) if durs else None,
    }


def _cell_tasks(cell: dict[str, Any], suite_tasks: list[str]) -> list[str]:
    present = cell.get("by_task") or {}
    return [tid for tid in suite_tasks if tid in present]


def _intersection_tasks(cells: list[dict[str, Any]], suite_tasks: list[str]) -> list[str]:
    if not cells:
        return []
    common: set[str] | None = None
    for cell in cells:
        covered = set(_cell_tasks(cell, suite_tasks))
        common = covered if common is None else common & covered
    return [tid for tid in suite_tasks if common is not None and tid in common]


def _cell_summary(cell: dict[str, Any], suite_tasks: list[str]) -> dict[str, Any]:
    present = _cell_tasks(cell, suite_tasks)
    by_task: dict[str, Any] = cell["by_task"]
    rates = [by_task[t]["solve_rate"] for t in present]
    costs = [
        by_task[t]["mean_cost"]
        for t in present
        if isinstance(by_task[t].get("mean_cost"), (int, float))
    ]
    cost_known = bool(present) and all(by_task[t].get("cost_known") for t in present)
    return {
        "member_id": cell["member_id"],
        "model": cell["model"],
        "effort": cell["effort"],
        "role": cell["role"],
        "n_present": len(present),
        "n_total": len(suite_tasks),
        "complete": len(present) == len(suite_tasks),
        "pass_at_1": _mean(rates),
        "mean_cost_per_task": _mean(costs),
        "cost_known": cost_known,
        "missing_tasks": [t for t in suite_tasks if t not in by_task],
    }


def _policy_from_routing(
    *,
    policy_id: str,
    kind: str,
    description: str,
    leaks_labels: bool,
    eval_tasks: list[str],
    routing: list[dict[str, Any]],
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    routed = [row for row in routing if row.get("task_id") in eval_tasks and "solve_rate" in row]
    rates = [float(row["solve_rate"]) for row in routed]
    costs = [
        float(row["cost_usd"]) for row in routed if isinstance(row.get("cost_usd"), (int, float))
    ]
    durs = [
        float(row["duration_s"])
        for row in routed
        if isinstance(row.get("duration_s"), (int, float))
    ]
    cost_known = bool(routed) and all(
        isinstance(row.get("cost_usd"), (int, float)) for row in routed
    )
    payload: dict[str, Any] = {
        "id": policy_id,
        "kind": kind,
        "description": description,
        "leaks_labels": leaks_labels,
        "n_eval_tasks": len(eval_tasks),
        "n_tasks": len(routed),
        "n_unrouted": len(eval_tasks) - len(routed),
        "pass_at_1": _mean(rates),
        "pass_at_1_stderr": _stderr(rates),
        "policy_cost_usd": round(sum(costs), 4) if costs and cost_known else _sum_or_none(costs),
        "cost_known": cost_known,
        "avg_duration_s": _mean(durs),
        "routing": routing,
    }
    if extra:
        payload.update(extra)
    return payload


def _static_policy(cell: dict[str, Any], eval_tasks: list[str]) -> dict[str, Any]:
    routing = [_choice_row(cell, tid) for tid in eval_tasks if tid in cell["by_task"]]
    effort = cell["effort"]
    return _policy_from_routing(
        policy_id=f"static:{cell['member_id']}@{effort}",
        kind="static",
        description=f"Always {cell['model']} at effort {effort}.",
        leaks_labels=False,
        eval_tasks=eval_tasks,
        routing=routing,
    )


def _oracle_policy(
    cells: list[dict[str, Any]], eval_tasks: list[str], *, mode: str
) -> dict[str, Any]:
    routing: list[dict[str, Any]] = []
    for task_id in eval_tasks:
        candidates = [_choice_row(cell, task_id) for cell in cells if task_id in cell["by_task"]]
        if not candidates:
            continue
        if mode == "cheapest_sufficient":
            sufficient = [c for c in candidates if c["solve_rate"] >= 1.0]
            pool = sufficient or candidates
            chosen = min(pool, key=_cost_then_neg_pass)
        else:
            chosen = min(candidates, key=_neg_pass_then_cost)
        chosen = {**chosen, "reason": mode}
        routing.append(chosen)
    label = "oracle_cheapest_sufficient" if mode == "cheapest_sufficient" else "oracle_max_pass"
    desc = (
        "Per task, pick the cheapest cell that always solved it "
        "(falls back to best pass@1). Peeks at that task's outcomes."
        if mode == "cheapest_sufficient"
        else "Per task, pick the highest pass@1 cell (tie-break cheaper). "
        "Peeks at that task's outcomes."
    )
    return _policy_from_routing(
        policy_id=label,
        kind="oracle",
        description=desc,
        leaks_labels=True,
        eval_tasks=eval_tasks,
        routing=routing,
    )


def _metadata_router_policy(
    cells: list[dict[str, Any]], eval_tasks: list[str], tasks_root: Path
) -> dict[str, Any]:
    strata = {tid: _stratum(tid, tasks_root) for tid in eval_tasks}
    routing: list[dict[str, Any]] = []
    for task_id in eval_tasks:
        same = [t for t in eval_tasks if t != task_id and strata[t] == strata[task_id]]
        pool = same or [t for t in eval_tasks if t != task_id]
        fallback = "stratum" if same else ("global" if pool else "single-task")
        chosen_cell = _pick_cell_on_pool(cells, pool if pool else [task_id], require_all=bool(pool))
        if chosen_cell is None or task_id not in chosen_cell["by_task"]:
            continue
        row = _choice_row(chosen_cell, task_id)
        row["stratum"] = strata[task_id]
        row["reason"] = f"loo-{fallback}"
        routing.append(row)
    return _policy_from_routing(
        policy_id="metadata_router",
        kind="router",
        description=(
            "Leave-one-task-out: pick the cell with the best pass@1 on other tasks "
            "in the same (language, scale, difficulty, complexity) stratum; "
            "fall back to a global LOO when the stratum is a singleton."
        ),
        leaks_labels=False,
        eval_tasks=eval_tasks,
        routing=routing,
    )


def _cascade_policy(
    spec: FamilySpec, cells: list[dict[str, Any]], eval_tasks: list[str]
) -> dict[str, Any]:
    ordered = _cascade_cells(spec, cells, eval_tasks)
    routing: list[dict[str, Any]] = []
    for task_id in eval_tasks:
        present = [c for c in ordered if task_id in c["by_task"]]
        if not present:
            continue
        remaining = 1.0
        p_solve = 0.0
        e_cost = 0.0
        e_dur = 0.0
        cost_known = True
        dur_known = True
        steps: list[dict[str, Any]] = []
        for cell in present:
            stats = cell["by_task"][task_id]
            s = float(stats["solve_rate"])
            c = stats.get("mean_cost")
            d = stats.get("mean_duration")
            if not isinstance(c, (int, float)):
                cost_known = False
                c = 0.0
            else:
                e_cost += remaining * float(c)
            if not isinstance(d, (int, float)):
                dur_known = False
            else:
                e_dur += remaining * float(d)
            p_solve += remaining * s
            steps.append(
                {
                    "member_id": cell["member_id"],
                    "effort": cell["effort"],
                    "solve_rate": round(s, 4),
                    "weight": round(remaining, 4),
                }
            )
            remaining *= 1.0 - s
        routing.append(
            {
                "task_id": task_id,
                "member_id": present[0]["member_id"],
                "model": present[0]["model"],
                "effort": present[0]["effort"],
                "solve_rate": p_solve,
                "cost_usd": e_cost if cost_known else None,
                "duration_s": e_dur if dur_known else None,
                "reason": "cascade_restart",
                "cascade_steps": steps,
            }
        )
    order_ids = [f"{c['member_id']}@{c['effort']}" for c in ordered]
    return _policy_from_routing(
        policy_id="cascade_restart",
        kind="cascade",
        description=(
            "Try cells cheapest-first (or spec cascade_order). On failure, restart "
            "independently with the next cell. Expected pass/cost from cached "
            "solve rates; no patch is handed off."
        ),
        leaks_labels=False,
        eval_tasks=eval_tasks,
        routing=routing,
        extra={"cascade_order": order_ids},
    )


def _cascade_cells(
    spec: FamilySpec, cells: list[dict[str, Any]], eval_tasks: list[str]
) -> list[dict[str, Any]]:
    if spec.cascade_order:
        by_key = {(c["member_id"], c["effort"]): c for c in cells}
        by_member: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for cell in cells:
            by_member[cell["member_id"]].append(cell)
        ordered: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for token in spec.cascade_order:
            if "@" in token:
                member_id, effort_raw = token.split("@", 1)
                effort = normalize_effort(effort_raw) or _UNSET_EFFORT
                chosen = by_key.get((member_id.strip(), effort))
                if chosen is not None:
                    key = (chosen["member_id"], chosen["effort"])
                    if key not in seen:
                        ordered.append(chosen)
                        seen.add(key)
            else:
                for cell in by_member.get(token.strip(), []):
                    key = (cell["member_id"], cell["effort"])
                    if key not in seen:
                        ordered.append(cell)
                        seen.add(key)
        for cell in cells:
            key = (cell["member_id"], cell["effort"])
            if key not in seen:
                ordered.append(cell)
                seen.add(key)
        return ordered
    return sorted(
        cells, key=lambda c: (_cell_mean_cost(c, eval_tasks), c["member_id"], c["effort"])
    )


def _pick_cell_on_pool(
    cells: list[dict[str, Any]], pool: list[str], *, require_all: bool
) -> dict[str, Any] | None:
    scored: list[tuple[float, float, dict[str, Any]]] = []
    for cell in cells:
        by_task = cell["by_task"]
        if require_all and any(tid not in by_task for tid in pool):
            continue
        rates = [by_task[tid]["solve_rate"] for tid in pool if tid in by_task]
        if not rates:
            continue
        costs = [
            by_task[tid]["mean_cost"]
            for tid in pool
            if tid in by_task and isinstance(by_task[tid].get("mean_cost"), (int, float))
        ]
        mean_cost = sum(costs) / len(costs) if costs else math.inf
        scored.append((sum(rates) / len(rates), mean_cost, cell))
    if not scored:
        return None
    scored.sort(key=lambda t: (-t[0], t[1], t[2]["member_id"], t[2]["effort"]))
    return scored[0][2]


def _choice_row(cell: dict[str, Any], task_id: str) -> dict[str, Any]:
    stats = cell["by_task"][task_id]
    return {
        "task_id": task_id,
        "member_id": cell["member_id"],
        "model": cell["model"],
        "effort": cell["effort"],
        "solve_rate": stats["solve_rate"],
        "cost_usd": stats.get("mean_cost"),
        "duration_s": stats.get("mean_duration"),
        "n_runs": stats["n_runs"],
    }


def _stratum(task_id: str, tasks_root: Path) -> str:
    try:
        meta = load_task(task_id, tasks_root).metadata
    except (OSError, ValueError):
        return "unknown"
    langs = meta.get("languages") or ["?"]
    language = langs[0] if isinstance(langs, list) and langs else "?"
    return f"{language}/{repo_scale(meta)}/{task_difficulty(meta)}/{task_complexity(meta)}"


def _cell_mean_cost(cell: dict[str, Any], eval_tasks: list[str]) -> float:
    costs = [
        cell["by_task"][tid]["mean_cost"]
        for tid in eval_tasks
        if tid in cell["by_task"]
        and isinstance(cell["by_task"][tid].get("mean_cost"), (int, float))
    ]
    return sum(costs) / len(costs) if costs else math.inf


def _cost_then_neg_pass(row: dict[str, Any]) -> tuple[float, float, str, str]:
    cost = row.get("cost_usd")
    cost_key = float(cost) if isinstance(cost, (int, float)) else math.inf
    return (cost_key, -float(row["solve_rate"]), row["member_id"], row["effort"])


def _neg_pass_then_cost(row: dict[str, Any]) -> tuple[float, float, str, str]:
    cost = row.get("cost_usd")
    cost_key = float(cost) if isinstance(cost, (int, float)) else math.inf
    return (-float(row["solve_rate"]), cost_key, row["member_id"], row["effort"])


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None


def _stderr(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return round(float(statistics.stdev(values)) / math.sqrt(len(values)), 4)


def _sum_or_none(values: list[float]) -> float | None:
    return round(sum(values), 4) if values else None


def _fmt(n: Any) -> str:
    if n is None:
        return "-"
    if isinstance(n, float):
        return f"{n:.4f}"
    return str(n)


def _fmt_cost(n: Any, known: Any) -> str:
    if not known or n is None:
        return "?"
    return f"${float(n):.4f}"


def _fmt_secs(n: Any) -> str:
    if n is None:
        return "-"
    return f"{float(n):.1f}s"
