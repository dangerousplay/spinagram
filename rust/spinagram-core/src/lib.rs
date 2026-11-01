//! spinagram engine core. The first slice ported from Python: font metrics, text measurement, wrapping
//! and fitting. The Python package keeps working without it; `spinagram-core-py` exposes it to Python.

pub mod fit;
pub mod css;
pub mod font;
pub mod pyfmt;
pub mod png;
pub mod route;
pub mod scene;
pub mod svg;
pub mod text;
pub mod verified;
