//! Draw a scene's items as SVG fragments: a port of the drawing half of `spinagram/backends/svg.py`.
//!
//! Returns the layers (`defs`, `back`, `mid`, `front`) and the characters drawn per font face. Python builds
//! the document around them (font faces, head, metadata, hash), so subsetting stays in fontTools.

use crate::pyfmt::{attr, esc, f1, g, py_sum, repr_f64};
use crate::scene::{Cell, Connector, Font, Icon, Item, Label, Scene, Shape, Table, Text, TextBlock};
use base64::Engine;
use std::collections::{BTreeMap, BTreeSet, HashMap, HashSet};
use std::fmt::Write as _;
use std::sync::{Arc, Mutex, OnceLock};

const DASH: &str = " stroke-dasharray=\"10 7\"";

/// `(family, weight, italic)` -> characters drawn in that face
pub type Chars = BTreeMap<(String, u32, bool), BTreeSet<char>>;

#[derive(Debug, Default)]
pub struct Drawn {
    pub defs: String,
    pub back: String,
    pub mid: String,
    pub front: String,
    pub chars: Chars,
}

#[derive(Debug)]
pub enum DrawError {
    /// An image or icon file does not exist.
    NotFound(String),
    Io(String),
    Scene(String),
}

impl std::fmt::Display for DrawError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            DrawError::NotFound(p) => write!(f, "[Errno 2] No such file or directory: '{p}'"),
            DrawError::Io(m) | DrawError::Scene(m) => write!(f, "{m}"),
        }
    }
}

type Shadow = (f64, f64, f64, String, f64);

#[derive(Clone, Copy)]
enum Layer {
    Back,
    Mid,
    Front,
}

fn marker_body(kind: &str, c: &str) -> Option<String> {
    Some(match kind {
        "open-arrow" => format!("<path d=\"M1,1 L9,5 L1,9\" fill=\"none\" stroke=\"{c}\" stroke-width=\"1.5\"/>"),
        "diamond" => format!("<path d=\"M0,5 L5,0 L10,5 L5,10 z\" fill=\"{c}\"/>"),
        "open-diamond" => format!("<path d=\"M0,5 L5,0 L10,5 L5,10 z\" fill=\"#FFFFFF\" stroke=\"{c}\" stroke-width=\"1.2\"/>"),
        "circle" => format!("<circle cx=\"5\" cy=\"5\" r=\"4\" fill=\"{c}\"/>"),
        "bar" => format!("<path d=\"M8,0 L8,10\" stroke=\"{c}\" stroke-width=\"2\"/>"),
        _ => return None,
    })
}

fn files() -> &'static Mutex<HashMap<String, Arc<Vec<u8>>>> {
    static FILES: OnceLock<Mutex<HashMap<String, Arc<Vec<u8>>>>> = OnceLock::new();
    FILES.get_or_init(Mutex::default)
}

/// Make the bytes of an image or icon available under `path`, so a scene that names that path draws without a
/// file system. This is how the browser supplies icons; registered files win over files on disk.
///
/// # Panics
///
/// Only when another thread panicked while holding the registry lock.
pub fn register_file(path: &str, bytes: &[u8]) {
    files().lock().unwrap().insert(path.to_owned(), Arc::new(bytes.to_vec()));
}

fn read_file(path: &str) -> Result<Arc<Vec<u8>>, DrawError> {
    if let Some(b) = files().lock().unwrap().get(path) {
        return Ok(b.clone());
    }
    read_disk(path)
}

#[cfg(not(target_arch = "wasm32"))]
fn read_disk(path: &str) -> Result<Arc<Vec<u8>>, DrawError> {
    std::fs::read(path).map(Arc::new).map_err(|e| match e.kind() {
        std::io::ErrorKind::NotFound => DrawError::NotFound(path.to_string()),
        _ => DrawError::Io(format!("{path}: {e}")),
    })
}

/// There is no file system on wasm32: only registered files exist.
#[cfg(target_arch = "wasm32")]
fn read_disk(path: &str) -> Result<Arc<Vec<u8>>, DrawError> {
    Err(DrawError::NotFound(path.to_string()))
}

fn mime(path: &str) -> &'static str {
    let ext = std::path::Path::new(path).extension().and_then(|e| e.to_str()).unwrap_or("").to_lowercase();
    match ext.as_str() {
        "svg" => "image/svg+xml",
        "png" => "image/png",
        "jpg" | "jpeg" => "image/jpeg",
        "otf" => "font/otf",
        "ttf" => "font/ttf",
        "woff2" => "font/woff2",
        "woff" => "font/woff",
        _ => "application/octet-stream",
    }
}

/// Python's `str(None)` for an optional colour printed with an f-string.
fn opt(s: Option<&String>) -> &str {
    s.map_or("None", String::as_str)
}

fn truthy(s: Option<&String>) -> bool {
    s.is_some_and(|v| !v.is_empty())
}

fn dash(dashed: bool, pattern: Option<&[f64]>) -> String {
    match pattern {
        Some(p) if !p.is_empty() => {
            format!(" stroke-dasharray=\"{}\"", p.iter().map(|v| g(*v)).collect::<Vec<_>>().join(" "))
        }
        _ if dashed => DASH.to_string(),
        _ => String::new(),
    }
}

fn family(font: &Font) -> String {
    format!("&apos;{}&apos;, {}", attr(&font.family), attr(&font.fallback))
}

#[expect(clippy::cast_precision_loss, reason = "pixel, glyph and count arithmetic on small non-negative values that f64, i64 and usize hold exactly")]
fn block_height(b: &TextBlock) -> f64 {
    b.lines.len() as f64 * b.leading
}

fn baseline_offset(b: &TextBlock) -> f64 {
    (b.leading - b.font.size) / 2.0 + b.font.size * 0.8
}

struct Writer<'a> {
    scene: &'a Scene,
    chars: Chars,
    defs: Vec<String>,
    back: Vec<String>,
    mid: Vec<String>,
    front: Vec<String>,
    markers: HashSet<String>,
    filters: Vec<(Shadow, String)>,
    images: HashMap<String, String>,
    /// Python's `sum()` is compensated (3.12+) on the interpreter that sent the scene.
    compensated_sum: bool,
}

impl<'a> Writer<'a> {
    fn new(scene: &'a Scene, compensated_sum: bool) -> Self {
        Writer { scene, chars: Chars::new(), defs: vec![], back: vec![], mid: vec![], front: vec![], markers: HashSet::new(),
                 filters: vec![], images: HashMap::new(), compensated_sum }
    }

    fn layer(&mut self, l: Layer) -> &mut Vec<String> {
        match l {
            Layer::Back => &mut self.back,
            Layer::Mid => &mut self.mid,
            Layer::Front => &mut self.front,
        }
    }

    fn used(&mut self, font: &Font, text: &str) {
        self.chars.entry((font.family.clone(), font.weight, font.italic)).or_default().extend(text.chars());
    }

    fn text_lines(&mut self, out: Layer, block: &TextBlock, x: f64, baseline: f64, anchor: &str, letter_spacing: &str) {
        let f = &block.font;
        let runs = block.runs.as_ref().filter(|r| !r.is_empty());
        let mut spans = String::new();
        for (i, line) in block.lines.iter().enumerate() {
            let content = match runs {
                None => {
                    self.used(f, line);
                    if line.is_empty() {
                        self.used(f, "\u{a0}");
                        "&#160;".to_string()
                    } else {
                        esc(line)
                    }
                }
                Some(all) => {
                    let line_runs = all.get(i).map_or(&[][..], Vec::as_slice);
                    for r in line_runs {
                        self.used(&r.font, &r.text);
                    }
                    if line_runs.iter().all(|r| r.text.is_empty()) {
                        self.used(f, "\u{a0}");
                    }
                    let html: String = line_runs
                        .iter()
                        .map(|r| {
                            if r.base {
                                esc(&r.text)
                            } else {
                                format!("<tspan font-family=\"{}\">{}</tspan>", family(&r.font), esc(&r.text))
                            }
                        })
                        .collect();
                    if html.is_empty() { "&#160;".to_string() } else { html }
                }
            };
            let dy = if i == 0 { 0.0 } else { block.leading };
            let _ = write!(spans, "<tspan x=\"{}\" dy=\"{}\">{content}</tspan>", f1(x), f1(dy));
        }
        let ls = if letter_spacing.is_empty() { String::new() } else { format!(" letter-spacing=\"{letter_spacing}\"") };
        let style = if f.italic { " font-style=\"italic\"" } else { "" };
        let el = format!(
            "<text x=\"{}\" y=\"{}\" font-family=\"{}\" font-size=\"{}\" font-weight=\"{}\"{style} fill=\"{}\" text-anchor=\"{anchor}\"{ls}>{spans}</text>",
            f1(x), f1(baseline), family(f), g(f.size), f.weight, block.color);
        self.layer(out).push(el);
    }

