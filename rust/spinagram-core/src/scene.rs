//! The scene: what a finished diagram looks like, as the JSON `spinagram.scene_json` writes.
//!
//! Every field the SVG writer reads is carried. `version` is checked on parse. Optional values are written
//! as `null`, so a scene round-trips to an equal JSON value.

use schemars::JsonSchema;
use serde::{Deserialize, Serialize};
use serde_json::{Number, Value};
use std::collections::BTreeMap;
use strum::{AsRefStr, Display, EnumString, IntoStaticStr, VariantArray};

use crate::edge_syntax::EndpointTarget;
use crate::edit_values::Axis;
use crate::route::Side;

pub const VERSION: u32 = 1;

/// Derive set of a closed string enum on the scene's wire: serde, JSON Schema and the strum conversions.
macro_rules! wire_enum {
    ($(#[$meta:meta])* $name:ident { $($(#[$vmeta:meta])* $variant:ident),+ $(,)? }, $rule:literal) => {
        $(#[$meta])*
        #[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize, JsonSchema, Display, EnumString, AsRefStr, IntoStaticStr, VariantArray)]
        #[serde(rename_all = $rule)]
        #[strum(serialize_all = $rule)]
        pub enum $name {
            $($(#[$vmeta])* $variant),+
        }

        impl $name {
            /// The value as the scene writes it.
            #[must_use]
            pub fn as_str(self) -> &'static str {
                self.into()
            }
        }
    };
}

wire_enum! {
    /// Horizontal alignment of a label.
    Align { /** Text starts at the box's left edge. */ Left, /** Text is centred in the box. */ Center }, "lowercase"
}

wire_enum! {
    /// Vertical alignment of a label.
    VAlign { /** Blocks start at the box's top edge. */ Top, /** Blocks are centred in the box. */ Middle }, "lowercase"
}

wire_enum! {
    /// SVG `text-anchor` of a text item.
    TextAnchor { /** Text starts at x. */ Start, /** Text is centred on x. */ Middle, /** Text ends at x. */ End }, "lowercase"
}

wire_enum! {
    /// How a symbol part is painted.
    Paint {
        /** Fill with the shape's fill and stroke with its stroke. */ Shape,
        /** Fill with the stroke colour. */ Solid,
        /** Outline only. */ Stroke,
    }, "lowercase"
}

wire_enum! {
    /// What a shape is for; it picks the layer it is drawn in.
    Role {
        /** A diagram node. */ Node,
        /** A zone background. */ Zone,
        /** A pill. */ Pill,
        /** A legend swatch. */ Swatch,
        /** Frame and title furniture. */ Chrome,
        /** A panel. */ Panel,
        /** A badge or accent that belongs to a node. */ NodePart,
        /** A callout. */ Callout,
    }, "kebab-case"
}

wire_enum! {
    /// How a connector's points are joined.
    ConnectorRoute {
        /** One straight segment. */ Straight,
        /** A polyline. */ Poly,
        /** A quadratic curve through three points. */ Curve,
    }, "lowercase"
}

wire_enum! {
    /// The head drawn at a connector end.
    MarkerKind {
        /** A filled triangle. */ Arrow,
        /** An outlined chevron. */ OpenArrow,
        /** A filled diamond. */ Diamond,
        /** An outlined diamond. */ OpenDiamond,
        /** A filled circle. */ Circle,
        /** A bar across the line. */ Bar,
        /** No head. */ None,
    }, "kebab-case"
}

wire_enum! {
    /// The stroke line cap of a shape.
    LineCap { /** Flat ends. */ Butt, /** Rounded ends. */ Round, /** Square ends. */ Square }, "lowercase"
}

/// The kind of a shape: the node kind or `rect`, `pill` and the like. The kinds whose outline touches the box
/// only at side midpoints are named; any other kind is kept as written.
#[derive(Clone, Debug, PartialEq, Eq, Hash, Serialize, Deserialize, JsonSchema)]
#[serde(from = "String", into = "String")]
#[schemars(with = "String")]
pub enum ShapeKind {
    /// `diamond`
    Diamond,
    /// `decision`
    Decision,
    /// `merge`
    Merge,
    /// `choice`
    Choice,
    /// `connector`
    Connector,
    /// `initial`
    Initial,
    /// `final`
    Final,
    /// `flow_final`
    FlowFinal,
    /// `history`
    History,
    /// `deep_history`
    DeepHistory,
    /// Any other kind (`rect`, `pill`, `action`, ...).
    Other(String),
}

impl ShapeKind {
    /// The kind as the scene writes it.
    #[must_use]
    pub fn as_str(&self) -> &str {
        match self {
            ShapeKind::Diamond => "diamond",
            ShapeKind::Decision => "decision",
            ShapeKind::Merge => "merge",
            ShapeKind::Choice => "choice",
            ShapeKind::Connector => "connector",
            ShapeKind::Initial => "initial",
            ShapeKind::Final => "final",
            ShapeKind::FlowFinal => "flow_final",
            ShapeKind::History => "history",
            ShapeKind::DeepHistory => "deep_history",
            ShapeKind::Other(s) => s,
        }
    }

    /// Whether the outline touches the box only at side midpoints, so an anchor ignores the fraction
    /// (`Shape.anchor`): a diamond or one of the state-chart and flowchart marks.
    #[must_use]
    pub fn midpoint_anchor(&self) -> bool {
        !matches!(self, ShapeKind::Other(_))
    }
}

impl From<String> for ShapeKind {
    fn from(s: String) -> Self {
        match s.as_str() {
            "diamond" => ShapeKind::Diamond,
            "decision" => ShapeKind::Decision,
            "merge" => ShapeKind::Merge,
            "choice" => ShapeKind::Choice,
            "connector" => ShapeKind::Connector,
            "initial" => ShapeKind::Initial,
            "final" => ShapeKind::Final,
            "flow_final" => ShapeKind::FlowFinal,
            "history" => ShapeKind::History,
            "deep_history" => ShapeKind::DeepHistory,
            _ => ShapeKind::Other(s),
        }
    }
}

impl From<ShapeKind> for String {
    fn from(k: ShapeKind) -> Self {
        k.as_str().to_owned()
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, JsonSchema)]
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
#[derive(Clone, Debug, Serialize, Deserialize, JsonSchema)]
pub struct Run {
    pub text: String,
    pub font: Font,
    pub base: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, JsonSchema)]
pub struct TextBlock {
    pub lines: Vec<String>,
    pub paragraphs: Vec<String>,
    pub font: Font,
    pub color: String,
    pub leading: f64,
    pub runs: Option<Vec<Vec<Run>>>,
}

#[derive(Clone, Debug, Serialize, Deserialize, JsonSchema)]
pub struct Label {
    pub blocks: Vec<TextBlock>,
    #[serde(rename = "box")]
    pub bbox: [f64; 4],
    pub align: Align,
    pub gap: f64,
    pub valign: VAlign,
}

#[derive(Clone, Debug, Serialize, Deserialize, JsonSchema)]
pub struct Icon {
    pub path: String,
    pub x: f64,
    pub y: f64,
    pub size: f64,
    pub w: Option<f64>,
}

#[derive(Clone, Debug, Serialize, Deserialize, JsonSchema)]
pub struct Part {
    pub d: String,
    pub paint: Paint,
}

#[derive(Clone, Debug, Serialize, Deserialize, JsonSchema)]
pub struct Shape {
    pub id: String,
    pub kind: ShapeKind,
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
    pub role: Role,
    pub parts: Option<Vec<Part>>,
    pub dash: Option<Vec<f64>>,
    /// `(dx, dy, blur, colour, alpha)`
    pub shadow: Option<(f64, f64, f64, String, f64)>,
    pub fill_opacity: f64,
    pub cap: Option<LineCap>,
}

#[derive(Clone, Debug, Serialize, Deserialize, JsonSchema)]
pub struct Binding {
    pub shape_id: String,
    pub side: Side,
    pub frac: f64,
    pub target: EndpointTarget,
    /// The author fixed the side (`node.side`): routers keep it. Written only when true; absent means false.
    #[serde(default, skip_serializing_if = "std::ops::Not::not")]
    pub explicit: bool,
}

/// A shape nested in another item carries its own `type` tag, as in the item list.
#[derive(Clone, Debug, Serialize, Deserialize, JsonSchema)]
#[serde(tag = "type")]
pub enum TaggedShape {
    #[serde(rename = "shape")]
    Shape(Shape),
}

#[derive(Clone, Debug, Serialize, Deserialize, JsonSchema)]
pub struct Connector {
    pub id: String,
    pub points: Vec<[f64; 2]>,
    pub route: ConnectorRoute,
    pub color: String,
    pub width: f64,
    pub dashed: bool,
    pub arrow_start: bool,
    pub arrow_end: bool,
    pub src: Option<Binding>,
    pub dst: Option<Binding>,
    pub label: Option<TaggedShape>,
    pub dash: Option<Vec<f64>>,
    pub marker_start: MarkerKind,
    pub marker_end: MarkerKind,
    pub opacity: f64,
}

#[derive(Clone, Debug, Serialize, Deserialize, JsonSchema)]
pub struct Text {
    pub id: String,
    pub x: f64,
    pub y: f64,
    pub block: TextBlock,
    pub anchor: TextAnchor,
    /// Kept as written (int or float): the SVG writer prints it with Python's `str`.
    pub letter_spacing: Number,
    pub width: Option<f64>,
}

#[derive(Clone, Debug, Serialize, Deserialize, JsonSchema)]
pub struct Line {
    pub id: String,
    pub x1: f64,
    pub y1: f64,
    pub x2: f64,
    pub y2: f64,
    pub color: String,
    pub width: f64,
}

#[derive(Clone, Debug, Serialize, Deserialize, JsonSchema)]
pub struct Image {
    pub id: String,
    pub path: String,
    pub x: f64,
    pub y: f64,
    pub w: f64,
    pub h: f64,
}

#[derive(Clone, Debug, Serialize, Deserialize, JsonSchema)]
pub struct Cell {
    pub block: TextBlock,
    pub fill: Option<String>,
    pub icon: Option<Icon>,
    pub pad_left: f64,
    pub bold: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, JsonSchema)]
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

#[derive(Clone, Debug, Serialize, Deserialize, JsonSchema)]
#[serde(tag = "type", rename_all = "lowercase")]
pub enum Item {
    Shape(Shape),
    Connector(Connector),
    Text(Text),
    Line(Line),
    Image(Image),
    Table(Table),
}

#[derive(Clone, Debug, Serialize, Deserialize, JsonSchema)]
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
    /// Zones with the ids the spec declares. Written only when there are zones.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub zones: Vec<ZoneInfo>,
    /// Row and column containers. Written only when there are some.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub containers: Vec<ContainerInfo>,
}

