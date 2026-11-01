//! Edit operations on diagram YAML text, and the source map from element ids to YAML byte ranges.
//!
//! Every operation is a set of byte-range patches computed from parser spans (`saphyr-parser`), so bytes outside
//! the patched ranges (comments, blank lines, key order, flow/block style) are never touched. A batch applies
//! all operations or none: the text is re-parsed after each one and the first failure returns the input unchanged.

use std::collections::BTreeMap;
use std::fmt;

use saphyr_parser::{Event, Parser, ScalarStyle};
use serde::Deserialize;

/// One edit. JSON form: `{"op": "move", "id": "a", "x": 10, "y": 20}`, `"from"`/`"to"` for edges.
#[derive(Clone, Debug, Deserialize, PartialEq)]
#[serde(tag = "op", rename_all = "snake_case", deny_unknown_fields)]
pub enum Op {
    /// Set the position of a node (`at` list or `x`/`y` keys) or a zone (`x`/`y` keys).
    Move { id: String, x: f64, y: f64 },
    /// Set the size of a node (`at` list or `w`/`h` keys) or a zone (`w`/`h` keys).
    Resize { id: String, w: f64, h: f64 },
    /// Set the `title` of a node, or the `label` of a zone.
    Rename { id: String, title: String },
    /// Remove a node (or zone), the edges touching it, and its id from `children` and `nodes` lists.
    Delete { id: String },
    /// Append a node to `nodes`.
    AddNode {
        id: String,
        title: Option<String>,
        kind: Option<String>,
        x: Option<f64>,
        y: Option<f64>,
        w: Option<f64>,
        h: Option<f64>,
    },
    /// Append the edge `"from -> to"` (`: label` optional) to `edges`.
    Connect { from: String, to: String, label: Option<String> },
    /// Remove the first edge from `from` to `to`.
    Disconnect { from: String, to: String },
}

impl Op {
    fn name(&self) -> &'static str {
        match self {
            Op::Move { .. } => "move",
            Op::Resize { .. } => "resize",
            Op::Rename { .. } => "rename",
            Op::Delete { .. } => "delete",
            Op::AddNode { .. } => "add_node",
            Op::Connect { .. } => "connect",
            Op::Disconnect { .. } => "disconnect",
        }
    }
}

/// Why a batch was rejected: the index of the operation (when one is to blame) and the reason.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct EditError {
    pub index: Option<usize>,
    pub reason: String,
}

impl fmt::Display for EditError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self.index {
            Some(i) => write!(f, "operation {i}: {}", self.reason),
            None => f.write_str(&self.reason),
        }
    }
}

impl std::error::Error for EditError {}

fn fail<T>(reason: impl Into<String>) -> Result<T, String> {
    Err(reason.into())
}

// ---------------------------------------------------------------------------------------------------------
// Parsed tree with byte spans

#[derive(Debug)]
enum Val {
    Scalar { text: String, style: ScalarStyle },
    Seq { items: Vec<Node>, flow: bool },
    Map { pairs: Vec<(Node, Node)>, flow: bool },
    Alias,
}

#[derive(Debug)]
struct Node {
    start: usize,
    end: usize,
    val: Val,
}

impl Node {
    fn text(&self) -> Option<&str> {
        match &self.val {
            Val::Scalar { text, .. } => Some(text),
            _ => None,
        }
    }

    fn get(&self, key: &str) -> Option<&Node> {
        match &self.val {
            Val::Map { pairs, .. } => pairs.iter().find(|(k, _)| k.text() == Some(key)).map(|(_, v)| v),
            _ => None,
        }
    }

    fn items(&self) -> &[Node] {
        match &self.val {
            Val::Seq { items, .. } => items,
            _ => &[],
        }
    }

    fn is_null(&self) -> bool {
        matches!(&self.val, Val::Scalar { text, style: ScalarStyle::Plain } if text.is_empty() || text == "~" || text == "null")
    }
}

enum Frame {
    Seq { start: usize, items: Vec<Node> },
    Map { start: usize, items: Vec<Node> },
}

fn parse(src: &str) -> Result<Node, String> {
    let offsets: Option<Vec<usize>> = if src.is_ascii() {
        None
    } else {
        Some(src.char_indices().map(|(i, _)| i).chain(std::iter::once(src.len())).collect())
    };
    let byte = |c: usize| offsets.as_ref().map_or(c, |o| o[c.min(o.len() - 1)]);
    let mut stack: Vec<Frame> = Vec::new();
    let mut root: Option<Node> = None;
    let mut docs = 0;
    for event in Parser::new_from_str(src) {
        let (event, span) = event.map_err(|e| format!("invalid YAML: {e}"))?;
        let (s, e) = (byte(span.start.index()), byte(span.end.index()));
        let done = match event {
            Event::DocumentStart(_) => {
                docs += 1;
                if docs > 1 {
                    return fail("several YAML documents in one file are not supported");
                }
                None
            }
            Event::Scalar(text, style, _, _) => Some(Node { start: s, end: e, val: Val::Scalar { text: text.into_owned(), style } }),
            Event::Alias(_) => Some(Node { start: s, end: e, val: Val::Alias }),
            Event::SequenceStart(..) => {
                stack.push(Frame::Seq { start: s, items: Vec::new() });
                None
            }
            Event::MappingStart(..) => {
                stack.push(Frame::Map { start: s, items: Vec::new() });
                None
            }
            Event::SequenceEnd | Event::MappingEnd => {
                let frame = stack.pop().ok_or("unbalanced YAML events")?;
                let (start, items, is_map) = match frame {
                    Frame::Seq { start, items } => (start, items, false),
                    Frame::Map { start, items } => (start, items, true),
                };
                let flow = matches!(src.as_bytes().get(start), Some(b'{' | b'['));
                let last = items.last().map_or(start + 1, |n| n.end);
                let end = if flow { closer(src, last).unwrap_or(e) } else { items.last().map_or(start, |n| n.end) };
                let val = if is_map {
                    let mut it = items.into_iter();
                    let mut pairs = Vec::new();
                    while let (Some(k), Some(v)) = (it.next(), it.next()) {
                        pairs.push((k, v));
                    }
                    Val::Map { pairs, flow }
                } else {
                    Val::Seq { items, flow }
                };
                Some(Node { start, end, val })
            }
            _ => None,
        };
        if let Some(node) = done {
            match stack.last_mut() {
                Some(Frame::Seq { items, .. } | Frame::Map { items, .. }) => items.push(node),
                None => root = Some(node),
            }
        }
    }
    root.ok_or_else(|| "empty YAML document".to_owned())
}

