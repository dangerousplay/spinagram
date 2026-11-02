//! The edge text grammar: `"a.right@0.3 -> zone:z: label"` and the endpoints inside it.
//!
//! It accepts exactly what the loader's `parse_edge` (`src/spinagram/model.py`) accepts, a backtracking regex:
//!
//! ```text
//! ^\s*(src .+?)\s*(<->|->|<-|--)\s*(dst (?:zone:)?[^:]+?)\s*(?::\s*(label .*))?$
//! ```
//!
//! The source is lazy, so the leftmost operator wins unless the rest then fails to match, in which case the next
//! operator is tried. `\s` is Unicode whitespace, `.` stops at a newline, and `$` also matches before one final
//! newline. `rust/schema/edge_vectors.json` pins the behaviour for both engines.

use std::str::FromStr;

use thiserror::Error;
use winnow::combinator::{opt, preceded};
use winnow::prelude::*;
use winnow::token::{literal, rest, take_till, take_while};

use crate::route::Side;

/// The prefix that makes an edge end a zone instead of a node.
pub const ZONE_PREFIX: &str = "zone:";

/// An edge operator.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum EdgeOp {
    /// `<->`: arrows at both ends.
    Both,
    /// `->`: arrow at the destination.
    Forward,
    /// `<-`: arrow at the source; the loader swaps the ends.
    Backward,
    /// `--`: no arrow.
    Line,
}

impl EdgeOp {
    /// The operators in the order the grammar tries them.
    pub const ALL: [EdgeOp; 4] = [EdgeOp::Both, EdgeOp::Forward, EdgeOp::Backward, EdgeOp::Line];

    /// The operator as written.
    #[must_use]
    pub fn as_str(self) -> &'static str {
        match self {
            EdgeOp::Both => "<->",
            EdgeOp::Forward => "->",
            EdgeOp::Backward => "<-",
            EdgeOp::Line => "--",
        }
    }

    /// The edge's `arrow` value.
    #[must_use]
    pub fn arrow(self) -> &'static str {
        match self {
            EdgeOp::Both => "both",
            EdgeOp::Forward | EdgeOp::Backward => "end",
            EdgeOp::Line => "none",
        }
    }
}

/// What an edge end points at.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum EndpointTarget {
    /// A node.
    Node,
    /// A zone (`zone:` prefix).
    Zone,
}

/// Why an edge end does not read.
#[derive(Debug, Error, PartialEq, Eq)]
pub enum EndpointError {
    /// The side is not top, bottom, left or right.
    #[error("unknown side `{0}` (expected top, bottom, left or right)")]
    Side(String),
    /// The position along the side is not a number.
    #[error("`{0}` is not a number")]
    Fraction(String),
    /// The end has no id.
    #[error("an edge end needs an id")]
    Empty,
}

/// An edge end cut into its parts, without checking the side or the fraction (the loader's `_split`).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct RawEndpoint<'a> {
    /// Node or zone.
    pub target: EndpointTarget,
    /// The id, without `zone:`.
    pub id: &'a str,
    /// The text after `.`, empty when absent.
    pub side: &'a str,
    /// The text after `@`, empty when absent.
    pub frac: &'a str,
}

/// A typed edge end: `a`, `a.right`, `a.right@0.3`, `zone:z.top`.
#[derive(Clone, Debug, PartialEq)]
pub struct Endpoint {
    /// Node or zone.
    pub target: EndpointTarget,
    /// The id, without `zone:`.
    pub id: String,
    /// The side the edge leaves from, when fixed.
    pub side: Option<Side>,
    /// The position along the side, when fixed.
    pub frac: Option<f64>,
}

fn endpoint_parts<'a>(input: &mut &'a str) -> winnow::Result<RawEndpoint<'a>> {
    let name = take_till(0.., '.').parse_next(input)?;
    let side = opt(preceded('.', take_till(0.., '@'))).parse_next(input)?.unwrap_or("");
    let frac = opt(preceded('@', rest)).parse_next(input)?.unwrap_or("");
    let (target, id) = match name.strip_prefix(ZONE_PREFIX) {
        Some(id) => (EndpointTarget::Zone, id),
        None => (EndpointTarget::Node, name),
    };
    Ok(RawEndpoint { target, id, side, frac })
}

/// Cut an edge end at the first `.` and the first `@` after it. Never fails.
#[must_use]
pub fn split_endpoint(s: &str) -> RawEndpoint<'_> {
    let mut input = s;
    // every alternative of the grammar accepts any text, so there is no failure to report
    endpoint_parts.parse_next(&mut input).unwrap_or(RawEndpoint { target: EndpointTarget::Node, id: s, side: "", frac: "" })
}

impl FromStr for Endpoint {
    type Err = EndpointError;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        let raw = split_endpoint(s);
        if raw.id.is_empty() {
            return Err(EndpointError::Empty);
        }
        let side = match raw.side {
            "" => None,
            name => Some(Side::from_name(name).ok_or_else(|| EndpointError::Side(name.to_owned()))?),
        };
        let frac = match raw.frac {
            "" => None,
            text => Some(text.trim().parse::<f64>().map_err(|_| EndpointError::Fraction(text.to_owned()))?),
        };
        Ok(Endpoint { target: raw.target, id: raw.id.to_owned(), side, frac })
    }
}

