#!/usr/bin/env bash
# Build spinagram-wasm: the release wasm, then wasm-bindgen glue for the browser (web/src/wasm) and for the
# bun tests (rust/spinagram-wasm/pkg-node, nodejs target).
#
# Needs the wasm32 target and a wasm-bindgen CLI of the same version as the `wasm-bindgen` crate in Cargo.lock:
#   rustup target add wasm32-unknown-unknown
#   cargo install wasm-bindgen-cli --version "$(awk '/name = "wasm-bindgen"$/{getline; gsub(/[^0-9.]/,""); print}' rust/Cargo.lock)" --locked
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
rust="$here/.."
cargo build --manifest-path "$rust/Cargo.toml" -p spinagram-wasm --target wasm32-unknown-unknown --release
wasm="$rust/target/wasm32-unknown-unknown/release/spinagram_wasm.wasm"
wasm-bindgen --target web --out-dir "$rust/../web/src/wasm" --out-name spinagram_wasm "$wasm"
wasm-bindgen --target nodejs --out-dir "$here/pkg-node" --out-name spinagram_wasm "$wasm"
# smaller output when binaryen is installed (optional)
if command -v wasm-opt >/dev/null 2>&1; then
  for f in "$rust/../web/src/wasm/spinagram_wasm_bg.wasm" "$here/pkg-node/spinagram_wasm_bg.wasm"; do
    wasm-opt -Oz --enable-bulk-memory --enable-nontrapping-float-to-int -o "$f.opt" "$f" && mv "$f.opt" "$f"
  done
fi
echo "wasm: $(gzip -c "$rust/../web/src/wasm/spinagram_wasm_bg.wasm" | wc -c | tr -d ' ') bytes gzipped"
