# Composer 2.5 on Cursor Cloud

Run the VulcanBench **v4** baseline (23 contamination-clean tasks) with
**Composer 2.5** inside Cursor cloud-agent windows. No `CURSOR_API_KEY`. This
is a different column from `--harness cursor` (the `cursor-agent` CLI on a
desktop login).

## Why two paths

| Path | Command | Auth | Token usage |
| --- | --- | --- | --- |
| Cursor CLI | `vulcanbench run --harness cursor --billing subscription --model composer-2.5` | `cursor-agent login` (fails closed if `CURSOR_API_KEY` is set) | Streamed `usage` events, priced at Composer list rates |
| Cursor Cloud | `vulcanbench cursor-cloud` + 8 Composer 2.5 windows | First-party cloud agent (this product) | Transcript usage when present, otherwise chars/4 estimate |

Do not mix the two on a leaderboard: both are "model + Cursor harness", but
the runtime (CLI vs cloud agent) is not the same.

## Desktop CLI (one machine)

```bash
unset CURSOR_API_KEY
vulcanbench harness doctor cursor
vulcanbench run --suite v4 --harness cursor --billing subscription \
  --model composer-2.5 --repeat 1 --no-judges --sandbox docker
```

`--max-run-cost` is enforced once the CLI streams usage. Pair it with
`--timeout` so an old CLI that emits no usage still stops.

## Eight cloud-agent windows (Composer 2.5)

Point every worker at **this branch** (the one that ships
`vulcanbench cursor-cloud`). Suite v4 has 23 tasks. Round-robin across 8
shards mixes languages (Python, Rust, TypeScript, JavaScript, Go):

```bash
pip install -e ".[dev,test]"
vulcanbench cursor-cloud shards --suite v4
vulcanbench cursor-cloud print-prompt --all --suite v4
```

Open **eight** new Cursor Cloud Agent windows against this repo/branch. Set
the model to **Composer 2.5**. Paste one shard prompt per window:

```bash
vulcanbench cursor-cloud print-prompt --shard 1 --suite v4
vulcanbench cursor-cloud print-prompt --shard 2 --suite v4
# ... through --shard 8
```

Each worker (the paste-ready prompt already includes this):

1. `pip install -e ".[dev,test]"` and `export PATH="$HOME/.local/bin:$HOME/.local/go/bin:$PATH"`
2. `vulcanbench cursor-cloud bootstrap --shard N --suite v4` then `doctor --shard N`
3. `vulcanbench cursor-cloud prepare-shard --shard N --suite v4`
4. Solves only the workspaces printed in that JSON (they live **outside** this
   checkout so the agent cannot walk up into `tasks/` and read gold patches)
5. `vulcanbench cursor-cloud finalize-shard --shard N --suite v4`

Cursor Cloud VMs do not have the per-task Docker images. Bootstrap installs the
host stand-ins: `tsx@4.20.3` (Hono), Go 1.23.4 (chi's `go 1.23` directive),
rustc 1.90 via rustup (edition 2024), and PennyLane jax/numpy on shard 6 only
(not pennylane itself; the workspace is on `PYTHONPATH`). `bootstrap --all`
skips jax. Missing tools are infrastructure errors, not model zeros.

Optional: pass `--transcript path/to/transcript.json` (or `--transcript-dir`
with `<run_id>.json` files) so finalize records token counts. Cursor cloud
transcripts typically have **no** provider `usage` object; the harness then
estimates chars/4 over user text, assistant `thinking`/`text`/`tool_calls`,
and `tool_result` payloads (the fields the real export uses).

After the eight windows finish, price an exported transcript without
re-running tests:

```bash
vulcanbench cursor-cloud price-transcript path/to/transcript.json \
  --model cursor-cloud:composer-2.5
vulcanbench cursor-cloud apply-transcript RUN_DIR --transcript path/to/transcript.json
```

Workers should print `$CURSOR_CONVERSATION_ID` (the cloud agent bcId) so a
coordinator can fetch that run's transcript later. Without a transcript,
`economics.api_equivalent_cost_usd` is unavailable (not a fake `$0`).

`oss-time-strftime-truncated-padding` needs rustc 1.90 (`vulcanbench/sandbox:rust-2024`).
Host finalize on an older toolchain records an infrastructure error for that
task rather than a model fail. v4 Python tests invoke `python` (not `python3`);
bootstrap links `python` to `python3` when the alias is missing. Check a worker
with `vulcanbench cursor-cloud doctor --shard N --suite v4`.

## Pricing (API-equivalent, not cash)

Composer 2.5 list rates from [Cursor models](https://cursor.com/docs/models):

| Variant | Input / 1M | Cache read / 1M | Output / 1M |
| --- | ---: | ---: | ---: |
| Standard (`composer-2.5`) | $0.50 | $0.20 | $2.50 |
| Fast (`composer-2.5-fast`) | $3.00 | $0.50 | $15.00 |

Subscription runs record this as `economics.api_equivalent_cost_usd`. Marginal
cash stays unknown: the run billed a Cursor plan, not an invoice line.

## Honesty rules

- Results measure **Composer 2.5 + Cursor**, not the uniform VulcanBench loop.
- Do not use WebSearch / WebFetch on a decontaminated suite (v4 tasks are
  public merged PRs).
- Do not read `gold_patch.diff` or hidden `tests/`.
- `CURSOR_API_KEY` on the CLI path is a hard fail: it would silently switch
  billing to metered API usage.
