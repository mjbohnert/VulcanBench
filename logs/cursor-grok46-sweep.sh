#!/bin/zsh
# Cursor-harness sweep of Grok 4.6: four effort-baked model ids, repeat 3.
# Effort lives in the model id (cursor-grok-4.6-<level>), so no --effort flag;
# non-fast variants deliberately (the -fast serving tier is a different system).
set -u
cd /Users/morganlinton/dev/VulcanBench
for level in low medium high xhigh; do
  echo "=== level $level ==="
  .venv/bin/vulcanbench run --suite v3 \
    --harness cursor --billing subscription \
    --model "cursor-grok-4.6-$level" \
    --repeat 3 --max-concurrency 2 \
    --sandbox local --no-judges
done
echo "=== sweep complete ==="
