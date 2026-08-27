"""Cursor Cloud Agent sessions for Composer 2.5 (no API key).

Prepare isolated task workspaces, solve them with a first-party Cursor cloud
agent (Composer 2.5), then finalize with VulcanBench grading and token
accounting. Distinct from ``--harness cursor`` (the ``cursor-agent`` CLI).
"""

from harness.cursor_cloud.session import finalize_session, prepare_session
from harness.cursor_cloud.shards import assign_shards, shard_tasks, worker_prompt
from harness.cursor_cloud.tokens import tokens_from_transcript
from harness.cursor_cloud.toolchains import requirements_for_shard

__all__ = [
    "assign_shards",
    "finalize_session",
    "prepare_session",
    "requirements_for_shard",
    "shard_tasks",
    "tokens_from_transcript",
    "worker_prompt",
]
