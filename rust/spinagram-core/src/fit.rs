//! Fit text blocks to a box: wrap, break long tokens, shrink in 1 px steps, then grow. A port of
//! `fit_blocks` in `spinagram/engine/textfit.py`.

use crate::text::{Font, Measurer};

pub const MODES: [&str; 4] = ["none", "shrink", "grow", "shrink-then-grow"];
pub const MIN_SCALE: f64 = 0.85;

/// One text block to fit: source paragraphs, font at its base size, line height factor.
#[derive(Clone, Debug)]
pub struct BlockSpec {
    pub paragraphs: Vec<String>,
    pub font: Font,
    pub leading: f64,
}

/// A fitted block: its wrapped lines, final font and line height in px.
#[derive(Clone, Debug)]
pub struct Block {
    pub lines: Vec<String>,
    pub font: Font,
    pub leading: f64,
}

#[derive(Clone, Debug)]
pub struct FitResult {
    pub blocks: Vec<Block>,
    pub height: f64,
    pub strategy: &'static str,
    pub ok: bool,
    pub size: f64,
}

#[expect(clippy::cast_possible_truncation, reason = "pixel, glyph and count arithmetic on small non-negative values that f64, i64 and usize hold exactly")]
fn floor_step(sp: &BlockSpec, min_scale: f64) -> i64 {
    (sp.font.size - sp.font.size * min_scale + 1e-9).floor() as i64
}

#[expect(clippy::cast_precision_loss, reason = "pixel, glyph and count arithmetic on small non-negative values that f64, i64 and usize hold exactly")]
fn height(blocks: &[Block], gap: f64) -> f64 {
    blocks.iter().map(|b| b.lines.len() as f64 * b.leading).sum::<f64>() + gap * blocks.len().saturating_sub(1) as f64
}

struct Fitter<'a> {
    m: &'a Measurer,
    specs: Vec<&'a BlockSpec>,
    width: f64,
    break_on: &'a str,
    plain: bool,
    min_scale: f64,
}

impl Fitter<'_> {
    #[expect(clippy::cast_precision_loss, reason = "pixel, glyph and count arithmetic on small non-negative values that f64, i64 and usize hold exactly")]
    fn lay(&self, step: i64) -> Vec<Block> {
        self.specs
            .iter()
            .map(|sp| {
                let s = step.min(floor_step(sp, self.min_scale));
                let font = if s != 0 { sp.font.with_size(sp.font.size - s as f64) } else { sp.font.clone() };
                let lines = if self.plain {
                    self.m.wrap_paragraphs(&sp.paragraphs, &font, self.width)
                } else {
                    self.m.wrap_fit(&sp.paragraphs, &font, self.width, self.break_on)
                };
                Block { lines, leading: font.size * sp.leading, font }
            })
            .collect()
    }

    fn fits_width(&self, blocks: &[Block]) -> bool {
        blocks.iter().all(|b| b.lines.iter().all(|ln| self.m.measure(ln, &b.font) <= self.width + 0.5))
    }
}

/// Fit `specs` into `width` x `max_height`: wrap at spaces, break tokens at safe points, then (by `mode`)
/// shrink every block in 1 px steps down to `min_scale` of its size, then grow the height.
///
/// # Errors
///
/// When `mode` is not one of `MODES`.
#[expect(clippy::too_many_arguments, reason = "mirrors the Python function: one argument per input")]
pub fn fit_blocks(
    m: &Measurer,
    specs: &[BlockSpec],
    width: f64,
    max_height: f64,
    mode: &str,
    min_scale: f64,
    break_on: &str,
    gap: f64,
) -> Result<FitResult, String> {
    if !MODES.contains(&mode) {
        return Err(format!("fit '{mode}'; use one of {}", MODES.join(", ")));
    }
    let specs: Vec<&BlockSpec> = specs.iter().filter(|sp| !sp.paragraphs.is_empty()).collect();
    if specs.is_empty() {
        return Ok(FitResult { blocks: vec![], height: 0.0, strategy: "none", ok: true, size: 0.0 });
    }
    let plain = mode == "none";
    let f = Fitter { m, specs, width, break_on, plain, min_scale };
    let done = |blocks: Vec<Block>, strategy, ok| {
        let (h, size) = (height(&blocks, gap), blocks[0].font.size);
        FitResult { blocks, height: h, strategy, ok, size }
    };
    let fits = |blocks: &[Block]| f.fits_width(blocks) && height(blocks, gap) <= max_height + 0.5;

    let mut blocks = f.lay(0);
    let wrapped = blocks.iter().zip(&f.specs).all(|(b, sp)| b.lines == m.wrap_paragraphs(&sp.paragraphs, &b.font, width));
    let strategy = if plain || wrapped { "wrap" } else { "break" };
    if plain || fits(&blocks) {
        let ok = fits(&blocks);
        return Ok(done(blocks, strategy, ok));
    }
    let mut first_width_fit = f.fits_width(&blocks).then(|| blocks.clone());
    let mut strategy = strategy;
    if mode.contains("shrink") {
        strategy = "shrink";
        let max_step = f.specs.iter().map(|sp| floor_step(sp, min_scale)).max().unwrap_or(0);
        for step in 1..=max_step {
            blocks = f.lay(step);
            if first_width_fit.is_none() && f.fits_width(&blocks) {
                first_width_fit = Some(blocks.clone());
            }
            if fits(&blocks) {
                return Ok(done(blocks, strategy, true));
            }
        }
    }
    if mode.contains("grow") {
        if let Some(b) = first_width_fit {
            return Ok(done(b, "grow", true)); // the largest size whose lines fit, taller box
        }
        strategy = "grow"; // tried last: no size makes the lines fit the width, so height cannot help
    }
    Ok(done(blocks, strategy, false))
}
