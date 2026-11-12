#!/usr/bin/env bash
# 用法：bash hifi/shoot.sh [页面名前缀...]，在 parallel-variable-aggregation 目录下执行；不带参数时截全部页面
set -euo pipefail
cd "$(dirname "$0")/.."
export npm_config_cache=/tmp/npm-cache-wiremd
mkdir -p designs
pages=("$@")
if [ ${#pages[@]} -eq 0 ]; then
  pages=($(ls hifi/*.html | xargs -n1 basename | sed 's/\.html$//'))
fi
for p in "${pages[@]}"; do
  f=$(ls hifi/${p}*.html | head -1)
  name=$(basename "$f" .html)
  npx -y playwright@1.62.0 screenshot --device "Desktop Chrome HiDPI" --full-page \
    --viewport-size "1920,900" "file://$PWD/$f" "designs/$name.png" >/dev/null
  echo "ok $name"
done