    #[expect(clippy::cast_precision_loss, reason = "pixel, glyph and count arithmetic on small non-negative values that f64, i64 and usize hold exactly")]
    fn label(&mut self, out: Layer, label: &Label) {
        let anchor = if label.align == "center" { "middle" } else { "start" };
        let [x, y, w, h] = label.bbox;
        let heights: Vec<f64> = label.blocks.iter().map(block_height).collect();
        let total = py_sum(&heights, self.compensated_sum) + label.gap * label.blocks.len().saturating_sub(1) as f64;
        let mut top = if label.valign == "middle" { y + (h - total) / 2.0 } else { y };
        for (b, height) in label.blocks.iter().zip(heights) {
            let bx = if label.align == "center" { x + w / 2.0 } else { x };
            self.text_lines(out, b, bx, top + baseline_offset(b), anchor, "");
            top += height + label.gap;
        }
    }

    fn b64(&mut self, path: &str) -> Result<String, DrawError> {
        if let Some(s) = self.images.get(path) {
            return Ok(s.clone());
        }
        let bytes = read_file(path)?;
        let s = base64::engine::general_purpose::STANDARD.encode(&*bytes);
        self.images.insert(path.to_string(), s.clone());
        Ok(s)
    }

    fn image(&mut self, out: Layer, path: &str, x: f64, y: f64, w: f64, h: f64) -> Result<(), DrawError> {
        let data = self.b64(path)?;
        let el = format!("<image x=\"{}\" y=\"{}\" width=\"{}\" height=\"{}\" href=\"data:{};base64,{data}\"/>",
                         f1(x), f1(y), g(w), g(h), mime(path));
        self.layer(out).push(el);
        Ok(())
    }

    fn icon(&mut self, out: Layer, icon: &Icon) -> Result<(), DrawError> {
        self.image(out, &icon.path, icon.x, icon.y, icon.w.unwrap_or(icon.size), icon.size)
    }

    fn shadow(&mut self, sh: Option<&Shadow>) -> String {
        let Some(sh) = sh else { return String::new() };
        let id = if let Some((_, id)) = self.filters.iter().find(|(k, _)| k == sh) { id.clone() } else {
            let id = format!("sh{}", self.filters.len());
            let (dx, dy, blur, color, alpha) = sh;
            self.defs.push(format!(
                "<filter id=\"{id}\" x=\"-20%\" y=\"-20%\" width=\"140%\" height=\"140%\"><feDropShadow dx=\"{}\" dy=\"{}\" stdDeviation=\"{}\" flood-color=\"{color}\" flood-opacity=\"{}\"/></filter>",
                g(*dx), g(*dy), g(blur / 2.0), g(*alpha)));
            self.filters.push((sh.clone(), id.clone()));
            id
        };
        format!(" filter=\"url(#{id})\"")
    }

    fn marker(&mut self, color: &str, kind: &str) -> String {
        let bare = color.trim_matches('#');
        if kind != "arrow" {
            if let Some(body) = marker_body(kind, color) {
                let id = format!("m{kind}-{bare}");
                if self.markers.insert(id.clone()) {
                    self.defs.push(format!("<marker id=\"{id}\" viewBox=\"0 0 10 10\" refX=\"5\" refY=\"5\" markerWidth=\"8\" markerHeight=\"8\" orient=\"auto-start-reverse\">{body}</marker>"));
                }
                return id;
            }
        }
        let id = format!("m{bare}");
        if self.markers.insert(id.clone()) {
            self.defs.push(format!("<marker id=\"{id}\" viewBox=\"0 0 10 10\" refX=\"9\" refY=\"5\" markerWidth=\"7\" markerHeight=\"7\" orient=\"auto-start-reverse\"><path d=\"M0,0 L10,5 L0,10 z\" fill=\"{color}\"/></marker>"));
        }
        id
    }

    fn tip(&self, item_id: &str) -> String {
        let ids = match self.scene.item_facts.get(item_id) {
            Some(ids) if !ids.is_empty() => ids,
            _ => return String::new(),
        };
        let text = ids.iter().map(|i| self.scene.meta_tooltips.get(i).unwrap_or(i).as_str()).collect::<Vec<_>>().join("\n\n");
        format!("<title>{}</title>", esc(&text))
    }

    fn with_tip(el: String, tag: &str, tip: &str) -> String {
        if !tip.is_empty() && el.ends_with("/>") {
            format!("{}>{tip}</{tag}>", &el[..el.len() - 2])
        } else {
            el
        }
    }

    fn shape(&mut self, s: &Shape) -> Result<(), DrawError> {
        let layer = match s.role.as_str() {
            "zone" | "chrome" => Layer::Back,
            "pill" | "swatch" => Layer::Front,
            _ => Layer::Mid,
        };
        let stroke = if truthy(s.stroke.as_ref()) && s.stroke_width != 0.0 {
            format!(" stroke=\"{}\" stroke-width=\"{}\"", opt(s.stroke.as_ref()), g(s.stroke_width))
        } else {
            String::new()
        };
        let cap = match &s.cap {
            Some(c) if !c.is_empty() && truthy(s.stroke.as_ref()) => format!(" stroke-linecap=\"{c}\""),
            _ => String::new(),
        };
        let dash = dash(s.dashed, s.dash.as_deref()) + &cap;
        let mut op = if s.opacity < 1.0 { format!(" opacity=\"{}\"", g(s.opacity)) } else { String::new() };
        op += &self.shadow(s.shadow.as_ref());
        let fill = if truthy(s.fill.as_ref()) { opt(s.fill.as_ref()) } else { "none" };
        let fop = if s.fill_opacity < 1.0 && truthy(s.fill.as_ref()) { format!(" fill-opacity=\"{}\"", g(s.fill_opacity)) } else { String::new() };
        let tip = self.tip(&s.id);
        match s.parts.as_ref().filter(|p| !p.is_empty()) {
            Some(parts) => {
                for (i, part) in parts.iter().enumerate() {
                    let paint = match part.paint.as_str() {
                        "solid" => format!("fill=\"{}\"", if truthy(s.stroke.as_ref()) { opt(s.stroke.as_ref()) } else { fill }),
                        "stroke" => format!("fill=\"none\" stroke=\"{}\" stroke-width=\"{}\"", opt(s.stroke.as_ref()), g(s.stroke_width)),
                        _ => format!("fill=\"{fill}\"{fop}{stroke}"),
                    };
                    let el = format!("<path d=\"{}\" {paint}{dash}{op}/>", part.d);
                    let el = if i == 0 { Self::with_tip(el, "path", &tip) } else { el };
                    self.layer(layer).push(el);
                }
            }
            None if s.kind == "diamond" => {
                let (cx, cy) = (s.x + s.w / 2.0, s.y + s.h / 2.0);
                let pts = format!("{},{} {},{} {},{} {},{}", f1(cx), f1(s.y), f1(s.x + s.w), f1(cy), f1(cx), f1(s.y + s.h), f1(s.x), f1(cy));
                let el = format!("<polygon points=\"{pts}\" fill=\"{fill}\"{fop}{stroke}{dash}{op}/>");
                self.layer(layer).push(Self::with_tip(el, "polygon", &tip));
            }
            None => {
                let el = format!("<rect x=\"{}\" y=\"{}\" width=\"{}\" height=\"{}\" rx=\"{}\" fill=\"{fill}\"{fop}{stroke}{dash}{op}/>",
                                 f1(s.x), f1(s.y), f1(s.w), f1(s.h), g(s.radius));
                self.layer(layer).push(Self::with_tip(el, "rect", &tip));
            }
        }
        let text_layer = if s.role == "zone" { Layer::Back } else { Layer::Front };
        if let Some(icon) = &s.icon {
            self.icon(Layer::Front, icon)?;
        }
        if let Some(label) = &s.label {
            self.label(text_layer, label);
        }
        Ok(())
    }

    fn connector(&mut self, c: &Connector) -> Result<(), DrawError> {
        let d = if c.route == "curve" {
            let [p1, p2, p3] = c.points[..] else {
                return Err(DrawError::Scene(format!("connector {}: a curve needs 3 points", c.id)));
            };
            format!("M{},{} Q{},{} {},{}", f1(p1[0]), f1(p1[1]), f1(p2[0]), f1(p2[1]), f1(p3[0]), f1(p3[1]))
        } else {
            let pts: Vec<String> = c.points.iter().map(|p| format!("{},{}", f1(p[0]), f1(p[1]))).collect();
            format!("M{}", pts.join(" L"))
        };
        let mut ends = String::new();
        if c.arrow_end {
            let _ = write!(ends, " marker-end=\"url(#{})\"", self.marker(&c.color, &c.marker_end));
        }
        if c.arrow_start {
            let _ = write!(ends, " marker-start=\"url(#{})\"", self.marker(&c.color, &c.marker_start));
        }
        let op = if c.opacity < 1.0 { format!(" opacity=\"{}\"", g(c.opacity)) } else { String::new() };
        self.mid.push(format!("<path d=\"{d}\" fill=\"none\" stroke=\"{}\" stroke-width=\"{}\"{}{op}{ends}/>",
                              c.color, g(c.width), dash(c.dashed, c.dash.as_deref())));
        if let Some(crate::scene::TaggedShape::Shape(label)) = &c.label {
            self.shape(label)?;
        }
        Ok(())
    }

