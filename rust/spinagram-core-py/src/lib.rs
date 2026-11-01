//! Python bindings for spinagram-core, compiled into spinagram as `spinagram._core`. Fonts cross the boundary as
//! `(file or None, size, weight)`; the fallback chain is a list of font file paths.

#![expect(clippy::needless_pass_by_value, reason = "PyO3 extracts owned arguments (Vec, String, tuples) from Python objects")]

use pyo3::exceptions::{PyFileNotFoundError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::PyBytes;
use spinagram_core::fit::{self, BlockSpec};
use spinagram_core::font;
use spinagram_core::css;
use spinagram_core::edit;
use spinagram_core::png;
use spinagram_core::scene;
use spinagram_core::svg::{self, DrawError};
use spinagram_core::route::{self as core_route, Crossings, Options, Pt, Rect, Side};
use spinagram_core::text::{Font, Measurer};

type FontArgs = (Option<String>, f64, u16);

fn to_font((file, size, weight): FontArgs) -> PyResult<Font> {
    let face = file.map(|p| font::load(&p)).transpose().map_err(PyValueError::new_err)?;
    Ok(Font { face, size, weight })
}

fn measurer(fallbacks: Vec<String>) -> PyResult<Measurer> {
    let fallbacks = fallbacks.iter().map(|p| font::load(p)).collect::<Result<_, _>>().map_err(PyValueError::new_err)?;
    Ok(Measurer { fallbacks })
}

#[pyfunction]
fn covers(file: &str, ch: char) -> PyResult<bool> {
    Ok(font::load(file).map_err(PyValueError::new_err)?.covers(ch))
}

#[pyfunction]
fn measure(py: Python<'_>, text: &str, font: FontArgs, fallbacks: Vec<String>) -> PyResult<f64> {
    let (f, m) = (to_font(font)?, measurer(fallbacks)?);
    Ok(py.detach(|| m.measure(text, &f)))
}

#[pyfunction]
fn wrap_paragraphs(paragraphs: Vec<String>, font: FontArgs, width: f64, fallbacks: Vec<String>) -> PyResult<Vec<String>> {
    Ok(measurer(fallbacks)?.wrap_paragraphs(&paragraphs, &to_font(font)?, width))
}

#[pyfunction]
fn wrap_fit(paragraphs: Vec<String>, font: FontArgs, width: f64, break_on: &str, fallbacks: Vec<String>) -> PyResult<Vec<String>> {
    Ok(measurer(fallbacks)?.wrap_fit(&paragraphs, &to_font(font)?, width, break_on))
}

/// `specs` is a list of `(paragraphs, font, leading)`. Returns
/// `([(lines, size, leading_px), ...], height, strategy, ok, size)`.
#[pyfunction]
#[pyo3(signature = (specs, width, height, mode, min_scale, break_on, gap, fallbacks))]
#[expect(clippy::too_many_arguments, clippy::type_complexity, reason = "mirrors the Python call: one argument per input, a nested result tuple")]
fn fit_blocks(
    py: Python<'_>,
    specs: Vec<(Vec<String>, FontArgs, f64)>,
    width: f64,
    height: f64,
    mode: &str,
    min_scale: f64,
    break_on: &str,
    gap: f64,
    fallbacks: Vec<String>,
) -> PyResult<(Vec<(Vec<String>, f64, f64)>, f64, &'static str, bool, f64)> {
    let m = measurer(fallbacks)?;
    let specs = specs
        .into_iter()
        .map(|(paragraphs, f, leading)| Ok(BlockSpec { paragraphs, font: to_font(f)?, leading }))
        .collect::<PyResult<Vec<_>>>()?;
    let r = py
        .detach(|| fit::fit_blocks(&m, &specs, width, height, mode, min_scale, break_on, gap))
        .map_err(PyValueError::new_err)?;
    let blocks = r.blocks.into_iter().map(|b| (b.lines, b.font.size, b.leading)).collect();
    Ok((blocks, r.height, r.strategy, r.ok, r.size))
}

type Segments = Vec<(Pt, Pt)>;

fn side(name: &str) -> PyResult<Side> {
    Side::from_name(name).ok_or_else(|| PyValueError::new_err(format!("unknown side {name:?}")))
}

fn sides(names: Vec<String>) -> PyResult<Vec<Side>> {
    names.iter().map(|n| side(n)).collect()
}

/// Orthogonal edge route, a port of `autolayout.route.route`. `crossing` is `(cost, drawn_segments)`.
/// Returns the polyline as a list of `(x, y)`.
#[pyfunction]
#[pyo3(signature = (src, dst, obstacles, margin, sides_, busy_src, busy_dst, crossing, guides, fracs))]
#[expect(clippy::too_many_arguments, reason = "mirrors the Python call: one argument per input")]
fn route(
    py: Python<'_>,
    src: Rect,
    dst: Rect,
    obstacles: Vec<Rect>,
    margin: f64,
    sides_: (Option<String>, Option<String>),
    busy_src: Vec<String>,
    busy_dst: Vec<String>,
    crossing: Option<(f64, Segments)>,
    guides: Vec<Pt>,
    fracs: (Option<f64>, Option<f64>),
) -> PyResult<Vec<Pt>> {
    let fixed = (sides_.0.as_deref().map(side).transpose()?, sides_.1.as_deref().map(side).transpose()?);
    let (busy_src, busy_dst) = (sides(busy_src)?, sides(busy_dst)?);
    let crossing = crossing.map(|(cost, drawn)| Crossings { cost, drawn });
    Ok(py.detach(|| {
        let o = Options { margin, sides: fixed, busy_src: &busy_src, busy_dst: &busy_dst, crossing: crossing.as_ref(), guides: &guides, fracs };
        core_route::route(src, dst, &obstacles, &o)
    }))
}

/// Parse scene JSON and write it back (the schema and round-trip check). Raises `ValueError` on a bad scene.
#[pyfunction]
fn scene_roundtrip(json: &str) -> PyResult<String> {
    let parsed = scene::parse(json).map_err(PyValueError::new_err)?;
    Ok(scene::to_json(&parsed))
}

type Chars = Vec<(String, u32, bool, String)>;

/// Draw the items of a scene JSON as SVG fragments: `(defs, back, mid, front, chars)` where `chars` lists
/// `(family, weight, italic, characters)` for each face drawn. `compensated_sum` is `sys.version_info >= (3, 12)`:
/// whether Python's `sum()` is compensated. A missing image raises `FileNotFoundError`.
#[pyfunction]
fn svg_draw(py: Python<'_>, json: &str, compensated_sum: bool) -> PyResult<(String, String, String, String, Chars)> {
    let drawn = py
        .detach(|| scene::parse(json).map_err(DrawError::Scene).and_then(|s| svg::draw(&s, compensated_sum)))
        .map_err(|e| match e {
            DrawError::NotFound(p) => PyFileNotFoundError::new_err(format!("[Errno 2] No such file or directory: '{p}'")),
            other => PyValueError::new_err(other.to_string()),
        })?;
    let chars = drawn.chars.into_iter().map(|((fam, w, it), cs)| (fam, w, it, cs.into_iter().collect())).collect();
    Ok((drawn.defs, drawn.back, drawn.mid, drawn.front, chars))
}

/// Render an SVG document of `width` x `height` to PNG bytes at `scale` with resvg (no browser). `font_files` are
/// loaded before the system fonts.
#[pyfunction]
fn render_png<'py>(py: Python<'py>, svg: &str, width: f64, height: f64, scale: f64, font_files: Vec<String>) -> PyResult<Bound<'py, PyBytes>> {
    let bytes = py.detach(|| png::render_png(svg, width, height, scale, &font_files)).map_err(PyValueError::new_err)?;
    Ok(PyBytes::new(py, &bytes))
}

