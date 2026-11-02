//! CSS selectors, matching and the cascade: the matching half of `spinagram/css.py`.
//!
//! Selector tokenizing and parsing are `cssparser` and the Servo `selectors` crate, which also matches and
//! computes specificity. Only the glue is ours: the element tree, the three pseudo-elements and the type names
//! (a node answers to its type and its kinds). Python keeps stylesheet tokenizing (tinycss2), value typing,
//! warnings and the trace, and has already accepted every selector text it sends.
//!
//! `SPEC_DEVIATION`: `selectors` follows the CSS grammar, which is stricter than spinagram's regex parser in two
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
use selectors::parser::{NonTSPseudoClass, Parser, SelectorImpl, SelectorParseErrorKind};
use selectors::{Element, OpaqueElement};
use std::borrow::Borrow;
use std::collections::HashMap;
use std::fmt;
use strum::{AsRefStr, Display, EnumString, IntoStaticStr, VariantArray};

use crate::verified;

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
        self.0.bytes().fold(2_166_136_261_u32, |h, b| (h ^ u32::from(b)).wrapping_mul(16_777_619))
    }
}

/// The pseudo-elements spinagram styles.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Display, EnumString, AsRefStr, IntoStaticStr, VariantArray)]
#[strum(serialize_all = "lowercase")]
pub enum PseudoElement {
    /// `::title`
    Title,
    /// `::body`
    Body,
    /// `::label`
    Label,
}

/// Cascade slots: the element itself, then each [`PseudoElement`] in declaration order.
pub const SLOTS: usize = 1 + PseudoElement::VARIANTS.len();

impl PseudoElement {
    fn name(self) -> &'static str {
        self.into()
    }

    /// Position in a cascade result: 0 is the element itself, so the first pseudo-element is 1.
    #[must_use]
    pub fn slot(self) -> usize {
        match self {
            PseudoElement::Title => 1,
            PseudoElement::Body => 2,
            PseudoElement::Label => 3,
        }
    }
}

impl ToCss for PseudoElement {
    fn to_css<W: fmt::Write>(&self, dest: &mut W) -> fmt::Result {
        write!(dest, "::{}", self.name())
    }
}

impl selectors::parser::PseudoElement for PseudoElement {}

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
    type PseudoElement = PseudoElement;
}

struct SelectorParser;

impl<'i> Parser<'i> for SelectorParser {
    type Impl = Impl;
    type Error = SelectorParseErrorKind;

    fn parse_pseudo_element(&self, name: CowRcStr<'i>) -> Result<PseudoElement, ParseError<Self::Error>> {
        name.parse().map_err(|_| ParseError::custom(SelectorParseErrorKind::UnsupportedPseudoClassOrElement))
    }
}

/// A parsed selector with the text it came from.
#[derive(Clone, Debug)]
pub struct Selector {
    pub text: String,
    inner: selectors::parser::Selector<Impl>,
    pub pseudo_element: Option<PseudoElement>,
}

impl Selector {
    /// `(ids, classes + attributes + pseudo-classes, types + pseudo-element)`; `:not()` counts its most specific
    /// argument. Components clamp at 1023 in the crate, far above any real selector.
    #[must_use]
    pub fn specificity(&self) -> (u32, u32, u32) {
        let s = self.inner.specificity();
        (s >> 20, (s >> 10) & 0x3ff, s & 0x3ff)
    }
}

