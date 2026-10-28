#!/usr/bin/env bash
# Re-render every diagram the docs show into docs/public/assets/. Run from the repository root:
#   bash docs/scripts/render_assets.sh
set -euo pipefail
OUT=$(mktemp -d)
A=docs/public/assets
trap 'rm -rf "$OUT"' EXIT

render() { uv run spinagram render "$@" -f svg --no-gallery -o "$OUT/$1" >/dev/null; }
copy() {  # copy <dir> <dest folder>: <ID>-<slug>.svg → <dest>/<id>.svg (ids lower-cased, LOOK0n → l0n)
  for f in "$OUT/$1"/*.svg; do
    id=$(basename "$f" | cut -d- -f1 | tr '[:upper:]' '[:lower:]' | sed 's/^look/l/')
    cp "$f" "$A/$2/$id.svg"
  done
}

render docs/diagrams/ && cp "$OUT/docs/diagrams/S00-spinagram.svg" "$A/overview.svg"
mkdir -p "$A/release-0-5" && cp "$OUT/docs/diagrams/release-0-5.svg" "$A/release-0-5/commit-to-production.svg"
render examples/quickstart.py && cp "$OUT/examples/quickstart.py/Q01-web-app-on-aws.svg" "$A/quickstart.svg"
mkdir -p "$A/demo" "$A/tutorial" "$A/gallery" "$A/examples"
render examples/behavior/ && copy examples/behavior/ demo
render examples/styling/styled.py && copy examples/styling/styled.py demo
render examples/tutorial/ && copy examples/tutorial/ tutorial
render examples/showcase/ && copy examples/showcase/ gallery
for d in looks mixed icons kubernetes; do render "examples/$d/" && copy "examples/$d/" examples; done
echo "assets updated in $A"
