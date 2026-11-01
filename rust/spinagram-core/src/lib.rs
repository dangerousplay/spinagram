//! spinagram engine core. The first slice ported from Python: font metrics, text measurement, wrapping
//! and fitting. `spinagram-core-py` compiles it into the spinagram Python package as `spinagram._core`.

pub mod fit;
pub mod css;
pub mod font;
pub mod pyfmt;
#[cfg(feature = "png")]
pub mod png;
pub mod route;
pub mod scene;
pub mod svg;
pub mod text;
pub mod verified;
