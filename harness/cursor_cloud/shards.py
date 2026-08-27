"""Stable 8-way (or N-way) sharding of a suite for parallel cloud agents."""

from __future__ import annotations

from harness.suite import load_suite

DEFAULT_SUITE = "v4"
DEFAULT_SHARDS = 8
DEFAULT_MODEL = "cursor-cloud:composer-2.5"


def assign_shards(task_ids: list[str], n_shards: int) -> list[list[str]]:
    """Round-robin split so languages mix across workers."""
    if n_shards < 1:
        raise ValueError("n_shards must be >= 1")
    buckets: list[list[str]] = [[] for _ in range(n_shards)]
    for index, task_id in enumerate(task_ids):
        buckets[index % n_shards].append(task_id)
    return buckets


def shard_tasks(task_ids: list[str], n_shards: int, shard_index: int) -> list[str]:
    """Return the task ids for a 1-based shard index."""
    if not 1 <= shard_index <= n_shards:
        raise ValueError(f"shard_index must be in 1..{n_shards}, got {shard_index}")
    return assign_shards(task_ids, n_shards)[shard_index - 1]


def suite_shard(suite: str, n_shards: int, shard_index: int) -> list[str]:
    """Task ids for one shard of a named suite."""
    return shard_tasks(list(load_suite(suite).task_ids), n_shards, shard_index)


def worker_prompt(
    *,
    shard_index: int,
    n_shards: int = DEFAULT_SHARDS,
    suite: str = DEFAULT_SUITE,
    model: str = DEFAULT_MODEL,
    task_ids: list[str] | None = None,
) -> str:
    """Paste-ready prompt for one Composer 2.5 Cursor Cloud Agent window."""
    tasks = task_ids if task_ids is not None else suite_shard(suite, n_shards, shard_index)
    listed = "\n".join(f"- `{tid}`" for tid in tasks)
    return f"""You are VulcanBench shard {shard_index}/{n_shards} running {model}.

Goal: solve the assigned baseline suite tasks using Cursor's first-party tools (no API key, no nested cursor-agent CLI).

## Setup

```bash
pip install -e ".[dev,test]"
vulcanbench cursor-cloud prepare-shard --suite {suite} --shard {shard_index} --shards {n_shards} --model {model}
```

The command prints JSON with one `workspace` path per task. Those workspaces live **outside** this checkout so you cannot walk up into `tasks/` and read `gold_patch.diff` or hidden tests. Stay inside that workspace; never `cd ..` into this checkout.

## Your tasks

{listed}

## For each task

1. Open the `workspace` path from the prepare JSON (it already contains `issue.md`).
2. Make the smallest correct change. Run the tests that the issue implies.
3. Leave changes uncommitted. Do not create git commits or pull requests for the task repo.
4. Do not use WebSearch or WebFetch. Do not read `gold_patch.diff`, `tasks/*/tests`, or other shards.
5. When finished with that workspace, stop editing it and move to the next task.

## When every task is done

```bash
vulcanbench cursor-cloud finalize-shard --suite {suite} --shard {shard_index} --shards {n_shards}
```

Print the finalize JSON. Do not guess token counts; the harness records usage from the CLI stream or from a transcript if one is supplied.

## Honesty

Results measure Composer 2.5 plus the Cursor cloud-agent harness, not the uniform VulcanBench tool loop. Do not compare them silently to `anthropic:` / `openai:` columns.
"""
