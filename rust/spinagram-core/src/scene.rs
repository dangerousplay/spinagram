//! The scene: what a finished diagram looks like, as the JSON `spinagram.scene_json` writes.
//!
//! Every field the SVG writer reads is carried. `version` is checked on parse. Optional values are written
//! as `null`, so a scene round-trips to an equal JSON value.

use serde::{Deserialize, Serialize};
use serde_json::{Number, Value};
use std::collections::BTreeMap;

pub const VERSION: u32 = 1;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Font {
    pub family: String,
    pub weight: u32,
    pub italic: bool,
    pub size: f64,
    pub file: Option<String>,
    pub fallback: String,
    pub figma_style: String,
}

/// A piece of a line drawn with one font. `base`: it uses the block's own font (no fallback span).
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Run {
    pub text: String,
    pub font: Font,
    pub base: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct TextBlock {
    pub lines: Vec<String>,
    pub paragraphs: Vec<String>,
    pub font: Font,
    pub color: String,
    pub leading: f64,
    pub runs: Option<Vec<Vec<Run>>>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Label {
    pub blocks: Vec<TextBlock>,
    #[serde(rename = "box")]
    pub bbox: [f64; 4],
    pub align: String,
    pub gap: f64,
    pub valign: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Icon {
    pub path: String,
    pub x: f64,
    pub y: f64,
    pub size: f64,
    pub w: Option<f64>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Part {
    pub d: String,
    pub paint: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Shape {
    pub id: String,
    pub kind: String,
    pub x: f64,
    pub y: f64,
    pub w: f64,
    pub h: f64,
    pub fill: Option<String>,
    pub stroke: Option<String>,
    pub stroke_width: f64,
    pub radius: f64,
    pub dashed: bool,
    pub opacity: f64,
    pub label: Option<Label>,
    pub icon: Option<Icon>,
    pub role: String,
    pub parts: Option<Vec<Part>>,
    pub dash: Option<Vec<f64>>,
    /// `(dx, dy, blur, colour, alpha)`
    pub shadow: Option<(f64, f64, f64, String, f64)>,
    pub fill_opacity: f64,
    pub cap: Option<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Binding {
    pub shape_id: String,
    pub side: String,
    pub frac: f64,
    pub target: String,
}

/// A shape nested in another item carries its own `type` tag, as in the item list.
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(tag = "type")]
pub enum TaggedShape {
    #[serde(rename = "shape")]
    Shape(Shape),
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Connector {
    pub id: String,
    pub points: Vec<[f64; 2]>,
    pub route: String,
    pub color: String,
    pub width: f64,
    pub dashed: bool,
    pub arrow_start: bool,
    pub arrow_end: bool,
    pub src: Option<Binding>,
    pub dst: Option<Binding>,
    pub label: Option<TaggedShape>,
    pub dash: Option<Vec<f64>>,
    pub marker_start: String,
    pub marker_end: String,
    pub opacity: f64,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Text {
    pub id: String,
    pub x: f64,
    pub y: f64,
    pub block: TextBlock,
    pub anchor: String,
    /// Kept as written (int or float): the SVG writer prints it with Python's `str`.
    pub letter_spacing: Number,
    pub width: Option<f64>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Line {
    pub id: String,
    pub x1: f64,
    pub y1: f64,
    pub x2: f64,
    pub y2: f64,
    pub color: String,
    pub width: f64,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Image {
    pub id: String,
    pub path: String,
    pub x: f64,
    pub y: f64,
    pub w: f64,
    pub h: f64,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Cell {
    pub block: TextBlock,
    pub fill: Option<String>,
    pub icon: Option<Icon>,
    pub pad_left: f64,
    pub bold: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Table {
    pub id: String,
    pub x: f64,
    pub y: f64,
    pub col_widths: Vec<f64>,
    pub row_heights: Vec<f64>,
    pub cells: Vec<Vec<Cell>>,
    pub border: String,
    pub header_radius: f64,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "lowercase")]
#[allow(clippy::large_enum_variant)] // items live in a Vec and are matched by reference
pub enum Item {
    Shape(Shape),
    Connector(Connector),
    Text(Text),
    Line(Line),
    Image(Image),
    Table(Table),
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Scene {
    pub version: u32,
    pub id: String,
    pub title: String,
    pub slug: String,
    pub width: f64,
    pub height: f64,
    pub background: String,
    pub items: Vec<Item>,
    pub item_facts: BTreeMap<String, Vec<String>>,
    pub sources: Vec<Value>,
    pub meta_tooltips: BTreeMap<String, String>,
}

#[derive(Deserialize)]
struct Header {
    version: Option<Value>,
}

/// Parse scene JSON. A `version` other than 1 is an error naming the found and the supported version.
pub fn parse(json: &str) -> Result<Scene, String> {
    let header: Header = serde_json::from_str(json).map_err(|e| format!("invalid scene JSON: {e}"))?;
    match header.version.as_ref().and_then(Value::as_u64) {
        Some(v) if v == VERSION as u64 => {}
        Some(v) => return Err(format!("scene version {v} is not supported (expected {VERSION})")),
        None => return Err(format!("scene version {} is not supported (expected {VERSION})", header.version.map_or("missing".into(), |v| v.to_string()))),
    }
    serde_json::from_str(json).map_err(|e| format!("invalid scene JSON: {e}"))
}

pub fn to_json(scene: &Scene) -> String {
    serde_json::to_string(scene).expect("a scene always serializes")
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn font(file: Value) -> Value {
        json!({"family": "Inter", "weight": 700, "italic": true, "size": 14.0, "file": file,
               "fallback": "sans-serif", "figma_style": "Bold Italic"})
    }

    fn block(runs: Value) -> Value {
        json!({"lines": ["one", ""], "paragraphs": ["one"], "font": font(json!("/f/inter.ttf")), "color": "#112233",
               "leading": 18.0, "runs": runs})
    }

    fn icon() -> Value {
        json!({"path": "/i/a.svg", "x": 1.0, "y": 2.0, "size": 24.0, "w": 30.0})
    }

    fn shape(id: &str) -> Value {
        json!({"type": "shape", "id": id, "kind": "rect", "x": 10.0, "y": 20.0, "w": 100.0, "h": 50.0, "fill": "#fff",
               "stroke": "#000", "stroke_width": 2.0, "radius": 6.0, "dashed": true, "opacity": 0.5,
               "label": {"blocks": [block(json!([[{"text": "o", "font": font(json!(null)), "base": true},
                                                  {"text": "ne", "font": font(json!(null)), "base": false}], []]))],
                         "box": [10.0, 20.0, 100.0, 50.0], "align": "center", "gap": 8.0, "valign": "top"},
               "icon": icon(), "role": "node",
               "parts": [{"d": "M 0 0 Z", "paint": "solid"}, {"d": "M 1 1 Z", "paint": "stroke"}],
               "dash": [4.0, 2.0], "shadow": [1.0, 2.0, 6.0, "#000000", 0.25], "fill_opacity": 0.75, "cap": "round"})
    }

    pub fn fixture() -> Value {
        let cell = json!({"block": block(json!(null)), "fill": "#eee", "icon": icon(), "pad_left": 20.0, "bold": true});
        json!({"version": 1, "id": "S1", "title": "Title & more", "slug": "s1-title", "width": 640.0, "height": 480.0,
               "background": "#fafafa",
               "items": [
                   shape("s1"),
                   {"type": "connector", "id": "c1", "points": [[0.0, 0.0], [5.0, 5.0], [9.0, 0.0]], "route": "curve",
                    "color": "#abcdef", "width": 1.5, "dashed": false, "arrow_start": true, "arrow_end": false,
                    "src": {"shape_id": "s1", "side": "right", "frac": 0.25, "target": "zone"}, "dst": null,
                    "label": shape("lab"), "dash": [3.0], "marker_start": "open-diamond", "marker_end": "bar",
                    "opacity": 0.5},
                   {"type": "text", "id": "t1", "x": 5.0, "y": 6.0, "block": block(json!(null)), "anchor": "middle",
                    "letter_spacing": 0.5, "width": 120.0},
                   {"type": "line", "id": "l1", "x1": 0.0, "y1": 1.0, "x2": 2.0, "y2": 3.0, "color": "#000", "width": 2.0},
                   {"type": "image", "id": "i1", "path": "/img/x.png", "x": 1.0, "y": 2.0, "w": 3.0, "h": 4.0},
                   {"type": "table", "id": "tb", "x": 1.0, "y": 2.0, "col_widths": [50.0, 60.0],
                    "row_heights": [20.0, 30.0], "cells": [[cell.clone(), cell.clone()], [cell.clone(), cell]],
                    "border": "#ccc", "header_radius": 4.0}],
               "item_facts": {"s1": ["f1"]}, "sources": [{"id": "f1", "display": "é"}],
               "meta_tooltips": {"f1": "from the wiki"}})
    }

    #[test]
    fn every_item_type_round_trips_to_an_equal_value() {
        let input = fixture();
        let scene = parse(&input.to_string()).unwrap();
        assert_eq!(scene.items.len(), 6);
        let output: Value = serde_json::from_str(&to_json(&scene)).unwrap();
        assert_eq!(output, input);
    }

    #[test]
    fn integer_letter_spacing_stays_an_integer() {
        let mut v = fixture();
        v["items"][2]["letter_spacing"] = json!(1);
        let output: Value = serde_json::from_str(&to_json(&parse(&v.to_string()).unwrap())).unwrap();
        assert_eq!(output["items"][2]["letter_spacing"], json!(1));
    }

    #[test]
    fn other_versions_are_rejected_naming_both() {
        let mut v = fixture();
        v["version"] = json!(2);
        assert_eq!(parse(&v.to_string()).unwrap_err(), "scene version 2 is not supported (expected 1)");
    }
}
