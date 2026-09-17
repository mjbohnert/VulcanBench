"""Family-of-models routing from cached single-model runs.

Claims ledger (promise -> proving test):
- "loads and rejects invalid family JSON"                         -> test_spec_validation
- "static policy matches a single member column"                  -> test_static_matches_column
- "oracle picks the cheaper solver when both always pass"         -> test_oracle_cheapest
- "oracle falls back to the only solver"                          -> test_oracle_picks_solver
- "metadata router splits on scale stratum (LOO)"                 -> test_metadata_router_by_scale
- "cascade expected pass/cost from independent solve rates"       -> test_cascade_expected_value
- "mixed cursor + API harness is flagged"                         -> test_mixed_harness_warning
- "comparative policies skipped without common coverage"          -> test_no_common_coverage
- "CLI family-report writes markdown/json"                        -> test_cli_family_report
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from harness.cli import app
from harness.family import (
    FamilySpec,
    FamilySpecError,
    build_family_report,
    family_from_models,
    load_family_spec,
    parse_members,
    to_markdown,
)
from harness.tasks import load_task, task_hash

runner = CliRunner()


def _make_task(
    suite: Path,
    task_id: str,
    *,
    repo_scale: str = "small",
    complexity: str = "localized",
    difficulty: str = "easy",
    language: str = "python",
) -> None:
    task = suite / task_id
    (task / "repo").mkdir(parents=True)
    (task / "tests").mkdir(parents=True)
    (task / "repo" / "m.py").write_text("def f():\n    return 0\n")
    (task / "tests" / "t.py").write_text("from m import f\n\ndef test_it():\n    assert f() == 2\n")
    (task / "metadata.json").write_text(
        json.dumps(
            {
                "id": task_id,
                "category": "bug_fix",
                "languages": [language],
                "difficulty": difficulty,
                "repo_scale": repo_scale,
                "task_complexity": complexity,
                "created": "2026-09-17",
                "source": "hand-authored",
                "decontamination_notes": "fixture",
                "tests": {
                    "fail_to_pass": [{"name": "it", "cmd": "python -m pytest t.py -q"}],
                    "pass_to_pass": [],
                },
            }
        )
    )
    (task / "issue.md").write_text("fix f")


def _make_suite(base: Path, name: str, specs: list[dict[str, str]]) -> Path:
    suite = base / name
    for spec in specs:
        _make_task(suite, spec["id"], **{k: v for k, v in spec.items() if k != "id"})
    return suite


def _write_run(
    runs: Path,
    *,
    task_id: str,
    model: str,
    functional: float,
    cost: float,
    thash: str,
    effort: str | None = None,
    duration_s: float = 10.0,
) -> None:
    label = effort or "unset"
    base = f"{task_id}-{model}-{label}".replace(":", "_")
    d = runs / base
    n = 1
    while d.exists():
        d = runs / f"{base}-{n}"
        n += 1
    d.mkdir(parents=True)
    payload: dict[str, object] = {
        "run_id": d.name,
        "task_id": task_id,
        "model": model,
        "scores": {"functional": functional},
        "cost_usd": cost,
        "duration_s": duration_s,
        "task_hash": thash,
    }
    if effort is not None:
        payload["effort"] = {"requested": effort, "supported": True}
    (d / "summary.json").write_text(json.dumps(payload), encoding="utf-8")


def _hashes(suite: Path, task_ids: list[str]) -> dict[str, str]:
    return {tid: task_hash(load_task(tid, suite)) for tid in task_ids}


def test_spec_validation(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text('{"id": "x", "members": []}', encoding="utf-8")
    with pytest.raises(FamilySpecError):
        load_family_spec(bad)

    dup = tmp_path / "dup.json"
    dup.write_text(
        json.dumps(
            {
                "id": "dup",
                "members": [
                    {"id": "a", "model": "mock:one"},
                    {"id": "a", "model": "mock:two"},
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(FamilySpecError):
        load_family_spec(dup)

    with pytest.raises(FamilySpecError):
        parse_members("  ,  ")

    spec = family_from_models(["mock:cheap", "mock:strong"])
    assert spec.id == "adhoc"
    assert [m.model for m in spec.members] == ["mock:cheap", "mock:strong"]


def test_example_family_files_load() -> None:
    grok = load_family_spec(Path("families/cursor-grok-composer.json"))
    assert grok.id == "cursor-grok-composer"
    assert grok.members[0].efforts == [None]
    sol = load_family_spec(Path("families/sol-terra-luna.json"))
    assert len(sol.members) == 3
    assert sol.cascade_order == ["luna", "terra", "sol"]


def test_static_matches_column(tmp_path: Path) -> None:
    suite = _make_suite(
        tmp_path,
        "s",
        [{"id": "a"}, {"id": "b"}],
    )
    hashes = _hashes(suite, ["a", "b"])
    runs = tmp_path / "runs"
    for tid in ("a", "b"):
        _write_run(
            runs, task_id=tid, model="mock:cheap", functional=1.0, cost=0.1, thash=hashes[tid]
        )
        _write_run(
            runs, task_id=tid, model="mock:strong", functional=1.0, cost=1.0, thash=hashes[tid]
        )
    spec = family_from_models(["mock:cheap", "mock:strong"])
    report = build_family_report(spec, "s", runs_dir=runs, tasks_base=tmp_path)
    assert report["n_fair_tasks"] == 2
    static = {p["id"]: p for p in report["policies"]}
    cheap = static["static:mock-cheap@-"]
    strong = static["static:mock-strong@-"]
    assert cheap["pass_at_1"] == 1.0
    assert strong["pass_at_1"] == 1.0
    assert cheap["policy_cost_usd"] == 0.2
    assert strong["policy_cost_usd"] == 2.0
    assert cheap["leaks_labels"] is False


def test_oracle_cheapest(tmp_path: Path) -> None:
    suite = _make_suite(tmp_path, "s", [{"id": "a"}, {"id": "b"}])
    hashes = _hashes(suite, ["a", "b"])
    runs = tmp_path / "runs"
    for tid in ("a", "b"):
        _write_run(
            runs, task_id=tid, model="mock:cheap", functional=1.0, cost=0.1, thash=hashes[tid]
        )
        _write_run(
            runs, task_id=tid, model="mock:strong", functional=1.0, cost=1.0, thash=hashes[tid]
        )
    spec = family_from_models(["mock:cheap", "mock:strong"])
    report = build_family_report(spec, "s", runs_dir=runs, tasks_base=tmp_path)
    oracle = next(p for p in report["policies"] if p["id"] == "oracle_cheapest_sufficient")
    assert oracle["leaks_labels"] is True
    assert oracle["pass_at_1"] == 1.0
    assert oracle["policy_cost_usd"] == 0.2
    assert {row["member_id"] for row in oracle["routing"]} == {"mock-cheap"}


def test_oracle_picks_solver(tmp_path: Path) -> None:
    suite = _make_suite(tmp_path, "s", [{"id": "easy"}, {"id": "hard"}])
    hashes = _hashes(suite, ["easy", "hard"])
    runs = tmp_path / "runs"
    _write_run(
        runs, task_id="easy", model="mock:cheap", functional=1.0, cost=0.1, thash=hashes["easy"]
    )
    _write_run(
        runs, task_id="hard", model="mock:cheap", functional=0.0, cost=0.1, thash=hashes["hard"]
    )
    _write_run(
        runs, task_id="easy", model="mock:strong", functional=1.0, cost=1.0, thash=hashes["easy"]
    )
    _write_run(
        runs, task_id="hard", model="mock:strong", functional=1.0, cost=1.0, thash=hashes["hard"]
    )
    spec = family_from_models(["mock:cheap", "mock:strong"])
    report = build_family_report(spec, "s", runs_dir=runs, tasks_base=tmp_path)
    oracle = next(p for p in report["policies"] if p["id"] == "oracle_cheapest_sufficient")
    by_task = {row["task_id"]: row["member_id"] for row in oracle["routing"]}
    assert by_task == {"easy": "mock-cheap", "hard": "mock-strong"}
    assert oracle["pass_at_1"] == 1.0
    assert oracle["policy_cost_usd"] == 1.1


def test_metadata_router_by_scale(tmp_path: Path) -> None:
    suite = _make_suite(
        tmp_path,
        "s",
        [
            {"id": "micro-a", "repo_scale": "micro"},
            {"id": "micro-b", "repo_scale": "micro"},
            {"id": "large-a", "repo_scale": "large"},
            {"id": "large-b", "repo_scale": "large"},
        ],
    )
    ids = ["micro-a", "micro-b", "large-a", "large-b"]
    hashes = _hashes(suite, ids)
    runs = tmp_path / "runs"
    for tid in ("micro-a", "micro-b"):
        _write_run(
            runs, task_id=tid, model="mock:cheap", functional=1.0, cost=0.1, thash=hashes[tid]
        )
        _write_run(
            runs, task_id=tid, model="mock:strong", functional=1.0, cost=1.0, thash=hashes[tid]
        )
    for tid in ("large-a", "large-b"):
        _write_run(
            runs, task_id=tid, model="mock:cheap", functional=0.0, cost=0.1, thash=hashes[tid]
        )
        _write_run(
            runs, task_id=tid, model="mock:strong", functional=1.0, cost=1.0, thash=hashes[tid]
        )
    spec = family_from_models(["mock:cheap", "mock:strong"])
    report = build_family_report(spec, "s", runs_dir=runs, tasks_base=tmp_path)
    router = next(p for p in report["policies"] if p["id"] == "metadata_router")
    by_task = {row["task_id"]: row["member_id"] for row in router["routing"]}
    assert by_task["micro-a"] == "mock-cheap"
    assert by_task["micro-b"] == "mock-cheap"
    assert by_task["large-a"] == "mock-strong"
    assert by_task["large-b"] == "mock-strong"
    assert router["pass_at_1"] == 1.0
    assert router["policy_cost_usd"] == 2.2
    assert router["leaks_labels"] is False


def test_cascade_expected_value(tmp_path: Path) -> None:
    suite = _make_suite(tmp_path, "s", [{"id": "easy"}, {"id": "hard"}])
    hashes = _hashes(suite, ["easy", "hard"])
    runs = tmp_path / "runs"
    _write_run(
        runs, task_id="easy", model="mock:cheap", functional=1.0, cost=0.1, thash=hashes["easy"]
    )
    _write_run(
        runs, task_id="hard", model="mock:cheap", functional=0.0, cost=0.1, thash=hashes["hard"]
    )
    _write_run(
        runs, task_id="easy", model="mock:strong", functional=1.0, cost=1.0, thash=hashes["easy"]
    )
    _write_run(
        runs, task_id="hard", model="mock:strong", functional=1.0, cost=1.0, thash=hashes["hard"]
    )
    spec = FamilySpec.model_validate(
        {
            "id": "pair",
            "members": [
                {"id": "cheap", "model": "mock:cheap"},
                {"id": "strong", "model": "mock:strong"},
            ],
            "cascade_order": ["cheap", "strong"],
        }
    )
    report = build_family_report(spec, "s", runs_dir=runs, tasks_base=tmp_path)
    cascade = next(p for p in report["policies"] if p["id"] == "cascade_restart")
    assert cascade["pass_at_1"] == 1.0
    # easy: pay 0.10 (cheap always solves). hard: pay 0.10 + 1.00.
    assert cascade["policy_cost_usd"] == 1.2
    assert cascade["kind"] == "cascade"


def test_mixed_harness_warning(tmp_path: Path) -> None:
    suite = _make_suite(tmp_path, "s", [{"id": "a"}])
    hashes = _hashes(suite, ["a"])
    runs = tmp_path / "runs"
    _write_run(
        runs, task_id="a", model="cursor:composer-2.5", functional=1.0, cost=0.5, thash=hashes["a"]
    )
    _write_run(runs, task_id="a", model="xai:grok-4.6", functional=1.0, cost=2.0, thash=hashes["a"])
    spec = family_from_models(["cursor:composer-2.5", "xai:grok-4.6"])
    report = build_family_report(spec, "s", runs_dir=runs, tasks_base=tmp_path)
    assert report["mixed_harness"] is True
    assert any("mixed harness" in w for w in report["warnings"])
    md = to_markdown(report)
    assert "Mixed harness" in md
    assert "metadata_router" in md


def test_no_common_coverage(tmp_path: Path) -> None:
    suite = _make_suite(tmp_path, "s", [{"id": "a"}, {"id": "b"}])
    hashes = _hashes(suite, ["a", "b"])
    runs = tmp_path / "runs"
    _write_run(runs, task_id="a", model="mock:cheap", functional=1.0, cost=0.1, thash=hashes["a"])
    spec = family_from_models(["mock:cheap", "mock:strong"])
    report = build_family_report(spec, "s", runs_dir=runs, tasks_base=tmp_path)
    assert report["n_fair_tasks"] == 0
    kinds = {p["kind"] for p in report["policies"]}
    assert kinds == {"static"}
    assert any("no common coverage" in w for w in report["warnings"])


def test_effort_cells_are_distinct(tmp_path: Path) -> None:
    suite = _make_suite(tmp_path, "s", [{"id": "a"}])
    hashes = _hashes(suite, ["a"])
    runs = tmp_path / "runs"
    _write_run(
        runs,
        task_id="a",
        model="mock:think",
        functional=0.0,
        cost=0.2,
        thash=hashes["a"],
        effort="low",
    )
    _write_run(
        runs,
        task_id="a",
        model="mock:think",
        functional=1.0,
        cost=0.8,
        thash=hashes["a"],
        effort="high",
    )
    spec = FamilySpec.model_validate(
        {
            "id": "think",
            "members": [{"id": "think", "model": "mock:think", "efforts": ["low", "high"]}],
            "cascade_order": ["think@low", "think@high"],
        }
    )
    report = build_family_report(spec, "s", runs_dir=runs, tasks_base=tmp_path)
    static = {p["id"]: p for p in report["policies"] if p["kind"] == "static"}
    assert static["static:think@low"]["pass_at_1"] == 0.0
    assert static["static:think@high"]["pass_at_1"] == 1.0
    oracle = next(p for p in report["policies"] if p["id"] == "oracle_cheapest_sufficient")
    assert oracle["routing"][0]["effort"] == "high"
    cascade = next(p for p in report["policies"] if p["id"] == "cascade_restart")
    assert cascade["cascade_order"] == ["think@low", "think@high"]


def test_cli_family_report(tmp_path: Path) -> None:
    suite = _make_suite(tmp_path, "s", [{"id": "a"}, {"id": "b"}])
    hashes = _hashes(suite, ["a", "b"])
    runs = tmp_path / "runs"
    for tid in ("a", "b"):
        _write_run(
            runs, task_id=tid, model="mock:cheap", functional=1.0, cost=0.1, thash=hashes[tid]
        )
        _write_run(
            runs, task_id=tid, model="mock:strong", functional=0.0, cost=1.0, thash=hashes[tid]
        )
    roster = tmp_path / "family.json"
    roster.write_text(
        json.dumps(
            {
                "id": "pair",
                "display_name": "Cheap + Strong",
                "members": [
                    {"id": "cheap", "model": "mock:cheap"},
                    {"id": "strong", "model": "mock:strong"},
                ],
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "family.md"
    result = runner.invoke(
        app,
        [
            "family-report",
            "--suite",
            "s",
            "--family",
            str(roster),
            "--runs-dir",
            str(runs),
            "--tasks-base",
            str(tmp_path),
            "-o",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    text = out.read_text(encoding="utf-8")
    assert "Cheap + Strong" in text
    assert "static:cheap@-" in text

    json_result = runner.invoke(
        app,
        [
            "family-report",
            "--suite",
            "s",
            "--members",
            "mock:cheap,mock:strong",
            "--runs-dir",
            str(runs),
            "--tasks-base",
            str(tmp_path),
            "--json",
        ],
    )
    assert json_result.exit_code == 0, json_result.output
    payload = json.loads(json_result.output)
    assert payload["n_fair_tasks"] == 2

    both = runner.invoke(
        app,
        ["family-report", "--suite", "s", "--family", str(roster), "--members", "mock:cheap"],
    )
    assert both.exit_code == 1
    assert "exactly one" in both.output

    bad_fmt = runner.invoke(
        app,
        [
            "family-report",
            "--suite",
            "s",
            "--members",
            "mock:cheap",
            "--format",
            "yaml",
        ],
    )
    assert bad_fmt.exit_code == 1
    assert "md|json" in bad_fmt.output