impl Endpoint {
    /// The end as written in an edge.
    #[must_use]
    pub fn render(&self) -> String {
        let mut out = String::new();
        if self.target == EndpointTarget::Zone {
            out.push_str(ZONE_PREFIX);
        }
        out.push_str(&self.id);
        if let Some(side) = self.side {
            out.push('.');
            out.push_str(side.as_str());
            if let Some(frac) = self.frac {
                out.push('@');
                out.push_str(&frac.to_string());
            }
        }
        out
    }
}

/// `\s` of the loader: Unicode whitespace, which for Python also covers the ASCII separators U+001C to U+001F.
fn is_space(c: char) -> bool {
    c.is_whitespace() || ('\x1c'..='\x1f').contains(&c)
}

fn spaces<'a>(input: &mut &'a str) -> winnow::Result<&'a str> {
    take_while(0.., is_space).parse_next(input)
}

/// The text of `t` from byte `at` on.
fn tail(t: &str, at: usize) -> &str {
    t.get(at..).unwrap_or("")
}

/// A string edge cut where the loader's `parse_edge` cuts it, keeping the exact spacing so a rewrite changes only
/// what it must: `{lead}{src}{gap1}{op}{gap2}{dst}{tail}`, where `tail` is empty or ` : label`.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct EdgeText {
    /// Whitespace before the source.
    pub lead: String,
    /// The text left of the operator.
    pub src: String,
    /// Whitespace before the operator.
    pub gap1: String,
    /// The operator.
    pub op: EdgeOp,
    /// Whitespace after the operator.
    pub gap2: String,
    /// The text right of the operator, without the label.
    pub dst: String,
    /// Whatever follows `dst`: blanks, `:` and the label.
    pub tail: String,
    label: Option<String>,
}

impl EdgeText {
    /// Read an edge string, or `None` when the loader would reject it.
    #[must_use]
    pub fn parse(t: &str) -> Option<EdgeText> {
        let lead_run = spaces.parse_peek(t).ok()?.1.len();
        // the lead is greedy and gives characters back; the source is lazy
        let lead_ends = t[..lead_run].char_indices().map(|(i, _)| i).chain([lead_run]).rev();
        for lead_end in lead_ends {
            let mut src_end = lead_end;
            for c in tail(t, lead_end).chars() {
                if c == '\n' {
                    break;
                }
                src_end += c.len_utf8();
                let mut input = tail(t, src_end);
                let gap1 = spaces(&mut input).unwrap_or("");
                let op_at = src_end + gap1.len();
                // all four operators are tried in order at this position
                for op in EdgeOp::ALL {
                    let Ok(after) = literal::<_, _, ()>(op.as_str()).parse_peek(tail(t, op_at)).map(|(after, _)| after) else { continue };
                    let gap2_from = t.len() - after.len();
                    if let Some(rest) = Self::rest(t, gap2_from) {
                        return Some(EdgeText {
                            lead: t[..lead_end].to_owned(),
                            src: t[lead_end..src_end].to_owned(),
                            gap1: t[src_end..op_at].to_owned(),
                            op,
                            gap2: t[gap2_from..rest.dst_from].to_owned(),
                            dst: t[rest.dst_from..rest.dst_to].to_owned(),
                            tail: t[rest.dst_to..].to_owned(),
                            label: rest.label,
                        });
                    }
                }
            }
        }
        None
    }

    /// The part after the operator at `from`: `\s*` `(?:zone:)?[^:]+?` `\s*` `(?::\s*(.*))?` `$`.
    fn rest(t: &str, from: usize) -> Option<Rest> {
        let run = spaces.parse_peek(tail(t, from)).ok()?.1.len();
        let gap_ends = t[from..from + run].char_indices().map(|(i, _)| from + i).chain([from + run]).rev();
        for dst_from in gap_ends {
            let zone = tail(t, dst_from).starts_with(ZONE_PREFIX);
            let starts = if zone { vec![dst_from + ZONE_PREFIX.len(), dst_from] } else { vec![dst_from] };
            for body in starts {
                let mut end = body;
                for c in tail(t, body).chars() {
                    if c == ':' {
                        break;
                    }
                    end += c.len_utf8();
                    if let Some(label) = Self::end(t, end) {
                        return Some(Rest { dst_from, dst_to: end, label: (!label.is_empty()).then_some(label) });
                    }
                }
            }
        }
        None
    }

    /// Whether the text can finish after a destination that ends at `at`: blanks, then the end or `:` and a label.
    /// The result is the label, empty when there is none.
    fn end(t: &str, at: usize) -> Option<String> {
        let mut input = tail(t, at);
        spaces(&mut input).ok()?;
        if input.is_empty() {
            return Some(String::new());
        }
        let mut after = input.strip_prefix(':')?;
        spaces(&mut after).ok()?;
        let label = after.split('\n').next().unwrap_or("");
        let rest = &after[label.len()..];
        // `$`: the end, or one final newline
        (rest.is_empty() || rest == "\n").then(|| label.to_owned())
    }