/// The CSS cascade of a style tree (JSON) under rules (JSON): per element and pseudo-element the matched
/// declarations in cascade order, as JSON. `ValueError` when a selector cannot be parsed.
#[pyfunction]
fn css_cascade(py: Python<'_>, tree: &str, rules: &str) -> PyResult<String> {
    py.detach(|| css::cascade_json(tree, rules)).map_err(PyValueError::new_err)
}

/// For each selector text, the indices of the elements of a style tree (JSON) it matches, as JSON.
#[pyfunction]
fn css_select(py: Python<'_>, tree: &str, selectors: Vec<String>) -> PyResult<String> {
    py.detach(|| css::select_json(tree, &selectors)).map_err(PyValueError::new_err)
}

/// Apply a JSON list of edit operations to YAML text as one batch; returns the patched text. `ValueError` with the
/// reason (the operation that failed and why) when the batch is rejected.
#[pyfunction]
fn apply_ops(py: Python<'_>, yaml: &str, ops_json: &str) -> PyResult<String> {
    py.detach(|| edit::apply_ops_json(yaml, ops_json)).map_err(PyValueError::new_err)
}

/// `{id: (start, end)}`: the UTF-8 byte range of the YAML entry of every node, zone and edge (`e0`, `e1`, ...).
#[pyfunction]
fn yaml_srcmap(py: Python<'_>, yaml: &str) -> PyResult<std::collections::BTreeMap<String, (usize, usize)>> {
    let map = py.detach(|| edit::srcmap(yaml)).map_err(PyValueError::new_err)?;
    Ok(map.into_iter().map(|(k, [a, b])| (k, (a, b))).collect())
}

#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Linker workaround, see rust/README.md: the macOS 27 linker writes a misaligned string table (and dyld
    // refuses the module) when the number of indirect symbols is odd. Touching Python data symbols adds GOT
    // entries; add or remove one here when the module stops importing.
    std::hint::black_box(unsafe { pyo3::ffi::PyExc_KeyError });
    std::hint::black_box(unsafe { pyo3::ffi::PyExc_IndexError });
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    m.add_function(wrap_pyfunction!(covers, m)?)?;
    m.add_function(wrap_pyfunction!(measure, m)?)?;
    m.add_function(wrap_pyfunction!(wrap_paragraphs, m)?)?;
    m.add_function(wrap_pyfunction!(wrap_fit, m)?)?;
    m.add_function(wrap_pyfunction!(fit_blocks, m)?)?;
    m.add_function(wrap_pyfunction!(route, m)?)?;
    m.add_function(wrap_pyfunction!(scene_roundtrip, m)?)?;
    m.add_function(wrap_pyfunction!(svg_draw, m)?)?;
    m.add_function(wrap_pyfunction!(css_cascade, m)?)?;
    m.add_function(wrap_pyfunction!(css_select, m)?)?;
    m.add_function(wrap_pyfunction!(render_png, m)?)?;
    m.add_function(wrap_pyfunction!(apply_ops, m)?)?;
    m.add_function(wrap_pyfunction!(yaml_srcmap, m)?)?;
    Ok(())
}