/// A zone: the id the edit operations use, the id of its shape in `items`, and its declared children.
#[derive(Clone, Debug, Serialize, Deserialize, JsonSchema)]
pub struct ZoneInfo {
    pub id: String,
    pub shape_id: String,
    pub children: Vec<String>,
}

/// A `rows`/`columns` container (`row0`, `column1`, ...): axis, member node ids in order, and the box
/// `[x, y, w, h]` enclosing the members.
#[derive(Clone, Debug, Serialize, Deserialize, JsonSchema)]
pub struct ContainerInfo {
    pub id: String,
    pub axis: Axis,
    pub members: Vec<String>,
    #[serde(rename = "box")]
    pub bbox: [f64; 4],
}

#[derive(Deserialize)]
struct Header {
    version: Option<Value>,
}

/// Parse scene JSON. A `version` other than 1 is an error naming the found and the supported version.
///
/// # Errors
///
/// When the JSON is invalid, or its `version` is not 1.
pub fn parse(json: &str) -> Result<Scene, String> {
    let header: Header = serde_json::from_str(json).map_err(|e| format!("invalid scene JSON: {e}"))?;
    match header.version.as_ref().and_then(Value::as_u64) {
        Some(v) if v == u64::from(VERSION) => {}
        Some(v) => return Err(format!("scene version {v} is not supported (expected {VERSION})")),
        None => return Err(format!("scene version {} is not supported (expected {VERSION})", header.version.map_or("missing".into(), |v| v.to_string()))),
    }
    serde_json::from_str(json).map_err(|e| format!("invalid scene JSON: {e}"))
}

