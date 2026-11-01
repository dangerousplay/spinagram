//! CSS selectors, matching and the cascade: a port of the matching half of `spinagram/css.py`.
//!
//! Python keeps stylesheet tokenizing (tinycss2), value typing, warnings and the trace. Rust only parses
//! selector texts Python has already accepted, so parse errors here are a safety net, not the user-facing path.

use regex::Regex;
use std::sync::OnceLock;

#[derive(Clone, Debug, Default, PartialEq)]
pub struct Compound {
    /// `None` or `*` match any type.
    pub typ: Option<String>,
    pub id: Option<String>,
    pub classes: Vec<String>,
    /// `(name, value)`; `None` is a presence test.
    pub attrs: Vec<(String, Option<String>)>,
    pub pseudos: Vec<Pseudo>,
}

#[derive(Clone, Debug, PartialEq)]
pub enum Pseudo {
    FirstChild,
    LastChild,
    Root,
    Not(Vec<Selector>),
}

/// Combinator before a compound: none (first), descendant or child.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Comb {
    None,
    Descendant,
    Child,
}

#[derive(Clone, Debug, PartialEq)]
pub struct Selector {
    pub text: String,
    pub parts: Vec<(Comb, Compound)>,
    pub pseudo_element: Option<String>,
}

impl Selector {
    /// `(ids, classes + attributes + pseudo-classes, types + pseudo-element)`
    pub fn specificity(&self) -> (u32, u32, u32) {
        let (mut a, mut b, mut c) = (0, 0, 0);
        for (_, comp) in &self.parts {
            a += comp.id.is_some() as u32;
            b += (comp.classes.len() + comp.attrs.len()) as u32;
            c += comp.typ.as_deref().is_some_and(|t| t != "*") as u32;
            for p in &comp.pseudos {
                match p {
                    Pseudo::Not(list) => {
                        let (sa, sb, sc) = list.iter().map(Selector::specificity).max().unwrap_or((0, 0, 0));
                        (a, b, c) = (a + sa, b + sb, c + sc);
                    }
                    _ => b += 1,
                }
            }
        }
        (a, b, c + self.pseudo_element.is_some() as u32)
    }
}

const IDENT: &str = r"-?[A-Za-z_][\w-]*";

fn token_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| {
        Regex::new(&format!(
            r#"\A(?:(?P<ws>\s+)|(?P<child>>)|(?P<comma>,)|(?P<pe>::{IDENT})|(?P<not>:not\()|(?P<pc>:{IDENT})|(?P<id>\#{IDENT})|(?P<cls>\.{IDENT})|(?P<attr>\[\s*{IDENT}\s*(?:=\s*(?:"[^"]*"|'[^']*'|[^\]\s]+)\s*)?\])|(?P<type>{IDENT}|\*)|(?P<close>\)))"#
        ))
        .expect("the token pattern is valid")
    })
}

const KINDS: [&str; 11] = ["ws", "child", "comma", "pe", "not", "pc", "id", "cls", "attr", "type", "close"];

fn split_top(text: &str) -> Vec<String> {
    let (mut out, mut depth, mut cur) = (Vec::new(), 0i32, String::new());
    for ch in text.chars() {
        match ch {
            '(' => depth += 1,
            ')' => depth -= 1,
            _ => {}
        }
        if ch == ',' && depth == 0 {
            out.push(std::mem::take(&mut cur));
        } else {
            cur.push(ch);
        }
    }
    out.push(cur);
    out
}

/// `parse_selectors`: a comma list of selectors.
pub fn parse_selectors(text: &str) -> Result<Vec<Selector>, String> {
    let mut out = Vec::new();
    for piece in split_top(text) {
        let piece = piece.trim();
        if !piece.is_empty() {
            out.push(parse_one(piece)?);
        }
    }
    if out.is_empty() {
        return Err(format!("empty selector {text:?}"));
    }
    Ok(out)
}

