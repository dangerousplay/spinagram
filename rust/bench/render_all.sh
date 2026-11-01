#!/usr/bin/env bash
# Render every example folder, every top-level example file and docs/diagrams/ to SVG.
# Used to check that two builds (or Python vs Rust) give byte-identical output.
# Run from the repository root:
#   bash rust/bench/render_all.sh OUT_DIR
# Override the CLI with SPINAGRAM_CMD (default: uv run --all-extras --no-sync spinagram).
set -euo pipefail
OUT=${1:?usage: render_all.sh OUT_DIR}
CMD=${SPINAGRAM_CMD:-uv run --all-extras --no-sync spinagram}
mkdir -p "$OUT"

targets=()
for p in examples/*; do
  case "$p" in
    *.py|*.yaml) targets+=("$p") ;;
    *) [ -d "$p" ] && targets+=("$p/") ;;
  esac
done
targets+=(docs/diagrams/)

for t in "${targets[@]}"; do
  name=$(echo "${t%/}" | tr '/' '_')
  $CMD render "$t" -f svg --no-gallery -o "$OUT/$name" >/dev/null
done
echo "$(find "$OUT" -name '*.svg' | wc -l | tr -d ' ') SVGs in $OUT"
