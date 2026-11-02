//! spinagram-core in the browser: `wasm-bindgen` exports over the same Rust code the server calls through
//! `PyO3`. Strings in, strings out (scene JSON, YAML text, operation JSON); a failure is a thrown JS error with
//! the reason. Fonts and icons arrive as bytes from the host, the core never reads a file here.

#![expect(clippy::missing_errors_doc, reason = "every fallible export throws a JS error with the reason; the text above each one says when")]

use spinagram_core::font;
use spinagram_core::text::{Font, Measurer};
use spinagram_core::{edit, reroute, scene, svg};
use wasm_bindgen::prelude::*;

/// A JS `Error` with `message`, and an `index` property (the position of the operation to blame) when there is one.
fn js_error(message: &str, index: Option<usize>) -> JsValue {
    let err = js_sys::Error::new(message);
    if let Some(i) = index {
        let index = f64::from(u32::try_from(i).unwrap_or(u32::MAX));
        // setting a property on a fresh `Error` cannot fail; the message already carries the index
        let _ = js_sys::Reflect::set(&err, &JsValue::from_str("index"), &JsValue::from_f64(index));
    }
    err.into()
}

/// A JS `Error` with the error's message.
fn throw(e: impl std::fmt::Display) -> JsValue {
    js_error(&e.to_string(), None)
}

/// Register a font under `name` so measuring can find it. Throws when the bytes are not a font.
#[wasm_bindgen(js_name = registerFont)]
pub fn register_font(name: &str, bytes: &[u8]) -> Result<(), JsValue> {
    font::register(name, bytes).map(|_| ()).map_err(throw)
}

/// Width in px of `text` in the font registered as `name`, at `size` and `weight`.
#[wasm_bindgen(js_name = measureText)]
pub fn measure_text(name: &str, text: &str, size: f64, weight: u16) -> Result<f64, JsValue> {
    let face = font::load(name).map_err(throw)?;
    Ok(Measurer::default().measure(text, &Font { face: Some(face), size, weight }))
}

/// Register the bytes of an icon or image under the `path` a scene names, so `renderSvg` can embed it.
#[wasm_bindgen(js_name = registerFile)]
pub fn register_file(path: &str, bytes: &[u8]) {
    svg::register_file(path, bytes);
}

/// The drawn layers of a scene (back, middle, front: the part that is byte-identical to the server's SVG).
#[wasm_bindgen(js_name = renderBody)]
pub fn render_body(scene_json: &str) -> Result<String, JsValue> {
    let drawn = draw(scene_json)?.1;
    Ok(format!("{}{}{}", drawn.back, drawn.mid, drawn.front))
}

/// A standalone SVG document of a scene. Fonts load from `fontBase + file name`; there is no sources
/// metadata or content hash. Icons and images must have been registered with `registerFile`.
#[wasm_bindgen(js_name = renderSvg)]
pub fn render_svg(scene_json: &str, font_base: &str) -> Result<String, JsValue> {
    let (scene, drawn) = draw(scene_json)?;
    Ok(svg::document(&scene, &drawn, font_base))
}

fn draw(scene_json: &str) -> Result<(scene::Scene, svg::Drawn), JsValue> {
    let scene = scene::parse(scene_json).map_err(throw)?;
    // `true`: block totals use the compensated sum of Python 3.12+, as the server does
    let drawn = svg::draw(&scene, true).map_err(throw)?;
    Ok((scene, drawn))
}

/// Move shapes (`{id: [dx, dy] | [x, y, w, h]}`) and re-route the connectors touching them; returns scene JSON.
#[wasm_bindgen(js_name = reroute)]
pub fn reroute_scene(scene_json: &str, moves_json: &str) -> Result<String, JsValue> {
    reroute::reroute(scene_json, moves_json).map_err(throw)
}

/// Apply a JSON list of edit operations to YAML text as one batch; returns the patched YAML. A rejected batch
/// throws an `Error` with the reason, and an `index` property when one operation is to blame.
#[wasm_bindgen(js_name = applyOps)]
pub fn apply_ops(yaml: &str, ops_json: &str) -> Result<String, JsValue> {
    edit::apply_ops_json(yaml, ops_json).map_err(|e| js_error(&e.to_string(), e.index))
}

/// `{id: [start, end]}` as JSON: the UTF-8 byte range of every node, zone and edge entry of the YAML.
#[wasm_bindgen]
pub fn srcmap(yaml: &str) -> Result<String, JsValue> {
    let map = edit::srcmap(yaml).map_err(throw)?;
    serde_json::to_string(&map).map_err(throw)
}