fn parse_one(text: &str) -> Result<Selector, String> {
    let mut pos = 0;
    let mut parts: Vec<(Comb, Compound)> = Vec::new();
    let mut comb = Comb::None;
    let mut comp: Option<Compound> = None;
    let mut pe: Option<String> = None;
    while pos < text.len() {
        let rest = &text[pos..];
        let caps = token_re().captures(rest).ok_or_else(|| {
            format!("cannot parse selector {text:?} near {:?}", rest.chars().take(12).collect::<String>())
        })?;
        let kind = KINDS.iter().find(|k| caps.name(k).is_some()).copied().expect("a group matched");
        let tok = caps.get(0).expect("whole match").as_str();
        pos += tok.len();
        if kind == "ws" || kind == "child" {
            if let Some(c) = comp.take() {
                parts.push((comb, c));
                comb = Comb::Descendant;
            }
            if kind == "child" {
                comb = Comb::Child;
            }
            continue;
        }
        if pe.is_some() {
            return Err(format!("pseudo-element must end the selector: {text:?}"));
        }
        let c = comp.get_or_insert_with(Compound::default);
        match kind {
            "type" => c.typ = Some(tok.to_string()),
            "id" => c.id = Some(tok[1..].to_string()),
            "cls" => c.classes.push(tok[1..].to_string()),
            "attr" => {
                let body = tok[1..tok.len() - 1].trim();
                let (name, val) = match body.split_once('=') {
                    Some((n, v)) => (n, Some(v.trim())),
                    None => (body, None),
                };
                let value = val.map(|v| {
                    if v.starts_with(['"', '\'']) {
                        v[1..v.len() - 1].to_string()
                    } else {
                        v.to_string()
                    }
                });
                c.attrs.push((name.trim().to_string(), value));
            }
            "pc" => c.pseudos.push(match &tok[1..] {
                "first-child" => Pseudo::FirstChild,
                "last-child" => Pseudo::LastChild,
                "root" => Pseudo::Root,
                name => return Err(format!("unsupported pseudo-class :{name}")),
            }),
            "not" => {
                let (mut depth, start) = (1i32, pos);
                let bytes = text.as_bytes();
                while pos < text.len() && depth != 0 {
                    match bytes[pos] {
                        b'(' => depth += 1,
                        b')' => depth -= 1,
                        _ => {}
                    }
                    pos += 1;
                }
                if depth != 0 {
                    return Err(format!("unclosed :not( in {text:?}"));
                }
                c.pseudos.push(Pseudo::Not(parse_selectors(&text[start..pos - 1])?));
            }
            "pe" => match &tok[2..] {
                name @ ("title" | "body" | "label") => pe = Some(name.to_string()),
                name => return Err(format!("unsupported pseudo-element ::{name}")),
            },
            _ => return Err(format!("unexpected {tok:?} in selector {text:?}")),
        }
    }
    if let Some(c) = comp {
        parts.push((comb, c));
    }
    if parts.is_empty() {
        if pe.is_none() {
            return Err(format!("empty selector {text:?}"));
        }
        parts.push((Comb::None, Compound::default())); // "::label" alone: any element
    }
    parts[0].0 = Comb::None;
    Ok(Selector { text: text.to_string(), parts, pseudo_element: pe })
}

/// A canonical one-line form of a selector, for comparing with Python's dataclasses in tests.
pub fn canon(sel: &Selector) -> String {
    let parts: Vec<String> = sel
        .parts
        .iter()
        .map(|(comb, c)| {
            let comb = match comb {
                Comb::None => "",
                Comb::Descendant => " ",
                Comb::Child => ">",
            };
            let attrs: Vec<String> =
                c.attrs.iter().map(|(n, v)| format!("{n}={}", v.as_deref().unwrap_or("\u{0}"))).collect();
            let ps: Vec<String> = c
                .pseudos
                .iter()
                .map(|p| match p {
                    Pseudo::FirstChild => "first-child".into(),
                    Pseudo::LastChild => "last-child".into(),
                    Pseudo::Root => "root".into(),
                    Pseudo::Not(list) => format!("not[{}]", list.iter().map(canon).collect::<Vec<_>>().join("/")),
                })
                .collect();
            format!(
                "[{comb}|{}|{}|{}|{}|{}]",
                c.typ.as_deref().unwrap_or("-"),
                c.id.as_deref().unwrap_or("-"),
                c.classes.join(","),
                attrs.join(";"),
                ps.join(",")
            )
        })
        .collect();
    let (a, b, c) = sel.specificity();
    format!("{}~{}~({a},{b},{c})~{}", sel.text, sel.pseudo_element.as_deref().unwrap_or("-"), parts.join(""))
}

#[cfg(test)]
mod tests {
    use super::*;

    // Expected strings come from Python's parse_selectors (structure and specificity), see canon().