/// The end of the flow collection whose last item ends at `from`: just past its closing bracket. The parser's own
/// end span runs on over a trailing comment.
fn closer(src: &str, from: usize) -> Option<usize> {
    let mut chars = src[from..].char_indices();
    while let Some((i, c)) = chars.next() {
        match c {
            '}' | ']' => return Some(from + i + 1),
            '#' => chars.by_ref().find(|&(_, c)| c == '\n')?,
            c if c.is_whitespace() || c == ',' => continue,
            _ => return None,
        };
    }
    None
}

/// The root mapping of a diagram file.
fn parse_diagram(src: &str) -> Result<Node, String> {
    let root = parse(src)?;
    match root.val {
        Val::Map { flow: false, .. } => Ok(root),
        Val::Map { flow: true, .. } => fail("a flow-style root mapping is not supported"),
        _ => fail("the diagram must be a YAML mapping"),
    }
}

// ---------------------------------------------------------------------------------------------------------
// Entries and the source map

/// Where an element lives: its mapping node, the sequence that holds it, and its position there.
struct Entry<'a> {
    id: &'a str,
    zone: bool,
    node: &'a Node,
    list: &'a Node,
    index: usize,
}

/// Every node and zone mapping with an `id`: `nodes`, `zones`, and the mappings inside `rows`/`columns` `nodes`.
fn entries(root: &Node) -> Vec<Entry<'_>> {
    fn push<'a>(out: &mut Vec<Entry<'a>>, list: &'a Node, zone: bool) {
        for (index, node) in list.items().iter().enumerate() {
            if let Some(id) = node.get("id").and_then(Node::text) {
                out.push(Entry { id, zone, node, list, index });
            }
        }
    }
    let mut out = Vec::new();
    if let Some(l) = root.get("nodes") {
        push(&mut out, l, false);
    }
    if let Some(l) = root.get("zones") {
        push(&mut out, l, true);
    }
    for axis in ["rows", "columns"] {
        for container in root.get(axis).map_or(&[][..], Node::items) {
            if let Some(l) = container.get("nodes") {
                push(&mut out, l, false);
            }
        }
    }
    out
}

/// The byte range `[start, end)` of the YAML entry of every node, zone (by id) and edge (`e0`, `e1`, ... by
/// position in `edges`, the connector ids of the scene).
///
/// # Errors
///
/// When the text is not a YAML mapping.
pub fn srcmap(yaml: &str) -> Result<BTreeMap<String, [usize; 2]>, String> {
    let root = parse_diagram(yaml)?;
    let mut map: BTreeMap<String, [usize; 2]> = entries(&root).into_iter().map(|e| (e.id.to_owned(), [e.node.start, e.node.end])).collect();
    for (i, edge) in root.get("edges").map_or(&[][..], Node::items).iter().enumerate() {
        map.insert(format!("e{i}"), [edge.start, edge.end]);
    }
    Ok(map)
}

// ---------------------------------------------------------------------------------------------------------
// Patches

#[derive(Debug)]
struct Patch {
    start: usize,
    end: usize,
    text: String,
}

fn apply_patches(src: &str, mut patches: Vec<Patch>) -> Result<String, String> {
    patches.sort_by_key(|p| (p.start, p.end));
    for w in patches.windows(2) {
        if w[0].end > w[1].start {
            return fail("internal error: overlapping patches");
        }
    }
    let mut out = src.to_owned();
    for p in patches.into_iter().rev() {
        out.replace_range(p.start..p.end, &p.text);
    }
    Ok(out)
}

fn line_start(src: &str, at: usize) -> usize {
    src[..at].rfind('\n').map_or(0, |i| i + 1)
}

/// The end of the line holding `at`, before its `\n`.
fn line_end(src: &str, at: usize) -> usize {
    src[at..].find('\n').map_or(src.len(), |i| at + i)
}

/// Columns (characters) between the start of the line and `at`.
fn column(src: &str, at: usize) -> usize {
    src[line_start(src, at)..at].chars().count()
}

fn num(v: f64) -> Result<String, String> {
    if !v.is_finite() {
        return fail(format!("{v} is not a finite number"));
    }
    #[expect(clippy::cast_possible_truncation, reason = "guarded by the fract and magnitude checks")]
    Ok(if v.fract() == 0.0 && v.abs() < 1e15 { format!("{}", v as i64) } else { format!("{v}") })
}

/// A YAML double-quoted scalar (JSON strings are valid YAML double-quoted scalars).
fn quoted(s: &str) -> String {
    serde_json::to_string(s).unwrap_or_else(|_| format!("\"{s}\""))
}

