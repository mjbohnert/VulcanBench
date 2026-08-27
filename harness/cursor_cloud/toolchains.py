"""Host toolchains for grading suite v4 on Cursor Cloud (no Docker).

Cursor cloud-agent VMs do not run the per-task sandbox images. Hidden tests
still invoke ``tsx``, ``go test``, ``cargo test --offline``, and (for
PennyLane) ``python`` with jax/numpy on PATH. Missing tools must be installed
before finalize, and must be recorded as infrastructure errors rather than
model zeros.
"""

from __future__ import annotations

import importlib.util
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from harness.cursor_cloud.shards import suite_shard
from harness.suite import load_suite
from harness.tasks import Task, load_task

TSX_SPEC = "tsx@4.20.3"
GO_VERSION = "1.23.4"
GO_MIN = (1, 23, 0)
RUSTC_2024_MIN = (1, 90, 0)
RUSTC_2024_TOOLCHAIN = "1.90.0"
PENNYLANE_IMAGE = "pennylane-9459"
PENNYLANE_PACKAGES = (
    "numpy>=2.0",
    "scipy",
    "networkx",
    "rustworkx>=0.14.0",
    "autograd",
    "appdirs",
    "autoray==0.8.10",
    "cachetools",
    "requests",
    "tomlkit",
    "typing_extensions",
    "packaging",
    "diastatic-malt",
    "gast",
    "jax",
    "jaxlib",
)


@dataclass(frozen=True)
class Requirements:
    """Toolchains one shard (or the whole suite) needs to grade on the host."""

    need_python: bool = False
    need_node: bool = False
    need_tsx: bool = False
    need_go: bool = False
    need_cargo: bool = False
    need_rustc_190: bool = False
    need_pennylane: bool = False
    task_ids: tuple[str, ...] = ()
    languages: tuple[str, ...] = ()
    images: tuple[str, ...] = ()


@dataclass(frozen=True)
class ToolSnapshot:
    python: bool
    node: bool
    tsx: bool
    npm: bool
    go: tuple[int, int, int] | None
    rustc: tuple[int, int, int] | None
    rustup: bool
    pennylane_deps: bool


def local_bin_dir() -> Path:
    return Path.home() / ".local" / "bin"


def local_go_root() -> Path:
    return Path.home() / ".local" / "go"


def search_path() -> str:
    """PATH with bootstrap prefixes first (tsx, python alias, Go 1.23)."""
    prefixes = [str(local_bin_dir()), str(local_go_root() / "bin")]
    current = os.environ.get("PATH", "")
    return os.pathsep.join([*prefixes, current] if current else prefixes)


def which(name: str) -> str | None:
    return shutil.which(name, path=search_path())


def _parse_semver(text: str) -> tuple[int, int, int] | None:
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", text)
    if match is None:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def _run_version(argv: list[str]) -> tuple[int, int, int] | None:
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "PATH": search_path()},
        )
    except OSError:
        return None
    return _parse_semver(proc.stdout or proc.stderr or "")


def _pennylane_deps_ok() -> bool:
    names = ("numpy", "scipy", "networkx", "autograd", "jax")
    return all(importlib.util.find_spec(name) is not None for name in names)


def _best_rustc_version() -> tuple[int, int, int] | None:
    """Newest rustc we can invoke (default PATH rustc or rustup 1.90)."""
    versions: list[tuple[int, int, int]] = []
    rustc_bin = which("rustc")
    if rustc_bin:
        ver = _run_version([rustc_bin, "--version"])
        if ver:
            versions.append(ver)
    rustup = which("rustup")
    if rustup:
        ver = _run_version([rustup, "run", RUSTC_2024_TOOLCHAIN, "rustc", "--version"])
        if ver:
            versions.append(ver)
    return max(versions) if versions else None


def _best_go_version() -> tuple[int, int, int] | None:
    go_bin = which("go")
    return _run_version([go_bin, "version"]) if go_bin else None


def current_snapshot() -> ToolSnapshot:
    return ToolSnapshot(
        python=which("python") is not None,
        node=which("node") is not None,
        tsx=which("tsx") is not None,
        npm=which("npm") is not None,
        go=_best_go_version(),
        rustc=_best_rustc_version(),
        rustup=which("rustup") is not None,
        pennylane_deps=_pennylane_deps_ok(),
    )


def _task_image(task: Task) -> str:
    raw = task.metadata.get("image")
    return str(raw) if raw else ""


def _task_languages(task: Task) -> list[str]:
    raw = task.metadata.get("languages") or []
    if isinstance(raw, list):
        return [str(item).lower() for item in raw]
    return []


