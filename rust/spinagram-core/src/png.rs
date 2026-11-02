//! PNG from an SVG with resvg, no browser. Text uses the given font files first, then the system fonts.

use std::sync::{Arc, OnceLock};

use resvg::{tiny_skia, usvg};
use thiserror::Error;

static SYSTEM_FONTS: OnceLock<usvg::fontdb::Database> = OnceLock::new();

fn system_fonts() -> &'static usvg::fontdb::Database {
    SYSTEM_FONTS.get_or_init(|| {
        let mut db = usvg::fontdb::Database::new();
        db.load_system_fonts();
        db
    })
}

#[expect(clippy::cast_possible_truncation, clippy::cast_sign_loss, reason = "pixel, glyph and count arithmetic on small non-negative values that f64, i64 and usize hold exactly")]
/// Pixels for `size * scale`, rounded like Python's `round` (halves to even).
fn pixels(size: f64, scale: f64) -> u32 {
    (size * scale).round_ties_even().max(1.0) as u32
}

/// Why a PNG could not be rendered.
#[derive(Debug, Error)]
pub enum PngError {
    /// A theme font file could not be loaded.
    #[error("font file {file}: {reason}")]
    Font {
        /// The file that failed.
        file: String,
        /// The loader's reason.
        reason: String,
    },
    /// The SVG did not parse.
    #[error("invalid SVG: {0}")]
    Svg(String),
    /// The image size is not allocatable.
    #[error("cannot allocate a {w}x{h} image")]
    Allocate {
        /// Width in px.
        w: u32,
        /// Height in px.
        h: u32,
    },
    /// The pixmap did not encode.
    #[error("cannot encode PNG: {0}")]
    Encode(String),
}

#[expect(clippy::cast_precision_loss, reason = "pixel, glyph and count arithmetic on small non-negative values that f64, i64 and usize hold exactly")]
/// Render `svg` (a `width` x `height` document) at `scale` to PNG bytes of `round(width*scale)` x `round(height*scale)`.
/// `font_files` are loaded before the system fonts, so a theme's own font wins over a system font of the same name.
///
/// # Errors
///
/// [`PngError`] when a font file cannot be loaded, the SVG is invalid, or the image cannot be allocated or encoded.
pub fn render_png(svg: &str, width: f64, height: f64, scale: f64, font_files: &[String]) -> Result<Vec<u8>, PngError> {
    let mut db = system_fonts().clone();
    for file in font_files {
        db.load_font_file(file).map_err(|e| PngError::Font { file: file.clone(), reason: e.to_string() })?;
    }
    let opt = usvg::Options { fontdb: Arc::new(db), ..usvg::Options::default() };
    let tree = usvg::Tree::from_str(svg, &opt).map_err(|e| PngError::Svg(e.to_string()))?;
    let (w, h) = (pixels(width, scale), pixels(height, scale));
    let mut pixmap = tiny_skia::Pixmap::new(w, h).ok_or(PngError::Allocate { w, h })?;
    let size = tree.size();
    let transform = tiny_skia::Transform::from_scale(w as f32 / size.width(), h as f32 / size.height());
    resvg::render(&tree, transform, &mut pixmap.as_mut());
    pixmap.encode_png().map_err(|e| PngError::Encode(e.to_string()))
}

#[cfg(test)]
mod tests {
    use super::*;

    const FONTS: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/../../src/spinagram/fonts");

    fn dims(png: &[u8]) -> (u32, u32) {
        assert_eq!(&png[..8], b"\x89PNG\r\n\x1a\n");
        (u32::from_be_bytes(png[16..20].try_into().unwrap()), u32::from_be_bytes(png[20..24].try_into().unwrap()))
    }

    const BOX: &str = "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 300 200\" width=\"300\" height=\"200\"><rect width=\"300\" height=\"200\" fill=\"#fff\"/><rect x=\"10\" y=\"10\" width=\"50\" height=\"50\" fill=\"#c00\"/></svg>";

    #[test]
    fn scale_gives_rounded_pixel_size() {
        assert_eq!(dims(&render_png(BOX, 300.0, 200.0, 1.5, &[]).unwrap()), (450, 300));
    }

    #[test]
    fn size_rounds_halves_to_even_like_python() {
        // Python: round(301 * 0.5) == 150 (150.5 -> even), round(303 * 0.5) == 152 (151.5 -> even)
        assert_eq!(pixels(301.0, 0.5), 150);
        assert_eq!(pixels(303.0, 0.5), 152);
    }

    fn text_svg() -> String {
        "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 120 60\" width=\"120\" height=\"60\"><rect width=\"120\" height=\"60\" fill=\"#fff\"/><text x=\"10\" y=\"45\" font-family=\"&apos;Noto Sans Math&apos;\" font-size=\"40\" fill=\"#000\">\u{2211}</text></svg>".to_string()
    }

    #[test]
    fn text_is_drawn_with_the_given_font_file() {
        let file = format!("{FONTS}/NotoSansMath-Regular.ttf");
        let with = render_png(&text_svg(), 120.0, 60.0, 1.0, &[file]).unwrap();
        let without = render_png(&text_svg(), 120.0, 60.0, 1.0, &[]).unwrap();
        let blank = render_png(&text_svg().replace('\u{2211}', " "), 120.0, 60.0, 1.0, &[]).unwrap();
        assert_ne!(with, without, "the font file must change the glyphs");
        assert_ne!(with, blank, "the text must draw something");
    }
}