/// Plain when that reads back as the same string, double-quoted otherwise.
fn scalar(s: &str) -> String {
    const RESERVED: [&str; 12] = ["true", "false", "yes", "no", "on", "off", "y", "n", "null", "~", "nan", "inf"];
    let plain = s.chars().next().is_some_and(|c| c.is_ascii_alphabetic())
        && s.chars().all(|c| c.is_ascii_alphanumeric() || matches!(c, '_' | '-' | '.'))
        && !RESERVED.contains(&s.to_ascii_lowercase().as_str());
    if plain { s.to_owned() } else { quoted(s) }
}

/// The text that replaces the scalar `old` with the string `new`: plain stays plain when it can.
fn replacement(old: &Node, new: &str) -> Result<String, String> {
    match &old.val {
        Val::Scalar { style: ScalarStyle::Literal | ScalarStyle::Folded, .. } => fail("block scalars (| and >) are not supported"),
        Val::Scalar { style: ScalarStyle::Plain, .. } => Ok(scalar(new)),
        _ => Ok(quoted(new)),
    }
}

/// Set the keys of mapping `map` (replace a value or append the pair), as patches.
fn set_keys(src: &str, map: &Node, pairs: &[(&str, String)]) -> Result<Vec<Patch>, String> {
    let Val::Map { pairs: existing, flow } = &map.val else { return fail("entry is not a mapping") };
    let mut patches = Vec::new();
    let mut missing: Vec<&(&str, String)> = Vec::new();
    for kv in pairs {
        match existing.iter().find(|(k, _)| k.text() == Some(kv.0)) {
            Some((_, v)) => patches.push(Patch { start: v.start, end: v.end, text: kv.1.clone() }),
            None => missing.push(kv),
        }
    }
    if missing.is_empty() {
        return Ok(patches);
    }
    let list = |sep: &str| missing.iter().map(|(k, v)| format!("{k}: {v}")).collect::<Vec<_>>().join(sep);
    if *flow {
        match existing.last() {
            Some((_, v)) => patches.push(Patch { start: v.end, end: v.end, text: format!(", {}", list(", ")) }),
            None => patches.push(Patch { start: map.start + 1, end: map.start + 1, text: list(", ") }),
        }
    } else {
        let Some((_, tail)) = existing.last() else { return fail("empty mapping") };
        let at = line_end(src, tail.end);
        let pad = " ".repeat(column(src, map.start));
        patches.push(Patch { start: at, end: at, text: format!("\n{pad}{}", list(&format!("\n{pad}"))) });
    }
    Ok(patches)
}

/// Remove the items `idxs` of sequence `seq`, with their separators or lines.
fn remove_items(src: &str, seq: &Node, idxs: &[usize]) -> Vec<Patch> {
    let Val::Seq { items, flow } = &seq.val else { return Vec::new() };
    let mut ranges: Vec<(usize, usize)> = Vec::new();
    if *flow {
        for &i in idxs {
            if i + 1 < items.len() {
                ranges.push((items[i].start, items[i + 1].start));
            } else if let Some(prev) = (0..i).rev().find(|j| !idxs.contains(j)) {
                ranges.push((items[prev].end, items[i].end));
            } else {
                ranges.push((items[0].start, items[i].end));
            }
        }
        ranges.sort_unstable();
        let mut merged: Vec<(usize, usize)> = Vec::new();
        for r in ranges {
            match merged.last_mut() {
                Some(last) if r.0 <= last.1 => last.1 = last.1.max(r.1),
                _ => merged.push(r),
            }
        }
        ranges = merged;
    } else {
        for &i in idxs {
            let end = line_end(src, items[i].end);
            ranges.push((line_start(src, items[i].start), (end + 1).min(src.len())));
        }
    }
    ranges.into_iter().map(|(start, end)| Patch { start, end, text: String::new() }).collect()
}

/// Append `item` (one line of YAML) to the sequence under `key` of the root mapping, creating the key if needed.
fn append_item(src: &str, root: &Node, key: &str, item: &str) -> Result<Vec<Patch>, String> {
    let Val::Map { pairs, .. } = &root.val else { return fail("the diagram must be a YAML mapping") };
    let Some((k, seq)) = pairs.iter().find(|(k, _)| k.text() == Some(key)) else {
        let Some((_, last)) = pairs.last() else { return fail("the diagram mapping is empty") };
        let at = line_end(src, last.end);
        let pad = " ".repeat(column(src, root.start));
        return Ok(vec![Patch { start: at, end: at, text: format!("\n{pad}{key}:\n{pad}  - {item}") }]);
    };
    match &seq.val {
        Val::Seq { items, flow: true } => Ok(vec![match items.last() {
            Some(last) => Patch { start: last.end, end: last.end, text: format!(", {item}") },
            None => Patch { start: seq.start + 1, end: seq.start + 1, text: item.to_owned() },
        }]),
        Val::Seq { items, flow: false } => {
            let Some(last) = items.last() else { return fail(format!("`{key}` is an empty block list")) };
            let at = line_end(src, last.end);
            let from = line_start(src, last.start);
            let lead = &src[from..from + leading_ws(&src[from..])];
            Ok(vec![Patch { start: at, end: at, text: format!("\n{lead}- {item}") }])
        }
        _ if seq.is_null() => {
            let at = line_end(src, k.end);
            let pad = " ".repeat(column(src, k.start) + 2);
            Ok(vec![Patch { start: at, end: at, text: format!("\n{pad}- {item}") }])
        }
        _ => fail(format!("`{key}` is not a list")),
    }
}

