# Composer 2.5 × VulcanBench v3

Two different “Composer 2.5” jobs get confused. This page is the operator
runbook for both.

## 1. Composer under test (automatic)

When you run:

```bash
export CURSOR_API_KEY=...
vulcanbench run --suite v3 --model cursor:composer-2.5 --sandbox local --no-judges
```

VulcanBench launches the Cursor Agent CLI (`agent -p` / `cursor-agent`) **once
per task**. You do not prompt Composer yourself. The kickoff text is:

```text
# Issue

<contents of that task's issue.md>

Solve this issue in the current repository. Make the smallest correct
change and run the tests to verify it. Leave your changes uncommitted in
the working tree — do not create git commits.
```

That is built by `harness.agent.cli_agents.build_cli_prompt`. The working
directory is a fresh copy of `tasks/v3/<task-id>/repo/`. After Composer
exits, the harness diffs, verifies hidden tests, and writes
`./runs/<id>/{summary.json,trace.jsonl,final.patch,replay.html}`.

Fast SLA (same model, ~6× list price): `--model cursor:composer-2.5-fast`.

Resume a partial suite with `--only-missing`. Cap a runaway task with
`--max-run-cost`. Requires `--sandbox local` and Cursor CLI on PATH
(`CURSOR_AGENT_BIN` if the binary is not `agent` / `cursor-agent`).

## 2. Composer as the person who *starts* the suite

If a Composer 2.5 Cloud Agent is asked to **operate** VulcanBench (install,
estimate, run the suite), paste the prompt below. That agent must **not**
solve `tasks/v3/*` by hand — it must invoke the command in section 1 so
each task is scored as `cursor:composer-2.5`.

### Copy-paste prompt

```text
You are operating VulcanBench, not solving the benchmark tasks yourself.

Goal: run suite v3 with Composer 2.5 through the Cursor CLI harness.

Do:
1. Confirm Cursor CLI is on PATH (`agent` or `cursor-agent`) and CURSOR_API_KEY is set.
2. From the repo root: pip install -e ".[dev,test]" if vulcanbench is missing.
3. Estimate (do not skip): vulcanbench estimate --suite v3 --model cursor:composer-2.5 --no-judges
4. Run: vulcanbench run --suite v3 --model cursor:composer-2.5 --sandbox local --no-judges --only-missing
5. If a task errors (usage limit, CLI crash), leave it and resume with --only-missing later.
6. When finished: vulcanbench leaderboard ; vulcanbench report -o report.md
7. Summarize pass@1, cost_usd total, and any errored task ids.

Do not:
- Edit files under tasks/v3/ to “fix” a task.
- Use --sandbox docker with cursor: models.
- Run --judges unless asked (it ~3× cost and needs a judge model).
- Solve hello-world or v3 issues in this chat; the harness must invoke Composer per task.

Model spec is cursor:composer-2.5 (standard list price). Use cursor:composer-2.5-fast only if asked.
```
