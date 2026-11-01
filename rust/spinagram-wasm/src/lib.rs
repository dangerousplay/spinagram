//! spinagram-core in the browser: `wasm-bindgen` exports over the same Rust code the server calls through
//! `PyO3`. Strings in, strings out (scene JSON, YAML text, operation JSON); a failure is a thrown JS error with
//! the reason. Fonts and icons arrive as bytes from the host, the core never reads a file here.

#![expect(clippy::missing_errors_doc, reason = "every fallible export throws a JS error with the reason; the text above each one says when")]

use spinagram_core::font;
use spinagram_core::text::{Font, Measurer};
use spinagram_core::{edit, reroute, scene, svg};
use wasm_bindgen::prelude::*;

/// Register a font under `name` so measuring can find it. Throws when the bytes are not a font.
#[wasm_bindgen(js_name = registerFont)]
pub fn register_font(name: &str, bytes: &[u8]) -> Result<(), String> {
    font::register(name, bytes).map(|_| ())
}

/// Width in px of `text` in the font registered as `name`, at `size` and `weight`.
#[wasm_bindgen(js_name = measureText)]
pub fn measure_text(name: &str, text: &str, size: f64, weight: u16) -> Result<f64, String> {
    let face = font::load(name)?;
    Ok(Measurer::default().measure(text, &Font { face: Some(face), size, weight }))
}

/// Register the bytes of an icon or image under the `path` a scene names, so `renderSvg` can embed it.
#[wasm_bindgen(js_name = registerFile)]
pub fn register_file(path: &str, bytes: &[u8]) {
    svg::register_file(path, bytes);
}

/// The drawn layers of a scene (back, middle, front: the part that is byte-identical to the server's SVG).
#[wasm_bindgen(js_name = renderBody)]
pub fn render_body(scene_json: &str) -> Result<String, String> {
    let drawn = draw(scene_json)?.1;
    Ok(format!("{}{}{}", drawn.back, drawn.mid, drawn.front))
}

/// A standalone SVG document of a scene. Fonts load from `fontBase + file name`; there is no sources
/// metadata or content hash. Icons and images must have been registered with `registerFile`.
#[wasm_bindgen(js_name = renderSvg)]
pub fn render_svg(scene_json: &str, font_base: &str) -> Result<String, String> {
    let (scene, drawn) = draw(scene_json)?;
    Ok(svg::document(&scene, &drawn, font_base))
}

fn draw(scene_json: &str) -> Result<(scene::Scene, svg::Drawn), String> {
    let scene = scene::parse(scene_json)?;
    // `true`: block totals use the compensated sum of Python 3.12+, as the server does
    let drawn = svg::draw(&scene, true).map_err(|e| e.to_string())?;
    Ok((scene, drawn))
}

/// Move shapes (`{id: [dx, dy] | [x, y, w, h]}`) and re-route the connectors touching them; returns scene JSON.
#[wasm_bindgen(js_name = reroute)]
pub fn reroute_scene(scene_json: &str, moves_json: &str) -> Result<String, String> {
    reroute::reroute(scene_json, moves_json)
}

/// Apply a JSON list of edit operations to YAML text as one batch; returns the patched YAML.
#[wasm_bindgen(js_name = applyOps)]
pub fn apply_ops(yaml: &str, ops_json: &str) -> Result<String, String> {
    edit::apply_ops_json(yaml, ops_json)
}

/// `{id: [start, end]}` as JSON: the UTF-8 byte range of every node, zone and edge entry of the YAML.
#[wasm_bindgen]
pub fn srcmap(yaml: &str) -> Result<String, String> {
    let map = edit::srcmap(yaml)?;
    serde_json::to_string(&map).map_err(|e| e.to_string())
}