fn leading_ws(line: &str) -> usize {
    line.len() - line.trim_start_matches([' ', '\t']).len()
}

// ---------------------------------------------------------------------------------------------------------
// Edges

/// The node (or zone) id of an edge endpoint: `a.right@0.3` is `a`, `zone:z` is `z`.
fn endpoint(s: &str) -> &str {
    let s = s.trim();
    s.strip_prefix("zone:").unwrap_or(s).split('.').next().unwrap_or(s)
}

/// `(src, dst)` of an edge entry: `"a -> b: label"` or `{from, to}`.
fn edge_ends(edge: &Node) -> Option<(String, String)> {
    if let Some(t) = edge.text() {
        let (lhs, op, rest) = ["<->", "->", "<-", "--"].iter().filter_map(|op| t.find(op).map(|i| (i, *op))).min_by_key(|(i, _)| *i).map(|(i, op)| (&t[..i], op, &t[i + op.len()..]))?;
        let dst = rest.split(':').next().unwrap_or(rest);
        let (a, b) = (endpoint(lhs).to_owned(), endpoint(dst).to_owned());
        return Some(if op == "<-" { (b, a) } else { (a, b) });
    }
    let (from, to) = (edge.get("from")?.text()?, edge.get("to")?.text()?);
    Some((endpoint(from).to_owned(), endpoint(to).to_owned()))
}

// ---------------------------------------------------------------------------------------------------------
// Operations

fn find<'a>(root: &'a Node, id: &str) -> Result<Entry<'a>, String> {
    entries(root).into_iter().find(|e| e.id == id).ok_or_else(|| format!("unknown id `{id}`"))
}

fn exists(root: &Node, id: &str) -> bool {
    entries(root).iter().any(|e| e.id == id)
}

/// `at: [x, y, w, h]` of an entry, when it uses that form: the flow list's scalar items.
fn at_items(entry: &Node) -> Result<Option<&Node>, String> {
    match entry.get("at") {
        None => Ok(None),
        Some(at @ Node { val: Val::Seq { flow: true, .. }, .. }) => Ok(Some(at)),
        Some(_) => fail("`at` must be a flow list like [x, y, w, h]"),
    }
}

fn patch_at(src: &str, at: &Node, first: usize, vals: [f64; 2]) -> Result<Vec<Patch>, String> {
    let items = at.items();
    let new = [num(vals[0])?, num(vals[1])?];
    if items.len() >= first + 2 {
        return Ok((0..2).map(|k| Patch { start: items[first + k].start, end: items[first + k].end, text: new[k].clone() }).collect());
    }
    // a short list: rewrite it whole as [x, y, w, h] with what it has plus the new values
    let mut cur: Vec<String> = items.iter().map(|n| src[n.start..n.end].to_owned()).collect();
    cur.truncate(first);
    cur.extend(new);
    Ok(vec![Patch { start: at.start, end: at.end, text: format!("[{}]", cur.join(", ")) }])
}

fn op_patches(src: &str, root: &Node, op: &Op) -> Result<Vec<Patch>, String> {
    match op {
        Op::Move { id, x, y } => {
            let e = find(root, id)?;
            match at_items(e.node)? {
                Some(at) if !e.zone => patch_at(src, at, 0, [*x, *y]),
                _ => set_keys(src, e.node, &[("x", num(*x)?), ("y", num(*y)?)]),
            }
        }
        Op::Resize { id, w, h } => {
            let e = find(root, id)?;
            match at_items(e.node)? {
                Some(at) if !e.zone => {
                    if at.items().len() < 2 {
                        return fail("`at` needs x and y before a size can be set");
                    }
                    patch_at(src, at, 2, [*w, *h])
                }
                _ => set_keys(src, e.node, &[("w", num(*w)?), ("h", num(*h)?)]),
            }
        }
        Op::Rename { id, title } => {
            let e = find(root, id)?;
            let key = if e.zone { "label" } else { "title" };
            let text = match e.node.get(key) {
                Some(old) => replacement(old, title)?,
                None => quoted(title),
            };
            set_keys(src, e.node, &[(key, text)])
        }
        Op::Delete { id } => delete(src, root, id),
        Op::AddNode { id, title, kind, x, y, w, h } => {
            if exists(root, id) {
                return fail(format!("duplicate id `{id}`"));
            }
            let mut fields = vec![format!("id: {}", scalar(id))];
            if let Some(k) = kind {
                fields.push(format!("kind: {}", scalar(k)));
            }
            if let Some(t) = title {
                fields.push(format!("title: {}", quoted(t)));
            }
            for (k, v) in [("x", x), ("y", y), ("w", w), ("h", h)] {
                if let Some(v) = v {
                    fields.push(format!("{k}: {}", num(*v)?));
                }
            }
            append_item(src, root, "nodes", &format!("{{{}}}", fields.join(", ")))
        }
        Op::Connect { from, to, label } => {
            for end in [from, to] {
                if !exists(root, endpoint(end)) {
                    return fail(format!("unknown id `{}`", endpoint(end)));
                }
            }
            let text = match label {
                Some(l) => format!("{from} -> {to}: {l}"),
                None => format!("{from} -> {to}"),
            };
            append_item(src, root, "edges", &quoted(&text))
        }
        Op::Disconnect { from, to } => {
            let edges = root.get("edges").ok_or_else(|| format!("no edge from `{from}` to `{to}`"))?;
            let (f, t) = (endpoint(from), endpoint(to));
            let idx = edges.items().iter().position(|e| edge_ends(e).is_some_and(|(a, b)| a == f && b == t));
            match idx {
                Some(i) => Ok(remove_items(src, edges, &[i])),
                None => fail(format!("no edge from `{from}` to `{to}`")),
            }
        }
    }
}

