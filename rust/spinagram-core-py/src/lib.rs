//! Python bindings for spinagram-core, imported as `spinagram_core._core`. Fonts cross the boundary as
//! `(file or None, size, weight)`; the fallback chain is a list of font file paths.

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use spinagram_core::fit::{self, BlockSpec};
use spinagram_core::font;
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
#[allow(clippy::too_many_arguments, clippy::type_complexity)]
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

#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    m.add_function(wrap_pyfunction!(covers, m)?)?;
    m.add_function(wrap_pyfunction!(measure, m)?)?;
    m.add_function(wrap_pyfunction!(wrap_paragraphs, m)?)?;
    m.add_function(wrap_pyfunction!(wrap_fit, m)?)?;
    m.add_function(wrap_pyfunction!(fit_blocks, m)?)?;
    Ok(())
}
