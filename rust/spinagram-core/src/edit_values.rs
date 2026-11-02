//! The closed sets of values an edit operation takes: container axis and alignment, and the keys (with the kind
//! of value each takes) that `set_props` accepts for a node, a zone and an edge.

use std::str::FromStr;

use schemars::JsonSchema;
use serde::{Deserialize, Deserializer, Serialize};
use strum::{Display, EnumString, IntoStaticStr, VariantArray, VariantNames};

/// The direction of a container.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize, JsonSchema, Display, EnumString, IntoStaticStr, VariantArray, VariantNames)]
#[serde(rename_all = "lowercase")]
#[strum(serialize_all = "lowercase")]
pub enum Axis {
    /// Members side by side (`rows:`).
    Row,
    /// Members stacked (`columns:`).
    Column,
}

impl Axis {
    /// The top-level YAML key that holds containers of this axis.
    #[must_use]
    pub fn key(self) -> &'static str {
        match self {
            Axis::Row => "rows",
            Axis::Column => "columns",
        }
    }
}

/// How a container placed in a zone sits in the zone's content area.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Display, EnumString, VariantNames)]
#[strum(serialize_all = "lowercase")]
pub enum Align {
    /// Centred (the loader's default in a zone).
    Center,
    /// At the start.
    Start,
    /// At the end.
    End,
}

/// The `arrow` of an edge.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Display, EnumString, VariantNames)]
#[strum(serialize_all = "lowercase")]
pub enum Arrow {
    /// Arrow head at the destination.
    End,
    /// Arrow head at the source.
    Start,
    /// Arrow heads at both ends.
    Both,
    /// No arrow heads.
    None,
}

/// The `route` of an edge.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Display, EnumString, VariantNames)]
#[strum(serialize_all = "lowercase")]
pub enum RouteKind {
    /// Right-angle routing around obstacles.
    Ortho,
    /// A single elbow.
    Elbow,
}

/// A deserializer for a field holding a name from a closed set: the error names the field and lists the values.
fn named<'de, D, T>(d: D, field: &str) -> Result<T, D::Error>
where
    D: Deserializer<'de>,
    T: FromStr + VariantNames,
{
    let s = String::deserialize(d)?;
    s.parse().map_err(|_| serde::de::Error::custom(format!("`{field}` must be one of {}, not `{s}`", T::VARIANTS.join(", "))))
}

/// `Axis` for `#[serde(deserialize_with)]`.
pub(crate) fn axis<'de, D: Deserializer<'de>>(d: D) -> Result<Axis, D::Error> {
    named(d, "axis")
}

/// `Option<Align>` for `#[serde(deserialize_with)]`.
pub(crate) fn align<'de, D: Deserializer<'de>>(d: D) -> Result<Option<Align>, D::Error> {
    Option::<String>::deserialize(d)?.map(|s| named(serde::de::value::StrDeserializer::<D::Error>::new(&s), "align")).transpose()
}

/// What a property's JSON value must be.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum PropKind {
    Str,
    Num,
    Bool,
    /// a string, number, boolean, list or mapping (the loader checks the rest)
    Any,
    /// one of [`Arrow`]
    Arrow,
    /// one of [`RouteKind`]
    Route,
}

/// What a `set_props` key belongs to.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum Owner {
    Node,
    Zone,
    Edge,
}

/// The keys `set_props` accepts for a node: the loader's `_NODE_KEYS` and `_NODE_EXTRA` (`src/spinagram/yaml_io.py`)
/// without the geometry (`x`, `y`, `w`, `h`, `at`: move and resize) and `id`.
#[derive(Clone, Debug, PartialEq, Eq, EnumString)]
#[strum(serialize_all = "snake_case")]
pub(crate) enum NodeProp {
    Kind,
    Title,
    Text,
    Lines,
    Style,
    Icon,
    IconSize,
    Align,
    TitleSize,
    BodySize,
    Radius,
    Dashed,
    Color,
    In,
    Class,
    Css,
    Cell,
    Weight,
    Font,
    Variant,
    Fit,
    MinScale,
    BreakOn,
    Badges,
    Size,
    Role,
    MaxWidth,
    /// `x-*`: any value, kept for tools
    #[strum(disabled)]
    Extension,
}

impl NodeProp {
    fn parse(key: &str) -> Option<Self> {
        key.parse().ok().or_else(|| key.starts_with("x-").then_some(NodeProp::Extension))
    }