fn delete(src: &str, root: &Node, id: &str) -> Result<Vec<Patch>, String> {
    let entry = find(root, id)?;
    let mut by_list: Vec<(&Node, Vec<usize>)> = vec![(entry.list, vec![entry.index])];
    if let Some(edges) = root.get("edges") {
        let hits: Vec<usize> = edges.items().iter().enumerate().filter(|(_, e)| edge_ends(e).is_some_and(|(a, b)| a == id || b == id)).map(|(i, _)| i).collect();
        if !hits.is_empty() {
            by_list.push((edges, hits));
        }
    }
    // the id inside `children` lists (groups, zones, nested groups) and `nodes` lists of rows and columns
    let mut refs: Vec<&Node> = Vec::new();
    collect_lists(root, &mut refs);
    for list in refs {
        let hits: Vec<usize> = list.items().iter().enumerate().filter(|(_, n)| n.text() == Some(id)).map(|(i, _)| i).collect();
        if !hits.is_empty() {
            by_list.push((list, hits));
        }
    }
    Ok(by_list.into_iter().flat_map(|(list, idxs)| remove_items(src, list, &idxs)).collect())
}

/// Every sequence under a `children` or `nodes` key anywhere (groups, zones, rows and columns).
fn collect_lists<'a>(node: &'a Node, out: &mut Vec<&'a Node>) {
    match &node.val {
        Val::Map { pairs, .. } => {
            for (k, v) in pairs {
                if matches!(k.text(), Some("children" | "nodes")) && matches!(v.val, Val::Seq { .. }) {
                    out.push(v);
                }
                collect_lists(v, out);
            }
        }
        Val::Seq { items, .. } => items.iter().for_each(|n| collect_lists(n, out)),
        _ => {}
    }
}

/// Apply `ops` to `yaml` as one batch and return the patched text. Bytes outside the patched ranges are
/// unchanged. The text is re-parsed after every operation; an invalid operation, or a patch that would not
/// re-parse, rejects the whole batch with a reason.
///
/// # Errors
///
/// An [`EditError`] naming the failing operation and why; the input is untouched.
pub fn apply_ops(yaml: &str, ops: &[Op]) -> Result<String, EditError> {
    apply_with(yaml, ops, op_patches)
}

/// The batch loop of [`apply_ops`], with the patch computation as a parameter. Production passes `op_patches`; a
/// test passes a function whose patches break the YAML, because no real operation does (every inserted scalar is
/// quoted and every removal takes whole entries), so the re-parse guard below is defence in depth that only a seam
/// can reach.
fn apply_with(yaml: &str, ops: &[Op], make: impl Fn(&str, &Node, &Op) -> Result<Vec<Patch>, String>) -> Result<String, EditError> {
    let mut text = yaml.to_owned();
    for (i, op) in ops.iter().enumerate() {
        let wrap = |reason: String| EditError { index: Some(i), reason: format!("{}: {reason}", op.name()) };
        let root = parse_diagram(&text).map_err(wrap)?;
        let patches = make(&text, &root, op).map_err(wrap)?;
        let next = apply_patches(&text, patches).map_err(wrap)?;
        text = checked(next).map_err(wrap)?;
    }
    Ok(text)
}

/// `apply_ops` with the operations as a JSON array.
///
/// # Errors
///
/// The reason as text: bad JSON, or the [`EditError`].
pub fn apply_ops_json(yaml: &str, ops_json: &str) -> Result<String, String> {
    let ops: Vec<Op> = serde_json::from_str(ops_json).map_err(|e| format!("invalid operations: {e}"))?;
    apply_ops(yaml, &ops).map_err(|e| e.to_string())
}

/// A patched text is kept only when it still parses as a diagram mapping.
fn checked(text: String) -> Result<String, String> {
    parse_diagram(&text).map_err(|e| format!("the patch would produce invalid YAML ({e})"))?;
    Ok(text)
}

#[cfg(test)]
mod tests {
    use super::*;

    const DATA: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/tests/data/edit");

    fn read(name: &str) -> String {
        std::fs::read_to_string(format!("{DATA}/{name}.yaml")).unwrap()
    }

    fn ops(json: &str) -> Vec<Op> {
        serde_json::from_str(json).unwrap()
    }

    /// The fixture with `ops` applied equals the hand-written expected file, byte for byte (OPS-02).
    fn check(fixture: &str, expected: &str, json: &str) {
        let out = apply_ops(&read(fixture), &ops(json)).unwrap_or_else(|e| panic!("{expected}: {e}"));
        assert_eq!(out, read(expected), "{expected}");
        parse_diagram(&out).expect("the output re-parses");
    }