    fn table(&mut self, t: &Table) -> Result<(), DrawError> {
        let x0 = t.x;
        let total = py_sum(&t.col_widths, self.compensated_sum);
        let mut y = t.y;
        for (r, (rh, row)) in t.row_heights.iter().zip(&t.cells).enumerate() {
            let fill = row.first().map_or("none", |c| opt(c.fill.as_ref()));
            if r == 0 {
                self.mid.push(format!("<rect x=\"{}\" y=\"{}\" width=\"{}\" height=\"{}\" rx=\"{}\" fill=\"{fill}\"/>",
                                      f1(x0), f1(y), f1(total), f1(*rh), g(t.header_radius)));
            } else {
                self.mid.push(format!("<rect x=\"{}\" y=\"{}\" width=\"{}\" height=\"{}\" fill=\"{fill}\"/>",
                                      f1(x0), f1(y), f1(total), f1(*rh)));
                self.mid.push(format!("<line x1=\"{}\" y1=\"{}\" x2=\"{}\" y2=\"{}\" stroke=\"{}\" stroke-width=\"1\"/>",
                                      f1(x0), f1(y + rh), f1(x0 + total), f1(y + rh), t.border));
            }
            let mut cx = x0;
            for (wcol, cell) in t.col_widths.iter().zip(row) {
                self.cell(cell, cx, y, *rh)?;
                cx += wcol;
            }
            y += rh;
        }
        let tip = self.tip(&t.id);
        if !tip.is_empty() {
            self.front.push(format!("<rect x=\"{}\" y=\"{}\" width=\"{}\" height=\"{}\" fill=\"none\" pointer-events=\"all\">{tip}</rect>",
                                    f1(t.x), f1(t.y), f1(total), f1(py_sum(&t.row_heights, self.compensated_sum))));
        }
        Ok(())
    }

    fn cell(&mut self, cell: &Cell, x: f64, y: f64, h: f64) -> Result<(), DrawError> {
        if let Some(icon) = &cell.icon {
            self.image(Layer::Front, &icon.path, x + 14.0, y + (h - icon.size) / 2.0, icon.size, icon.size)?;
        }
        let b = &cell.block;
        let top = y + (h - block_height(b)) / 2.0;
        self.text_lines(Layer::Front, b, x + cell.pad_left, top + baseline_offset(b), "start", "");
        Ok(())
    }

    fn text_item(&mut self, it: &Text) {
        let layer = if it.id.starts_with('z') { Layer::Back } else { Layer::Front };
        let ls = match it.letter_spacing.as_f64() {
            Some(v) if v != 0.0 => match it.letter_spacing.as_i64() {
                Some(i) => i.to_string(),
                None => repr_f64(v),
            },
            _ => String::new(),
        };
        self.text_lines(layer, &it.block, it.x, it.y, &it.anchor, &ls);
        let tip = self.tip(&it.id);
        if !tip.is_empty() {
            if let Some(last) = self.layer(layer).last_mut() {
                *last = last.replacen("</text>", &format!("{tip}</text>"), 1);
            }
        }
    }

    fn draw(mut self) -> Result<Drawn, DrawError> {
        let scene = self.scene;
        for it in &scene.items {
            match it {
                Item::Shape(s) => self.shape(s)?,
                Item::Connector(c) => self.connector(c)?,
                Item::Text(t) => self.text_item(t),
                Item::Line(l) => self.front.push(format!(
                    "<line x1=\"{}\" y1=\"{}\" x2=\"{}\" y2=\"{}\" stroke=\"{}\" stroke-width=\"{}\"/>",
                    f1(l.x1), f1(l.y1), f1(l.x2), f1(l.y2), l.color, g(l.width))),
                Item::Image(i) => self.image(Layer::Front, &i.path, i.x, i.y, i.w, i.h)?,
                Item::Table(t) => self.table(t)?,
            }
        }
        Ok(Drawn { defs: self.defs.concat(), back: self.back.concat(), mid: self.mid.concat(), front: self.front.concat(),
                   chars: self.chars })
    }
}

/// Draw every item of the scene. `compensated_sum`: whether the Python that sends the scene has the compensated
/// `sum()` of 3.12+ (block and table totals are `sum()` calls there).
///
/// # Errors
///
/// When an image or icon file is missing or unreadable, or a curve does not have three points.
pub fn draw(scene: &Scene, compensated_sum: bool) -> Result<Drawn, DrawError> {
    Writer::new(scene, compensated_sum).draw()
}

fn collect_block<'a>(b: &'a TextBlock, seen: &mut Vec<&'a Font>) {
    let runs = b.runs.iter().flatten().flatten().map(|r| &r.font);
    for f in std::iter::once(&b.font).chain(runs) {
        if !seen.iter().any(|o| (&o.family, o.weight, o.italic) == (&f.family, f.weight, f.italic)) {
            seen.push(f);
        }
    }
}

/// Distinct fonts of a scene, in the order `Scene.fonts()` finds them (labels, texts, connector labels, tables).
#[must_use]
pub fn scene_fonts(scene: &Scene) -> Vec<&Font> {
    let mut seen: Vec<&Font> = Vec::new();
    for it in &scene.items {
        match it {
            Item::Shape(s) => s.label.iter().flat_map(|l| &l.blocks).for_each(|b| collect_block(b, &mut seen)),
            Item::Text(t) => collect_block(&t.block, &mut seen),
            Item::Connector(c) => {
                if let Some(crate::scene::TaggedShape::Shape(s)) = &c.label {
                    s.label.iter().flat_map(|l| &l.blocks).for_each(|b| collect_block(b, &mut seen));
                }
            }
            Item::Table(t) => t.cells.iter().flatten().for_each(|c| collect_block(&c.block, &mut seen)),
            _ => {}
        }
    }
    seen
}

