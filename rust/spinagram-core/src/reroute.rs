//! Move shapes in a scene and re-route the connectors that touch them, for live feedback while a node is
//! dragged. The server stays the authority: this reproduces `endpoints.resolve` and the ortho router of the
//! Python layout for the touched connectors only, so a full render of the saved YAML replaces the preview.
//!
//! Limits (each one a thing the scene JSON does not record): zone header rectangles are not obstacles;
//! connectors with a free (unbound) end, bus bars and bundles are left as they are; a `poly` connector is
//! always routed by the ortho router (the scene does not say whether it was an elbow, a `via` list or routed);
//! a `straight` connector keeps both ends on facing sides instead of re-running `straight_refs`.

#![expect(clippy::many_single_char_names, reason = "geometry names (x, y, w, h, a, b) mirror the Python endpoints code")]

use std::collections::{BTreeMap, HashMap};

use regex::Regex;
use svgtypes::{PathParser, PathSegment};
use thiserror::Error;

use crate::pyfmt::g;
use crate::route::{self, round2, Crossings, Options, Pt, Rect, Side, MARGIN};
use crate::edge_syntax::EndpointTarget;
use crate::scene::{self, Binding, SceneError, Connector, ConnectorRoute, Item, Role, Scene, Shape, ShapeKind, TaggedShape};