/// The JSON Schema of the scene format, as committed in `rust/schema/scene.schema.json`.
///
/// # Panics
///
/// Never: a derived schema always serializes.
#[must_use]
pub fn schema_json() -> String {
    let mut out = serde_json::to_string_pretty(&schemars::schema_for!(Scene)).expect("a schema serializes");
    out.push('\n');
    out
}

/// # Panics
///
/// Never: a scene always serializes.
#[must_use]
pub fn to_json(scene: &Scene) -> String {
    serde_json::to_string(scene).expect("a scene always serializes")
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    use strum::VariantArray;

    /// Every variant serialises to the string the Python writer uses, reads back from it, and parses with strum.
    fn round_trips<T>(expected: &[&str])
    where
        T: VariantArray + Serialize + serde::de::DeserializeOwned + std::str::FromStr + PartialEq + std::fmt::Debug + Copy + Into<&'static str>,
    {
        let got: Vec<&str> = T::VARIANTS.iter().map(|v| (*v).into()).collect();
        assert_eq!(got, expected);
        for (v, text) in T::VARIANTS.iter().zip(expected) {
            assert_eq!(serde_json::to_string(v).unwrap(), format!("\"{text}\""));
            assert_eq!(serde_json::from_str::<T>(&format!("\"{text}\"")).unwrap(), *v);
            assert_eq!(text.parse::<T>().ok(), Some(*v));
        }
        assert!(serde_json::from_str::<T>("\"no-such-value\"").is_err());
    }

    #[test]
    fn closed_string_sets_keep_the_strings_the_python_scene_writes() {
        round_trips::<Align>(&["left", "center"]);
        round_trips::<VAlign>(&["top", "middle"]);
        round_trips::<TextAnchor>(&["start", "middle", "end"]);
        round_trips::<Paint>(&["shape", "solid", "stroke"]);
        round_trips::<Role>(&["node", "zone", "pill", "swatch", "chrome", "panel", "node-part", "callout"]);
        round_trips::<ConnectorRoute>(&["straight", "poly", "curve"]);
        round_trips::<MarkerKind>(&["arrow", "open-arrow", "diamond", "open-diamond", "circle", "bar", "none"]);
        round_trips::<LineCap>(&["butt", "round", "square"]);
        round_trips::<Side>(&["top", "bottom", "left", "right"]);
        round_trips::<Axis>(&["row", "column"]);
        round_trips::<EndpointTarget>(&["node", "zone"]);
    }

    #[test]
    fn a_shape_kind_keeps_unknown_kinds_and_knows_the_midpoint_ones() {
        for (text, midpoint) in [("diamond", true), ("decision", true), ("flow_final", true), ("deep_history", true), ("rect", false), ("pill", false), ("action", false)] {
            let kind: ShapeKind = serde_json::from_str(&format!("\"{text}\"")).unwrap();
            assert_eq!(kind.midpoint_anchor(), midpoint, "{text}");
            assert_eq!(serde_json::to_string(&kind).unwrap(), format!("\"{text}\""));
        }
    }

    #[expect(clippy::needless_pass_by_value, reason = "test fixture builders take JSON literals by value")]
    fn font(file: Value) -> Value {
        json!({"family": "Inter", "weight": 700, "italic": true, "size": 14.0, "file": file,
               "fallback": "sans-serif", "figma_style": "Bold Italic"})
    }

    #[expect(clippy::needless_pass_by_value, reason = "test fixture builders take JSON literals by value")]
    fn block(runs: Value) -> Value {
        json!({"lines": ["one", ""], "paragraphs": ["one"], "font": font(json!("/f/inter.ttf")), "color": "#112233",
               "leading": 27.599_999_999_999_998, "runs": runs})
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
                    "src": {"shape_id": "s1", "side": "right", "frac": 0.25, "target": "zone", "explicit": true}, "dst": null,
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

    const SCHEMA_FILE: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/../schema/scene.schema.json");

    /// `UPDATE_SCHEMA=1 cargo test -p spinagram-core schema` rewrites the committed file.
    #[test]
    fn committed_schema_is_fresh() {
        let fresh = schema_json();
        if std::env::var("UPDATE_SCHEMA").is_ok_and(|v| v == "1") {
            std::fs::create_dir_all(std::path::Path::new(SCHEMA_FILE).parent().unwrap()).unwrap();
            std::fs::write(SCHEMA_FILE, &fresh).unwrap();
        }
        let committed = std::fs::read_to_string(SCHEMA_FILE).expect("rust/schema/scene.schema.json is missing");
        assert!(committed == fresh, "rust/schema/scene.schema.json is stale: run UPDATE_SCHEMA=1 cargo test -p spinagram-core schema");
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