    /// The label after the colon, or none.
    #[must_use]
    pub fn label(&self) -> Option<&str> {
        self.label.as_deref()
    }

    /// The loader's `arrow` value.
    #[must_use]
    pub fn arrow(&self) -> &'static str {
        self.op.arrow()
    }

    /// The edge with a new label (or none), the spacing before the colon kept.
    #[must_use]
    pub fn with_label(&self, label: Option<&str>) -> String {
        let ws = &self.tail[..self.tail.len() - self.tail.trim_start().len()];
        let tail = match label {
            Some(l) => format!("{ws}: {l}"),
            None => String::new(),
        };
        self.render(&self.src, &self.dst, &tail)
    }

    fn render(&self, src: &str, dst: &str, tail: &str) -> String {
        format!("{}{src}{}{}{}{dst}{tail}", self.lead, self.gap1, self.op.as_str(), self.gap2)
    }

    /// `(from, to)` as the loader reads them: `<-` points the other way.
    #[must_use]
    pub fn ends(&self) -> (&str, &str) {
        if self.op == EdgeOp::Backward { (&self.dst, &self.src) } else { (&self.src, &self.dst) }
    }

    /// The edge with new ends, in the loader's `(from, to)` order.
    #[must_use]
    pub fn with_ends(&self, from: &str, to: &str) -> String {
        let (l, r) = if self.op == EdgeOp::Backward { (to, from) } else { (from, to) };
        self.render(l, r, &self.tail)
    }
}

struct Rest {
    dst_from: usize,
    dst_to: usize,
    label: Option<String>,
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::Value;

    fn vectors() -> Value {
        serde_json::from_str(include_str!("../../schema/edge_vectors.json")).unwrap()
    }

    #[test]
    fn edge_strings_parse_as_the_loader_parses_them() {
        let v = vectors();
        let cases = v["edges"].as_array().unwrap();
        assert!(cases.len() >= 30);
        for case in cases {
            let input = case["input"].as_str().unwrap();
            let got = EdgeText::parse(input).map(|p| {
                let (src, dst) = p.ends();
                serde_json::json!({"src": src, "dst": dst, "label": p.label(), "arrow": p.arrow()})
            });
            let want = (!case["parsed"].is_null()).then(|| case["parsed"].clone());
            assert_eq!(got, want, "{input:?}");
        }
    }

    #[test]
    fn edge_ends_split_as_the_loader_splits_them() {
        let v = vectors();
        for case in v["endpoints"].as_array().unwrap() {
            let input = case["input"].as_str().unwrap();
            let raw = split_endpoint(input);
            let target = if raw.target == EndpointTarget::Zone { "zone" } else { "node" };
            let got = serde_json::json!({"target": target, "id": raw.id, "side": raw.side, "frac": raw.frac});
            assert_eq!(got, case["raw"], "{input:?}");
            let typed = input.parse::<Endpoint>().ok().map(|e| {
                let target = if e.target == EndpointTarget::Zone { "zone" } else { "node" };
                serde_json::json!({"target": target, "id": e.id, "side": e.side.map(Side::as_str), "frac": e.frac})
            });
            let want = (!case["typed"].is_null()).then(|| case["typed"].clone());
            assert_eq!(typed, want, "{input:?}");
        }
    }

    #[test]
    fn an_operator_that_fails_the_rest_falls_back_to_the_next() {
        let p = EdgeText::parse("a<->b").unwrap();
        assert_eq!(p.op, EdgeOp::Both);
        let p = EdgeText::parse("a --> b").unwrap();
        assert_eq!((p.op, p.dst.as_str()), (EdgeOp::Line, "> b"));
        let p = EdgeText::parse("a -> zone:").unwrap();
        assert_eq!((p.dst.as_str(), p.label()), ("zone", None));
    }

    #[test]
    fn spacing_survives_a_rewrite() {
        let p = EdgeText::parse("  a   ->  b : old").unwrap();
        assert_eq!(p.with_label(Some("new")), "  a   ->  b : new");
        assert_eq!(p.with_label(None), "  a   ->  b");
        assert_eq!(p.with_ends("x", "y"), "  x   ->  y : old");
        let back = EdgeText::parse("a <- b").unwrap();
        assert_eq!(back.ends(), ("b", "a"));
        assert_eq!(back.with_ends("p", "q"), "q <- p");
    }

    #[test]
    fn endpoints_render_back() {
        for s in ["a", "a.right", "a.right@0.3", "zone:z.top@0.75", "zone:z"] {
            assert_eq!(s.parse::<Endpoint>().unwrap().render(), s);
        }
        assert_eq!("a.up".parse::<Endpoint>(), Err(EndpointError::Side("up".into())));
        assert_eq!("a.top@x".parse::<Endpoint>(), Err(EndpointError::Fraction("x".into())));
    }
}
