//! CSS selectors, matching and the cascade: the matching half of `spinagram/css.py`.
//!
//! Selector tokenizing and parsing are `cssparser` and the Servo `selectors` crate, which also matches and
//! computes specificity. Only the glue is ours: the element tree, the three pseudo-elements and the type names
//! (a node answers to its type and its kinds). Python keeps stylesheet tokenizing (tinycss2), value typing,
//! warnings and the trace, and has already accepted every selector text it sends.
//!
//! SPEC_DEVIATION: `selectors` follows the CSS grammar, which is stricter than spinagram's regex parser in two
//! places: a leading or trailing combinator (`> a`, `a >`) and an unquoted attribute value that is not an
//! identifier (`[w=100px]`). Parsing those fails here and the caller falls back to the Python path, so results
//! stay identical. No crate reproduces spinagram's looser grammar.

use cssparser::{CowRcStr, ParseError, Parser as CssParser, ToCss};
use precomputed_hash::PrecomputedHash;
use selectors::attr::{AttrSelectorOperation, CaseSensitivity, NamespaceConstraint};
use selectors::context::{
    MatchingContext, MatchingForInvalidation, MatchingMode, NeedsSelectorFlags, QuirksMode, SelectorCaches,
};
use selectors::matching::{matches_selector, ElementSelectorFlags};
use selectors::parser::{NonTSPseudoClass, Parser, PseudoElement, SelectorImpl, SelectorParseErrorKind};
use selectors::{Element, OpaqueElement};
use std::borrow::Borrow;
use std::collections::HashMap;
use std::fmt;

/// The string type of every selector part (identifiers, type names, attribute values).
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct Str(String);

impl From<&str> for Str {
    fn from(s: &str) -> Self {
        Str(s.to_string())
    }
}

impl Borrow<str> for Str {
    fn borrow(&self) -> &str {
        &self.0
    }
}

impl AsRef<str> for Str {
    fn as_ref(&self) -> &str {
        &self.0
    }
}

impl ToCss for Str {
    fn to_css<W: fmt::Write>(&self, dest: &mut W) -> fmt::Result {
        cssparser::serialize_identifier(&self.0, dest)
    }
}

impl PrecomputedHash for Str {
    fn precomputed_hash(&self) -> u32 {
        self.0.bytes().fold(2166136261u32, |h, b| (h ^ b as u32).wrapping_mul(16777619))
    }
}

/// The pseudo-elements spinagram styles.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Pe {
    Title,
    Body,
    Label,
}

impl Pe {
    fn name(self) -> &'static str {
        match self {
            Pe::Title => "title",
            Pe::Body => "body",
            Pe::Label => "label",
        }
    }
}

impl ToCss for Pe {
    fn to_css<W: fmt::Write>(&self, dest: &mut W) -> fmt::Result {
        write!(dest, "::{}", self.name())
    }
}

impl PseudoElement for Pe {}

/// Spinagram has no pseudo-classes beyond the built-in `:first-child`, `:last-child`, `:root` and `:not()`.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum NoPseudoClass {}

impl ToCss for NoPseudoClass {
    fn to_css<W: fmt::Write>(&self, _: &mut W) -> fmt::Result {
        match *self {}
    }
}

impl NonTSPseudoClass for NoPseudoClass {
    fn is_active_or_hover(&self) -> bool {
        match *self {}
    }

    fn is_user_action_state(&self) -> bool {
        match *self {}
    }
}

#[derive(Clone, Debug)]
pub struct Impl;

impl SelectorImpl for Impl {
    type ExtraMatchingData<'a> = ();
    type AttrValue = Str;
    type Identifier = Str;
    type LocalName = Str;
    type NamespaceUrl = Str;
    type NamespacePrefix = Str;
    type BorrowedNamespaceUrl = str;
    type BorrowedLocalName = str;
    type NonTSPseudoClass = NoPseudoClass;
    type PseudoElement = Pe;
}

struct SelectorParser;

impl<'i> Parser<'i> for SelectorParser {
    type Impl = Impl;
    type Error = SelectorParseErrorKind;