    #[test]
    fn parse_type_node() {
        let got: Vec<String> = parse_selectors(r####"node"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"node~-~(0,0,1)~[|node|-|||]"####]);
    }

    #[test]
    fn parse_type_kind() {
        let got: Vec<String> = parse_selectors(r####"state"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"state~-~(0,0,1)~[|state|-|||]"####]);
    }

    #[test]
    fn parse_universal() {
        let got: Vec<String> = parse_selectors(r####"*"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"*~-~(0,0,0)~[|*|-|||]"####]);
    }

    #[test]
    fn parse_class() {
        let got: Vec<String> = parse_selectors(r####".hot"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####".hot~-~(0,1,0)~[|-|-|hot||]"####]);
    }

    #[test]
    fn parse_two_classes() {
        let got: Vec<String> = parse_selectors(r####".a.b"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####".a.b~-~(0,2,0)~[|-|-|a,b||]"####]);
    }

    #[test]
    fn parse_id() {
        let got: Vec<String> = parse_selectors(r####"#n1"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"#n1~-~(1,0,0)~[|-|n1|||]"####]);
    }

    #[test]
    fn parse_type_id_class() {
        let got: Vec<String> = parse_selectors(r####"node#n1.hot"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"node#n1.hot~-~(1,1,1)~[|node|n1|hot||]"####]);
    }

    #[test]
    fn parse_attr_presence() {
        let got: Vec<String> = parse_selectors(r####"[icon]"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"[icon]~-~(0,1,0)~[|-|-||icon= |]"####]);
    }

    #[test]
    fn parse_attr_unquoted() {
        let got: Vec<String> = parse_selectors(r####"[kind=decision]"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"[kind=decision]~-~(0,1,0)~[|-|-||kind=decision|]"####]);
    }

    #[test]
    fn parse_attr_double_quoted() {
        let got: Vec<String> = parse_selectors(r####"[label="a b"]"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"[label="a b"]~-~(0,1,0)~[|-|-||label=a b|]"####]);
    }

    #[test]
    fn parse_attr_single_quoted() {
        let got: Vec<String> = parse_selectors(r####"[label='x y']"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"[label='x y']~-~(0,1,0)~[|-|-||label=x y|]"####]);
    }

    #[test]
    fn parse_attr_spaces() {
        let got: Vec<String> = parse_selectors(r####"[ kind = box ]"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"[ kind = box ]~-~(0,1,0)~[|-|-||kind=box|]"####]);
    }

    #[test]
    fn parse_descendant() {
        let got: Vec<String> = parse_selectors(r####"group node"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"group node~-~(0,0,2)~[|group|-|||][ |node|-|||]"####]);
    }

    #[test]
    fn parse_child() {
        let got: Vec<String> = parse_selectors(r####"group > node"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"group > node~-~(0,0,2)~[|group|-|||][>|node|-|||]"####]);
    }

    #[test]
    fn parse_child_tight() {
        let got: Vec<String> = parse_selectors(r####"group>node"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"group>node~-~(0,0,2)~[|group|-|||][>|node|-|||]"####]);
    }

    #[test]
    fn parse_three_levels() {
        let got: Vec<String> = parse_selectors(r####"diagram group > node.hot"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"diagram group > node.hot~-~(0,1,3)~[|diagram|-|||][ |group|-|||][>|node|-|hot||]"####]);
    }

    #[test]
    fn parse_list() {
        let got: Vec<String> = parse_selectors(r####"node, edge , .x"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"node~-~(0,0,1)~[|node|-|||]"####, r####"edge~-~(0,0,1)~[|edge|-|||]"####, r####".x~-~(0,1,0)~[|-|-|x||]"####]);
    }

    #[test]
    fn parse_first_child() {
        let got: Vec<String> = parse_selectors(r####"node:first-child"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"node:first-child~-~(0,1,1)~[|node|-|||first-child]"####]);
    }

    #[test]
    fn parse_last_child() {
        let got: Vec<String> = parse_selectors(r####"node:last-child"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"node:last-child~-~(0,1,1)~[|node|-|||last-child]"####]);
    }

    #[test]
    fn parse_root() {
        let got: Vec<String> = parse_selectors(r####":root"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####":root~-~(0,1,0)~[|-|-|||root]"####]);
    }

    #[test]
    fn parse_root_type() {
        let got: Vec<String> = parse_selectors(r####"diagram:root"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"diagram:root~-~(0,1,1)~[|diagram|-|||root]"####]);
    }

    #[test]
    fn parse_not_simple() {
        let got: Vec<String> = parse_selectors(r####"node:not(.hot)"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"node:not(.hot)~-~(0,1,1)~[|node|-|||not[.hot~-~(0,1,0)~[|-|-|hot||]]]"####]);
    }

    #[test]
    fn parse_not_list() {
        let got: Vec<String> = parse_selectors(r####"node:not(.a, #b)"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"node:not(.a, #b)~-~(1,0,1)~[|node|-|||not[.a~-~(0,1,0)~[|-|-|a||]/#b~-~(1,0,0)~[|-|b|||]]]"####]);
    }

    #[test]
    fn parse_not_nested() {
        let got: Vec<String> = parse_selectors(r####"node:not(:not(.a))"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"node:not(:not(.a))~-~(0,1,1)~[|node|-|||not[:not(.a)~-~(0,1,0)~[|-|-|||not[.a~-~(0,1,0)~[|-|-|a||]]]]]"####]);
    }

    #[test]
    fn parse_not_with_combinator() {
        let got: Vec<String> = parse_selectors(r####"node:not(group node)"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"node:not(group node)~-~(0,0,3)~[|node|-|||not[group node~-~(0,0,2)~[|group|-|||][ |node|-|||]]]"####]);
    }

    #[test]
    fn parse_not_pseudo_class() {
        let got: Vec<String> = parse_selectors(r####"node:not(:first-child)"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"node:not(:first-child)~-~(0,1,1)~[|node|-|||not[:first-child~-~(0,1,0)~[|-|-|||first-child]]]"####]);
    }

    #[test]
    fn parse_pe_title() {
        let got: Vec<String> = parse_selectors(r####"node::title"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"node::title~title~(0,0,2)~[|node|-|||]"####]);
    }

    #[test]
    fn parse_pe_body() {
        let got: Vec<String> = parse_selectors(r####"node.hot::body"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"node.hot::body~body~(0,1,2)~[|node|-|hot||]"####]);
    }

    #[test]
    fn parse_pe_label_alone() {
        let got: Vec<String> = parse_selectors(r####"::label"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"::label~label~(0,0,1)~[|-|-|||]"####]);
    }

    #[test]
    fn parse_pe_title_alone() {
        let got: Vec<String> = parse_selectors(r####"::title"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"::title~title~(0,0,1)~[|-|-|||]"####]);
    }

    #[test]
    fn parse_pe_after_child() {
        let got: Vec<String> = parse_selectors(r####"group > node::label"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"group > node::label~label~(0,0,3)~[|group|-|||][>|node|-|||]"####]);
    }

    #[test]
    fn parse_list_with_pe() {
        let got: Vec<String> = parse_selectors(r####"node::title, edge::label"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"node::title~title~(0,0,2)~[|node|-|||]"####, r####"edge::label~label~(0,0,2)~[|edge|-|||]"####]);
    }

    #[test]
    fn parse_ident_dash() {
        let got: Vec<String> = parse_selectors(r####"my-kind"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"my-kind~-~(0,0,1)~[|my-kind|-|||]"####]);
    }

    #[test]
    fn parse_ident_underscore() {
        let got: Vec<String> = parse_selectors(r####"_x"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"_x~-~(0,0,1)~[|_x|-|||]"####]);
    }

    #[test]
    fn parse_leading_dash_class() {
        let got: Vec<String> = parse_selectors(r####".-x"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####".-x~-~(0,1,0)~[|-|-|-x||]"####]);
    }

    #[test]
    fn parse_universal_child() {
        let got: Vec<String> = parse_selectors(r####"* > *"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"* > *~-~(0,0,0)~[|*|-|||][>|*|-|||]"####]);
    }

    #[test]
    fn parse_trailing_comb_ignored() {
        let got: Vec<String> = parse_selectors(r####"node >"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"node >~-~(0,0,1)~[|node|-|||]"####]);
    }

    #[test]
    fn parse_spec_complex() {
        let got: Vec<String> = parse_selectors(r####"group#g.a.b > node[kind=box][icon]:first-child:not(.x, #y.z)::body"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"group#g.a.b > node[kind=box][icon]:first-child:not(.x, #y.z)::body~body~(2,6,3)~[|group|g|a,b||][>|node|-||kind=box;icon= |first-child,not[.x~-~(0,1,0)~[|-|-|x||]/#y.z~-~(1,1,0)~[|-|y|z||]]]"####]);
    }

    #[test]
    fn parse_not_specificity_max() {
        let got: Vec<String> = parse_selectors(r####"node:not(.a, #b.c)"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"node:not(.a, #b.c)~-~(1,1,1)~[|node|-|||not[.a~-~(0,1,0)~[|-|-|a||]/#b.c~-~(1,1,0)~[|-|b|c||]]]"####]);
    }
}
