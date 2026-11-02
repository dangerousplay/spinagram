//! spinagram engine core: font metrics, text measurement, wrapping and fitting, edge routing, the CSS cascade, the
//! scene and its SVG and PNG writers, and the edit operations on diagram YAML. `spinagram-core-py` compiles it
//! into the spinagram Python package as `spinagram._core`; `spinagram-wasm` runs it in the browser.

#![warn(missing_docs)]

pub mod css;
pub mod edge_syntax;
pub mod edit;
pub mod edit_values;
pub mod fit;
pub mod font;
#[cfg(feature = "png")]
pub mod png;
pub(crate) mod pyfmt;
pub mod reroute;
pub mod route;
pub mod scene;
pub mod svg;
pub mod text;
pub(crate) mod verified;
pub(crate) mod yaml_span;

pub use yaml_span::YamlError;