    fn kind(&self) -> PropKind {
        match self {
            Self::Kind | Self::Title | Self::Text | Self::Style | Self::Align | Self::Color | Self::In | Self::Class | Self::Css | Self::Font | Self::Variant | Self::Fit | Self::Role => PropKind::Str,
            Self::IconSize | Self::TitleSize | Self::BodySize | Self::Radius | Self::MinScale | Self::Size | Self::MaxWidth => PropKind::Num,
            Self::Dashed => PropKind::Bool,
            Self::Lines | Self::Icon | Self::Cell | Self::Weight | Self::BreakOn | Self::Badges | Self::Extension => PropKind::Any,
        }
    }
}

/// The keys for a zone: the fields of the model's `Zone` the loader passes through, without the geometry, `id`,
/// `children` (reparent) and `gid` (set by the layout).
#[derive(Clone, Copy, Debug, PartialEq, Eq, EnumString)]
#[strum(serialize_all = "snake_case")]
pub(crate) enum ZoneProp {
    Label,
    Color,
    Icon,
    Dash,
    Stroke,
    StrokeWidth,
    Fill,
    Header,
    Fit,
    Padding,
    Equalize,
    Band,
    Meaning,
    Class,
}

impl ZoneProp {
    fn kind(self) -> PropKind {
        match self {
            Self::Label | Self::Color | Self::Stroke | Self::Fill | Self::Fit | Self::Equalize | Self::Meaning | Self::Class => PropKind::Str,
            Self::StrokeWidth | Self::Padding => PropKind::Num,
            Self::Icon | Self::Dash | Self::Header | Self::Band => PropKind::Any,
        }
    }
}

/// The keys for an edge mapping: the fields of the model's `Edge`, without the ends (reconnect).
#[derive(Clone, Copy, Debug, PartialEq, Eq, EnumString)]
#[strum(serialize_all = "snake_case")]
pub(crate) enum EdgeProp {
    Label,
    LabelAt,
    Color,
    Dashed,
    Width,
    Via,
    Curve,
    Arrow,
    LabelSize,
    Class,
    Css,
    Fan,
    Route,
    FanIn,
    Meaning,
    Straight,
    Mid,
}

impl EdgeProp {
    fn kind(self) -> PropKind {
        match self {
            Self::Label | Self::Color | Self::Class | Self::Css | Self::Fan | Self::Meaning => PropKind::Str,
            Self::Width | Self::LabelSize | Self::Mid => PropKind::Num,
            Self::Dashed | Self::FanIn | Self::Straight => PropKind::Bool,
            Self::LabelAt | Self::Via | Self::Curve => PropKind::Any,
            Self::Arrow => PropKind::Arrow,
            Self::Route => PropKind::Route,
        }
    }
}

/// The kind of value `key` takes on an `owner`, or `None` when it is not a property of it.
pub(crate) fn prop_kind(owner: Owner, key: &str) -> Option<PropKind> {
    match owner {
        Owner::Node => NodeProp::parse(key).map(|p| p.kind()),
        Owner::Zone => key.parse::<ZoneProp>().ok().map(ZoneProp::kind),
        Owner::Edge => key.parse::<EdgeProp>().ok().map(EdgeProp::kind),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn axis_and_align_read_their_lowercase_names() {
        assert_eq!("row".parse(), Ok(Axis::Row));
        assert_eq!(Axis::Column.to_string(), "column");
        assert_eq!(Axis::Column.key(), "columns");
        assert_eq!(<Axis as VariantNames>::VARIANTS, ["row", "column"]);
        assert!("diagonal".parse::<Axis>().is_err());
        assert_eq!(Align::VARIANTS, ["center", "start", "end"]);
        assert_eq!(Arrow::VARIANTS, ["end", "start", "both", "none"]);
        assert_eq!(RouteKind::VARIANTS, ["ortho", "elbow"]);
    }

    #[test]
    fn property_keys_keep_their_names_and_kinds() {
        assert_eq!(prop_kind(Owner::Node, "icon_size"), Some(PropKind::Num));
        assert_eq!(prop_kind(Owner::Node, "in"), Some(PropKind::Str));
        assert_eq!(prop_kind(Owner::Node, "x-note"), Some(PropKind::Any));
        assert_eq!(prop_kind(Owner::Zone, "x-note"), None);
        assert_eq!(prop_kind(Owner::Zone, "stroke_width"), Some(PropKind::Num));
        assert_eq!(prop_kind(Owner::Edge, "arrow"), Some(PropKind::Arrow));
        assert_eq!(prop_kind(Owner::Edge, "fan_in"), Some(PropKind::Bool));
        assert_eq!(prop_kind(Owner::Edge, "x"), None);
        assert_eq!(prop_kind(Owner::Node, "extension"), None);
    }
}
