//! The YAML span tree: a parse of diagram text into scalars, sequences and mappings with UTF-8 byte spans, built
//! from `saphyr-parser` events. Edit operations patch those spans; the text outside is never re-serialised.

use saphyr_parser::{Event, Parser, ScalarStyle};
use thiserror::Error;

/// Why a YAML text could not be read into a span tree.
#[derive(Debug, Error, PartialEq, Eq)]
pub enum YamlError {
    /// The parser rejected the text. `byte` is the UTF-8 offset, `line` and `column` count from 1.
    #[error("invalid YAML: {info} at byte {byte} line {line} column {column}")]
    Syntax { info: String, byte: usize, line: usize, column: usize },
    /// The file holds more than one document.
    #[error("several YAML documents in one file are not supported")]
    MultipleDocuments,
    /// The file holds no document.
    #[error("empty YAML document")]
    Empty,
    /// The parser's events did not nest.
    #[error("unbalanced YAML events")]
    Unbalanced,
    /// The root is a flow mapping.
    #[error("a flow-style root mapping is not supported")]
    FlowRoot,
    /// The root is not a mapping.
    #[error("the diagram must be a YAML mapping")]
    NotAMapping,
    /// An anchor or alias sits in a list an operation edits.
    #[error("anchors and aliases are not supported")]
    AnchorOrAlias,
}

impl From<YamlError> for String {
    fn from(e: YamlError) -> Self {
        e.to_string()
    }
}

/// A parsed value.
#[derive(Debug)]
pub(crate) enum Val {
    Scalar { text: String, style: ScalarStyle },
    Seq { items: Vec<Node>, flow: bool },
    Map { pairs: Vec<(Node, Node)>, flow: bool },
    Alias,
}

/// A value with its byte range in the source. A collection's range excludes its anchor and tag.
#[derive(Debug)]
pub(crate) struct Node {
    pub(crate) start: usize,
    pub(crate) end: usize,
    pub(crate) val: Val,
    /// The value carries an anchor (`&a`).
    pub(crate) anchored: bool,
}

impl Node {
    pub(crate) fn text(&self) -> Option<&str> {
        match &self.val {
            Val::Scalar { text, .. } => Some(text),
            _ => None,
        }
    }

    pub(crate) fn get(&self, key: &str) -> Option<&Node> {
        match &self.val {
            Val::Map { pairs, .. } => pairs.iter().find(|(k, _)| k.text() == Some(key)).map(|(_, v)| v),
            _ => None,
        }
    }

    pub(crate) fn items(&self) -> &[Node] {
        match &self.val {
            Val::Seq { items, .. } => items,
            _ => &[],
        }
    }

    pub(crate) fn is_null(&self) -> bool {
        matches!(&self.val, Val::Scalar { text, style: ScalarStyle::Plain } if text.is_empty() || text == "~" || text == "null")
    }

    /// An anchor or alias is this value or inside it.
    pub(crate) fn has_anchor_or_alias(&self) -> bool {
        self.anchored
            || match &self.val {
                Val::Alias => true,
                Val::Scalar { .. } => false,
                Val::Seq { items, .. } => items.iter().any(Node::has_anchor_or_alias),
                Val::Map { pairs, .. } => pairs.iter().any(|(k, v)| k.has_anchor_or_alias() || v.has_anchor_or_alias()),
            }
    }
}

enum Frame {
    Seq { start: usize, anchored: bool, items: Vec<Node> },
    Map { start: usize, anchored: bool, items: Vec<Node> },
}

#[cfg(test)]
thread_local! {
    /// How many times this thread has parsed, for the tests that count parses per operation.
    pub(crate) static PARSES: std::cell::Cell<usize> = const { std::cell::Cell::new(0) };
}