    fn parse_pseudo_element(&self, name: CowRcStr<'i>) -> Result<Pe, ParseError<Self::Error>> {
        match &*name {
            "title" => Ok(Pe::Title),
            "body" => Ok(Pe::Body),
            "label" => Ok(Pe::Label),
            _ => Err(ParseError::custom(SelectorParseErrorKind::UnsupportedPseudoClassOrElement)),
        }
    }
}

/// A parsed selector with the text it came from.
#[derive(Clone, Debug)]
pub struct Selector {
    pub text: String,
    inner: selectors::parser::Selector<Impl>,
    pub pseudo_element: Option<Pe>,
}

impl Selector {
    /// `(ids, classes + attributes + pseudo-classes, types + pseudo-element)`; `:not()` counts its most specific
    /// argument. Components clamp at 1023 in the crate, far above any real selector.
    pub fn specificity(&self) -> (u32, u32, u32) {
        let s = self.inner.specificity();
        (s >> 20, (s >> 10) & 0x3ff, s & 0x3ff)
    }
}

/// A comma list of selectors, each with its own source text.
pub fn parse_selectors(text: &str) -> Result<Vec<Selector>, String> {
    let mut parser = CssParser::new(text);
    let list = parser
        .parse_comma_separated(|p| {
            let start = p.position();
            let inner = selectors::parser::Selector::parse(&SelectorParser, p)?;
            let src = p.slice_from(start).trim().to_string();
            let pseudo_element = inner.pseudo_element().copied();
            Ok(Selector { text: src, inner, pseudo_element })
        })
        .map_err(|e| format!("cannot parse selector {text:?}: {:?}", e.kind))?;
    if list.is_empty() {
        return Err(format!("empty selector {text:?}"));
    }
    Ok(list)
}

// matching ---------------------------------------------------------------------------------------

/// A declaration as the stylesheet or an inline `css=` gave it.
#[derive(Clone, Debug, PartialEq)]
pub struct Decl {
    pub name: String,
    pub value: String,
    pub important: bool,
}

/// One element of the style tree: the diagram, a group, a node, an edge...
#[derive(Clone, Debug, Default)]
pub struct Node {
    pub parent: Option<usize>,
    pub children: Vec<usize>,
    /// Position among the parent's children (set by `Tree::link`).
    pub pos: usize,
    pub typ: String,
    /// Extra type names it answers to (node kind).
    pub kinds: Vec<String>,
    pub id: Option<String>,
    pub classes: Vec<String>,
    pub attrs: HashMap<String, String>,
    pub inline: Vec<Decl>,
}

/// Elements in pre-order; index 0 is the root. Children are listed in document order.
#[derive(Clone, Debug, Default)]
pub struct Tree {
    pub nodes: Vec<Node>,
}

impl Tree {
    /// Link `children` and `pos` from each node's `parent` (nodes must be in pre-order).
    pub fn link(&mut self) {
        for n in &mut self.nodes {
            n.children.clear();
        }
        for i in 0..self.nodes.len() {
            if let Some(p) = self.nodes[i].parent {
                self.nodes[i].pos = self.nodes[p].children.len();
                self.nodes[p].children.push(i);
            }
        }
    }
}

#[derive(Clone, Copy, Debug)]
struct El<'a> {
    tree: &'a Tree,
    i: usize,
}

impl<'a> El<'a> {
    fn node(&self) -> &'a Node {
        &self.tree.nodes[self.i]
    }

    fn at(&self, i: usize) -> El<'a> {
        El { tree: self.tree, i }
    }
}