def requirements_for_tasks(tasks: list[Task]) -> Requirements:
    languages: set[str] = set()
    images: set[str] = set()
    ids: list[str] = []
    for task in tasks:
        ids.append(task.task_id)
        languages.update(_task_languages(task))
        image = _task_image(task)
        if image:
            images.add(image)
    return Requirements(
        need_python="python" in languages,
        need_node="javascript" in languages or "typescript" in languages,
        need_tsx="typescript" in languages,
        need_go="go" in languages,
        need_cargo="rust" in languages,
        need_rustc_190=any("rust-2024" in img for img in images),
        need_pennylane=any(PENNYLANE_IMAGE in img for img in images),
        task_ids=tuple(ids),
        languages=tuple(sorted(languages)),
        images=tuple(sorted(images)),
    )


def tasks_for_shard(suite: str, n_shards: int, shard_index: int) -> list[Task]:
    suite_obj = load_suite(suite)
    return [
        load_task(tid, suite_obj.tasks_root) for tid in suite_shard(suite, n_shards, shard_index)
    ]


def requirements_for_shard(suite: str, n_shards: int, shard_index: int) -> Requirements:
    return requirements_for_tasks(tasks_for_shard(suite, n_shards, shard_index))


def requirements_for_suite(suite: str, *, include_pennylane: bool = True) -> Requirements:
    suite_obj = load_suite(suite)
    req = requirements_for_tasks(
        [load_task(tid, suite_obj.tasks_root) for tid in suite_obj.task_ids]
    )
    if include_pennylane:
        return req
    return replace(req, need_pennylane=False)


def missing_from_snapshot(req: Requirements, snap: ToolSnapshot) -> list[str]:
    missing: list[str] = []
    if req.need_python and not snap.python:
        missing.append("python (alias to python3)")
    if req.need_node and not snap.node:
        missing.append("node")
    if req.need_tsx and not snap.tsx:
        missing.append(f"{TSX_SPEC} on PATH")
    if req.need_tsx and not snap.npm and not snap.tsx:
        missing.append("npm (to install tsx)")
    if req.need_go and (snap.go is None or snap.go < GO_MIN):
        got = ".".join(str(p) for p in snap.go) if snap.go else "missing"
        missing.append(f"go >={GO_MIN[0]}.{GO_MIN[1]} (have {got}; need {GO_VERSION} for chi)")
    if req.need_cargo and snap.rustc is None:
        missing.append("cargo/rustc")
    if req.need_rustc_190 and (snap.rustc is None or snap.rustc < RUSTC_2024_MIN):
        got = ".".join(str(p) for p in snap.rustc) if snap.rustc else "missing"
        missing.append(f"rustc >={RUSTC_2024_TOOLCHAIN} (have {got})")
    if (
        req.need_rustc_190
        and not snap.rustup
        and (snap.rustc is None or snap.rustc < RUSTC_2024_MIN)
    ):
        missing.append("rustup (to install rustc 1.90)")
    if req.need_pennylane and not snap.pennylane_deps:
        missing.append("PennyLane host deps (numpy/jax/autograd; not pennylane itself)")
    return missing


def preflight_errors(task: Task, snap: ToolSnapshot | None = None) -> list[str]:
    """Reasons this task cannot be graded on the current host."""
    return missing_from_snapshot(requirements_for_tasks([task]), snap or current_snapshot())


def verifier_env(task: Task | None = None, workspace: Path | None = None) -> dict[str, str]:
    """Env for host grading: local toolchains, isolated caches, rustc 1.90 when needed."""
    env = os.environ.copy()
    env["PATH"] = search_path()
    env["PYTEST_ADDOPTS"] = "-o addopts="
    if workspace is not None:
        env.setdefault("GOCACHE", str(workspace / ".gocache"))
        env.setdefault("CARGO_TARGET_DIR", str(workspace / "target"))
    if task is not None and "rust-2024" in _task_image(task):
        env["RUSTUP_TOOLCHAIN"] = RUSTC_2024_TOOLCHAIN
    return env


def ensure_python_alias() -> dict[str, Any]:
    if which("python"):
        return {"name": "python-alias", "ok": True, "skipped": True}
    python3 = which("python3")
    if python3 is None:
        return {"name": "python-alias", "ok": False, "error": "python3 not found"}
    dest = local_bin_dir() / "python"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() or dest.is_symlink():
        dest.unlink()
    dest.symlink_to(python3)
    return {"name": "python-alias", "ok": True, "path": str(dest)}


def _install_tsx() -> dict[str, Any]:
    npm = which("npm")
    if npm is None:
        return {"name": "tsx", "ok": False, "error": "npm not found"}
    prefix = Path.home() / ".local"
    prefix.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [npm, "install", "-g", TSX_SPEC, "--prefix", str(prefix)],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PATH": search_path()},
    )
    return {
        "name": "tsx",
        "ok": proc.returncode == 0 and which("tsx") is not None,
        "returncode": proc.returncode,
        "stderr": (proc.stderr or "")[-500:],
    }