/// A standalone SVG document around the drawn layers, for the browser: faces are `@font-face` rules that
/// load `{font_base}{file name}` (no embedded subsets), and the sources metadata and content hash are left
/// out. The layers (`back`, `mid`, `front`) are byte-identical to the server's.
#[must_use]
pub fn document(scene: &Scene, drawn: &Drawn, font_base: &str) -> String {
    let faces: String = scene_fonts(scene)
        .iter()
        .filter_map(|f| {
            let file = f.file.as_deref()?;
            let name = std::path::Path::new(file).file_name()?.to_str()?;
            Some(format!(
                "@font-face{{font-family:'{}';src:url({font_base}{name});font-weight:{};font-style:{}}}",
                f.family, f.weight, if f.italic { "italic" } else { "normal" }))
        })
        .collect();
    let (w, h) = (g(scene.width), g(scene.height));
    format!(
        "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 {w} {h}\" width=\"{w}\" height=\"{h}\"><title>{}</title><defs><style>{}</style>{}</defs><rect width=\"{w}\" height=\"{h}\" fill=\"{}\"/>{}{}{}</svg>",
        esc(&scene.title), esc(&faces), drawn.defs, scene.background, drawn.back, drawn.mid, drawn.front)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::scene;

    const ROOT: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/../..");

    fn drawn(json: &str) -> Drawn {
        draw(&scene::parse(&json.replace("@ROOT@", ROOT)).unwrap(), true).unwrap()
    }

    fn chars(d: &Drawn) -> String {
        d.chars
            .iter()
            .map(|((fam, w, it), cs)| format!("{fam}|{w}|{it}={}", cs.iter().collect::<String>()))
            .collect::<Vec<_>>()
            .join("; ")
    }

    // The expected layers below come from running the Python writer (`_Svg(scene)._draw()`) on the same scenes.

    #[test]
    fn shape_rect_label_icon() {
        let d = drawn(r##"{"version": 1, "id": "S", "title": "T", "slug": "s", "width": 400, "height": 300, "background": "#fff", "items": [{"type": "shape", "id": "a", "kind": "rect", "x": 10, "y": 20.25, "w": 200, "h": 80, "fill": "#fafafa", "stroke": "#111111", "stroke_width": 2, "radius": 8, "dashed": false, "opacity": 1.0, "label": {"blocks": [{"lines": ["Title", "second line"], "paragraphs": ["Title", "second line"], "font": {"family": "Inter", "weight": 700, "italic": true, "size": 13.5, "file": "/fonts/Inter-Bold.ttf", "fallback": "Helvetica, sans-serif", "figma_style": "Regular"}, "color": "#333", "leading": 19.6, "runs": null}, {"lines": ["body", ""], "paragraphs": ["body", ""], "font": {"family": "Inter", "weight": 400, "italic": false, "size": 14, "file": null, "fallback": "sans-serif", "figma_style": "Regular"}, "color": "#333", "leading": 19.6, "runs": null}], "box": [20, 30, 160, 70], "align": "center", "gap": 10, "valign": "middle"}, "icon": {"path": "@ROOT@/examples/icons/acme.svg", "x": 16, "y": 28, "size": 24, "w": null}, "role": "node", "parts": null, "dash": null, "shadow": null, "fill_opacity": 1.0, "cap": null}], "item_facts": {}, "sources": [], "meta_tooltips": {}}"##);
        assert_eq!(d.defs, r"");
        assert_eq!(d.back, r"");
        assert_eq!(d.mid, r##"<rect x="10.0" y="20.2" width="200.0" height="80.0" rx="8" fill="#fafafa" stroke="#111111" stroke-width="2"/>"##);
        assert_eq!(d.front, r##"<image x="16.0" y="28.0" width="24" height="24" href="data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxMjggMTI4IiB3aWR0aD0iMTI4IiBoZWlnaHQ9IjEyOCI+CiAgPHRpdGxlPnNwaW5hZ3JhbTwvdGl0bGU+CiAgPGRlZnM+CiAgICA8bWFya2VyIGlkPSJhIiB2aWV3Qm94PSIwIDAgMTAgMTAiIHJlZlg9IjYiIHJlZlk9IjUiIG1hcmtlcldpZHRoPSI0IiBtYXJrZXJIZWlnaHQ9IjQiIG9yaWVudD0iYXV0by1zdGFydC1yZXZlcnNlIj4KICAgICAgPHBhdGggZD0iTTAgMCAxMCA1IDAgMTB6IiBmaWxsPSIjOTNDNUZEIi8+CiAgICA8L21hcmtlcj4KICA8L2RlZnM+CiAgPHJlY3Qgd2lkdGg9IjEyOCIgaGVpZ2h0PSIxMjgiIHJ4PSIyOCIgZmlsbD0iIzI1NjNFQiIvPgogIDxnIGZpbGw9Im5vbmUiIHN0cm9rZT0iIzkzQzVGRCIgc3Ryb2tlLXdpZHRoPSI2IiBzdHJva2UtbGluZWNhcD0icm91bmQiIG1hcmtlci1lbmQ9InVybCgjYSkiPgogICAgPHBhdGggZD0iTTc2LjcgMzIuNUEzNCAzNCAwIDAgMSA5Ny43IDY4LjciLz4KICAgIDxwYXRoIGQ9Ik04NC45IDkwLjhBMzQgMzQgMCAwIDEgNDMuMSA5MC44Ii8+CiAgICA8cGF0aCBkPSJNMzAuMyA2OC43QTM0IDM0IDAgMCAxIDUxLjMgMzIuNSIvPgogIDwvZz4KICA8ZyBmaWxsPSIjRkZGRkZGIj4KICAgIDxyZWN0IHg9IjUwIiB5PSIyMCIgd2lkdGg9IjI4IiBoZWlnaHQ9IjIwIiByeD0iNiIvPgogICAgPHJlY3QgeD0iNzkuNCIgeT0iNzEiIHdpZHRoPSIyOCIgaGVpZ2h0PSIyMCIgcng9IjYiLz4KICAgIDxyZWN0IHg9IjIwLjYiIHk9IjcxIiB3aWR0aD0iMjgiIGhlaWdodD0iMjAiIHJ4PSI2Ii8+CiAgPC9nPgo8L3N2Zz4K"/><text x="100.0" y="34.6" font-family="&apos;Inter&apos;, Helvetica, sans-serif" font-size="13.5" font-weight="700" font-style="italic" fill="#333" text-anchor="middle"><tspan x="100.0" dy="0.0">Title</tspan><tspan x="100.0" dy="19.6">second line</tspan></text><text x="100.0" y="84.0" font-family="&apos;Inter&apos;, sans-serif" font-size="14" font-weight="400" fill="#333" text-anchor="middle"><tspan x="100.0" dy="0.0">body</tspan><tspan x="100.0" dy="19.6">&#160;</tspan></text>"##);
        assert_eq!(chars(&d), r"Inter|400|false=bdoy ; Inter|700|true= Tcdeilnost");
    }

    #[test]
    fn shape_rect_left_top_valign_dash_cap_opacity() {
        let d = drawn(r##"{"version": 1, "id": "S", "title": "T", "slug": "s", "width": 400, "height": 300, "background": "#fff", "items": [{"type": "shape", "id": "a", "kind": "rect", "x": 10, "y": 20, "w": 200, "h": 80, "fill": "#fafafa", "stroke": "#111", "stroke_width": 1.5, "radius": 0, "dashed": true, "opacity": 0.5, "label": {"blocks": [{"lines": ["x"], "paragraphs": ["x"], "font": {"family": "Inter", "weight": 400, "italic": false, "size": 14, "file": null, "fallback": "sans-serif", "figma_style": "Regular"}, "color": "#333", "leading": 19.6, "runs": null}], "box": [20, 30, 160, 70], "align": "left", "gap": 10, "valign": "top"}, "icon": null, "role": "node", "parts": null, "dash": [4, 2.5], "shadow": null, "fill_opacity": 0.4, "cap": "round"}], "item_facts": {}, "sources": [], "meta_tooltips": {}}"##);
        assert_eq!(d.defs, r"");
        assert_eq!(d.back, r"");
        assert_eq!(d.mid, r##"<rect x="10.0" y="20.0" width="200.0" height="80.0" rx="0" fill="#fafafa" fill-opacity="0.4" stroke="#111" stroke-width="1.5" stroke-dasharray="4 2.5" stroke-linecap="round" opacity="0.5"/>"##);
        assert_eq!(d.front, r##"<text x="20.0" y="44.0" font-family="&apos;Inter&apos;, sans-serif" font-size="14" font-weight="400" fill="#333" text-anchor="start"><tspan x="20.0" dy="0.0">x</tspan></text>"##);
        assert_eq!(chars(&d), r"Inter|400|false=x");
    }

    #[test]
    fn shape_diamond_with_tip() {
        let d = drawn(r##"{"version": 1, "id": "S", "title": "T", "slug": "s", "width": 400, "height": 300, "background": "#fff", "items": [{"type": "shape", "id": "d", "kind": "diamond", "x": 10, "y": 20, "w": 100, "h": 60, "fill": null, "stroke": "#000", "stroke_width": 1, "radius": 0, "dashed": false, "opacity": 1.0, "label": null, "icon": null, "role": "node", "parts": null, "dash": null, "shadow": null, "fill_opacity": 1.0, "cap": null}], "item_facts": {"d": ["f1", "f2"]}, "sources": [], "meta_tooltips": {"f1": "one <&> two", "f2": "second"}}"##);
        assert_eq!(d.defs, r"");
        assert_eq!(d.back, r"");
        assert_eq!(d.mid, r##"<polygon points="60.0,20.0 110.0,50.0 60.0,80.0 10.0,50.0" fill="none" stroke="#000" stroke-width="1"><title>one &lt;&amp;&gt; two

second</title></polygon>"##);
        assert_eq!(d.front, r"");
        assert_eq!(chars(&d), r"");
    }

    #[test]
    fn shape_roles_layers() {
        let d = drawn(r##"{"version": 1, "id": "S", "title": "T", "slug": "s", "width": 400, "height": 300, "background": "#fff", "items": [{"type": "shape", "id": "r-node", "kind": "rect", "x": 1, "y": 2, "w": 30, "h": 40, "fill": "#eee", "stroke": null, "stroke_width": 0, "radius": 0, "dashed": false, "opacity": 1.0, "label": {"blocks": [{"lines": ["node"], "paragraphs": ["node"], "font": {"family": "Inter", "weight": 400, "italic": false, "size": 14, "file": null, "fallback": "sans-serif", "figma_style": "Regular"}, "color": "#333", "leading": 19.6, "runs": null}], "box": [20, 30, 160, 70], "align": "left", "gap": 10, "valign": "middle"}, "icon": null, "role": "node", "parts": null, "dash": null, "shadow": null, "fill_opacity": 1.0, "cap": null}, {"type": "shape", "id": "r-zone", "kind": "rect", "x": 1, "y": 2, "w": 30, "h": 40, "fill": "#eee", "stroke": null, "stroke_width": 0, "radius": 0, "dashed": false, "opacity": 1.0, "label": {"blocks": [{"lines": ["zone"], "paragraphs": ["zone"], "font": {"family": "Inter", "weight": 400, "italic": false, "size": 14, "file": null, "fallback": "sans-serif", "figma_style": "Regular"}, "color": "#333", "leading": 19.6, "runs": null}], "box": [20, 30, 160, 70], "align": "left", "gap": 10, "valign": "middle"}, "icon": null, "role": "zone", "parts": null, "dash": null, "shadow": null, "fill_opacity": 1.0, "cap": null}, {"type": "shape", "id": "r-pill", "kind": "rect", "x": 1, "y": 2, "w": 30, "h": 40, "fill": "#eee", "stroke": null, "stroke_width": 0, "radius": 0, "dashed": false, "opacity": 1.0, "label": {"blocks": [{"lines": ["pill"], "paragraphs": ["pill"], "font": {"family": "Inter", "weight": 400, "italic": false, "size": 14, "file": null, "fallback": "sans-serif", "figma_style": "Regular"}, "color": "#333", "leading": 19.6, "runs": null}], "box": [20, 30, 160, 70], "align": "left", "gap": 10, "valign": "middle"}, "icon": null, "role": "pill", "parts": null, "dash": null, "shadow": null, "fill_opacity": 1.0, "cap": null}, {"type": "shape", "id": "r-swatch", "kind": "rect", "x": 1, "y": 2, "w": 30, "h": 40, "fill": "#eee", "stroke": null, "stroke_width": 0, "radius": 0, "dashed": false, "opacity": 1.0, "label": {"blocks": [{"lines": ["swatch"], "paragraphs": ["swatch"], "font": {"family": "Inter", "weight": 400, "italic": false, "size": 14, "file": null, "fallback": "sans-serif", "figma_style": "Regular"}, "color": "#333", "leading": 19.6, "runs": null}], "box": [20, 30, 160, 70], "align": "left", "gap": 10, "valign": "middle"}, "icon": null, "role": "swatch", "parts": null, "dash": null, "shadow": null, "fill_opacity": 1.0, "cap": null}, {"type": "shape", "id": "r-chrome", "kind": "rect", "x": 1, "y": 2, "w": 30, "h": 40, "fill": "#eee", "stroke": null, "stroke_width": 0, "radius": 0, "dashed": false, "opacity": 1.0, "label": {"blocks": [{"lines": ["chrome"], "paragraphs": ["chrome"], "font": {"family": "Inter", "weight": 400, "italic": false, "size": 14, "file": null, "fallback": "sans-serif", "figma_style": "Regular"}, "color": "#333", "leading": 19.6, "runs": null}], "box": [20, 30, 160, 70], "align": "left", "gap": 10, "valign": "middle"}, "icon": null, "role": "chrome", "parts": null, "dash": null, "shadow": null, "fill_opacity": 1.0, "cap": null}], "item_facts": {}, "sources": [], "meta_tooltips": {}}"##);
        assert_eq!(d.defs, r"");
        assert_eq!(d.back, r##"<rect x="1.0" y="2.0" width="30.0" height="40.0" rx="0" fill="#eee"/><text x="20.0" y="69.2" font-family="&apos;Inter&apos;, sans-serif" font-size="14" font-weight="400" fill="#333" text-anchor="start"><tspan x="20.0" dy="0.0">zone</tspan></text><rect x="1.0" y="2.0" width="30.0" height="40.0" rx="0" fill="#eee"/>"##);
        assert_eq!(d.mid, r##"<rect x="1.0" y="2.0" width="30.0" height="40.0" rx="0" fill="#eee"/>"##);
        assert_eq!(d.front, r##"<text x="20.0" y="69.2" font-family="&apos;Inter&apos;, sans-serif" font-size="14" font-weight="400" fill="#333" text-anchor="start"><tspan x="20.0" dy="0.0">node</tspan></text><rect x="1.0" y="2.0" width="30.0" height="40.0" rx="0" fill="#eee"/><text x="20.0" y="69.2" font-family="&apos;Inter&apos;, sans-serif" font-size="14" font-weight="400" fill="#333" text-anchor="start"><tspan x="20.0" dy="0.0">pill</tspan></text><rect x="1.0" y="2.0" width="30.0" height="40.0" rx="0" fill="#eee"/><text x="20.0" y="69.2" font-family="&apos;Inter&apos;, sans-serif" font-size="14" font-weight="400" fill="#333" text-anchor="start"><tspan x="20.0" dy="0.0">swatch</tspan></text><text x="20.0" y="69.2" font-family="&apos;Inter&apos;, sans-serif" font-size="14" font-weight="400" fill="#333" text-anchor="start"><tspan x="20.0" dy="0.0">chrome</tspan></text>"##);
        assert_eq!(chars(&d), r"Inter|400|false=acdehilmnoprstwz");
    }

    #[test]
    fn shape_parts_paints() {
        let d = drawn(r##"{"version": 1, "id": "S", "title": "T", "slug": "s", "width": 400, "height": 300, "background": "#fff", "items": [{"type": "shape", "id": "p", "kind": "rect", "x": 0, "y": 0, "w": 50, "h": 50, "fill": "#abc", "stroke": "#123456", "stroke_width": 2, "radius": 0, "dashed": false, "opacity": 1.0, "label": null, "icon": null, "role": "node", "parts": [{"d": "M 0 0 L 10 10 Z", "paint": "shape"}, {"d": "M 1 1 L 2 2 Z", "paint": "solid"}, {"d": "M 3 3 Z", "paint": "stroke"}], "dash": null, "shadow": null, "fill_opacity": 1.0, "cap": null}], "item_facts": {"p": ["f"]}, "sources": [], "meta_tooltips": {"f": "tip"}}"##);
        assert_eq!(d.defs, r"");
        assert_eq!(d.back, r"");
        assert_eq!(d.mid, r##"<path d="M 0 0 L 10 10 Z" fill="#abc" stroke="#123456" stroke-width="2"><title>tip</title></path><path d="M 1 1 L 2 2 Z" fill="#123456"/><path d="M 3 3 Z" fill="none" stroke="#123456" stroke-width="2"/>"##);
        assert_eq!(d.front, r"");
        assert_eq!(chars(&d), r"");
    }

    #[test]
    fn shape_parts_no_stroke() {
        let d = drawn(r##"{"version": 1, "id": "S", "title": "T", "slug": "s", "width": 400, "height": 300, "background": "#fff", "items": [{"type": "shape", "id": "p", "kind": "rect", "x": 0, "y": 0, "w": 50, "h": 50, "fill": "#abc", "stroke": null, "stroke_width": 0, "radius": 0, "dashed": false, "opacity": 1.0, "label": null, "icon": null, "role": "node", "parts": [{"d": "M 0 0 Z", "paint": "solid"}, {"d": "M 3 3 Z", "paint": "stroke"}], "dash": null, "shadow": null, "fill_opacity": 0.5, "cap": null}], "item_facts": {}, "sources": [], "meta_tooltips": {}}"##);
        assert_eq!(d.defs, r"");
        assert_eq!(d.back, r"");
        assert_eq!(d.mid, r##"<path d="M 0 0 Z" fill="#abc"/><path d="M 3 3 Z" fill="none" stroke="None" stroke-width="0"/>"##);
        assert_eq!(d.front, r"");
        assert_eq!(chars(&d), r"");
    }

    #[test]
    fn shape_shadows_dedupe() {
        let d = drawn(r##"{"version": 1, "id": "S", "title": "T", "slug": "s", "width": 400, "height": 300, "background": "#fff", "items": [{"type": "shape", "id": "a", "kind": "rect", "x": 0, "y": 0, "w": 50, "h": 50, "fill": "#fff", "stroke": null, "stroke_width": 0, "radius": 0, "dashed": false, "opacity": 1.0, "label": null, "icon": null, "role": "node", "parts": null, "dash": null, "shadow": [2, 4, 10, "#00000033", 0.25], "fill_opacity": 1.0, "cap": null}, {"type": "shape", "id": "b", "kind": "rect", "x": 60, "y": 0, "w": 50, "h": 50, "fill": "#fff", "stroke": null, "stroke_width": 0, "radius": 0, "dashed": false, "opacity": 1.0, "label": null, "icon": null, "role": "node", "parts": null, "dash": null, "shadow": [2, 4, 10, "#00000033", 0.25], "fill_opacity": 1.0, "cap": null}, {"type": "shape", "id": "c", "kind": "rect", "x": 120, "y": 0, "w": 50, "h": 50, "fill": "#fff", "stroke": null, "stroke_width": 0, "radius": 0, "dashed": false, "opacity": 0.9, "label": null, "icon": null, "role": "node", "parts": null, "dash": null, "shadow": [0, 1, 3, "#000", 0.5], "fill_opacity": 1.0, "cap": null}], "item_facts": {}, "sources": [], "meta_tooltips": {}}"##);
        assert_eq!(d.defs, r##"<filter id="sh0" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="2" dy="4" stdDeviation="5" flood-color="#00000033" flood-opacity="0.25"/></filter><filter id="sh1" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="1" stdDeviation="1.5" flood-color="#000" flood-opacity="0.5"/></filter>"##);
        assert_eq!(d.back, r"");
        assert_eq!(d.mid, r##"<rect x="0.0" y="0.0" width="50.0" height="50.0" rx="0" fill="#fff" filter="url(#sh0)"/><rect x="60.0" y="0.0" width="50.0" height="50.0" rx="0" fill="#fff" filter="url(#sh0)"/><rect x="120.0" y="0.0" width="50.0" height="50.0" rx="0" fill="#fff" opacity="0.9" filter="url(#sh1)"/>"##);
        assert_eq!(d.front, r"");
        assert_eq!(chars(&d), r"");
    }

    #[test]
    fn connectors_markers() {
        let d = drawn(r##"{"version": 1, "id": "S", "title": "T", "slug": "s", "width": 400, "height": 300, "background": "#fff", "items": [{"type": "connector", "id": "c0", "points": [[0, 0], [50, 0], [50, 5]], "route": "poly", "color": "#112233", "width": 1.5, "dashed": true, "arrow_start": true, "arrow_end": true, "src": null, "dst": null, "label": null, "dash": null, "marker_start": "arrow", "marker_end": "arrow", "opacity": 1.0}, {"type": "connector", "id": "c1", "points": [[0, 10], [50, 10], [50, 15]], "route": "poly", "color": "#aa00ff", "width": 1.5, "dashed": false, "arrow_start": true, "arrow_end": false, "src": null, "dst": null, "label": null, "dash": [3, 3], "marker_start": "open-arrow", "marker_end": "open-arrow", "opacity": 1.0}, {"type": "connector", "id": "c2", "points": [[0, 20], [50, 20], [50, 25]], "route": "poly", "color": "#112233", "width": 1.5, "dashed": false, "arrow_start": true, "arrow_end": true, "src": null, "dst": null, "label": null, "dash": null, "marker_start": "diamond", "marker_end": "arrow", "opacity": 1.0}, {"type": "connector", "id": "c3", "points": [[0, 30], [50, 30], [50, 35]], "route": "poly", "color": "#aa00ff", "width": 1.5, "dashed": true, "arrow_start": true, "arrow_end": false, "src": null, "dst": null, "label": null, "dash": null, "marker_start": "open-diamond", "marker_end": "open-diamond", "opacity": 1.0}, {"type": "connector", "id": "c4", "points": [[0, 40], [50, 40], [50, 45]], "route": "poly", "color": "#112233", "width": 1.5, "dashed": false, "arrow_start": true, "arrow_end": true, "src": null, "dst": null, "label": null, "dash": null, "marker_start": "circle", "marker_end": "circle", "opacity": 0.8}, {"type": "connector", "id": "c5", "points": [[0, 50], [50, 50], [50, 55]], "route": "poly", "color": "#aa00ff", "width": 1.5, "dashed": false, "arrow_start": true, "arrow_end": false, "src": null, "dst": null, "label": null, "dash": null, "marker_start": "bar", "marker_end": "bar", "opacity": 1.0}, {"type": "connector", "id": "c6", "points": [[0, 60], [50, 60], [50, 65]], "route": "poly", "color": "#112233", "width": 1.5, "dashed": true, "arrow_start": true, "arrow_end": true, "src": null, "dst": null, "label": null, "dash": null, "marker_start": "none", "marker_end": "none", "opacity": 1.0}], "item_facts": {}, "sources": [], "meta_tooltips": {}}"##);
        assert_eq!(d.defs, r##"<marker id="m112233" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#112233"/></marker><marker id="mopen-arrow-aa00ff" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M1,1 L9,5 L1,9" fill="none" stroke="#aa00ff" stroke-width="1.5"/></marker><marker id="mdiamond-112233" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0,5 L5,0 L10,5 L5,10 z" fill="#112233"/></marker><marker id="mopen-diamond-aa00ff" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0,5 L5,0 L10,5 L5,10 z" fill="#FFFFFF" stroke="#aa00ff" stroke-width="1.2"/></marker><marker id="mcircle-112233" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><circle cx="5" cy="5" r="4" fill="#112233"/></marker><marker id="mbar-aa00ff" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M8,0 L8,10" stroke="#aa00ff" stroke-width="2"/></marker>"##);
        assert_eq!(d.back, r"");
        assert_eq!(d.mid, r##"<path d="M0.0,0.0 L50.0,0.0 L50.0,5.0" fill="none" stroke="#112233" stroke-width="1.5" stroke-dasharray="10 7" marker-end="url(#m112233)" marker-start="url(#m112233)"/><path d="M0.0,10.0 L50.0,10.0 L50.0,15.0" fill="none" stroke="#aa00ff" stroke-width="1.5" stroke-dasharray="3 3" marker-start="url(#mopen-arrow-aa00ff)"/><path d="M0.0,20.0 L50.0,20.0 L50.0,25.0" fill="none" stroke="#112233" stroke-width="1.5" marker-end="url(#m112233)" marker-start="url(#mdiamond-112233)"/><path d="M0.0,30.0 L50.0,30.0 L50.0,35.0" fill="none" stroke="#aa00ff" stroke-width="1.5" stroke-dasharray="10 7" marker-start="url(#mopen-diamond-aa00ff)"/><path d="M0.0,40.0 L50.0,40.0 L50.0,45.0" fill="none" stroke="#112233" stroke-width="1.5" opacity="0.8" marker-end="url(#mcircle-112233)" marker-start="url(#mcircle-112233)"/><path d="M0.0,50.0 L50.0,50.0 L50.0,55.0" fill="none" stroke="#aa00ff" stroke-width="1.5" marker-start="url(#mbar-aa00ff)"/><path d="M0.0,60.0 L50.0,60.0 L50.0,65.0" fill="none" stroke="#112233" stroke-width="1.5" stroke-dasharray="10 7" marker-end="url(#m112233)" marker-start="url(#m112233)"/>"##);
        assert_eq!(d.front, r"");
        assert_eq!(chars(&d), r"");
    }

    #[test]
    fn connector_curve_and_label() {
        let d = drawn(r##"{"version": 1, "id": "S", "title": "T", "slug": "s", "width": 400, "height": 300, "background": "#fff", "items": [{"type": "connector", "id": "c", "points": [[0, 0], [50.55, 80.05], [100, 0]], "route": "curve", "color": "#334455", "width": 2, "dashed": true, "arrow_start": true, "arrow_end": true, "src": null, "dst": null, "label": {"type": "shape", "id": "c-label", "kind": "pill", "x": 40, "y": 40, "w": 60, "h": 20, "fill": "#fff", "stroke": "#ccc", "stroke_width": 1, "radius": 10, "dashed": false, "opacity": 1.0, "label": {"blocks": [{"lines": ["lbl"], "paragraphs": ["lbl"], "font": {"family": "Inter", "weight": 400, "italic": false, "size": 14, "file": null, "fallback": "sans-serif", "figma_style": "Regular"}, "color": "#333", "leading": 19.6, "runs": null}], "box": [20, 30, 160, 70], "align": "left", "gap": 10, "valign": "middle"}, "icon": null, "role": "pill", "parts": null, "dash": null, "shadow": null, "fill_opacity": 1.0, "cap": null}, "dash": null, "marker_start": "arrow", "marker_end": "arrow", "opacity": 1.0}], "item_facts": {}, "sources": [], "meta_tooltips": {}}"##);
        assert_eq!(d.defs, r##"<marker id="m334455" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#334455"/></marker>"##);
        assert_eq!(d.back, r"");
        assert_eq!(d.mid, r##"<path d="M0.0,0.0 Q50.5,80.0 100.0,0.0" fill="none" stroke="#334455" stroke-width="2" stroke-dasharray="10 7" marker-end="url(#m334455)" marker-start="url(#m334455)"/>"##);
        assert_eq!(d.front, r##"<rect x="40.0" y="40.0" width="60.0" height="20.0" rx="10" fill="#fff" stroke="#ccc" stroke-width="1"/><text x="20.0" y="69.2" font-family="&apos;Inter&apos;, sans-serif" font-size="14" font-weight="400" fill="#333" text-anchor="start"><tspan x="20.0" dy="0.0">lbl</tspan></text>"##);
        assert_eq!(chars(&d), r"Inter|400|false=bl");
    }

    #[test]
    fn text_items() {
        let d = drawn(r##"{"version": 1, "id": "S", "title": "T", "slug": "s", "width": 400, "height": 300, "background": "#fff", "items": [{"type": "text", "id": "t1", "x": 10.04, "y": 20.05, "block": {"lines": ["hello & <world>", "two"], "paragraphs": ["hello & <world>", "two"], "font": {"family": "Inter", "weight": 700, "italic": true, "size": 13.5, "file": "/fonts/Inter-Bold.ttf", "fallback": "Helvetica, sans-serif", "figma_style": "Regular"}, "color": "#abcdef", "leading": 20, "runs": null}, "anchor": "middle", "letter_spacing": 0.5, "width": null}, {"type": "text", "id": "zbg", "x": 5, "y": 6, "block": {"lines": ["back"], "paragraphs": ["back"], "font": {"family": "Inter", "weight": 400, "italic": false, "size": 14, "file": null, "fallback": "sans-serif", "figma_style": "Regular"}, "color": "#333", "leading": 19.6, "runs": null}, "anchor": "start", "letter_spacing": 1, "width": null}, {"type": "text", "id": "t3", "x": 5, "y": 6, "block": {"lines": ["tipped"], "paragraphs": ["tipped"], "font": {"family": "Inter", "weight": 400, "italic": false, "size": 14, "file": null, "fallback": "sans-serif", "figma_style": "Regular"}, "color": "#333", "leading": 19.6, "runs": null}, "anchor": "end", "letter_spacing": 0, "width": 120}, {"type": "text", "id": "t4", "x": 1, "y": 2, "block": {"lines": ["tiny"], "paragraphs": ["tiny"], "font": {"family": "Inter", "weight": 400, "italic": false, "size": 14, "file": null, "fallback": "sans-serif", "figma_style": "Regular"}, "color": "#333", "leading": 19.6, "runs": null}, "anchor": "start", "letter_spacing": 1e-05, "width": null}, {"type": "text", "id": "t5", "x": 1, "y": 2, "block": {"lines": ["neg"], "paragraphs": ["neg"], "font": {"family": "Inter", "weight": 400, "italic": false, "size": 14, "file": null, "fallback": "sans-serif", "figma_style": "Regular"}, "color": "#333", "leading": 19.6, "runs": null}, "anchor": "start", "letter_spacing": -0.25, "width": null}], "item_facts": {"t3": ["f"], "zbg": ["f"]}, "sources": [], "meta_tooltips": {"f": "why & how"}}"##);
        assert_eq!(d.defs, r"");
        assert_eq!(d.back, r##"<text x="5.0" y="6.0" font-family="&apos;Inter&apos;, sans-serif" font-size="14" font-weight="400" fill="#333" text-anchor="start" letter-spacing="1"><tspan x="5.0" dy="0.0">back</tspan><title>why &amp; how</title></text>"##);
        assert_eq!(d.mid, r"");
        assert_eq!(d.front, r##"<text x="10.0" y="20.1" font-family="&apos;Inter&apos;, Helvetica, sans-serif" font-size="13.5" font-weight="700" font-style="italic" fill="#abcdef" text-anchor="middle" letter-spacing="0.5"><tspan x="10.0" dy="0.0">hello &amp; &lt;world&gt;</tspan><tspan x="10.0" dy="20.0">two</tspan></text><text x="5.0" y="6.0" font-family="&apos;Inter&apos;, sans-serif" font-size="14" font-weight="400" fill="#333" text-anchor="end"><tspan x="5.0" dy="0.0">tipped</tspan><title>why &amp; how</title></text><text x="1.0" y="2.0" font-family="&apos;Inter&apos;, sans-serif" font-size="14" font-weight="400" fill="#333" text-anchor="start" letter-spacing="1e-05"><tspan x="1.0" dy="0.0">tiny</tspan></text><text x="1.0" y="2.0" font-family="&apos;Inter&apos;, sans-serif" font-size="14" font-weight="400" fill="#333" text-anchor="start" letter-spacing="-0.25"><tspan x="1.0" dy="0.0">neg</tspan></text>"##);
        assert_eq!(chars(&d), r"Inter|400|false=abcdegiknpty; Inter|700|true= &<>dehlortw");
    }

    #[test]
    fn text_runs_fallback_and_empty() {
        let d = drawn(r##"{"version": 1, "id": "S", "title": "T", "slug": "s", "width": 400, "height": 300, "background": "#fff", "items": [{"type": "text", "id": "t", "x": 10, "y": 20, "block": {"lines": ["ab中c", "", "", "x"], "paragraphs": ["ab中c", "", "", "x"], "font": {"family": "Inter", "weight": 400, "italic": false, "size": 14, "file": null, "fallback": "sans-serif", "figma_style": "Regular"}, "color": "#000", "leading": 20, "runs": [[{"text": "ab", "font": {"family": "Inter", "weight": 400, "italic": false, "size": 14, "file": null, "fallback": "sans-serif", "figma_style": "Regular"}, "base": true}, {"text": "中", "font": {"family": "Noto Sans <CJK>", "weight": 400, "italic": false, "size": 14, "file": null, "fallback": "serif", "figma_style": "Regular"}, "base": false}, {"text": "c", "font": {"family": "Inter", "weight": 400, "italic": false, "size": 14, "file": null, "fallback": "sans-serif", "figma_style": "Regular"}, "base": true}], [], [{"text": "", "font": {"family": "Inter", "weight": 400, "italic": false, "size": 14, "file": null, "fallback": "sans-serif", "figma_style": "Regular"}, "base": true}], [{"text": "x", "font": {"family": "Noto Sans <CJK>", "weight": 400, "italic": false, "size": 14, "file": null, "fallback": "serif", "figma_style": "Regular"}, "base": false}]]}, "anchor": "start", "letter_spacing": 0, "width": null}, {"type": "text", "id": "u", "x": 10, "y": 100, "block": {"lines": ["", "plain é"], "paragraphs": ["", "plain é"], "font": {"family": "Inter", "weight": 700, "italic": true, "size": 13.5, "file": "/fonts/Inter-Bold.ttf", "fallback": "Helvetica, sans-serif", "figma_style": "Regular"}, "color": "#000", "leading": 20, "runs": null}, "anchor": "start", "letter_spacing": 0, "width": null}], "item_facts": {}, "sources": [], "meta_tooltips": {}}"##);
        assert_eq!(d.defs, r"");
        assert_eq!(d.back, r"");
        assert_eq!(d.mid, r"");
        assert_eq!(d.front, r##"<text x="10.0" y="20.0" font-family="&apos;Inter&apos;, sans-serif" font-size="14" font-weight="400" fill="#000" text-anchor="start"><tspan x="10.0" dy="0.0">ab<tspan font-family="&apos;Noto Sans &lt;CJK&gt;&apos;, serif">中</tspan>c</tspan><tspan x="10.0" dy="20.0">&#160;</tspan><tspan x="10.0" dy="20.0">&#160;</tspan><tspan x="10.0" dy="20.0"><tspan font-family="&apos;Noto Sans &lt;CJK&gt;&apos;, serif">x</tspan></tspan></text><text x="10.0" y="100.0" font-family="&apos;Inter&apos;, Helvetica, sans-serif" font-size="13.5" font-weight="700" font-style="italic" fill="#000" text-anchor="start"><tspan x="10.0" dy="0.0">&#160;</tspan><tspan x="10.0" dy="20.0">plain é</tspan></text>"##);
        assert_eq!(chars(&d), r"Inter|400|false=abc ; Inter|700|true= ailnp é; Noto Sans <CJK>|400|false=x中");
    }

    #[test]
    fn line_item() {
        let d = drawn(r##"{"version": 1, "id": "S", "title": "T", "slug": "s", "width": 400, "height": 300, "background": "#fff", "items": [{"type": "line", "id": "l", "x1": 1, "y1": 2.55, "x2": 30, "y2": 40.25, "color": "#0a0a0a", "width": 2}, {"type": "line", "id": "l2", "x1": 0, "y1": 0, "x2": 5, "y2": 5, "color": "#fff", "width": 1}], "item_facts": {}, "sources": [], "meta_tooltips": {}}"##);
        assert_eq!(d.defs, r"");
        assert_eq!(d.back, r"");
        assert_eq!(d.mid, r"");
        assert_eq!(d.front, r##"<line x1="1.0" y1="2.5" x2="30.0" y2="40.2" stroke="#0a0a0a" stroke-width="2"/><line x1="0.0" y1="0.0" x2="5.0" y2="5.0" stroke="#fff" stroke-width="1"/>"##);
        assert_eq!(chars(&d), r"");
    }

    #[test]
    fn image_png_and_icon_svg() {
        let d = drawn(r##"{"version": 1, "id": "S", "title": "T", "slug": "s", "width": 400, "height": 300, "background": "#fff", "items": [{"type": "image", "id": "i", "path": "@ROOT@/rust/spinagram-core/tests/data/pixel.png", "x": 1, "y": 2, "w": 30, "h": 40.5}, {"type": "image", "id": "j", "path": "@ROOT@/rust/spinagram-core/tests/data/pixel.jpeg", "x": 5, "y": 6, "w": 7, "h": 8}, {"type": "shape", "id": "a", "kind": "rect", "x": 0, "y": 0, "w": 40, "h": 40, "fill": "#fff", "stroke": null, "stroke_width": 0, "radius": 0, "dashed": false, "opacity": 1.0, "label": null, "icon": {"path": "@ROOT@/examples/icons/acme.svg", "x": 4, "y": 5, "size": 20, "w": 33}, "role": "node", "parts": null, "dash": null, "shadow": null, "fill_opacity": 1.0, "cap": null}], "item_facts": {}, "sources": [], "meta_tooltips": {}}"##);
        assert_eq!(d.defs, r"");
        assert_eq!(d.back, r"");
        assert_eq!(d.mid, r##"<rect x="0.0" y="0.0" width="40.0" height="40.0" rx="0" fill="#fff"/>"##);
        assert_eq!(d.front, r#"<image x="1.0" y="2.0" width="30" height="40.5" href="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGM4ISf3HwAEugIEPlcfxwAAAABJRU5ErkJggg=="/><image x="5.0" y="6.0" width="7" height="8" href="data:image/jpeg;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGM4ISf3HwAEugIEPlcfxwAAAABJRU5ErkJggg=="/><image x="4.0" y="5.0" width="33" height="20" href="data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxMjggMTI4IiB3aWR0aD0iMTI4IiBoZWlnaHQ9IjEyOCI+CiAgPHRpdGxlPnNwaW5hZ3JhbTwvdGl0bGU+CiAgPGRlZnM+CiAgICA8bWFya2VyIGlkPSJhIiB2aWV3Qm94PSIwIDAgMTAgMTAiIHJlZlg9IjYiIHJlZlk9IjUiIG1hcmtlcldpZHRoPSI0IiBtYXJrZXJIZWlnaHQ9IjQiIG9yaWVudD0iYXV0by1zdGFydC1yZXZlcnNlIj4KICAgICAgPHBhdGggZD0iTTAgMCAxMCA1IDAgMTB6IiBmaWxsPSIjOTNDNUZEIi8+CiAgICA8L21hcmtlcj4KICA8L2RlZnM+CiAgPHJlY3Qgd2lkdGg9IjEyOCIgaGVpZ2h0PSIxMjgiIHJ4PSIyOCIgZmlsbD0iIzI1NjNFQiIvPgogIDxnIGZpbGw9Im5vbmUiIHN0cm9rZT0iIzkzQzVGRCIgc3Ryb2tlLXdpZHRoPSI2IiBzdHJva2UtbGluZWNhcD0icm91bmQiIG1hcmtlci1lbmQ9InVybCgjYSkiPgogICAgPHBhdGggZD0iTTc2LjcgMzIuNUEzNCAzNCAwIDAgMSA5Ny43IDY4LjciLz4KICAgIDxwYXRoIGQ9Ik04NC45IDkwLjhBMzQgMzQgMCAwIDEgNDMuMSA5MC44Ii8+CiAgICA8cGF0aCBkPSJNMzAuMyA2OC43QTM0IDM0IDAgMCAxIDUxLjMgMzIuNSIvPgogIDwvZz4KICA8ZyBmaWxsPSIjRkZGRkZGIj4KICAgIDxyZWN0IHg9IjUwIiB5PSIyMCIgd2lkdGg9IjI4IiBoZWlnaHQ9IjIwIiByeD0iNiIvPgogICAgPHJlY3QgeD0iNzkuNCIgeT0iNzEiIHdpZHRoPSIyOCIgaGVpZ2h0PSIyMCIgcng9IjYiLz4KICAgIDxyZWN0IHg9IjIwLjYiIHk9IjcxIiB3aWR0aD0iMjgiIGhlaWdodD0iMjAiIHJ4PSI2Ii8+CiAgPC9nPgo8L3N2Zz4K"/>"#);
        assert_eq!(chars(&d), r"");
    }

    #[test]
    fn table_full() {
        let d = drawn(r##"{"version": 1, "id": "S", "title": "T", "slug": "s", "width": 400, "height": 300, "background": "#fff", "items": [{"type": "table", "id": "tb", "x": 10, "y": 20, "col_widths": [100, 90.5], "row_heights": [30, 28, 28.5], "cells": [[{"block": {"lines": ["H1"], "paragraphs": ["H1"], "font": {"family": "Inter", "weight": 700, "italic": true, "size": 13.5, "file": "/fonts/Inter-Bold.ttf", "fallback": "Helvetica, sans-serif", "figma_style": "Regular"}, "color": "#222", "leading": 18, "runs": null}, "fill": "#e0e0e0", "icon": null, "pad_left": 12, "bold": true}, {"block": {"lines": ["H2"], "paragraphs": ["H2"], "font": {"family": "Inter", "weight": 700, "italic": true, "size": 13.5, "file": "/fonts/Inter-Bold.ttf", "fallback": "Helvetica, sans-serif", "figma_style": "Regular"}, "color": "#222", "leading": 18, "runs": null}, "fill": "#e0e0e0", "icon": null, "pad_left": 12, "bold": true}], [{"block": {"lines": ["a"], "paragraphs": ["a"], "font": {"family": "Inter", "weight": 700, "italic": true, "size": 13.5, "file": "/fonts/Inter-Bold.ttf", "fallback": "Helvetica, sans-serif", "figma_style": "Regular"}, "color": "#222", "leading": 18, "runs": null}, "fill": "#fff", "icon": {"path": "@ROOT@/examples/icons/acme.svg", "x": 0, "y": 0, "size": 16, "w": null}, "pad_left": 12, "bold": true}, {"block": {"lines": ["b"], "paragraphs": ["b"], "font": {"family": "Inter", "weight": 700, "italic": true, "size": 13.5, "file": "/fonts/Inter-Bold.ttf", "fallback": "Helvetica, sans-serif", "figma_style": "Regular"}, "color": "#222", "leading": 18, "runs": null}, "fill": "#f6f6f6", "icon": null, "pad_left": 12, "bold": true}], [{"block": {"lines": ["c"], "paragraphs": ["c"], "font": {"family": "Inter", "weight": 700, "italic": true, "size": 13.5, "file": "/fonts/Inter-Bold.ttf", "fallback": "Helvetica, sans-serif", "figma_style": "Regular"}, "color": "#222", "leading": 18, "runs": null}, "fill": "#fff", "icon": null, "pad_left": 12, "bold": true}, {"block": {"lines": [""], "paragraphs": [""], "font": {"family": "Inter", "weight": 700, "italic": true, "size": 13.5, "file": "/fonts/Inter-Bold.ttf", "fallback": "Helvetica, sans-serif", "figma_style": "Regular"}, "color": "#222", "leading": 18, "runs": null}, "fill": "#f6f6f6", "icon": null, "pad_left": 12, "bold": true}]], "border": "#cccccc", "header_radius": 6}], "item_facts": {"tb": ["f"]}, "sources": [], "meta_tooltips": {"f": "table tip"}}"##);
        assert_eq!(d.defs, r"");
        assert_eq!(d.back, r"");
        assert_eq!(d.mid, r##"<rect x="10.0" y="20.0" width="190.5" height="30.0" rx="6" fill="#e0e0e0"/><rect x="10.0" y="50.0" width="190.5" height="28.0" fill="#fff"/><line x1="10.0" y1="78.0" x2="200.5" y2="78.0" stroke="#cccccc" stroke-width="1"/><rect x="10.0" y="78.0" width="190.5" height="28.5" fill="#fff"/><line x1="10.0" y1="106.5" x2="200.5" y2="106.5" stroke="#cccccc" stroke-width="1"/>"##);
        assert_eq!(d.front, r##"<text x="22.0" y="39.0" font-family="&apos;Inter&apos;, Helvetica, sans-serif" font-size="13.5" font-weight="700" font-style="italic" fill="#222" text-anchor="start"><tspan x="22.0" dy="0.0">H1</tspan></text><text x="122.0" y="39.0" font-family="&apos;Inter&apos;, Helvetica, sans-serif" font-size="13.5" font-weight="700" font-style="italic" fill="#222" text-anchor="start"><tspan x="122.0" dy="0.0">H2</tspan></text><image x="24.0" y="56.0" width="16" height="16" href="data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxMjggMTI4IiB3aWR0aD0iMTI4IiBoZWlnaHQ9IjEyOCI+CiAgPHRpdGxlPnNwaW5hZ3JhbTwvdGl0bGU+CiAgPGRlZnM+CiAgICA8bWFya2VyIGlkPSJhIiB2aWV3Qm94PSIwIDAgMTAgMTAiIHJlZlg9IjYiIHJlZlk9IjUiIG1hcmtlcldpZHRoPSI0IiBtYXJrZXJIZWlnaHQ9IjQiIG9yaWVudD0iYXV0by1zdGFydC1yZXZlcnNlIj4KICAgICAgPHBhdGggZD0iTTAgMCAxMCA1IDAgMTB6IiBmaWxsPSIjOTNDNUZEIi8+CiAgICA8L21hcmtlcj4KICA8L2RlZnM+CiAgPHJlY3Qgd2lkdGg9IjEyOCIgaGVpZ2h0PSIxMjgiIHJ4PSIyOCIgZmlsbD0iIzI1NjNFQiIvPgogIDxnIGZpbGw9Im5vbmUiIHN0cm9rZT0iIzkzQzVGRCIgc3Ryb2tlLXdpZHRoPSI2IiBzdHJva2UtbGluZWNhcD0icm91bmQiIG1hcmtlci1lbmQ9InVybCgjYSkiPgogICAgPHBhdGggZD0iTTc2LjcgMzIuNUEzNCAzNCAwIDAgMSA5Ny43IDY4LjciLz4KICAgIDxwYXRoIGQ9Ik04NC45IDkwLjhBMzQgMzQgMCAwIDEgNDMuMSA5MC44Ii8+CiAgICA8cGF0aCBkPSJNMzAuMyA2OC43QTM0IDM0IDAgMCAxIDUxLjMgMzIuNSIvPgogIDwvZz4KICA8ZyBmaWxsPSIjRkZGRkZGIj4KICAgIDxyZWN0IHg9IjUwIiB5PSIyMCIgd2lkdGg9IjI4IiBoZWlnaHQ9IjIwIiByeD0iNiIvPgogICAgPHJlY3QgeD0iNzkuNCIgeT0iNzEiIHdpZHRoPSIyOCIgaGVpZ2h0PSIyMCIgcng9IjYiLz4KICAgIDxyZWN0IHg9IjIwLjYiIHk9IjcxIiB3aWR0aD0iMjgiIGhlaWdodD0iMjAiIHJ4PSI2Ii8+CiAgPC9nPgo8L3N2Zz4K"/><text x="22.0" y="68.0" font-family="&apos;Inter&apos;, Helvetica, sans-serif" font-size="13.5" font-weight="700" font-style="italic" fill="#222" text-anchor="start"><tspan x="22.0" dy="0.0">a</tspan></text><text x="122.0" y="68.0" font-family="&apos;Inter&apos;, Helvetica, sans-serif" font-size="13.5" font-weight="700" font-style="italic" fill="#222" text-anchor="start"><tspan x="122.0" dy="0.0">b</tspan></text><text x="22.0" y="96.3" font-family="&apos;Inter&apos;, Helvetica, sans-serif" font-size="13.5" font-weight="700" font-style="italic" fill="#222" text-anchor="start"><tspan x="22.0" dy="0.0">c</tspan></text><text x="122.0" y="96.3" font-family="&apos;Inter&apos;, Helvetica, sans-serif" font-size="13.5" font-weight="700" font-style="italic" fill="#222" text-anchor="start"><tspan x="122.0" dy="0.0">&#160;</tspan></text><rect x="10.0" y="20.0" width="190.5" height="86.5" fill="none" pointer-events="all"><title>table tip</title></rect>"##);
        assert_eq!(chars(&d), r"Inter|700|true=12Habc ");
    }

    #[test]
    fn missing_image_names_the_path() {
        let json = r##"{"version":1,"id":"S","title":"T","slug":"s","width":10,"height":10,"background":"#fff","items":[{"type":"image","id":"i","path":"/no/such/file.png","x":0,"y":0,"w":1,"h":1}],"item_facts":{},"sources":[],"meta_tooltips":{}}"##;
        match draw(&scene::parse(json).unwrap(), true) {
            Err(DrawError::NotFound(p)) => assert_eq!(p, "/no/such/file.png"),
            other => panic!("expected NotFound, got {other:?}"),
        }
    }
}