impl Element for El<'_> {
    type Impl = Impl;

    fn opaque(&self) -> OpaqueElement {
        OpaqueElement::new(self.node())
    }

    fn parent_element(&self) -> Option<Self> {
        self.node().parent.map(|p| self.at(p))
    }

    fn parent_node_is_shadow_root(&self) -> bool {
        false
    }

    fn containing_shadow_host(&self) -> Option<Self> {
        None
    }

    fn is_pseudo_element(&self) -> bool {
        false
    }

    fn prev_sibling_element(&self) -> Option<Self> {
        let n = self.node();
        let parent = &self.tree.nodes[n.parent?];
        n.pos.checked_sub(1).map(|p| self.at(parent.children[p]))
    }

    fn next_sibling_element(&self) -> Option<Self> {
        let n = self.node();
        let parent = &self.tree.nodes[n.parent?];
        parent.children.get(n.pos + 1).map(|&c| self.at(c))
    }

    fn first_element_child(&self) -> Option<Self> {
        self.node().children.first().map(|&c| self.at(c))
    }

    fn is_html_element_in_html_document(&self) -> bool {
        false
    }

    fn has_local_name(&self, name: &str) -> bool {
        let n = self.node();
        n.typ == name || n.kinds.iter().any(|k| k == name)
    }

    fn has_namespace(&self, _ns: &str) -> bool {
        true
    }

    fn is_same_type(&self, other: &Self) -> bool {
        self.node().typ == other.node().typ
    }

    fn attr_matches(&self, _ns: &NamespaceConstraint<&Str>, local_name: &Str, operation: &AttrSelectorOperation<&Str>) -> bool {
        self.node().attrs.get(&local_name.0).is_some_and(|have| operation.eval_str(have))
    }

    fn match_non_ts_pseudo_class(&self, pc: &NoPseudoClass, _: &mut MatchingContext<Impl>) -> bool {
        match *pc {}
    }

    fn match_pseudo_element(&self, _pe: &Pe, _: &mut MatchingContext<Impl>) -> bool {
        true // the pseudo-element is the caller's concern: the originating element matches
    }

    fn apply_selector_flags(&self, _flags: ElementSelectorFlags) {}

    fn is_link(&self) -> bool {
        false
    }

    fn is_html_slot_element(&self) -> bool {
        false
    }

    fn has_id(&self, id: &Str, case_sensitivity: CaseSensitivity) -> bool {
        self.node().id.as_deref().is_some_and(|have| case_sensitivity.eq(have.as_bytes(), id.0.as_bytes()))
    }

    fn has_class(&self, name: &Str, case_sensitivity: CaseSensitivity) -> bool {
        self.node().classes.iter().any(|c| case_sensitivity.eq(c.as_bytes(), name.0.as_bytes()))
    }

    fn has_custom_state(&self, _name: &Str) -> bool {
        false
    }

    fn imported_part(&self, _name: &Str) -> Option<Str> {
        None
    }

    fn is_part(&self, _name: &Str) -> bool {
        false
    }

    fn is_empty(&self) -> bool {
        self.node().children.is_empty()
    }

    fn is_root(&self) -> bool {
        self.node().parent.is_none()
    }

    fn add_element_unique_hashes(&self, _filter: &mut selectors::bloom::BloomFilter) -> bool {
        false
    }
}

/// Matches selectors against a tree; keeps the crate's caches between calls.
#[derive(Default)]
pub struct Matcher {
    caches: SelectorCaches,
}