def _install_go() -> dict[str, Any]:
    machine = platform.machine().lower()
    if machine in {"x86_64", "amd64"}:
        goarch = "amd64"
    elif machine in {"aarch64", "arm64"}:
        goarch = "arm64"
    else:
        goarch = machine
    url = f"https://go.dev/dl/go{GO_VERSION}.linux-{goarch}.tar.gz"
    dest_root = Path.home() / ".local"
    dest_root.mkdir(parents=True, exist_ok=True)
    tarball = Path("/tmp") / f"go{GO_VERSION}.linux-{goarch}.tar.gz"
    try:
        with urllib.request.urlopen(url, timeout=120) as resp, tarball.open("wb") as handle:
            shutil.copyfileobj(resp, handle)
        go_root = local_go_root()
        if go_root.exists():
            shutil.rmtree(go_root)
        with tarfile.open(tarball) as tar:
            tar.extractall(dest_root)
    except (OSError, tarfile.TarError) as exc:
        return {"name": "go", "ok": False, "error": str(exc)}
    go_bin = local_go_root() / "bin" / "go"
    return {"name": "go", "ok": go_bin.is_file(), "path": str(go_bin), "version": GO_VERSION}


def _install_rustc_190() -> dict[str, Any]:
    rustup = which("rustup")
    if rustup is None:
        return {
            "name": "rustc-1.90",
            "ok": False,
            "error": "rustup not found; install rustup to get rustc 1.90",
        }
    proc = subprocess.run(
        [rustup, "toolchain", "install", RUSTC_2024_TOOLCHAIN, "--profile", "minimal"],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PATH": search_path()},
    )
    return {
        "name": "rustc-1.90",
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stderr": (proc.stderr or "")[-500:],
    }


def _install_pennylane_deps() -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, "-m", "pip", "install", *PENNYLANE_PACKAGES],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PATH": search_path()},
    )
    return {
        "name": "pennylane-deps",
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stderr": (proc.stderr or "")[-800:],
    }


def bootstrap_plan(req: Requirements, snap: ToolSnapshot | None = None) -> list[str]:
    """Step names that would run for this requirement set."""
    snap = snap or current_snapshot()
    names: list[str] = []
    if req.need_python and not snap.python:
        names.append("python-alias")
    if req.need_tsx and not snap.tsx:
        names.append("tsx")
    if req.need_go and (snap.go is None or snap.go < GO_MIN):
        names.append("go")
    if req.need_rustc_190 and (snap.rustc is None or snap.rustc < RUSTC_2024_MIN):
        names.append("rustc-1.90")
    if req.need_pennylane and not snap.pennylane_deps:
        names.append("pennylane-deps")
    return names


def run_bootstrap(
    req: Requirements,
    *,
    dry_run: bool = False,
    snap: ToolSnapshot | None = None,
) -> dict[str, Any]:
    snap = snap or current_snapshot()
    planned = bootstrap_plan(req, snap)
    ran: list[dict[str, Any]] = []
    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "planned": planned,
            "path_prefix": search_path().split(os.pathsep)[:2],
        }
    actions = {
        "python-alias": ensure_python_alias,
        "tsx": _install_tsx,
        "go": _install_go,
        "rustc-1.90": _install_rustc_190,
        "pennylane-deps": _install_pennylane_deps,
    }
    for name in planned:
        ran.append(actions[name]())
    after = current_snapshot()
    missing = missing_from_snapshot(req, after)
    return {
        "ok": not missing,
        "dry_run": False,
        "planned": planned,
        "ran": ran,
        "missing": missing,
        "path_prefix": search_path().split(os.pathsep)[:2],
    }


def doctor_report(
    *,
    suite: str,
    n_shards: int,
    shard_index: int | None,
    all_shards: bool,
) -> dict[str, Any]:
    if all_shards:
        req = requirements_for_suite(suite)
        bootstrap_cmd = f"vulcanbench cursor-cloud bootstrap --all --suite {suite}"
    elif shard_index is not None:
        req = requirements_for_shard(suite, n_shards, shard_index)
        bootstrap_cmd = (
            f"vulcanbench cursor-cloud bootstrap --shard {shard_index} "
            f"--shards {n_shards} --suite {suite}"
        )
    else:
        raise ValueError("pass --shard N or --all")
    snap = current_snapshot()
    missing = missing_from_snapshot(req, snap)
    return {
        "ok": not missing,
        "suite": suite,
        "shard_index": None if all_shards else shard_index,
        "n_shards": n_shards,
        "task_ids": list(req.task_ids),
        "languages": list(req.languages),
        "images": list(req.images),
        "missing": missing,
        "planned_bootstrap": bootstrap_plan(req, snap),
        "bootstrap": bootstrap_cmd,
        "path_prefix": search_path().split(os.pathsep)[:2],
        "tools": {
            "python": snap.python,
            "node": snap.node,
            "tsx": snap.tsx,
            "npm": snap.npm,
            "go": None if snap.go is None else ".".join(str(p) for p in snap.go),
            "rustc": None if snap.rustc is None else ".".join(str(p) for p in snap.rustc),
            "rustup": snap.rustup,
            "pennylane_deps": snap.pennylane_deps,
        },
    }