/// Parse `src` (one document) into a span tree.
///
/// # Errors
///
/// [`YamlError`] when the text is not valid YAML, is empty, or holds several documents.
pub(crate) fn parse(src: &str) -> Result<Node, YamlError> {
    #[cfg(test)]
    PARSES.with(|n| n.set(n.get() + 1));
    // saphyr marks count characters; the table turns them into byte offsets
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
        let (event, span) = event.map_err(|e| {
            let mark = e.marker();
            YamlError::Syntax { info: e.info().to_owned(), byte: byte(mark.index()), line: mark.line(), column: mark.col() + 1 }
        })?;
        let (s, e) = (byte(span.start.index()), byte(span.end.index()));
        let done = match event {
            Event::DocumentStart(_) => {
                docs += 1;
                if docs > 1 {
                    return Err(YamlError::MultipleDocuments);
                }
                None
            }
            Event::Scalar(text, style, anchor, _) => {
                Some(Node { start: s, end: e, val: Val::Scalar { text: text.into_owned(), style }, anchored: anchor != 0 })
            }
            Event::Alias(_) => Some(Node { start: s, end: e, val: Val::Alias, anchored: false }),
            Event::SequenceStart(anchor, _) => {
                stack.push(Frame::Seq { start: s, anchored: anchor != 0, items: Vec::new() });
                None
            }
            Event::MappingStart(anchor, _) => {
                stack.push(Frame::Map { start: s, anchored: anchor != 0, items: Vec::new() });
                None
            }
            Event::SequenceEnd | Event::MappingEnd => {
                let (start, anchored, items, is_map) = match stack.pop().ok_or(YamlError::Unbalanced)? {
                    Frame::Seq { start, anchored, items } => (start, anchored, items, false),
                    Frame::Map { start, anchored, items } => (start, anchored, items, true),
                };
                let start = skip_properties(src, start);
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
                Some(Node { start, end, val, anchored })
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
    root.ok_or(YamlError::Empty)
}

/// `from` moved past any anchor (`&a`) and tag (`!t`, `!!map`) tokens and the blanks after them.
fn skip_properties(src: &str, from: usize) -> usize {
    let mut at = from;
    while let Some(rest) = src.get(at..) {
        if !(rest.starts_with('&') || rest.starts_with('!')) {
            break;
        }
        let token = rest.find(char::is_whitespace).unwrap_or(rest.len());
        let after = &rest[token..];
        at += token + (after.len() - after.trim_start().len());
    }
    at
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
///
/// # Errors
///
/// [`YamlError`] when the text does not parse or the root is not a block mapping.
pub(crate) fn parse_diagram(src: &str) -> Result<Node, YamlError> {
    let root = parse(src)?;
    match root.val {
        Val::Map { flow: false, .. } => Ok(root),
        Val::Map { flow: true, .. } => Err(YamlError::FlowRoot),
        _ => Err(YamlError::NotAMapping),
    }
}

/// The top-level lists an operation edits hold no anchor or alias, which a byte patch could not keep consistent.
///
/// # Errors
///
/// [`YamlError::AnchorOrAlias`] when one does.
pub(crate) fn edited_lists_have_no_anchors(root: &Node) -> Result<(), YamlError> {
    let bad = ["nodes", "zones", "edges", "rows", "columns"].iter().any(|k| root.get(k).is_some_and(Node::has_anchor_or_alias));
    if bad {
        Err(YamlError::AnchorOrAlias)
    } else {
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn flow_of(src: &str, key: &str) -> (bool, String) {
        let root = parse_diagram(src).unwrap();
        let n = root.get(key).unwrap();
        let flow = matches!(&n.val, Val::Map { flow: true, .. } | Val::Seq { flow: true, .. });
        (flow, src[n.start..n.end].to_owned())
    }

    #[test]
    fn a_tagged_flow_map_has_its_own_span() {
        let (flow, text) = flow_of("k: !!map {a: 1, b: 2}\n", "k");
        assert!(flow);
        assert_eq!(text, "{a: 1, b: 2}");
    }

    #[test]
    fn an_anchored_flow_seq_has_its_own_span() {
        let (flow, text) = flow_of("k: &x [1, 2] # note\nz: 1\n", "k");
        assert!(flow);
        assert_eq!(text, "[1, 2]");
        assert!(parse_diagram("k: &x [1, 2]\n").unwrap().get("k").unwrap().anchored);
    }

    #[test]
    fn a_tagged_block_map_stays_block() {
        let (flow, _) = flow_of("k: !t\n  a: 1\n", "k");
        assert!(!flow);
    }

    #[test]
    fn anchors_and_aliases_are_reported() {
        let root = parse_diagram("a: &x {p: 1}\nb: *x\n").unwrap();
        assert!(root.get("a").unwrap().has_anchor_or_alias());
        assert!(root.get("b").unwrap().has_anchor_or_alias());
        assert!(!parse_diagram("a: {p: 1}\n").unwrap().has_anchor_or_alias());
    }

    #[test]
    fn a_syntax_error_reports_the_byte_offset_after_non_ascii_text() {
        // `é` is two bytes: the unclosed bracket is reported at the end of the text, byte 11 and char 10
        let src = "t: é\na: [1";
        let YamlError::Syntax { byte, line, column, .. } = parse(src).unwrap_err() else { panic!("not a syntax error") };
        assert_eq!(byte, src.len());
        assert!(line >= 2 && column >= 1);
    }

    #[test]
    fn an_alias_in_an_edited_list_is_rejected_elsewhere_it_is_not() {
        let aliased = parse_diagram("d: &d {w: 1}\nnodes:\n  - {id: a, k: *d}\n").unwrap();
        assert_eq!(edited_lists_have_no_anchors(&aliased), Err(YamlError::AnchorOrAlias));
        let anchored = parse_diagram("nodes:\n  - &n {id: a}\n").unwrap();
        assert_eq!(edited_lists_have_no_anchors(&anchored), Err(YamlError::AnchorOrAlias));
        let outside = parse_diagram("d: &d {w: 1}\ne: *d\nnodes:\n  - {id: a}\n").unwrap();
        assert_eq!(edited_lists_have_no_anchors(&outside), Ok(()));
    }

    #[test]
    fn the_error_text_is_unchanged_for_ascii() {
        assert!(parse("a: [1").unwrap_err().to_string().starts_with("invalid YAML: "));
    }

    #[test]
    fn structural_errors_are_typed() {
        assert_eq!(parse("a: 1\n---\nb: 2\n").unwrap_err(), YamlError::MultipleDocuments);
        assert_eq!(parse("").unwrap_err(), YamlError::Empty);
        assert_eq!(parse_diagram("{a: 1}").unwrap_err(), YamlError::FlowRoot);
        assert_eq!(parse_diagram("- 1\n").unwrap_err(), YamlError::NotAMapping);
    }
}