impl Matcher {
    /// Right-to-left match of a selector (its pseudo-element is the caller's concern).
    pub fn matches(&mut self, sel: &Selector, tree: &Tree, el: usize) -> bool {
        let mode = if sel.pseudo_element.is_some() { MatchingMode::ForStatelessPseudoElement } else { MatchingMode::Normal };
        let mut ctx = MatchingContext::new(mode, None, &mut self.caches, QuirksMode::NoQuirks, NeedsSelectorFlags::No, MatchingForInvalidation::No);
        matches_selector(&sel.inner, 0, None, &El { tree, i: el }, &mut ctx)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // Expected values come from Python: parse_selectors (text, pseudo-element, specificity) and matches() over
    // the tree in fixture().
    fn canon(sel: &Selector) -> String {
        let (a, b, c) = sel.specificity();
        format!("{}~{}~({a},{b},{c})", sel.text, sel.pseudo_element.map_or("-", Pe::name))
    }

    fn node(parent: Option<usize>, typ: &str, kinds: &[&str], id: Option<&str>, classes: &[&str], attrs: &[(&str, &str)]) -> Node {
        Node {
            parent,
            typ: typ.into(),
            kinds: kinds.iter().map(|k| k.to_string()).collect(),
            id: id.map(String::from),
            classes: classes.iter().map(|c| c.to_string()).collect(),
            attrs: attrs.iter().map(|(k, v)| (k.to_string(), v.to_string())).collect(),
            ..Node::default()
        }
    }

    fn tree(nodes: Vec<Node>) -> Tree {
        let mut t = Tree { nodes };
        t.link();
        t
    }

    fn match_set(text: &str, tree: &Tree) -> Vec<usize> {
        let sels = parse_selectors(text).unwrap();
        let mut m = Matcher::default();
        (0..tree.nodes.len()).filter(|&i| sels.iter().any(|s| m.matches(s, tree, i))).collect()
    }

    fn fixture() -> Tree {
        tree(vec![
        node(None, "diagram", &[], Some("d"), &[], &[]),
        node(Some(0), "group", &["group"], Some("g1"), &["a"], &[("label", "Net")]),
        node(Some(1), "node", &["box"], Some("n1"), &["hot", "a"], &[("kind", "box"), ("label", "a b"), ("icon", "x")]),
        node(Some(1), "node", &["decision"], Some("n2"), &[], &[("kind", "decision")]),
        node(Some(1), "region", &["group", "aws"], Some("r1"), &[], &[]),
        node(Some(4), "node", &["state"], Some("n3"), &["hot"], &[("kind", "state")]),
        node(Some(1), "node", &["text", "label"], None, &[], &[("label", "x y")]),
        node(Some(0), "node", &["box", "chip"], Some("n5"), &["b"], &[("kind", "box")]),
        node(Some(0), "edge", &[], None, &[], &[("from", "n1"), ("to", "n2")]),
        node(Some(0), "edge", &[], None, &["hot"], &[("label", "a b")]),
        ])
    }

    fn lone_root() -> Tree {
        tree(vec![
        node(None, "diagram", &[], Some("d"), &[], &[]),
        ])
    }

    #[test]
    fn match_type_node() {
        assert_eq!(match_set(r####"node"####, &fixture()), vec![2, 3, 5, 6, 7]);
    }

    #[test]
    fn match_type_kind() {
        assert_eq!(match_set(r####"state"####, &fixture()), vec![5]);
    }

    #[test]
    fn match_type_kind_alias() {
        assert_eq!(match_set(r####"chip"####, &fixture()), vec![7]);
    }

    #[test]
    fn match_type_group_alias() {
        assert_eq!(match_set(r####"group"####, &fixture()), vec![1, 4]);
    }

    #[test]
    fn match_universal() {
        assert_eq!(match_set(r####"*"####, &fixture()), vec![0, 1, 2, 3, 4, 5, 6, 7, 8, 9]);
    }

    #[test]
    fn match_class() {
        assert_eq!(match_set(r####".hot"####, &fixture()), vec![2, 5, 9]);
    }

    #[test]
    fn match_two_classes() {
        assert_eq!(match_set(r####".a.b"####, &fixture()), Vec::<usize>::new());
    }

    #[test]
    fn match_id() {
        assert_eq!(match_set(r####"#n1"####, &fixture()), vec![2]);
    }

    #[test]
    fn match_type_id_class() {
        assert_eq!(match_set(r####"node#n1.hot"####, &fixture()), vec![2]);
    }

    #[test]
    fn match_attr_presence() {
        assert_eq!(match_set(r####"[icon]"####, &fixture()), vec![2]);
    }

    #[test]
    fn match_attr_unquoted() {
        assert_eq!(match_set(r####"[kind=box]"####, &fixture()), vec![2, 7]);
    }

    #[test]
    fn match_attr_double_quoted() {
        assert_eq!(match_set(r####"[label="a b"]"####, &fixture()), vec![2, 9]);
    }

    #[test]
    fn match_attr_single_quoted() {
        assert_eq!(match_set(r####"[label='x y']"####, &fixture()), vec![6]);
    }

    #[test]
    fn match_attr_value_mismatch() {
        assert_eq!(match_set(r####"[kind=nope]"####, &fixture()), Vec::<usize>::new());
    }

    #[test]
    fn match_attr_spaces() {
        assert_eq!(match_set(r####"[ kind = decision ]"####, &fixture()), vec![3]);
    }

    #[test]
    fn match_descendant() {
        assert_eq!(match_set(r####"group node"####, &fixture()), vec![2, 3, 5, 6]);
    }

    #[test]
    fn match_descendant_skips_levels() {
        assert_eq!(match_set(r####"diagram node"####, &fixture()), vec![2, 3, 5, 6, 7]);
    }

    #[test]
    fn match_child() {
        assert_eq!(match_set(r####"group > node"####, &fixture()), vec![2, 3, 5, 6]);
    }

    #[test]
    fn match_child_tight() {
        assert_eq!(match_set(r####"group>node"####, &fixture()), vec![2, 3, 5, 6]);
    }

    #[test]
    fn match_child_not_grandchild() {
        assert_eq!(match_set(r####"diagram > node"####, &fixture()), vec![7]);
    }

    #[test]
    fn match_three_levels() {
        assert_eq!(match_set(r####"diagram group > node.hot"####, &fixture()), vec![2, 5]);
    }

    #[test]
    fn match_list() {
        assert_eq!(match_set(r####"edge, .a"####, &fixture()), vec![1, 2, 8, 9]);
    }

    #[test]
    fn match_first_child() {
        assert_eq!(match_set(r####"node:first-child"####, &fixture()), vec![2, 5]);
    }

    #[test]
    fn match_last_child() {
        assert_eq!(match_set(r####"node:last-child"####, &fixture()), vec![5, 6]);
    }

    #[test]
    fn match_root() {
        assert_eq!(match_set(r####":root"####, &fixture()), vec![0]);
    }

    #[test]
    fn match_root_type() {
        assert_eq!(match_set(r####"diagram:root"####, &fixture()), vec![0]);
    }

    #[test]
    fn match_root_not_child() {
        assert_eq!(match_set(r####"node:root"####, &fixture()), Vec::<usize>::new());
    }

    #[test]
    fn match_not_simple() {
        assert_eq!(match_set(r####"node:not(.hot)"####, &fixture()), vec![3, 6, 7]);
    }

    #[test]
    fn match_not_list() {
        assert_eq!(match_set(r####"node:not(.a, #n5)"####, &fixture()), vec![3, 5, 6]);
    }

    #[test]
    fn match_not_nested() {
        assert_eq!(match_set(r####"node:not(:not(.hot))"####, &fixture()), vec![2, 5]);
    }

    #[test]
    fn match_not_with_combinator() {
        assert_eq!(match_set(r####"node:not(group node)"####, &fixture()), vec![7]);
    }

    #[test]
    fn match_not_pseudo_class() {
        assert_eq!(match_set(r####"node:not(:first-child)"####, &fixture()), vec![3, 6, 7]);
    }

    #[test]
    fn match_pe_title_ignored() {
        assert_eq!(match_set(r####"node::title"####, &fixture()), vec![2, 3, 5, 6, 7]);
    }

    #[test]
    fn match_pe_label_alone() {
        assert_eq!(match_set(r####"::label"####, &fixture()), vec![0, 1, 2, 3, 4, 5, 6, 7, 8, 9]);
    }

    #[test]
    fn match_complex() {
        assert_eq!(match_set(r####"group > node[kind=box]:first-child:not(#n9)"####, &fixture()), vec![2]);
    }

    #[test]
    fn match_universal_child() {
        assert_eq!(match_set(r####"* > *"####, &fixture()), vec![1, 2, 3, 4, 5, 6, 7, 8, 9]);
    }

    #[test]
    fn match_last_child_group() {
        assert_eq!(match_set(r####"group:last-child"####, &fixture()), Vec::<usize>::new());
    }

    #[test]
    fn match_descendant_backtracks() {
        assert_eq!(match_set(r####"group group node"####, &fixture()), vec![5]);
    }

    #[test]
    fn match_edge_attr() {
        assert_eq!(match_set(r####"edge[from=n1]"####, &fixture()), vec![8]);
    }

    #[test]
    fn match_lone_first_child() {
        assert_eq!(match_set(r####"node:first-child"####, &lone_root()), Vec::<usize>::new());
    }

    #[test]
    fn match_lone_last_child() {
        assert_eq!(match_set(r####"diagram:last-child"####, &lone_root()), vec![0]);
    }

    #[test]
    fn match_lone_root() {
        assert_eq!(match_set(r####":root"####, &lone_root()), vec![0]);
    }

    #[test]
    fn match_lone_not_root() {
        assert_eq!(match_set(r####":not(:root)"####, &lone_root()), Vec::<usize>::new());
    }

    #[test]
    fn parse_type_node() {
        let got: Vec<String> = parse_selectors(r####"node"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"node~-~(0,0,1)"####]);
    }

    #[test]
    fn parse_type_kind() {
        let got: Vec<String> = parse_selectors(r####"state"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"state~-~(0,0,1)"####]);
    }

    #[test]
    fn parse_universal() {
        let got: Vec<String> = parse_selectors(r####"*"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"*~-~(0,0,0)"####]);
    }

    #[test]
    fn parse_class() {
        let got: Vec<String> = parse_selectors(r####".hot"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####".hot~-~(0,1,0)"####]);
    }

    #[test]
    fn parse_two_classes() {
        let got: Vec<String> = parse_selectors(r####".a.b"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####".a.b~-~(0,2,0)"####]);
    }

    #[test]
    fn parse_id() {
        let got: Vec<String> = parse_selectors(r####"#n1"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"#n1~-~(1,0,0)"####]);
    }

    #[test]
    fn parse_type_id_class() {
        let got: Vec<String> = parse_selectors(r####"node#n1.hot"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"node#n1.hot~-~(1,1,1)"####]);
    }

    #[test]
    fn parse_attr_presence() {
        let got: Vec<String> = parse_selectors(r####"[icon]"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"[icon]~-~(0,1,0)"####]);
    }

    #[test]
    fn parse_attr_unquoted() {
        let got: Vec<String> = parse_selectors(r####"[kind=decision]"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"[kind=decision]~-~(0,1,0)"####]);
    }

    #[test]
    fn parse_attr_double_quoted() {
        let got: Vec<String> = parse_selectors(r####"[label="a b"]"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"[label="a b"]~-~(0,1,0)"####]);
    }

    #[test]
    fn parse_attr_single_quoted() {
        let got: Vec<String> = parse_selectors(r####"[label='x y']"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"[label='x y']~-~(0,1,0)"####]);
    }

    #[test]
    fn parse_attr_spaces() {
        let got: Vec<String> = parse_selectors(r####"[ kind = box ]"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"[ kind = box ]~-~(0,1,0)"####]);
    }

    #[test]
    fn parse_descendant() {
        let got: Vec<String> = parse_selectors(r####"group node"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"group node~-~(0,0,2)"####]);
    }

    #[test]
    fn parse_child() {
        let got: Vec<String> = parse_selectors(r####"group > node"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"group > node~-~(0,0,2)"####]);
    }

    #[test]
    fn parse_child_tight() {
        let got: Vec<String> = parse_selectors(r####"group>node"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"group>node~-~(0,0,2)"####]);
    }

    #[test]
    fn parse_three_levels() {
        let got: Vec<String> = parse_selectors(r####"diagram group > node.hot"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"diagram group > node.hot~-~(0,1,3)"####]);
    }

    #[test]
    fn parse_list() {
        let got: Vec<String> = parse_selectors(r####"node, edge , .x"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"node~-~(0,0,1)"####, r####"edge~-~(0,0,1)"####, r####".x~-~(0,1,0)"####]);
    }

    #[test]
    fn parse_first_child() {
        let got: Vec<String> = parse_selectors(r####"node:first-child"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"node:first-child~-~(0,1,1)"####]);
    }

    #[test]
    fn parse_last_child() {
        let got: Vec<String> = parse_selectors(r####"node:last-child"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"node:last-child~-~(0,1,1)"####]);
    }

    #[test]
    fn parse_root() {
        let got: Vec<String> = parse_selectors(r####":root"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####":root~-~(0,1,0)"####]);
    }

    #[test]
    fn parse_root_type() {
        let got: Vec<String> = parse_selectors(r####"diagram:root"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"diagram:root~-~(0,1,1)"####]);
    }

    #[test]
    fn parse_not_simple() {
        let got: Vec<String> = parse_selectors(r####"node:not(.hot)"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"node:not(.hot)~-~(0,1,1)"####]);
    }

    #[test]
    fn parse_not_list() {
        let got: Vec<String> = parse_selectors(r####"node:not(.a, #b)"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"node:not(.a, #b)~-~(1,0,1)"####]);
    }

    #[test]
    fn parse_not_nested() {
        let got: Vec<String> = parse_selectors(r####"node:not(:not(.a))"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"node:not(:not(.a))~-~(0,1,1)"####]);
    }

    #[test]
    fn parse_not_with_combinator() {
        let got: Vec<String> = parse_selectors(r####"node:not(group node)"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"node:not(group node)~-~(0,0,3)"####]);
    }

    #[test]
    fn parse_not_pseudo_class() {
        let got: Vec<String> = parse_selectors(r####"node:not(:first-child)"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"node:not(:first-child)~-~(0,1,1)"####]);
    }

    #[test]
    fn parse_pe_title() {
        let got: Vec<String> = parse_selectors(r####"node::title"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"node::title~title~(0,0,2)"####]);
    }

    #[test]
    fn parse_pe_body() {
        let got: Vec<String> = parse_selectors(r####"node.hot::body"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"node.hot::body~body~(0,1,2)"####]);
    }

    #[test]
    fn parse_pe_label_alone() {
        let got: Vec<String> = parse_selectors(r####"::label"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"::label~label~(0,0,1)"####]);
    }

    #[test]
    fn parse_pe_title_alone() {
        let got: Vec<String> = parse_selectors(r####"::title"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"::title~title~(0,0,1)"####]);
    }

    #[test]
    fn parse_pe_after_child() {
        let got: Vec<String> = parse_selectors(r####"group > node::label"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"group > node::label~label~(0,0,3)"####]);
    }

    #[test]
    fn parse_list_with_pe() {
        let got: Vec<String> = parse_selectors(r####"node::title, edge::label"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"node::title~title~(0,0,2)"####, r####"edge::label~label~(0,0,2)"####]);
    }

    #[test]
    fn parse_ident_dash() {
        let got: Vec<String> = parse_selectors(r####"my-kind"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"my-kind~-~(0,0,1)"####]);
    }

    #[test]
    fn parse_ident_underscore() {
        let got: Vec<String> = parse_selectors(r####"_x"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"_x~-~(0,0,1)"####]);
    }

    #[test]
    fn parse_leading_dash_class() {
        let got: Vec<String> = parse_selectors(r####".-x"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####".-x~-~(0,1,0)"####]);
    }

    #[test]
    fn parse_universal_child() {
        let got: Vec<String> = parse_selectors(r####"* > *"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"* > *~-~(0,0,0)"####]);
    }


    #[test]
    fn parse_spec_complex() {
        let got: Vec<String> = parse_selectors(r####"group#g.a.b > node[kind=box][icon]:first-child:not(.x, #y.z)::body"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"group#g.a.b > node[kind=box][icon]:first-child:not(.x, #y.z)::body~body~(2,6,3)"####]);
    }

    #[test]
    fn parse_not_specificity_max() {
        let got: Vec<String> = parse_selectors(r####"node:not(.a, #b.c)"####).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r####"node:not(.a, #b.c)~-~(1,1,1)"####]);
    }

    #[test]
    fn fallback_trailing_combinator() {
        assert!(parse_selectors(r####"node >"####).is_err());
    }

    #[test]
    fn fallback_leading_combinator() {
        assert!(parse_selectors(r####"> node"####).is_err());
    }

    #[test]
    fn fallback_attr_value_not_ident() {
        assert!(parse_selectors(r####"[w=100px]"####).is_err());
    }
}