/// Why a move was refused.
#[derive(Debug, Error)]
pub enum RerouteError {
    /// The scene JSON is not a scene.
    #[error(transparent)]
    Scene(#[from] SceneError),
    /// The scene did not serialise again.
    #[error("cannot write the scene: {0}")]
    Write(#[from] serde_json::Error),
    /// The moves JSON is not a map of ids to numbers.
    #[error("invalid moves: {0}")]
    Moves(String),
    /// A move names a shape the scene does not have.
    #[error("unknown shape `{0}`")]
    UnknownShape(String),
    /// A move is neither `[dx, dy]` nor `[x, y, w, h]`.
    #[error("move of `{0}` must be [dx, dy] or [x, y, w, h]")]
    MoveShape(String),
    /// A move gives a box that is not finite and non-negative.
    #[error("move of `{0}` is not a finite, non-negative box")]
    MoveBox(String),
    /// The pattern for a shape's own parts did not compile.
    #[error("{0}")]
    Pattern(#[from] regex::Error),
}

/// Shape id to `[dx, dy]` (move) or `[x, y, w, h]` (new box).
pub type Moves = BTreeMap<String, Vec<f64>>;

/// Cost of crossing an edge already routed, in px of length (`engine.route.CROSSING`).
const CROSSING: f64 = 120.0;
/// Zone endpoints stay this far from the corners (`engine.endpoints.CORNER`).
const CORNER: f64 = 24.0;

#[derive(Clone)]
struct Geo {
    x: f64,
    y: f64,
    w: f64,
    h: f64,
    kind: ShapeKind,
}

impl Geo {
    fn of(s: &Shape) -> Geo {
        Geo { x: s.x, y: s.y, w: s.w, h: s.h, kind: s.kind.clone() }
    }

    fn rect(&self) -> Rect {
        (self.x, self.y, self.w, self.h)
    }

    fn center(&self) -> Pt {
        (self.x + self.w / 2.0, self.y + self.h / 2.0)
    }

    /// `Shape.anchor`: outlines that touch the box only at side midpoints ignore the fraction.
    fn anchor(&self, side: Side, frac: f64) -> Pt {
        let (x, y, w, h) = self.rect();
        let f = if self.kind.midpoint_anchor() { 0.5 } else { frac };
        match side {
            Side::Top => (x + w * f, y),
            Side::Bottom => (x + w * f, y + h),
            Side::Left => (x, y + h * f),
            Side::Right => (x + w, y + h * f),
        }
    }

    /// `endpoints._facing`: the side facing a point.
    fn facing(&self, o: Pt) -> Side {
        let (cx, cy) = self.center();
        let (dx, dy) = (o.0 - cx, o.1 - cy);
        if dx.abs() * self.h >= dy.abs() * self.w {
            if dx > 0.0 { Side::Right } else { Side::Left }
        } else if dy > 0.0 {
            Side::Bottom
        } else {
            Side::Top
        }
    }

    /// `endpoints._zone_side`: facing a point outside, the nearest side for a point inside.
    fn zone_side(&self, o: Pt) -> Side {
        let (x, y, w, h) = self.rect();
        if x < o.0 && o.0 < x + w && y < o.1 && o.1 < y + h {
            let d = [(Side::Top, o.1 - y), (Side::Bottom, y + h - o.1), (Side::Left, o.0 - x), (Side::Right, x + w - o.0)];
            return d.iter().fold(d[0], |best, &c| if c.1 < best.1 { c } else { best }).0;
        }
        self.facing(o)
    }

    /// `endpoints._clamped_frac`.
    fn clamped_frac(&self, side: Side, o: Pt) -> f64 {
        let (lo, hi, v, span, start) = if matches!(side, Side::Top | Side::Bottom) {
            (self.x + CORNER, self.x + self.w - CORNER, o.0, self.w, self.x)
        } else {
            (self.y + CORNER, self.y + self.h - CORNER, o.1, self.h, self.y)
        };
        let v = if lo <= hi { v.max(lo).min(hi) } else { start + span / 2.0 };
        (v - start) / span
    }
}

/// The point an end aims at: the anchor when the author fixed a side, else the shape centre.
fn aim(b: &Binding, s: &Geo) -> Pt {
    if b.explicit { s.anchor(b.side, b.frac) } else { s.center() }
}

/// `endpoints.resolve` for a bound end: the point and the binding it gets.
fn resolve(b: &Binding, s: &Geo, other: Pt) -> (Pt, Binding) {
    let (side, frac) = if b.explicit {
        (b.side, b.frac)
    } else if b.target == EndpointTarget::Zone {
        let side = s.zone_side(other);
        (side, s.clamped_frac(side, other))
    } else {
        (s.facing(other), 0.5)
    };
    (s.anchor(side, frac), Binding { side, frac, ..b.clone() })
}

fn polyline(c: &Connector) -> Vec<Pt> {
    let pts: Vec<Pt> = c.points.iter().map(|p| (p[0], p[1])).collect();
    if c.route != ConnectorRoute::Curve || pts.len() != 3 {
        return pts;
    }
    let ((x0, y0), (qx, qy), (x2, y2)) = (pts[0], pts[1], pts[2]);
    (0..=24)
        .map(|i| {
            let t = f64::from(i) / 24.0;
            let u = 1.0 - t;
            (u * u * x0 + 2.0 * u * t * qx + t * t * x2, u * u * y0 + 2.0 * u * t * qy + t * t * y2)
        })
        .collect()
}

/// `engine.route._side`: the side of a box a segment leaves from.
fn side_of(p: Pt, q: Pt) -> Side {
    let (dx, dy) = (q.0 - p.0, q.1 - p.1);
    let sign = |v: f64| i8::from(v > 0.0) - i8::from(v < 0.0);
    Side::of_step(sign(dx), sign(dy))
}

/// How a path moves with its shape: the `ox`/`oy` corner scales by `sx`/`sy` and lands at `x`/`y`.
struct PathMap {
    sx: f64,
    sy: f64,
    ox: f64,
    oy: f64,
    x: f64,
    y: f64,
}

impl PathMap {
    fn abs(&self, px: f64, py: f64) -> (f64, f64) {
        (self.x + (px - self.ox) * self.sx, self.y + (py - self.oy) * self.sy)
    }

    /// Offsets scale only: the translation cancels between two points.
    fn rel(&self, dx: f64, dy: f64) -> (f64, f64) {
        (dx * self.sx, dy * self.sy)
    }

    fn point(&self, abs: bool, px: f64, py: f64) -> (f64, f64) {
        if abs { self.abs(px, py) } else { self.rel(px, py) }
    }
}

/// Map the coordinates of an SVG path (`M L H V C S Q T A Z`, absolute or relative, any number syntax) with `m`.
/// A path that does not parse is returned as it is.
fn map_path(d: &str, m: &PathMap) -> String {
    let mut out: Vec<String> = Vec::new();
    let num = |v: f64| g(round2(v));
    for (i, seg) in PathParser::from(d).enumerate() {
        let Ok(seg) = seg else { return d.to_owned() };
        let cmd = char::from(seg.command()).to_string();
        let nums: Vec<f64> = match seg {
            PathSegment::MoveTo { abs, x, y } | PathSegment::LineTo { abs, x, y } | PathSegment::SmoothQuadratic { abs, x, y } => {
                // the first `m` of a path is absolute whatever its case
                let first_move = i == 0 && matches!(seg, PathSegment::MoveTo { .. });
                let (x, y) = m.point(abs || first_move, x, y);
                vec![x, y]
            }
            PathSegment::HorizontalLineTo { abs, x } => vec![if abs { m.abs(x, m.oy).0 } else { m.rel(x, 0.0).0 }],
            PathSegment::VerticalLineTo { abs, y } => vec![if abs { m.abs(m.ox, y).1 } else { m.rel(0.0, y).1 }],
            PathSegment::CurveTo { abs, x1, y1, x2, y2, x, y } => {
                let ((x1, y1), (x2, y2), (x, y)) = (m.point(abs, x1, y1), m.point(abs, x2, y2), m.point(abs, x, y));
                vec![x1, y1, x2, y2, x, y]
            }
            PathSegment::SmoothCurveTo { abs, x2, y2, x, y } => {
                let ((x2, y2), (x, y)) = (m.point(abs, x2, y2), m.point(abs, x, y));
                vec![x2, y2, x, y]
            }
            PathSegment::Quadratic { abs, x1, y1, x, y } => {
                let ((x1, y1), (x, y)) = (m.point(abs, x1, y1), m.point(abs, x, y));
                vec![x1, y1, x, y]
            }
            PathSegment::EllipticalArc { abs, rx, ry, x_axis_rotation, large_arc, sweep, x, y } => {
                let (x, y) = m.point(abs, x, y);
                let flag = |b: bool| if b { 1.0 } else { 0.0 };
                vec![rx * m.sx, ry * m.sy, x_axis_rotation, flag(large_arc), flag(sweep), x, y]
            }
            PathSegment::ClosePath { .. } => Vec::new(),
        };
        out.push(cmd);
        out.extend(nums.into_iter().map(num));
    }
    out.join(" ")
}

/// Move a shape and what it carries (label box, icon, symbol path) to `(x, y)` with size `(w, h)`.
fn place(s: &mut Shape, x: f64, y: f64, w: f64, h: f64) {
    let (ox, oy, ow, oh) = (s.x, s.y, s.w, s.h);
    let (sx, sy) = (if ow > 0.0 { w / ow } else { 1.0 }, if oh > 0.0 { h / oh } else { 1.0 });
    let (dx, dy) = (x - ox, y - oy);
    if let Some(l) = s.label.as_mut() {
        l.bbox[0] += dx;
        l.bbox[1] += dy;
    }
    if let Some(i) = s.icon.as_mut() {
        i.x += dx;
        i.y += dy;
    }
    if let Some(parts) = s.parts.as_mut() {
        for p in parts {
            p.d = map_path(&p.d, &PathMap { sx, sy, ox, oy, x, y });
        }
    }
    (s.x, s.y, s.w, s.h) = (x, y, w, h);
}

fn shift_shape(s: &mut Shape, dx: f64, dy: f64) {
    place(s, s.x + dx, s.y + dy, s.w, s.h);
}

/// Apply `moves`, then re-route every connector that touches a moved shape.
///
/// # Errors
///
/// [`RerouteError`] when a move names an unknown shape or is not `[dx, dy]` or `[x, y, w, h]`.
pub fn reroute_scene(scene: &mut Scene, moves: &Moves) -> Result<(), RerouteError> {
    if moves.is_empty() {
        return Ok(());
    }
    // 1. move the shapes and their own parts (accent bar, quote mark, badges; a zone's label, icons and strip)
    for (id, m) in moves {
        let Some(Item::Shape(s)) = scene.items.iter().find(|it| matches!(it, Item::Shape(s) if &s.id == id)) else {
            return Err(RerouteError::UnknownShape(id.clone()));
        };
        let (x, y, w, h) = match m.as_slice() {
            [dx, dy] => (s.x + dx, s.y + dy, s.w, s.h),
            [x, y, w, h] => (*x, *y, *w, *h),
            _ => return Err(RerouteError::MoveShape(id.clone())),
        };
        if ![x, y, w, h].iter().all(|v| v.is_finite()) || w < 0.0 || h < 0.0 {
            return Err(RerouteError::MoveBox(id.clone()));
        }
        let (dx, dy) = (x - s.x, y - s.y);
        let own = Regex::new(&format!("^{}-(accent|badge[0-9]+(-halo)?)$", regex::escape(id)))?;
        let zone_own = Regex::new(&format!("^{}-(icon[0-9]*|strip)$", regex::escape(id)))?;
        let (mark, label) = (format!("{id}-mark"), format!("{id}-label"));
        for it in &mut scene.items {
            match it {
                Item::Shape(p) if p.id == *id => place(p, x, y, w, h),
                Item::Shape(p) if p.role == Role::NodePart && own.is_match(&p.id) => shift_shape(p, dx, dy),
                Item::Shape(p) if p.role == Role::Zone && zone_own.is_match(&p.id) => shift_shape(p, dx, dy), // header icons, accent strip
                Item::Text(t) if t.id == mark || t.id == label => {
                    t.x += dx;
                    t.y += dy;
                }
                _ => {}
            }
        }
    }
    // 2. geometry after the moves
    let mut geo: HashMap<String, Geo> = HashMap::new();
    let mut obstacles: Vec<Rect> = Vec::new();
    for it in &scene.items {
        if let Item::Shape(s) = it {
            geo.entry(s.id.clone()).or_insert_with(|| Geo::of(s));
            if s.role == Role::Node {
                obstacles.push((s.x, s.y, s.w, s.h));
            }
        }
    }
    // 3. the connectors that touch a moved shape and have both ends bound, in item order
    let touches = |c: &Connector| [&c.src, &c.dst].iter().any(|b| b.as_ref().is_some_and(|b| moves.contains_key(&b.shape_id)));
    let todo: Vec<usize> = scene
        .items
        .iter()
        .enumerate()
        .filter_map(|(i, it)| match it {
            Item::Connector(c) if touches(c) && c.src.is_some() && c.dst.is_some() && geo.contains_key(&c.src.as_ref()?.shape_id) && geo.contains_key(&c.dst.as_ref()?.shape_id) => Some(i),
            _ => None,
        })
        .collect();
    let mut placed: Vec<Vec<(Pt, Pt)>> = scene
        .items
        .iter()
        .enumerate()
        .filter_map(|(i, it)| match it {
            Item::Connector(c) if !todo.contains(&i) => Some(polyline(c).windows(2).map(|w| (w[0], w[1])).collect()),
            _ => None,
        })
        .collect();
    for i in todo {
        let Item::Connector(c) = &mut scene.items[i] else { continue };
        let (Some(sb), Some(db)) = (c.src.clone(), c.dst.clone()) else { continue };
        let (a, b) = (geo[&sb.shape_id].clone(), geo[&db.shape_id].clone());
        let old_mid = mid(c);
        match c.route {
            ConnectorRoute::Poly => {
                let drawn: Vec<(Pt, Pt)> = placed.iter().flatten().copied().collect();
                let guides: Vec<Pt> = drawn.iter().flat_map(|&(p, q)| [p, q]).flat_map(|(x, y)| [(x - MARGIN, y - MARGIN), (x + MARGIN, y + MARGIN)]).collect();
                let crossing = Crossings { cost: CROSSING, drawn };
                let keep = |bd: &Binding| bd.explicit; // a side the author chose, on a node or a zone
                let sides = (keep(&sb).then_some(sb.side), keep(&db).then_some(db.side));
                let zone_frac = |bd: &Binding| (bd.target == EndpointTarget::Zone && bd.explicit).then_some(bd.frac);
                let fracs = (zone_frac(&sb), zone_frac(&db));
                let opts = Options { margin: MARGIN, sides, busy_src: &[], busy_dst: &[], crossing: Some(&crossing), guides: &guides, fracs };
                let pts = route::route(a.rect(), b.rect(), &obstacles, &opts);
                let fin = |bd: &Binding, p: Pt, q: Pt, f: Option<f64>| Binding { side: side_of(p, q), frac: f.unwrap_or(0.5), explicit: false, ..bd.clone() };
                c.src = Some(fin(&sb, pts[0], pts[1], fracs.0));
                c.dst = Some(fin(&db, pts[pts.len() - 1], pts[pts.len() - 2], fracs.1));
                c.points = pts.iter().map(|p| [p.0, p.1]).collect();
            }
            route_kind @ (ConnectorRoute::Straight | ConnectorRoute::Curve) => {
                let (p1, nb1) = resolve(&sb, &a, aim(&db, &b));
                let (p2, nb2) = resolve(&db, &b, aim(&sb, &a));
                c.points = if route_kind == ConnectorRoute::Curve && c.points.len() == 3 { vec![[p1.0, p1.1], c.points[1], [p2.0, p2.1]] } else { vec![[p1.0, p1.1], [p2.0, p2.1]] };
                (c.src, c.dst) = (Some(nb1), Some(nb2));
            }
        }
        let new_mid = mid(c);
        if let Some(TaggedShape::Shape(label)) = c.label.as_mut() {
            shift_shape(label, new_mid.0 - old_mid.0, new_mid.1 - old_mid.1);
        }
        placed.push(polyline(c).windows(2).map(|w| (w[0], w[1])).collect());
    }
    Ok(())
}

/// Where the edge label sits relative to the ends: the midpoint of the first and last point.
fn mid(c: &Connector) -> Pt {
    match (c.points.first(), c.points.last()) {
        (Some(a), Some(b)) => (f64::midpoint(a[0], b[0]), f64::midpoint(a[1], b[1])),
        _ => (0.0, 0.0),
    }
}

/// `reroute_scene` on JSON: the scene and `{id: [dx, dy] | [x, y, w, h]}`, returning the scene JSON.
///
/// # Errors
///
/// [`RerouteError`] for bad JSON or an invalid move.
pub fn reroute(scene_json: &str, moves_json: &str) -> Result<String, RerouteError> {
    let mut scene = scene::parse(scene_json)?;
    let moves: Moves = serde_json::from_str(moves_json).map_err(|e| RerouteError::Moves(e.to_string()))?;
    reroute_scene(&mut scene, &moves)?;
    Ok(scene::to_json(&scene)?)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::Value;

    #[test]
    fn map_path_moves_absolute_coordinates() {
        let m = PathMap { sx: 2.0, sy: 3.0, ox: 10.0, oy: 20.0, x: 100.0, y: 50.0 };
        assert_eq!(map_path("M 10 20 L 30 40 C 1 2 3 4 5 6 Z", &m), "M 100 50 L 140 110 C 82 -4 86 2 90 8 Z");
        assert_eq!(map_path("M10,20L30,40Z", &m), "M 100 50 L 140 110 Z");
    }

    #[test]
    fn map_path_scales_relative_offsets_and_reads_exponents() {
        let m = PathMap { sx: 2.0, sy: 3.0, ox: 0.0, oy: 0.0, x: 5.0, y: 7.0 };
        // the first `m` is absolute; `l`, `h`, `v` are offsets that only scale; `1e1` and `2.5e1` are numbers
        assert_eq!(map_path("m 1e1 2.5e1 l 1 1 h 2 v -3 z", &m), "m 25 82 l 2 3 h 4 v -9 z");
        assert_eq!(map_path("M 0 0 H 10 V 10", &m), "M 5 7 H 25 V 37");
    }

    #[test]
    fn map_path_leaves_an_unreadable_path_alone() {
        let m = PathMap { sx: 1.0, sy: 1.0, ox: 0.0, oy: 0.0, x: 1.0, y: 1.0 };
        assert_eq!(map_path("M 1 2 L nope", &m), "M 1 2 L nope");
    }

    const DATA: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/tests/data/reroute");
    const ROOT: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/../..");

    /// A scene the Python engine rendered (`rust/bench/reroute_fixtures.py`).
    fn fixture(name: &str) -> String {
        std::fs::read_to_string(format!("{DATA}/{name}.scene.json")).unwrap().replace("@ROOT@", ROOT)
    }

    fn connectors(s: &Scene) -> Vec<&Connector> {
        s.items.iter().filter_map(|i| if let Item::Connector(c) = i { Some(c) } else { None }).collect()
    }

    fn shape<'a>(s: &'a Scene, id: &str) -> &'a Shape {
        s.items.iter().find_map(|i| match i { Item::Shape(p) if p.id == id => Some(p), _ => None }).unwrap()
    }

    fn moved(name: &str, moves: &str) -> Scene {
        scene::parse(&reroute(&fixture(name), moves).unwrap()).unwrap()
    }

    /// Points equal within 1e-9: the router is the same code, the only difference is float summation order in
    /// the Python anchors (`x + w * f`), which can differ in the last bit.
    fn same_points(a: &Connector, b: &Connector, what: &str) {
        assert_eq!(a.points.len(), b.points.len(), "{what}: {:?} vs {:?}", a.points, b.points);
        for (p, q) in a.points.iter().zip(&b.points) {
            assert!((p[0] - q[0]).abs() < 1e-9 && (p[1] - q[1]).abs() < 1e-9, "{what}: {:?} vs {:?}", a.points, b.points);
        }
    }

    /// Equal JSON where a number written `420` equals `420.0` (Python writes ints, the scene stores f64).
    fn same_json(a: &Value, b: &Value) -> bool {
        match (a, b) {
            (Value::Number(x), Value::Number(y)) => x.as_f64() == y.as_f64(),
            (Value::Array(x), Value::Array(y)) => x.len() == y.len() && x.iter().zip(y).all(|(p, q)| same_json(p, q)),
            (Value::Object(x), Value::Object(y)) => x.len() == y.len() && x.iter().all(|(k, v)| y.get(k).is_some_and(|w| same_json(v, w))),
            _ => a == b,
        }
    }

    #[test]
    fn an_empty_move_map_returns_an_equal_scene() {
        let input = fixture("decision");
        let out = reroute(&input, "{}").unwrap();
        let (a, b): (Value, Value) = (serde_json::from_str(&input).unwrap(), serde_json::from_str(&out).unwrap());
        assert!(same_json(&a, &b), "the scene changed");
    }

    #[test]
    fn touching_connectors_end_on_the_moved_boundary_and_others_do_not_change() {
        let before = scene::parse(&fixture("decision")).unwrap();
        let after = moved("decision", r#"{"std": [60, 40]}"#);
        let std = shape(&after, "std");
        assert_eq!((std.x, std.y), (960.0, 260.0));
        let on_boundary = |p: [f64; 2]| {
            let (x, y) = (p[0], p[1]);
            let inside_x = std.x - 1e-9 <= x && x <= std.x + std.w + 1e-9;
            let inside_y = std.y - 1e-9 <= y && y <= std.y + std.h + 1e-9;
            inside_x && inside_y && (x - std.x).abs() < 1e-9 || (x - std.x - std.w).abs() < 1e-9 && inside_y || inside_x && ((y - std.y).abs() < 1e-9 || (y - std.y - std.h).abs() < 1e-9)
        };
        for (old, new) in connectors(&before).into_iter().zip(connectors(&after)) {
            let touches = [&old.src, &old.dst].iter().any(|b| b.as_ref().is_some_and(|b| b.shape_id == "std"));
            if touches {
                let end = if old.dst.as_ref().is_some_and(|b| b.shape_id == "std") { new.points.last() } else { new.points.first() };
                assert!(on_boundary(*end.unwrap()), "{} should end on std: {:?}", new.id, new.points);
                assert_ne!(old.points, new.points, "{} did not move", new.id);
            } else {
                assert_eq!(serde_json::to_value(old).unwrap(), serde_json::to_value(new).unwrap(), "{} must not change", new.id);
            }
        }
    }

    #[test]
    fn straight_connectors_equal_the_python_render_of_the_moved_yaml() {
        for (moves, expected, touched) in [
            (r#"{"std": [60, 40]}"#, "decision_std", vec!["e1"]),
            (r#"{"known": [0, 30]}"#, "decision_known", vec!["e0", "e1", "e2"]),
        ] {
            let got = moved("decision", moves);
            let want = scene::parse(&fixture(expected)).unwrap();
            for (g, w) in connectors(&got).into_iter().zip(connectors(&want)) {
                assert_eq!(g.id, w.id);
                same_points(g, w, &format!("{expected} {}", g.id));
                if touched.contains(&g.id.as_str()) {
                    for (a, b) in [(&g.src, &w.src), (&g.dst, &w.dst)] {
                        let (a, b) = (a.as_ref().unwrap(), b.as_ref().unwrap());
                        assert_eq!((&a.shape_id, &a.side, a.target, a.explicit), (&b.shape_id, &b.side, b.target, b.explicit), "{expected} {}", g.id);
                    }
                }
            }
        }
    }

    #[test]
    fn the_diamond_keeps_its_midpoint_anchors() {
        // `known` is a diamond: moving it keeps the ends on side midpoints, whatever fraction the binding says
        let got = moved("decision", r#"{"known": [0, 30]}"#);
        let k = shape(&got, "known");
        let e0 = connectors(&got)[0].points.clone();
        assert_eq!(e0.last().unwrap(), &[k.x, k.y + k.h / 2.0]);
    }

    #[test]
    fn ortho_connectors_equal_the_python_render_of_the_moved_yaml() {
        for (moves, expected) in [(r#"{"b": [0, 200]}"#, "ortho_b"), (r#"{"a": [0, 200]}"#, "ortho_a")] {
            let got = moved("ortho", moves);
            let want = scene::parse(&fixture(expected)).unwrap();
            let (g, w) = (connectors(&got)[0], connectors(&want)[0]);
            same_points(g, w, expected);
            assert_eq!(g.src.as_ref().map(|b| b.side.as_str()), w.src.as_ref().map(|b| b.side.as_str()), "{expected} src side");
            assert_eq!(g.dst.as_ref().map(|b| b.side.as_str()), w.dst.as_ref().map(|b| b.side.as_str()), "{expected} dst side");
        }
    }

    #[test]
    fn the_connector_label_follows_the_edge() {
        let before = scene::parse(&fixture("ortho")).unwrap();
        let after = moved("ortho", r#"{"a": [0, 200]}"#);
        let (old, new) = (connectors(&before)[0], connectors(&after)[0]);
        let (Some(TaggedShape::Shape(l0)), Some(TaggedShape::Shape(l1))) = (&old.label, &new.label) else { panic!("the fixture edge has a label") };
        let (m0, m1) = (mid(old), mid(new));
        assert!((l1.x - l0.x - (m1.0 - m0.0)).abs() < 1e-9 && (l1.y - l0.y - (m1.1 - m0.1)).abs() < 1e-9);
        let (b0, b1) = (l0.label.as_ref().unwrap().bbox, l1.label.as_ref().unwrap().bbox);
        assert!((b1[0] - b0[0] - (l1.x - l0.x)).abs() < 1e-9 && (b1[1] - b0[1] - (l1.y - l0.y)).abs() < 1e-9);
    }

    #[test]
    fn a_shape_takes_its_label_and_icon_along() {
        let before = scene::parse(&fixture("decision")).unwrap();
        let after = moved("decision", r#"{"std": [60, 40]}"#);
        let (a, b) = (shape(&before, "std"), shape(&after, "std"));
        let (la, lb) = (a.label.as_ref().unwrap().bbox, b.label.as_ref().unwrap().bbox);
        assert_eq!([lb[0] - la[0], lb[1] - la[1], lb[2], lb[3]], [60.0, 40.0, la[2], la[3]]);
        // a full render of the moved YAML puts the label in the same place
        let want = scene::parse(&fixture("decision_std")).unwrap();
        let lw = shape(&want, "std").label.as_ref().unwrap().bbox;
        assert!(lb.iter().zip(lw).all(|(x, y)| (x - y).abs() < 1e-9), "{lb:?} vs {lw:?}");
    }

    #[test]
    fn symbol_paths_move_with_the_shape() {
        // `known` is a diamond with a path part: the moved path equals the Python path of the moved YAML
        let got = moved("decision", r#"{"known": [0, 30]}"#);
        let want = scene::parse(&fixture("decision_known")).unwrap();
        let (pg, pw) = (shape(&got, "known").parts.as_ref(), shape(&want, "known").parts.as_ref());
        assert_eq!(pg.map(|p| p.iter().map(|x| x.d.clone()).collect::<Vec<_>>()), pw.map(|p| p.iter().map(|x| x.d.clone()).collect::<Vec<_>>()));
    }

    #[test]
    fn a_new_box_sets_position_and_size() {
        let got = moved("decision", r#"{"std": [1000, 300, 200, 100]}"#);
        let s = shape(&got, "std");
        assert_eq!((s.x, s.y, s.w, s.h), (1000.0, 300.0, 200.0, 100.0));
        let e1 = connectors(&got)[1];
        assert_eq!(e1.points.last().unwrap(), &[1000.0, 350.0]);
    }

    #[test]
    fn invalid_moves_are_errors() {
        let s = fixture("decision");
        assert!(reroute(&s, r#"{"nope": [1, 2]}"#).unwrap_err().to_string().contains("unknown shape `nope`"));
        assert!(reroute(&s, r#"{"std": [1]}"#).unwrap_err().to_string().contains("[dx, dy]"));
        assert!(reroute(&s, r#"{"std": [1, 2, -3, 4]}"#).unwrap_err().to_string().contains("non-negative"));
        assert!(reroute(&s, "[1]").unwrap_err().to_string().contains("invalid moves"));
        assert!(reroute("{}", "{}").is_err());
    }

    /// Equal JSON up to 1e-9 on numbers (a zone moved by an offset against a render at the moved coordinates).
    fn close_json(a: &Value, b: &Value) -> bool {
        match (a, b) {
            (Value::Number(x), Value::Number(y)) => (x.as_f64().unwrap() - y.as_f64().unwrap()).abs() < 1e-9,
            (Value::Array(x), Value::Array(y)) => x.len() == y.len() && x.iter().zip(y).all(|(p, q)| close_json(p, q)),
            (Value::Object(x), Value::Object(y)) => x.len() == y.len() && x.iter().all(|(k, v)| y.get(k).is_some_and(|w| close_json(v, w))),
            _ => a == b,
        }
    }

    #[test]
    fn moving_a_zone_with_its_children_equals_a_render_of_the_moved_yaml() {
        // the zone and both children by (+60, +40): its label moves with it, and the edges follow
        let out = reroute(&fixture("zone"), r#"{"z0": [60, 40], "a": [60, 40], "b": [60, 40]}"#).unwrap();
        let (got, want): (Value, Value) = (serde_json::from_str(&out).unwrap(), serde_json::from_str(&fixture("zone_moved")).unwrap());
        let items = |v: &Value| v["items"].as_array().unwrap().clone();
        let (g, w) = (items(&got), items(&want));
        assert_eq!(g.len(), w.len());
        for (gi, wi) in g.iter().zip(&w) {
            assert!(close_json(gi, wi), "item {} differs:\n{gi}\n{wi}", wi["id"]);
        }
        // the label is its own text item and must have moved
        let label = |v: &[Value]| v.iter().find(|i| i["id"] == "z0-label").unwrap().clone();
        assert_ne!(label(&g)["x"], label(&items(&serde_json::from_str(&fixture("zone")).unwrap()))["x"]);
    }

    #[test]
    fn moving_only_the_zone_leaves_children_and_their_edges_alone() {
        let before = scene::parse(&fixture("zone")).unwrap();
        let after = moved("zone", r#"{"z0": [60, 40]}"#);
        assert_eq!((shape(&after, "z0").x, shape(&after, "z0").y), (shape(&before, "z0").x + 60.0, shape(&before, "z0").y + 40.0));
        for id in ["a", "b", "c"] {
            assert_eq!((shape(&after, id).x, shape(&after, id).y), (shape(&before, id).x, shape(&before, id).y), "{id}");
        }
        for (x, y) in connectors(&before).into_iter().zip(connectors(&after)) {
            assert_eq!(x.points, y.points, "nothing touching the zone's own shape moved a connector");
        }
    }
}