/// A comma list of selectors, each with its own source text.
///
/// # Errors
///
/// When the text is empty or a selector is outside the grammar the `selectors` crate accepts.
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

    fn match_pseudo_element(&self, _pe: &PseudoElement, _: &mut MatchingContext<Impl>) -> bool {
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

// cascade ----------------------------------------------------------------------------------------

/// A style rule: selectors sharing one declaration block. `order` is its position over all sheets.
#[derive(Clone, Debug)]
pub struct Rule {
    pub selectors: Vec<Selector>,
    pub decls: Vec<Decl>,
    pub order: i64,
}

/// A matched declaration: `rule` is the rule index or `None` for the element's inline css; `sel` the index of the
/// selector that matched; `decl` the declaration index; `resolved` the value after `var()` (None for `--custom`).
#[derive(Clone, Debug, PartialEq)]
pub struct Entry {
    pub rule: Option<usize>,
    pub sel: usize,
    pub decl: usize,
    pub resolved: Option<String>,
}

type Custom = std::rc::Rc<std::collections::HashMap<String, String>>;

/// How many times `substitute` rescans for `var(` after a replacement (Python's limit): nested references resolve
/// to this depth, deeper ones stay as text.
const MAX_VAR_PASSES: usize = 8;

/// `var(--x[, fallback])` replacement, as `css._substitute`: up to 8 passes; an unknown `--x` without a fallback
/// becomes `x` (the theme token). Fallbacks may contain functions.
#[must_use]
pub fn substitute<S: std::hash::BuildHasher>(value: &str, custom: &std::collections::HashMap<String, String, S>) -> String {
    let mut chars: Vec<char> = value.chars().collect();
    for _ in 0..MAX_VAR_PASSES {
        let Some(start) = find_var(&chars) else { break };
        let end = verified::brackets::scan_close(&chars, start + 4);
        // Python slices `value[i + 4:j - 1]`, which is empty when nothing follows `var(`
        let inner: String = chars[start + 4..end.saturating_sub(1).max(start + 4)].iter().collect();
        let (name, fallback) = match inner.split_once(',') {
            Some((n, f)) => (n, f),
            None => (inner.as_str(), ""),
        };
        let name = name.trim();
        let replacement: String = match custom.get(name) {
            Some(r) => r.clone(),
            None if !fallback.trim().is_empty() => fallback.trim().to_string(),
            None => name.chars().skip(2).collect(),
        };
        let mut next: Vec<char> = chars[..start].to_vec();
        next.extend(replacement.chars());
        next.extend_from_slice(&chars[end..]);
        chars = next;
    }
    chars.into_iter().collect()
}

fn find_var(v: &[char]) -> Option<usize> {
    v.windows(4).position(|w| w == ['v', 'a', 'r', '('])
}

fn level(important: bool, inline: bool) -> u8 {
    match (inline, important) {
        (false, false) => 0,
        (true, false) => 1,
        (false, true) => 2,
        (true, true) => 3,
    }
}

type SortKey = (u8, (u32, u32, u32), i64, usize);

/// `found` in cascade order: stable over `(level, specificity, rule order, declaration index)`, by the verified
/// `stable_order` permutation.
fn sorted_by_cascade(found: Vec<(SortKey, Entry)>) -> Vec<(SortKey, Entry)> {
    let keys: Vec<verified::cascade::Key> = found
        .iter()
        .map(|((level, (a, b, c), order, index), _)| verified::cascade::Key {
            level: u64::from(*level),
            a: u64::from(*a),
            b: u64::from(*b),
            c: u64::from(*c),
            order: *order,
            index: u64::try_from(*index).unwrap_or(u64::MAX),
        })
        .collect();
    let mut slots: Vec<Option<(SortKey, Entry)>> = found.into_iter().map(Some).collect();
    verified::cascade::stable_order(&keys)
        .into_iter()
        .map(|p| slots[p].take().expect("a permutation visits each position once"))
        .collect()
}

/// For every element (index order) and pseudo-element (`SLOTS`): the declarations that apply, in cascade order
/// (the winner of a property last): by `(important, specificity, rule order, declaration index)`, with inline
/// declarations at levels 1 (normal) and 3 (important). Custom properties inherit from the parent element; a
/// pseudo-element sees its element's custom properties plus its own.
pub fn cascade(tree: &Tree, rules: &[Rule]) -> Vec<[Vec<Entry>; SLOTS]> {
    let specs: Vec<Vec<(u32, u32, u32)>> = rules.iter().map(|r| r.selectors.iter().map(Selector::specificity).collect()).collect();
    let mut matcher = Matcher::default();
    let mut out: Vec<[Vec<Entry>; SLOTS]> = Vec::with_capacity(tree.nodes.len());
    let mut customs: Vec<Custom> = Vec::with_capacity(tree.nodes.len());
    for (el, node) in tree.nodes.iter().enumerate() {
        let mut found: [Vec<(SortKey, Entry)>; SLOTS] = Default::default();
        for (ri, r) in rules.iter().enumerate() {
            for (si, sel) in r.selectors.iter().enumerate() {
                let slot = sel.pseudo_element.map_or(0, PseudoElement::slot);
                if matcher.matches(sel, tree, el) {
                    for (di, d) in r.decls.iter().enumerate() {
                        let key = (level(d.important, false), specs[ri][si], r.order, di);
                        found[slot].push((key, Entry { rule: Some(ri), sel: si, decl: di, resolved: None }));
                    }
                }
            }
        }
        for (di, d) in node.inline.iter().enumerate() {
            found[0].push(((level(d.important, true), (0, 0, 0), 0, di), Entry { rule: None, sel: 0, decl: di, resolved: None }));
        }
        let decl_of = |e: &Entry| -> &Decl {
            match e.rule {
                None => &node.inline[e.decl],
                Some(r) => &rules[r].decls[e.decl],
            }
        };
        let parent_custom: Custom = node.parent.map_or_else(Default::default, |p| customs[p].clone());
        let mut element_custom = parent_custom;
        let mut result: [Vec<Entry>; SLOTS] = Default::default();
        for slot in 0..SLOTS {
            let mut list = std::mem::take(&mut found[slot]);
            list = sorted_by_cascade(list);
            let own: Vec<(&str, &str)> = list
                .iter()
                .map(|(_, e)| decl_of(e))
                .filter(|d| d.name.starts_with("--"))
                .map(|d| (d.name.as_str(), d.value.as_str()))
                .collect();
            let custom: Custom = if own.is_empty() {
                element_custom.clone()
            } else {
                let mut m = (*element_custom).clone();
                for (k, v) in own {
                    m.insert(k.to_string(), v.to_string());
                }
                std::rc::Rc::new(m)
            };
            result[slot] = list
                .into_iter()
                .map(|(_, mut e)| {
                    let d = decl_of(&e);
                    e.resolved = if d.name.starts_with("--") { None } else { Some(substitute(&d.value, &custom)) };
                    e
                })
                .collect();
            if slot == 0 {
                element_custom = custom; // children inherit the element's own scope, not a pseudo-element's
            }
        }
        customs.push(element_custom);
        out.push(result);
    }
    out
}


// JSON boundary ----------------------------------------------------------------------------------

#[derive(serde::Deserialize)]
struct NodeIn {
    parent: Option<usize>,
    #[serde(rename = "type")]
    typ: String,
    #[serde(default)]
    kinds: Vec<String>,
    id: Option<String>,
    #[serde(default)]
    classes: Vec<String>,
    #[serde(default)]
    attrs: HashMap<String, String>,
    #[serde(default)]
    inline: Vec<DeclIn>,
}

#[derive(serde::Deserialize)]
struct DeclIn {
    name: String,
    value: String,
    #[serde(default)]
    important: bool,
}

#[derive(serde::Deserialize)]
struct RuleIn {
    selectors: Vec<String>,
    decls: Vec<DeclIn>,
    order: i64,
}

impl From<DeclIn> for Decl {
    fn from(d: DeclIn) -> Decl {
        Decl { name: d.name, value: d.value, important: d.important }
    }
}

/// The style tree from `{"nodes": [{parent, type, kinds, id, classes, attrs, inline}, ...]}` in pre-order.
///
/// # Errors
///
/// When the JSON does not describe a style tree.
pub fn tree_from_json(json: &str) -> Result<Tree, String> {
    #[derive(serde::Deserialize)]
    struct In {
        nodes: Vec<NodeIn>,
    }
    let parsed: In = serde_json::from_str(json).map_err(|e| format!("invalid style tree: {e}"))?;
    let nodes = parsed
        .nodes
        .into_iter()
        .map(|n| Node {
            parent: n.parent,
            typ: n.typ,
            kinds: n.kinds,
            id: n.id,
            classes: n.classes,
            attrs: n.attrs,
            inline: n.inline.into_iter().map(Decl::from).collect(),
            ..Node::default()
        })
        .collect();
    let mut tree = Tree { nodes };
    tree.link();
    Ok(tree)
}

/// One cascade entry on the JSON boundary: rule index or -1 for inline, selector, declaration, resolved value.
type Row = (i64, usize, usize, Option<String>);

/// The cascade as JSON: per element, per pseudo-element (`PseudoElement` order), a list of
/// `[rule index or -1, selector index, declaration index, resolved value or null]`.
/// `rules_json` is `[{"selectors": [text], "decls": [{name, value, important}], "order": n}]`.
///
/// # Errors
///
/// When the tree or rules JSON is invalid or a selector cannot be parsed.
pub fn cascade_json(tree_json: &str, rules_json: &str) -> Result<String, String> {
    let tree = tree_from_json(tree_json)?;
    let raw: Vec<RuleIn> = serde_json::from_str(rules_json).map_err(|e| format!("invalid rules: {e}"))?;
    let mut rules = Vec::with_capacity(raw.len());
    for r in raw {
        let mut selectors = Vec::new();
        for text in &r.selectors {
            let mut parsed = parse_selectors(text)?;
            if parsed.len() != 1 {
                return Err(format!("expected one selector in {text:?}"));
            }
            selectors.append(&mut parsed);
        }
        rules.push(Rule { selectors, decls: r.decls.into_iter().map(Decl::from).collect(), order: r.order });
    }
    let result = cascade(&tree, &rules);
    let json: Vec<Vec<Vec<Row>>> = result
        .into_iter()
        .map(|el| el.into_iter().map(|list| list.into_iter().map(|e| (e.rule.map_or(-1, |r| i64::try_from(r).unwrap_or(i64::MAX)), e.sel, e.decl, e.resolved)).collect()).collect())
        .collect();
    serde_json::to_string(&json).map_err(|e| e.to_string())
}

/// For each selector text, the indices of the elements it matches (pseudo-elements ignored), as JSON.
///
/// # Errors
///
/// When the tree JSON is invalid or a selector cannot be parsed.
pub fn select_json(tree_json: &str, texts: &[String]) -> Result<String, String> {
    let tree = tree_from_json(tree_json)?;
    let mut matcher = Matcher::default();
    let mut out: Vec<Vec<usize>> = Vec::with_capacity(texts.len());
    for t in texts {
        let sels = parse_selectors(t)?;
        out.push((0..tree.nodes.len()).filter(|&i| sels.iter().any(|s| matcher.matches(s, &tree, i))).collect());
    }
    serde_json::to_string(&out).map_err(|e| e.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    // Expected values come from Python: parse_selectors (text, pseudo-element, specificity) and matches() over
    // the tree in fixture().
    fn canon(sel: &Selector) -> String {
        let (a, b, c) = sel.specificity();
        format!("{}~{}~({a},{b},{c})", sel.text, sel.pseudo_element.map_or("-", PseudoElement::name))
    }

    fn node(parent: Option<usize>, typ: &str, kinds: &[&str], id: Option<&str>, classes: &[&str], attrs: &[(&str, &str)]) -> Node {
        Node {
            parent,
            typ: typ.into(),
            kinds: kinds.iter().map(std::string::ToString::to_string).collect(),
            id: id.map(String::from),
            classes: classes.iter().map(std::string::ToString::to_string).collect(),
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
        assert_eq!(match_set(r"node", &fixture()), vec![2, 3, 5, 6, 7]);
    }

    #[test]
    fn match_type_kind() {
        assert_eq!(match_set(r"state", &fixture()), vec![5]);
    }

    #[test]
    fn match_type_kind_alias() {
        assert_eq!(match_set(r"chip", &fixture()), vec![7]);
    }

    #[test]
    fn match_type_group_alias() {
        assert_eq!(match_set(r"group", &fixture()), vec![1, 4]);
    }

    #[test]
    fn match_universal() {
        assert_eq!(match_set(r"*", &fixture()), vec![0, 1, 2, 3, 4, 5, 6, 7, 8, 9]);
    }

    #[test]
    fn match_class() {
        assert_eq!(match_set(r".hot", &fixture()), vec![2, 5, 9]);
    }

    #[test]
    fn match_two_classes() {
        assert_eq!(match_set(r".a.b", &fixture()), Vec::<usize>::new());
    }

    #[test]
    fn match_id() {
        assert_eq!(match_set(r"#n1", &fixture()), vec![2]);
    }

    #[test]
    fn match_type_id_class() {
        assert_eq!(match_set(r"node#n1.hot", &fixture()), vec![2]);
    }

    #[test]
    fn match_attr_presence() {
        assert_eq!(match_set(r"[icon]", &fixture()), vec![2]);
    }

    #[test]
    fn match_attr_unquoted() {
        assert_eq!(match_set(r"[kind=box]", &fixture()), vec![2, 7]);
    }

    #[test]
    fn match_attr_double_quoted() {
        assert_eq!(match_set(r#"[label="a b"]"#, &fixture()), vec![2, 9]);
    }

    #[test]
    fn match_attr_single_quoted() {
        assert_eq!(match_set(r"[label='x y']", &fixture()), vec![6]);
    }

    #[test]
    fn match_attr_value_mismatch() {
        assert_eq!(match_set(r"[kind=nope]", &fixture()), Vec::<usize>::new());
    }

    #[test]
    fn match_attr_spaces() {
        assert_eq!(match_set(r"[ kind = decision ]", &fixture()), vec![3]);
    }

    #[test]
    fn match_descendant() {
        assert_eq!(match_set(r"group node", &fixture()), vec![2, 3, 5, 6]);
    }

    #[test]
    fn match_descendant_skips_levels() {
        assert_eq!(match_set(r"diagram node", &fixture()), vec![2, 3, 5, 6, 7]);
    }

    #[test]
    fn match_child() {
        assert_eq!(match_set(r"group > node", &fixture()), vec![2, 3, 5, 6]);
    }

    #[test]
    fn match_child_tight() {
        assert_eq!(match_set(r"group>node", &fixture()), vec![2, 3, 5, 6]);
    }

    #[test]
    fn match_child_not_grandchild() {
        assert_eq!(match_set(r"diagram > node", &fixture()), vec![7]);
    }

    #[test]
    fn match_three_levels() {
        assert_eq!(match_set(r"diagram group > node.hot", &fixture()), vec![2, 5]);
    }

    #[test]
    fn match_list() {
        assert_eq!(match_set(r"edge, .a", &fixture()), vec![1, 2, 8, 9]);
    }

    #[test]
    fn match_first_child() {
        assert_eq!(match_set(r"node:first-child", &fixture()), vec![2, 5]);
    }

    #[test]
    fn match_last_child() {
        assert_eq!(match_set(r"node:last-child", &fixture()), vec![5, 6]);
    }

    #[test]
    fn match_root() {
        assert_eq!(match_set(r":root", &fixture()), vec![0]);
    }

    #[test]
    fn match_root_type() {
        assert_eq!(match_set(r"diagram:root", &fixture()), vec![0]);
    }

    #[test]
    fn match_root_not_child() {
        assert_eq!(match_set(r"node:root", &fixture()), Vec::<usize>::new());
    }

    #[test]
    fn match_not_simple() {
        assert_eq!(match_set(r"node:not(.hot)", &fixture()), vec![3, 6, 7]);
    }

    #[test]
    fn match_not_list() {
        assert_eq!(match_set(r"node:not(.a, #n5)", &fixture()), vec![3, 5, 6]);
    }

    #[test]
    fn match_not_nested() {
        assert_eq!(match_set(r"node:not(:not(.hot))", &fixture()), vec![2, 5]);
    }

    #[test]
    fn match_not_with_combinator() {
        assert_eq!(match_set(r"node:not(group node)", &fixture()), vec![7]);
    }

    #[test]
    fn match_not_pseudo_class() {
        assert_eq!(match_set(r"node:not(:first-child)", &fixture()), vec![3, 6, 7]);
    }

    #[test]
    fn match_pe_title_ignored() {
        assert_eq!(match_set(r"node::title", &fixture()), vec![2, 3, 5, 6, 7]);
    }

    #[test]
    fn match_pe_label_alone() {
        assert_eq!(match_set(r"::label", &fixture()), vec![0, 1, 2, 3, 4, 5, 6, 7, 8, 9]);
    }

    #[test]
    fn match_complex() {
        assert_eq!(match_set(r"group > node[kind=box]:first-child:not(#n9)", &fixture()), vec![2]);
    }

    #[test]
    fn match_universal_child() {
        assert_eq!(match_set(r"* > *", &fixture()), vec![1, 2, 3, 4, 5, 6, 7, 8, 9]);
    }

    #[test]
    fn match_last_child_group() {
        assert_eq!(match_set(r"group:last-child", &fixture()), Vec::<usize>::new());
    }

    #[test]
    fn match_descendant_backtracks() {
        assert_eq!(match_set(r"group group node", &fixture()), vec![5]);
    }

    #[test]
    fn match_edge_attr() {
        assert_eq!(match_set(r"edge[from=n1]", &fixture()), vec![8]);
    }

    #[test]
    fn match_lone_first_child() {
        assert_eq!(match_set(r"node:first-child", &lone_root()), Vec::<usize>::new());
    }

    #[test]
    fn match_lone_last_child() {
        assert_eq!(match_set(r"diagram:last-child", &lone_root()), vec![0]);
    }

    #[test]
    fn match_lone_root() {
        assert_eq!(match_set(r":root", &lone_root()), vec![0]);
    }

    #[test]
    fn match_lone_not_root() {
        assert_eq!(match_set(r":not(:root)", &lone_root()), Vec::<usize>::new());
    }

    #[test]
    fn parse_type_node() {
        let got: Vec<String> = parse_selectors(r"node").unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r"node~-~(0,0,1)"]);
    }

    #[test]
    fn parse_type_kind() {
        let got: Vec<String> = parse_selectors(r"state").unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r"state~-~(0,0,1)"]);
    }

    #[test]
    fn parse_universal() {
        let got: Vec<String> = parse_selectors(r"*").unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r"*~-~(0,0,0)"]);
    }

    #[test]
    fn parse_class() {
        let got: Vec<String> = parse_selectors(r".hot").unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r".hot~-~(0,1,0)"]);
    }

    #[test]
    fn parse_two_classes() {
        let got: Vec<String> = parse_selectors(r".a.b").unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r".a.b~-~(0,2,0)"]);
    }

    #[test]
    fn parse_id() {
        let got: Vec<String> = parse_selectors(r"#n1").unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r"#n1~-~(1,0,0)"]);
    }

    #[test]
    fn parse_type_id_class() {
        let got: Vec<String> = parse_selectors(r"node#n1.hot").unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r"node#n1.hot~-~(1,1,1)"]);
    }

    #[test]
    fn parse_attr_presence() {
        let got: Vec<String> = parse_selectors(r"[icon]").unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r"[icon]~-~(0,1,0)"]);
    }

    #[test]
    fn parse_attr_unquoted() {
        let got: Vec<String> = parse_selectors(r"[kind=decision]").unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r"[kind=decision]~-~(0,1,0)"]);
    }

    #[test]
    fn parse_attr_double_quoted() {
        let got: Vec<String> = parse_selectors(r#"[label="a b"]"#).unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r#"[label="a b"]~-~(0,1,0)"#]);
    }

    #[test]
    fn parse_attr_single_quoted() {
        let got: Vec<String> = parse_selectors(r"[label='x y']").unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r"[label='x y']~-~(0,1,0)"]);
    }

    #[test]
    fn parse_attr_spaces() {
        let got: Vec<String> = parse_selectors(r"[ kind = box ]").unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r"[ kind = box ]~-~(0,1,0)"]);
    }

    #[test]
    fn parse_descendant() {
        let got: Vec<String> = parse_selectors(r"group node").unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r"group node~-~(0,0,2)"]);
    }

    #[test]
    fn parse_child() {
        let got: Vec<String> = parse_selectors(r"group > node").unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r"group > node~-~(0,0,2)"]);
    }

    #[test]
    fn parse_child_tight() {
        let got: Vec<String> = parse_selectors(r"group>node").unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r"group>node~-~(0,0,2)"]);
    }

    #[test]
    fn parse_three_levels() {
        let got: Vec<String> = parse_selectors(r"diagram group > node.hot").unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r"diagram group > node.hot~-~(0,1,3)"]);
    }

    #[test]
    fn parse_list() {
        let got: Vec<String> = parse_selectors(r"node, edge , .x").unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r"node~-~(0,0,1)", r"edge~-~(0,0,1)", r".x~-~(0,1,0)"]);
    }

    #[test]
    fn parse_first_child() {
        let got: Vec<String> = parse_selectors(r"node:first-child").unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r"node:first-child~-~(0,1,1)"]);
    }

    #[test]
    fn parse_last_child() {
        let got: Vec<String> = parse_selectors(r"node:last-child").unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r"node:last-child~-~(0,1,1)"]);
    }

    #[test]
    fn parse_root() {
        let got: Vec<String> = parse_selectors(r":root").unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r":root~-~(0,1,0)"]);
    }

    #[test]
    fn parse_root_type() {
        let got: Vec<String> = parse_selectors(r"diagram:root").unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r"diagram:root~-~(0,1,1)"]);
    }

    #[test]
    fn parse_not_simple() {
        let got: Vec<String> = parse_selectors(r"node:not(.hot)").unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r"node:not(.hot)~-~(0,1,1)"]);
    }

    #[test]
    fn parse_not_list() {
        let got: Vec<String> = parse_selectors(r"node:not(.a, #b)").unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r"node:not(.a, #b)~-~(1,0,1)"]);
    }

    #[test]
    fn parse_not_nested() {
        let got: Vec<String> = parse_selectors(r"node:not(:not(.a))").unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r"node:not(:not(.a))~-~(0,1,1)"]);
    }

    #[test]
    fn parse_not_with_combinator() {
        let got: Vec<String> = parse_selectors(r"node:not(group node)").unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r"node:not(group node)~-~(0,0,3)"]);
    }

    #[test]
    fn parse_not_pseudo_class() {
        let got: Vec<String> = parse_selectors(r"node:not(:first-child)").unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r"node:not(:first-child)~-~(0,1,1)"]);
    }

    #[test]
    fn parse_pe_title() {
        let got: Vec<String> = parse_selectors(r"node::title").unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r"node::title~title~(0,0,2)"]);
    }

    #[test]
    fn parse_pe_body() {
        let got: Vec<String> = parse_selectors(r"node.hot::body").unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r"node.hot::body~body~(0,1,2)"]);
    }

    #[test]
    fn parse_pe_label_alone() {
        let got: Vec<String> = parse_selectors(r"::label").unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r"::label~label~(0,0,1)"]);
    }

    #[test]
    fn parse_pe_title_alone() {
        let got: Vec<String> = parse_selectors(r"::title").unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r"::title~title~(0,0,1)"]);
    }

    #[test]
    fn parse_pe_after_child() {
        let got: Vec<String> = parse_selectors(r"group > node::label").unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r"group > node::label~label~(0,0,3)"]);
    }

    #[test]
    fn parse_list_with_pe() {
        let got: Vec<String> = parse_selectors(r"node::title, edge::label").unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r"node::title~title~(0,0,2)", r"edge::label~label~(0,0,2)"]);
    }

    #[test]
    fn parse_ident_dash() {
        let got: Vec<String> = parse_selectors(r"my-kind").unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r"my-kind~-~(0,0,1)"]);
    }

    #[test]
    fn parse_ident_underscore() {
        let got: Vec<String> = parse_selectors(r"_x").unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r"_x~-~(0,0,1)"]);
    }

    #[test]
    fn parse_leading_dash_class() {
        let got: Vec<String> = parse_selectors(r".-x").unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r".-x~-~(0,1,0)"]);
    }

    #[test]
    fn parse_universal_child() {
        let got: Vec<String> = parse_selectors(r"* > *").unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r"* > *~-~(0,0,0)"]);
    }


    #[test]
    fn parse_spec_complex() {
        let got: Vec<String> = parse_selectors(r"group#g.a.b > node[kind=box][icon]:first-child:not(.x, #y.z)::body").unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r"group#g.a.b > node[kind=box][icon]:first-child:not(.x, #y.z)::body~body~(2,6,3)"]);
    }

    #[test]
    fn parse_not_specificity_max() {
        let got: Vec<String> = parse_selectors(r"node:not(.a, #b.c)").unwrap().iter().map(canon).collect();
        assert_eq!(got, vec![r"node:not(.a, #b.c)~-~(1,1,1)"]);
    }

    #[test]
    fn fallback_trailing_combinator() {
        assert!(parse_selectors(r"node >").is_err());
    }

    #[test]
    fn fallback_leading_combinator() {
        assert!(parse_selectors(r"> node").is_err());
    }

    #[test]
    fn fallback_attr_value_not_ident() {
        assert!(parse_selectors(r"[w=100px]").is_err());
    }

    // Cascade expectations come from Python's compute() trace over the same tree and rules (see cascade_fixture).
    fn rule(order: i64, selectors: &[&str], decls: &[(&str, &str, bool)]) -> Rule {
        Rule {
            selectors: selectors.iter().flat_map(|s| parse_selectors(s).unwrap()).collect(),
            decls: self::decls(decls),
            order,
        }
    }

    fn decls(list: &[(&str, &str, bool)]) -> Vec<Decl> {
        list.iter().map(|(n, v, i)| Decl { name: n.to_string(), value: v.to_string(), important: *i }).collect()
    }

    /// `(name, value, resolved)` of each entry, in cascade order.
    fn listing_of<'a>(tree: &'a Tree, el: usize, rules: &'a [Rule], entries: &'a [Entry]) -> Vec<(&'a str, &'a str, Option<&'a str>)> {
        entries
            .iter()
            .map(|e| {
                let d = match e.rule {
                    None => &tree.nodes[el].inline[e.decl],
                    Some(r) => &rules[r].decls[e.decl],
                };
                (d.name.as_str(), d.value.as_str(), e.resolved.as_deref())
            })
            .collect()
    }

    fn cascade_fixture() -> Tree {
        tree(vec![
            node(None, "diagram", &[], Some("d"), &[], &[]),
            node(Some(0), "group", &["group"], Some("g1"), &["a"], &[]),
            node(Some(1), "node", &["box"], Some("n1"), &["hot"], &[]),
            node(Some(1), "node", &["box"], Some("n2"), &[], &[]),
            node(Some(0), "edge", &[], None, &[], &[]),
        ])
    }

    #[test]
    fn cascade_levels_normal_inline_important() {
        let mut t = cascade_fixture();
        t.nodes[2].inline = decls(&[(r"stroke", r"#c00", false), (r"opacity", r"0.5", true), (r"font-size", r"20", false)]);
        let rules = vec![
            rule(0, &[r"node"], &[(r"stroke", r"#111", false)]),
            rule(1, &[r"node"], &[(r"fill", r"#222", true)]),
            rule(2, &[r"node"], &[(r"stroke-width", r"1", false)])
        ];
        let got = cascade(&t, &rules);
        assert_eq!(listing_of(&t, 0, &rules, &got[0][0]), Vec::<(&str, &str, Option<&str>)>::new(), "element 0 ::");
        assert_eq!(listing_of(&t, 0, &rules, &got[0][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 0 ::title");
        assert_eq!(listing_of(&t, 0, &rules, &got[0][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 0 ::body");
        assert_eq!(listing_of(&t, 0, &rules, &got[0][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 0 ::label");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][0]), Vec::<(&str, &str, Option<&str>)>::new(), "element 1 ::");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 1 ::title");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 1 ::body");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 1 ::label");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][0]), vec![(r"stroke", r"#111", Some(r"#111")), (r"stroke-width", r"1", Some(r"1")), (r"stroke", r"#c00", Some(r"#c00")), (r"font-size", r"20", Some(r"20")), (r"fill", r"#222", Some(r"#222")), (r"opacity", r"0.5", Some(r"0.5"))], "element 2 ::");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 2 ::title");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 2 ::body");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 2 ::label");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][0]), vec![(r"stroke", r"#111", Some(r"#111")), (r"stroke-width", r"1", Some(r"1")), (r"fill", r"#222", Some(r"#222"))], "element 3 ::");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 3 ::title");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 3 ::body");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 3 ::label");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][0]), Vec::<(&str, &str, Option<&str>)>::new(), "element 4 ::");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 4 ::title");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 4 ::body");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 4 ::label");
    }

    #[test]
    fn cascade_specificity_then_order_then_index() {
        let t = cascade_fixture();
        let rules = vec![
            rule(0, &[r"node"], &[(r"fill", r"#111", false), (r"fill", r"#112", false)]),
            rule(1, &[r".hot"], &[(r"fill", r"#222", false)]),
            rule(2, &[r"#n1"], &[(r"fill", r"#333", false)]),
            rule(3, &[r"node.hot"], &[(r"fill", r"#444", false)]),
            rule(4, &[r"node"], &[(r"fill", r"#555", false)])
        ];
        let got = cascade(&t, &rules);
        assert_eq!(listing_of(&t, 0, &rules, &got[0][0]), Vec::<(&str, &str, Option<&str>)>::new(), "element 0 ::");
        assert_eq!(listing_of(&t, 0, &rules, &got[0][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 0 ::title");
        assert_eq!(listing_of(&t, 0, &rules, &got[0][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 0 ::body");
        assert_eq!(listing_of(&t, 0, &rules, &got[0][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 0 ::label");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][0]), Vec::<(&str, &str, Option<&str>)>::new(), "element 1 ::");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 1 ::title");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 1 ::body");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 1 ::label");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][0]), vec![(r"fill", r"#111", Some(r"#111")), (r"fill", r"#112", Some(r"#112")), (r"fill", r"#555", Some(r"#555")), (r"fill", r"#222", Some(r"#222")), (r"fill", r"#444", Some(r"#444")), (r"fill", r"#333", Some(r"#333"))], "element 2 ::");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 2 ::title");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 2 ::body");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 2 ::label");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][0]), vec![(r"fill", r"#111", Some(r"#111")), (r"fill", r"#112", Some(r"#112")), (r"fill", r"#555", Some(r"#555"))], "element 3 ::");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 3 ::title");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 3 ::body");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 3 ::label");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][0]), Vec::<(&str, &str, Option<&str>)>::new(), "element 4 ::");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 4 ::title");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 4 ::body");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 4 ::label");
    }

    #[test]
    fn cascade_selector_list_duplicates_and_ties() {
        let t = cascade_fixture();
        let rules = vec![
            rule(0, &[r"node", r"node"], &[(r"fill", r"#111", false), (r"stroke", r"#222", false)]),
            rule(1, &[r"box"], &[(r"fill", r"#333", false)]),
            rule(2, &[r"[kind]"], &[(r"fill", r"#444", false)])
        ];
        let got = cascade(&t, &rules);
        assert_eq!(listing_of(&t, 0, &rules, &got[0][0]), Vec::<(&str, &str, Option<&str>)>::new(), "element 0 ::");
        assert_eq!(listing_of(&t, 0, &rules, &got[0][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 0 ::title");
        assert_eq!(listing_of(&t, 0, &rules, &got[0][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 0 ::body");
        assert_eq!(listing_of(&t, 0, &rules, &got[0][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 0 ::label");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][0]), Vec::<(&str, &str, Option<&str>)>::new(), "element 1 ::");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 1 ::title");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 1 ::body");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 1 ::label");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][0]), vec![(r"fill", r"#111", Some(r"#111")), (r"fill", r"#111", Some(r"#111")), (r"stroke", r"#222", Some(r"#222")), (r"stroke", r"#222", Some(r"#222")), (r"fill", r"#333", Some(r"#333"))], "element 2 ::");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 2 ::title");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 2 ::body");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 2 ::label");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][0]), vec![(r"fill", r"#111", Some(r"#111")), (r"fill", r"#111", Some(r"#111")), (r"stroke", r"#222", Some(r"#222")), (r"stroke", r"#222", Some(r"#222")), (r"fill", r"#333", Some(r"#333"))], "element 3 ::");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 3 ::title");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 3 ::body");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 3 ::label");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][0]), Vec::<(&str, &str, Option<&str>)>::new(), "element 4 ::");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 4 ::title");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 4 ::body");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 4 ::label");
    }

    #[test]
    fn cascade_important_beats_specificity() {
        let t = cascade_fixture();
        let rules = vec![
            rule(0, &[r"#n1"], &[(r"fill", r"#111", false)]),
            rule(1, &[r"node"], &[(r"fill", r"#222", true)]),
            rule(2, &[r".hot"], &[(r"fill", r"#333", true)])
        ];
        let got = cascade(&t, &rules);
        assert_eq!(listing_of(&t, 0, &rules, &got[0][0]), Vec::<(&str, &str, Option<&str>)>::new(), "element 0 ::");
        assert_eq!(listing_of(&t, 0, &rules, &got[0][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 0 ::title");
        assert_eq!(listing_of(&t, 0, &rules, &got[0][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 0 ::body");
        assert_eq!(listing_of(&t, 0, &rules, &got[0][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 0 ::label");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][0]), Vec::<(&str, &str, Option<&str>)>::new(), "element 1 ::");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 1 ::title");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 1 ::body");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 1 ::label");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][0]), vec![(r"fill", r"#111", Some(r"#111")), (r"fill", r"#222", Some(r"#222")), (r"fill", r"#333", Some(r"#333"))], "element 2 ::");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 2 ::title");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 2 ::body");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 2 ::label");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][0]), vec![(r"fill", r"#222", Some(r"#222"))], "element 3 ::");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 3 ::title");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 3 ::body");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 3 ::label");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][0]), Vec::<(&str, &str, Option<&str>)>::new(), "element 4 ::");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 4 ::title");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 4 ::body");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 4 ::label");
    }

    #[test]
    fn cascade_pseudo_elements_split() {
        let t = cascade_fixture();
        let rules = vec![
            rule(0, &[r"node::title"], &[(r"color", r"#111", false)]),
            rule(1, &[r"node"], &[(r"color", r"#222", false)]),
            rule(2, &[r"::label"], &[(r"color", r"#333", false)]),
            rule(3, &[r"group::body"], &[(r"color", r"#444", false)]),
            rule(4, &[r"node::title"], &[(r"font-size", r"12", false)])
        ];
        let got = cascade(&t, &rules);
        assert_eq!(listing_of(&t, 0, &rules, &got[0][0]), Vec::<(&str, &str, Option<&str>)>::new(), "element 0 ::");
        assert_eq!(listing_of(&t, 0, &rules, &got[0][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 0 ::title");
        assert_eq!(listing_of(&t, 0, &rules, &got[0][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 0 ::body");
        assert_eq!(listing_of(&t, 0, &rules, &got[0][3]), vec![(r"color", r"#333", Some(r"#333"))], "element 0 ::label");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][0]), Vec::<(&str, &str, Option<&str>)>::new(), "element 1 ::");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 1 ::title");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][2]), vec![(r"color", r"#444", Some(r"#444"))], "element 1 ::body");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][3]), vec![(r"color", r"#333", Some(r"#333"))], "element 1 ::label");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][0]), vec![(r"color", r"#222", Some(r"#222"))], "element 2 ::");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][1]), vec![(r"color", r"#111", Some(r"#111")), (r"font-size", r"12", Some(r"12"))], "element 2 ::title");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 2 ::body");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][3]), vec![(r"color", r"#333", Some(r"#333"))], "element 2 ::label");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][0]), vec![(r"color", r"#222", Some(r"#222"))], "element 3 ::");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][1]), vec![(r"color", r"#111", Some(r"#111")), (r"font-size", r"12", Some(r"12"))], "element 3 ::title");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 3 ::body");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][3]), vec![(r"color", r"#333", Some(r"#333"))], "element 3 ::label");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][0]), Vec::<(&str, &str, Option<&str>)>::new(), "element 4 ::");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 4 ::title");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 4 ::body");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][3]), vec![(r"color", r"#333", Some(r"#333"))], "element 4 ::label");
    }

    #[test]
    fn cascade_var_nested_and_inherited() {
        let t = cascade_fixture();
        let rules = vec![
            rule(0, &[r"diagram"], &[(r"--a", r"var(--b)", false), (r"--b", r"Inter", false), (r"--p", r"Parent", false)]),
            rule(1, &[r"node"], &[(r"font-family", r"var(--a)", false)]),
            rule(2, &[r"group"], &[(r"font-family", r"var(--p)", false)]),
            rule(3, &[r"edge"], &[(r"font-family", r"var(--none)", false)])
        ];
        let got = cascade(&t, &rules);
        assert_eq!(listing_of(&t, 0, &rules, &got[0][0]), vec![(r"--a", r"var(--b)", None), (r"--b", r"Inter", None), (r"--p", r"Parent", None)], "element 0 ::");
        assert_eq!(listing_of(&t, 0, &rules, &got[0][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 0 ::title");
        assert_eq!(listing_of(&t, 0, &rules, &got[0][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 0 ::body");
        assert_eq!(listing_of(&t, 0, &rules, &got[0][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 0 ::label");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][0]), vec![(r"font-family", r"var(--p)", Some(r"Parent"))], "element 1 ::");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 1 ::title");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 1 ::body");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 1 ::label");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][0]), vec![(r"font-family", r"var(--a)", Some(r"Inter"))], "element 2 ::");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 2 ::title");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 2 ::body");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 2 ::label");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][0]), vec![(r"font-family", r"var(--a)", Some(r"Inter"))], "element 3 ::");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 3 ::title");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 3 ::body");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 3 ::label");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][0]), vec![(r"font-family", r"var(--none)", Some(r"none"))], "element 4 ::");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 4 ::title");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 4 ::body");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 4 ::label");
    }

    #[test]
    fn cascade_var_fallbacks() {
        let t = cascade_fixture();
        let rules = vec![
            rule(0, &[r"node"], &[(r"font-family", r"var(--missing, rgb(1, 2, 3))", false)]),
            rule(1, &[r"group"], &[(r"font-family", r"var( --x , fallback )", false)]),
            rule(2, &[r"edge"], &[(r"font-family", r"var(--nope,)", false)])
        ];
        let got = cascade(&t, &rules);
        assert_eq!(listing_of(&t, 0, &rules, &got[0][0]), Vec::<(&str, &str, Option<&str>)>::new(), "element 0 ::");
        assert_eq!(listing_of(&t, 0, &rules, &got[0][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 0 ::title");
        assert_eq!(listing_of(&t, 0, &rules, &got[0][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 0 ::body");
        assert_eq!(listing_of(&t, 0, &rules, &got[0][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 0 ::label");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][0]), vec![(r"font-family", r"var( --x , fallback )", Some(r"fallback"))], "element 1 ::");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 1 ::title");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 1 ::body");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 1 ::label");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][0]), vec![(r"font-family", r"var(--missing, rgb(1, 2, 3))", Some(r"rgb(1, 2, 3)"))], "element 2 ::");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 2 ::title");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 2 ::body");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 2 ::label");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][0]), vec![(r"font-family", r"var(--missing, rgb(1, 2, 3))", Some(r"rgb(1, 2, 3)"))], "element 3 ::");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 3 ::title");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 3 ::body");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 3 ::label");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][0]), vec![(r"font-family", r"var(--nope,)", Some(r"nope"))], "element 4 ::");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 4 ::title");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 4 ::body");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 4 ::label");
    }

    #[test]
    fn cascade_var_pseudo_scope() {
        let t = cascade_fixture();
        let rules = vec![
            rule(0, &[r"node"], &[(r"--c", r"Own", false)]),
            rule(1, &[r"node::title"], &[(r"--d", r"PseudoOnly", false), (r"font-family", r"var(--c)", false)]),
            rule(2, &[r"node::body"], &[(r"font-family", r"var(--d)", false)]),
            rule(3, &[r"node::label"], &[(r"font-family", r"var(--c)", false)])
        ];
        let got = cascade(&t, &rules);
        assert_eq!(listing_of(&t, 0, &rules, &got[0][0]), Vec::<(&str, &str, Option<&str>)>::new(), "element 0 ::");
        assert_eq!(listing_of(&t, 0, &rules, &got[0][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 0 ::title");
        assert_eq!(listing_of(&t, 0, &rules, &got[0][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 0 ::body");
        assert_eq!(listing_of(&t, 0, &rules, &got[0][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 0 ::label");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][0]), Vec::<(&str, &str, Option<&str>)>::new(), "element 1 ::");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 1 ::title");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 1 ::body");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 1 ::label");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][0]), vec![(r"--c", r"Own", None)], "element 2 ::");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][1]), vec![(r"--d", r"PseudoOnly", None), (r"font-family", r"var(--c)", Some(r"Own"))], "element 2 ::title");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][2]), vec![(r"font-family", r"var(--d)", Some(r"d"))], "element 2 ::body");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][3]), vec![(r"font-family", r"var(--c)", Some(r"Own"))], "element 2 ::label");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][0]), vec![(r"--c", r"Own", None)], "element 3 ::");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][1]), vec![(r"--d", r"PseudoOnly", None), (r"font-family", r"var(--c)", Some(r"Own"))], "element 3 ::title");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][2]), vec![(r"font-family", r"var(--d)", Some(r"d"))], "element 3 ::body");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][3]), vec![(r"font-family", r"var(--c)", Some(r"Own"))], "element 3 ::label");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][0]), Vec::<(&str, &str, Option<&str>)>::new(), "element 4 ::");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 4 ::title");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 4 ::body");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 4 ::label");
    }

    #[test]
    fn cascade_var_custom_wins_by_cascade() {
        let mut t = cascade_fixture();
        t.nodes[2].inline = decls(&[(r"--k", r"Inline", false)]);
        let rules = vec![
            rule(0, &[r"node"], &[(r"--k", r"First", false)]),
            rule(1, &[r".hot"], &[(r"--k", r"Hot", false)]),
            rule(2, &[r"#n1"], &[(r"--k", r"Id", false)]),
            rule(3, &[r"node"], &[(r"font-family", r"var(--k)", false)])
        ];
        let got = cascade(&t, &rules);
        assert_eq!(listing_of(&t, 0, &rules, &got[0][0]), Vec::<(&str, &str, Option<&str>)>::new(), "element 0 ::");
        assert_eq!(listing_of(&t, 0, &rules, &got[0][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 0 ::title");
        assert_eq!(listing_of(&t, 0, &rules, &got[0][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 0 ::body");
        assert_eq!(listing_of(&t, 0, &rules, &got[0][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 0 ::label");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][0]), Vec::<(&str, &str, Option<&str>)>::new(), "element 1 ::");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 1 ::title");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 1 ::body");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 1 ::label");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][0]), vec![(r"--k", r"First", None), (r"font-family", r"var(--k)", Some(r"Inline")), (r"--k", r"Hot", None), (r"--k", r"Id", None), (r"--k", r"Inline", None)], "element 2 ::");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 2 ::title");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 2 ::body");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 2 ::label");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][0]), vec![(r"--k", r"First", None), (r"font-family", r"var(--k)", Some(r"First"))], "element 3 ::");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 3 ::title");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 3 ::body");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 3 ::label");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][0]), Vec::<(&str, &str, Option<&str>)>::new(), "element 4 ::");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 4 ::title");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 4 ::body");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 4 ::label");
    }

    #[test]
    fn cascade_var_nine_levels() {
        let t = cascade_fixture();
        let rules = vec![
            rule(0, &[r"node"], &[(r"--v0", r"var(--v1)", false), (r"--v1", r"var(--v2)", false), (r"--v2", r"var(--v3)", false), (r"--v3", r"var(--v4)", false), (r"--v4", r"var(--v5)", false), (r"--v5", r"var(--v6)", false), (r"--v6", r"var(--v7)", false), (r"--v7", r"var(--v8)", false), (r"--v8", r"var(--v9)", false), (r"--v9", r"End", false), (r"font-family", r"var(--v0)", false)])
        ];
        let got = cascade(&t, &rules);
        assert_eq!(listing_of(&t, 0, &rules, &got[0][0]), Vec::<(&str, &str, Option<&str>)>::new(), "element 0 ::");
        assert_eq!(listing_of(&t, 0, &rules, &got[0][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 0 ::title");
        assert_eq!(listing_of(&t, 0, &rules, &got[0][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 0 ::body");
        assert_eq!(listing_of(&t, 0, &rules, &got[0][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 0 ::label");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][0]), Vec::<(&str, &str, Option<&str>)>::new(), "element 1 ::");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 1 ::title");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 1 ::body");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 1 ::label");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][0]), vec![(r"--v0", r"var(--v1)", None), (r"--v1", r"var(--v2)", None), (r"--v2", r"var(--v3)", None), (r"--v3", r"var(--v4)", None), (r"--v4", r"var(--v5)", None), (r"--v5", r"var(--v6)", None), (r"--v6", r"var(--v7)", None), (r"--v7", r"var(--v8)", None), (r"--v8", r"var(--v9)", None), (r"--v9", r"End", None), (r"font-family", r"var(--v0)", Some(r"var(--v8)"))], "element 2 ::");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 2 ::title");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 2 ::body");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 2 ::label");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][0]), vec![(r"--v0", r"var(--v1)", None), (r"--v1", r"var(--v2)", None), (r"--v2", r"var(--v3)", None), (r"--v3", r"var(--v4)", None), (r"--v4", r"var(--v5)", None), (r"--v5", r"var(--v6)", None), (r"--v6", r"var(--v7)", None), (r"--v7", r"var(--v8)", None), (r"--v8", r"var(--v9)", None), (r"--v9", r"End", None), (r"font-family", r"var(--v0)", Some(r"var(--v8)"))], "element 3 ::");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 3 ::title");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 3 ::body");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 3 ::label");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][0]), Vec::<(&str, &str, Option<&str>)>::new(), "element 4 ::");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 4 ::title");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 4 ::body");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 4 ::label");
    }

    #[test]
    fn cascade_var_eight_levels() {
        let t = cascade_fixture();
        let rules = vec![
            rule(0, &[r"node"], &[(r"--v0", r"var(--v1)", false), (r"--v1", r"var(--v2)", false), (r"--v2", r"var(--v3)", false), (r"--v3", r"var(--v4)", false), (r"--v4", r"var(--v5)", false), (r"--v5", r"var(--v6)", false), (r"--v6", r"var(--v7)", false), (r"--v7", r"End", false), (r"font-family", r"var(--v0)", false)])
        ];
        let got = cascade(&t, &rules);
        assert_eq!(listing_of(&t, 0, &rules, &got[0][0]), Vec::<(&str, &str, Option<&str>)>::new(), "element 0 ::");
        assert_eq!(listing_of(&t, 0, &rules, &got[0][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 0 ::title");
        assert_eq!(listing_of(&t, 0, &rules, &got[0][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 0 ::body");
        assert_eq!(listing_of(&t, 0, &rules, &got[0][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 0 ::label");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][0]), Vec::<(&str, &str, Option<&str>)>::new(), "element 1 ::");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 1 ::title");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 1 ::body");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 1 ::label");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][0]), vec![(r"--v0", r"var(--v1)", None), (r"--v1", r"var(--v2)", None), (r"--v2", r"var(--v3)", None), (r"--v3", r"var(--v4)", None), (r"--v4", r"var(--v5)", None), (r"--v5", r"var(--v6)", None), (r"--v6", r"var(--v7)", None), (r"--v7", r"End", None), (r"font-family", r"var(--v0)", Some(r"End"))], "element 2 ::");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 2 ::title");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 2 ::body");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 2 ::label");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][0]), vec![(r"--v0", r"var(--v1)", None), (r"--v1", r"var(--v2)", None), (r"--v2", r"var(--v3)", None), (r"--v3", r"var(--v4)", None), (r"--v4", r"var(--v5)", None), (r"--v5", r"var(--v6)", None), (r"--v6", r"var(--v7)", None), (r"--v7", r"End", None), (r"font-family", r"var(--v0)", Some(r"End"))], "element 3 ::");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 3 ::title");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 3 ::body");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 3 ::label");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][0]), Vec::<(&str, &str, Option<&str>)>::new(), "element 4 ::");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 4 ::title");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 4 ::body");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 4 ::label");
    }

    #[test]
    fn cascade_var_unclosed() {
        let t = cascade_fixture();
        let rules = vec![
            rule(0, &[r"node"], &[(r"font-family", r"var(--oops })", false)])
        ];
        let got = cascade(&t, &rules);
        assert_eq!(listing_of(&t, 0, &rules, &got[0][0]), Vec::<(&str, &str, Option<&str>)>::new(), "element 0 ::");
        assert_eq!(listing_of(&t, 0, &rules, &got[0][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 0 ::title");
        assert_eq!(listing_of(&t, 0, &rules, &got[0][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 0 ::body");
        assert_eq!(listing_of(&t, 0, &rules, &got[0][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 0 ::label");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][0]), Vec::<(&str, &str, Option<&str>)>::new(), "element 1 ::");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 1 ::title");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 1 ::body");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 1 ::label");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][0]), vec![(r"font-family", r"var(--oops })", Some(r"oops }"))], "element 2 ::");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 2 ::title");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 2 ::body");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 2 ::label");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][0]), vec![(r"font-family", r"var(--oops })", Some(r"oops }"))], "element 3 ::");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 3 ::title");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 3 ::body");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 3 ::label");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][0]), Vec::<(&str, &str, Option<&str>)>::new(), "element 4 ::");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 4 ::title");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 4 ::body");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 4 ::label");
    }

    #[test]
    fn cascade_var_inline_uses_css_scope() {
        let mut t = cascade_fixture();
        t.nodes[2].inline = decls(&[(r"font-family", r"var(--z)", false)]);
        let rules = vec![
            rule(0, &[r"node"], &[(r"--z", r"FromRule", false)])
        ];
        let got = cascade(&t, &rules);
        assert_eq!(listing_of(&t, 0, &rules, &got[0][0]), Vec::<(&str, &str, Option<&str>)>::new(), "element 0 ::");
        assert_eq!(listing_of(&t, 0, &rules, &got[0][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 0 ::title");
        assert_eq!(listing_of(&t, 0, &rules, &got[0][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 0 ::body");
        assert_eq!(listing_of(&t, 0, &rules, &got[0][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 0 ::label");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][0]), Vec::<(&str, &str, Option<&str>)>::new(), "element 1 ::");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 1 ::title");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 1 ::body");
        assert_eq!(listing_of(&t, 1, &rules, &got[1][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 1 ::label");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][0]), vec![(r"--z", r"FromRule", None), (r"font-family", r"var(--z)", Some(r"FromRule"))], "element 2 ::");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 2 ::title");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 2 ::body");
        assert_eq!(listing_of(&t, 2, &rules, &got[2][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 2 ::label");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][0]), vec![(r"--z", r"FromRule", None)], "element 3 ::");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 3 ::title");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 3 ::body");
        assert_eq!(listing_of(&t, 3, &rules, &got[3][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 3 ::label");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][0]), Vec::<(&str, &str, Option<&str>)>::new(), "element 4 ::");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][1]), Vec::<(&str, &str, Option<&str>)>::new(), "element 4 ::title");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][2]), Vec::<(&str, &str, Option<&str>)>::new(), "element 4 ::body");
        assert_eq!(listing_of(&t, 4, &rules, &got[4][3]), Vec::<(&str, &str, Option<&str>)>::new(), "element 4 ::label");
    }

    // Expected strings come from Python's _substitute(value, {"--a": "Z"}).
    #[test]
    fn substitute_edge_cases_match_python() {
        let custom: HashMap<String, String> = HashMap::from([("--a".to_string(), "Z".to_string())]);
        for (value, want) in [
            ("a var(", "a "),
            ("var(", ""),
            ("x var(--a", "x "),
            ("var(--a) var(", "Z "),
            ("var(--a, (b)) c", "Z c"),
        ] {
            assert_eq!(substitute(value, &custom), want, "_substitute({value:?})");
        }
    }
}
