---
name: vulcancyber-build-toolchain
description: Prerequisites and setup for building/validating VulcanCyber v1 tasks on this Windows machine
metadata:
  type: project
---

Building a VulcanCyber v1 task (mine → `gh pr diff` → `scripts/slice_repo.py` → `scripts/validate_tasks.py --sandbox docker`) needs four things on this Win11 machine. As of 2026-08-16:

- **`gh`** — installed via `winget install --id GitHub.cli --scope user` (v2.97.0). Authenticated as `morganlinton` (keyring; scopes repo/workflow/read:org/gist). PATH needs a shell restart after install; refresh in-session with `$env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')`.
- **Project venv** — `.venv` at repo root; `.\.venv\Scripts\python.exe -m pip install -e .` makes `harness` importable (the raw system Python 3.13 can't import `harness`, so `slice_repo.py`/`validate_tasks.py` fail with ModuleNotFoundError there). Always invoke scripts via `.\.venv\Scripts\python.exe`.
- **Docker Desktop** — INSTALLED & working (Docker 29.7.2, Linux engine). Required for the ×3 admission gate (`validate_tasks.py --sandbox docker`). If the daemon is down, launch `"C:\Program Files\Docker\Docker\Docker Desktop.exe"` and poll `docker info` (~12s to come up). Two Win11-specific gotchas hit while running the gate: (a) the validator prints ✓/✗ icons — set `PYTHONIOENCODING=utf-8 PYTHONUTF8=1` or the cp1252 console crashes on the result line; (b) `harness/sandbox/docker_executor.py` `os.getuid()` was Windows-crashing — now guarded (fixed 2026-08-16). Per-task images are NOT auto-built by the validator: build the Dockerfile chain first (`docker build -t vulcanbench/sandbox:<tag> -f sandbox/Dockerfile.<tag> .`); images resolve from `metadata.image` via `resolve_sandbox_image`.
- **network** — `slice_repo.py` clones the upstream repo at the PR base commit; offline runs then vendor deps (`go mod vendor`, `cargo vendor`) so the sandbox stays network-off.

See [[vulcancyber-hard-tail-plan]] for what's being built with this toolchain.