    #[test]
    fn block_entries_patch_only_the_touched_bytes() {
        let cases = [
            ("block_move_at", r#"[{"op":"move","id":"a","x":100,"y":200}]"#),
            ("block_move_keys", r#"[{"op":"move","id":"b","x":300,"y":85}]"#),
            ("block_move_insert", r#"[{"op":"move","id":"c","x":500,"y":40}]"#),
            ("block_move_zone", r#"[{"op":"move","id":"zone-a","x":30,"y":40}]"#),
            ("block_resize_at", r#"[{"op":"resize","id":"a","w":200,"h":90}]"#),
            ("block_resize_keys", r#"[{"op":"resize","id":"b","w":150,"h":70}]"#),
            ("block_rename_quoted", r#"[{"op":"rename","id":"a","title":"Alpha Prime"}]"#),
            ("block_rename_plain", r#"[{"op":"rename","id":"b","title":"Delta"}]"#),
            ("block_rename_zone", r#"[{"op":"rename","id":"zone-a","title":"Zone B"}]"#),
            ("block_delete_b", r#"[{"op":"delete","id":"b"}]"#),
            ("block_delete_c", r#"[{"op":"delete","id":"c"}]"#),
            ("block_delete_a", r#"[{"op":"delete","id":"a"}]"#),
            ("block_add_node", r#"[{"op":"add_node","id":"d","title":"Delta","x":10,"y":20,"w":100,"h":50}]"#),
            ("block_connect", r#"[{"op":"connect","from":"a","to":"c","label":"uses"}]"#),
            ("block_disconnect_bc", r#"[{"op":"disconnect","from":"b","to":"c"}]"#),
            ("block_disconnect_ab", r#"[{"op":"disconnect","from":"a","to":"b"}]"#),
        ];
        for (expected, json) in cases {
            check("block", expected, json);
        }
    }

    #[test]
    fn flow_entries_patch_only_the_touched_bytes() {
        let cases = [
            ("flow_move_at", r#"[{"op":"move","id":"a","x":1,"y":2}]"#),
            ("flow_move_keys", r#"[{"op":"move","id":"b","x":250,"y":70}]"#),
            ("flow_move_short_at", r#"[{"op":"move","id":"c","x":410,"y":70}]"#),
            ("flow_move_insert", r#"[{"op":"move","id":"d","x":5,"y":6}]"#),
            ("flow_resize_at", r#"[{"op":"resize","id":"a","w":300,"h":80}]"#),
            ("flow_resize_short_at", r#"[{"op":"resize","id":"c","w":90,"h":45}]"#),
            ("flow_resize_insert", r#"[{"op":"resize","id":"b","w":90,"h":45}]"#),
            ("flow_rename", r#"[{"op":"rename","id":"b","title":"Beta 2"}]"#),
            ("flow_delete_b", r#"[{"op":"delete","id":"b"}]"#),
            ("flow_delete_c", r#"[{"op":"delete","id":"c"}]"#),
            ("flow_add_node", r#"[{"op":"add_node","id":"e","title":"E","kind":"note","x":1,"y":2}]"#),
            ("flow_connect", r#"[{"op":"connect","from":"a","to":"d"}]"#),
            ("flow_disconnect", r#"[{"op":"disconnect","from":"a","to":"b"}]"#),
        ];
        for (expected, json) in cases {
            check("flow", expected, json);
        }
    }

    #[test]
    fn batches_apply_in_order() {
        // move then resize of the same node equals the two single results combined
        let out = apply_ops(&read("block"), &ops(r#"[{"op":"move","id":"a","x":100,"y":200},{"op":"resize","id":"a","w":200,"h":90}]"#)).unwrap();
        let expected = read("block").replace("at: [40, 60, 120, 60]", "at: [100, 200, 200, 90]");
        assert_eq!(out, expected);
    }

    fn reject(yaml: &str, json: &str, needle: &str) {
        let err = apply_ops_json(yaml, json).unwrap_err();
        assert!(err.contains(needle), "{err:?} should mention {needle:?}");
    }

    #[test]
    fn invalid_operations_are_rejected_with_a_reason() {
        let y = read("block");
        reject(&y, r#"[{"op":"move","id":"nope","x":1,"y":2}]"#, "unknown id `nope`");
        reject(&y, r#"[{"op":"resize","id":"nope","w":1,"h":2}]"#, "unknown id `nope`");
        reject(&y, r#"[{"op":"rename","id":"nope","title":"x"}]"#, "unknown id `nope`");
        reject(&y, r#"[{"op":"delete","id":"nope"}]"#, "unknown id `nope`");
        reject(&y, r#"[{"op":"add_node","id":"a","title":"again"}]"#, "duplicate id `a`");
        reject(&y, r#"[{"op":"add_node","id":"zone-a"}]"#, "duplicate id `zone-a`");
        reject(&y, r#"[{"op":"connect","from":"a","to":"ghost"}]"#, "unknown id `ghost`");
        reject(&y, r#"[{"op":"connect","from":"ghost","to":"a"}]"#, "unknown id `ghost`");
        reject(&y, r#"[{"op":"disconnect","from":"c","to":"b"}]"#, "no edge from `c` to `b`");
        reject(&y, r#"[{"op":"frobnicate","id":"a"}]"#, "invalid operations");
        reject(&y, "not json", "invalid operations");
        reject("a: [1", r#"[{"op":"delete","id":"a"}]"#, "invalid YAML");
        reject("- just\n- a list\n", r#"[{"op":"delete","id":"a"}]"#, "mapping");
    }

    #[test]
    fn a_rejected_operation_names_its_index_and_leaves_the_input_alone() {
        let y = read("block");
        let err = apply_ops(&y, &ops(r#"[{"op":"move","id":"a","x":1,"y":2},{"op":"delete","id":"ghost"}]"#)).unwrap_err();
        assert_eq!(err.index, Some(1));
        assert!(err.reason.contains("unknown id `ghost`"));
        assert_eq!(y, read("block"), "the caller's text is not modified");
    }

    #[test]
    fn a_batch_with_one_invalid_op_changes_nothing() {
        let y = read("flow");
        for bad in [r#"{"op":"delete","id":"zzz"}"#, r#"{"op":"add_node","id":"a"}"#, r#"{"op":"connect","from":"a","to":"zzz"}"#] {
            let json = format!(r#"[{{"op":"move","id":"a","x":9,"y":9}},{{"op":"delete","id":"d"}},{bad}]"#);
            assert!(apply_ops(&y, &ops(&json)).is_err());
            // there is no partial output: Err carries no text, and the same batch minus the bad op does apply
            let ok = r#"[{"op":"move","id":"a","x":9,"y":9},{"op":"delete","id":"d"}]"#;
            assert_ne!(apply_ops(&y, &ops(ok)).unwrap(), y);
        }
    }

    #[test]
    fn a_patch_that_does_not_reparse_is_rejected() {
        assert!(checked("id: x\nnodes: [unclosed\n".to_owned()).is_err());
        assert!(checked("- a\n- b\n".to_owned()).is_err());
        assert_eq!(checked("id: x\n".to_owned()).unwrap(), "id: x\n");
    }

    #[test]
    fn apply_ops_rejects_a_patch_whose_result_does_not_reparse() {
        // a patcher that opens a flow list and never closes it: the batch must fail, naming the operation
        let broken = |_: &str, root: &Node, _: &Op| Ok(vec![Patch { start: root.start, end: root.start, text: "x: [unclosed\n".to_owned() }]);
        let y = read("block");
        let err = apply_with(&y, &ops(r#"[{"op":"move","id":"a","x":1,"y":2}]"#), broken).unwrap_err();
        assert_eq!(err.index, Some(0));
        assert!(err.reason.contains("would produce invalid YAML"), "{}", err.reason);
        // a patch that turns the mapping into a list is rejected too
        let to_list = |src: &str, _: &Node, _: &Op| Ok(vec![Patch { start: 0, end: src.len(), text: "- a\n- b\n".to_owned() }]);
        let err = apply_with(&y, &ops(r#"[{"op":"delete","id":"a"}]"#), to_list).unwrap_err();
        assert!(err.reason.contains("would produce invalid YAML"), "{}", err.reason);
    }

    #[test]
    fn special_characters_are_quoted_so_the_result_still_parses() {
        let y = "id: t\nnodes:\n  - {id: a, title: A}\nedges: []\n";
        let out = apply_ops(y, &ops(r#"[{"op":"rename","id":"a","title":"say \"hi\": a # b\\c"},{"op":"add_node","id":"yes","title":"x: y"},{"op":"add_node","id":"1","title":"Ünï"},{"op":"connect","from":"a","to":"yes","label":"a: \"b\""}]"#)).unwrap();
        let root = parse_diagram(&out).unwrap();
        let nodes = root.get("nodes").unwrap().items();
        assert_eq!(nodes[0].get("title").and_then(Node::text), Some("say \"hi\": a # b\\c"));
        assert_eq!(nodes[1].get("id").and_then(Node::text), Some("yes"));
        assert_eq!(nodes[1].get("title").and_then(Node::text), Some("x: y"));
        assert_eq!(nodes[2].get("id").and_then(Node::text), Some("1"));
        assert_eq!(nodes[2].get("title").and_then(Node::text), Some("Ünï"));
        assert_eq!(root.get("edges").unwrap().items()[0].text(), Some("a -> yes: a: \"b\""));
    }

    #[test]
    fn missing_or_empty_lists_are_created_and_flow_lists_are_edited_in_place() {
        // no edges key at all: the key is added at the end of the root
        let out = apply_ops("id: t\nnodes:\n  - {id: a}\n  - {id: b}\n", &ops(r#"[{"op":"connect","from":"a","to":"b"}]"#)).unwrap();
        assert_eq!(out, "id: t\nnodes:\n  - {id: a}\n  - {id: b}\nedges:\n  - \"a -> b\"\n");
        // an empty value
        let out = apply_ops("id: t\nnodes:\n  - {id: a}\nedges:   # none yet\n", &ops(r#"[{"op":"connect","from":"a","to":"a"}]"#)).unwrap();
        assert_eq!(out, "id: t\nnodes:\n  - {id: a}\nedges:   # none yet\n  - \"a -> a\"\n");
        // no nodes key: added, with the new node
        let out = apply_ops("id: t\ntitle: T", &ops(r#"[{"op":"add_node","id":"new","title":"N"}]"#)).unwrap();
        assert_eq!(out, "id: t\ntitle: T\nnodes:\n  - {id: new, title: \"N\"}");
        // flow lists
        let flow = "id: t\nnodes: [{id: a}, {id: b}]\nedges: []\n";
        let out = apply_ops(flow, &ops(r#"[{"op":"add_node","id":"c"},{"op":"connect","from":"a","to":"c"}]"#)).unwrap();
        assert_eq!(out, "id: t\nnodes: [{id: a}, {id: b}, {id: c}]\nedges: [\"a -> c\"]\n");
        let out = apply_ops(&out, &ops(r#"[{"op":"connect","from":"b","to":"c"},{"op":"delete","id":"a"}]"#)).unwrap();
        assert_eq!(out, "id: t\nnodes: [{id: b}, {id: c}]\nedges: [\"b -> c\"]\n");
    }

    #[test]
    fn delete_removes_flow_list_items_and_the_node_from_group_lists() {
        let y = "id: t\nnodes:\n  - {id: a}\n  - {id: b}\n  - {id: c}\ngroups:\n  - {id: g, children: [a, b, c]}\n  - id: h\n    children:\n      - b\n      - c\nrows:\n  - nodes: [a, b, c]\n";
        for (id, children, block, rows) in [("a", "[b, c]", "      - b\n      - c\n", "[b, c]"), ("b", "[a, c]", "      - c\n", "[a, c]"), ("c", "[a, b]", "      - b\n", "[a, b]")] {
            let out = apply_ops(y, &ops(&format!(r#"[{{"op":"delete","id":"{id}"}}]"#))).unwrap();
            let want = y
                .replace(&format!("  - {{id: {id}}}\n"), "")
                .replace("children: [a, b, c]", &format!("children: {children}"))
                .replace("      - b\n      - c\n", block)
                .replace("nodes: [a, b, c]", &format!("nodes: {rows}"));
            assert_eq!(out, want, "delete {id}");
        }
        let out = apply_ops(y, &ops(r#"[{"op":"delete","id":"a"},{"op":"delete","id":"b"},{"op":"delete","id":"c"}]"#)).unwrap();
        assert_eq!(out, "id: t\nnodes:\ngroups:\n  - {id: g, children: []}\n  - id: h\n    children:\nrows:\n  - nodes: []\n");
    }

    #[test]
    fn delete_removes_edges_touching_the_node_in_every_edge_form() {
        let y = "id: t\nnodes:\n  - {id: a}\n  - {id: b}\n  - {id: c}\nedges:\n  - \"a.right@0.3 -> b.left: x\"\n  - \"c <- b\"\n  - \"a -- c\"\n  - {from: c, to: b, label: y}\n  - \"a -> c: keep\"\n";
        let out = apply_ops(y, &ops(r#"[{"op":"delete","id":"b"}]"#)).unwrap();
        assert!(out.ends_with("edges:\n  - \"a -- c\"\n  - \"a -> c: keep\"\n"), "{out}");
        assert!(!out.contains("id: b"));
    }

    #[test]
    fn srcmap_ranges_slice_exactly_the_entry_text() {
        let y = read("block");
        let map = srcmap(&y).unwrap();
        let slice = |id: &str| &y[map[id][0]..map[id][1]];
        assert_eq!(slice("zone-a"), "id: zone-a\n    label: Zone A\n    x: 20\n    y: 20\n    w: 400\n    h: 300");
        assert_eq!(slice("a"), "id: a\n    title: Alpha   # keep me\n    at: [40, 60, 120, 60]");
        assert_eq!(slice("b"), "id: b\n    title: Beta\n    x: 240\n    y: 60\n    w: 120\n    h: 60");
        assert_eq!(slice("c"), "id: c\n    title: Gamma");
        assert_eq!(slice("e0"), "\"a -> b: calls\"");
        assert_eq!(slice("e1"), "{from: b, to: c}");
        assert_eq!(slice("e2"), "\"c -> a\"");
        assert_eq!(map.len(), 7);

        let f = read("flow");
        let map = srcmap(&f).unwrap();
        assert_eq!(&f[map["a"][0]..map["a"][1]], "{id: a, title: Alpha, at: [40, 60, 120, 60]}");
        assert_eq!(&f[map["c"][0]..map["c"][1]], "{id: c, title: \"Gamma\", at: [400, 60]}");
        assert_eq!(&f[map["d"][0]..map["d"][1]], "{id: d, title: Delta}");
        assert_eq!(&f[map["e1"][0]..map["e1"][1]], "\"b -> c: next\"");
    }

    #[test]
    fn srcmap_is_in_bytes_with_non_ascii_text_before_the_entry() {
        let y = "id: t\ntitle: Ünï côde — ok\nnodes:\n  - {id: a, title: \"Ω\"}\n";
        let map = srcmap(y).unwrap();
        assert_eq!(&y[map["a"][0]..map["a"][1]], "{id: a, title: \"Ω\"}");
        let out = apply_ops(y, &ops(r#"[{"op":"move","id":"a","x":1,"y":2}]"#)).unwrap();
        assert_eq!(out, "id: t\ntitle: Ünï côde — ok\nnodes:\n  - {id: a, title: \"Ω\", x: 1, y: 2}\n");
    }

    #[test]
    fn nodes_inside_rows_and_columns_are_addressable() {
        let y = "id: t\nrows:\n  - x: 0\n    nodes:\n      - {id: r1, title: R}\n      - r2\n";
        let map = srcmap(y).unwrap();
        assert_eq!(&y[map["r1"][0]..map["r1"][1]], "{id: r1, title: R}");
        let out = apply_ops(y, &ops(r#"[{"op":"move","id":"r1","x":5,"y":6}]"#)).unwrap();
        assert!(out.contains("{id: r1, title: R, x: 5, y: 6}"));
        let out = apply_ops(y, &ops(r#"[{"op":"delete","id":"r1"}]"#)).unwrap();
        assert_eq!(out, "id: t\nrows:\n  - x: 0\n    nodes:\n      - r2\n");
    }

    #[test]
    fn unsupported_shapes_are_rejected_not_mangled() {
        reject("id: t\nnodes:\n  - id: a\n    title: |\n      one\n    at: [1, 2, 3, 4]\n", r#"[{"op":"rename","id":"a","title":"x"}]"#, "block scalars");
        reject("id: t\nnodes:\n  - id: a\n    at:\n      - 1\n      - 2\n", r#"[{"op":"move","id":"a","x":1,"y":1}]"#, "flow list");
        reject("id: t\nnodes:\n  - {id: a}\n", r#"[{"op":"move","id":"a","x":1e999,"y":1}]"#, "invalid operations");
        reject("---\nid: a\n---\nid: b\n", r#"[{"op":"delete","id":"a"}]"#, "several YAML documents");
    }
}
