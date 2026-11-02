//! Font faces: glyph coverage and advance widths read from TrueType/OpenType files with skrifa.
//!
//! Widths follow `spinagram.text`, which measures with Pillow at 10x the size and divides by ten: each glyph
//! advance is rounded to whole pixels at that size (`ppem = round(size * 10)`), then the sum is scaled back.

use std::collections::HashMap;
use std::sync::{Arc, Mutex, OnceLock, PoisonError};

use skrifa::instance::{LocationRef, Size};
use skrifa::raw::TableProvider;
use skrifa::{FontRef, MetadataProvider};
use thiserror::Error;

/// Why a font could not be loaded.
#[derive(Debug, Error)]
pub enum FontError {
    /// The bytes are not a font the metrics reader accepts.
    #[error("not a font: {0}")]
    NotAFont(String),
    /// The file could not be read.
    #[error("{path}: {reason}")]
    Read {
        /// The path that was opened.
        path: String,
        /// The operating system's reason.
        reason: String,
    },
    /// No file system (wasm32) and the font was never registered.
    #[error("{0}: font not registered (no file system on wasm32)")]
    NotRegistered(String),
    /// A registered font that did not parse.
    #[error("{name}: {source}")]
    Named {
        /// The name it was registered under.
        name: String,
        /// Why it did not parse.
        source: Box<FontError>,
    },
}

/// One face of a font file: units per em, the advance of every mapped character, and `.notdef`.
#[derive(Debug)]
pub struct Face {
    upem: f64,
    glyphs: HashMap<u32, (u32, i64)>, // char → (glyph id, advance in font units)
    notdef: i64,
    kern: HashMap<(u32, u32), i64>,    // legacy `kern` table pairs, horizontal format 0
}

impl Face {
    /// # Errors
    ///
    /// When the bytes are not a font the metrics reader accepts.
    #[expect(clippy::cast_possible_truncation, reason = "pixel, glyph and count arithmetic on small non-negative values that f64, i64 and usize hold exactly")]
    pub fn from_bytes(data: &[u8], index: u32) -> Result<Face, FontError> {
        let font = FontRef::from_index(data, index).map_err(|e| FontError::NotAFont(e.to_string()))?;
        let upem = f64::from(font.head().map_err(|e| FontError::NotAFont(e.to_string()))?.units_per_em());
        let metrics = font.glyph_metrics(Size::unscaled(), LocationRef::default());
        let advance = |gid| metrics.advance_width(gid).unwrap_or(0.0) as i64;
        let glyphs = font.charmap().mappings().map(|(ch, gid)| (ch, (gid.to_u32(), advance(gid)))).collect();
        Ok(Face { upem, glyphs, notdef: advance(skrifa::GlyphId::NOTDEF), kern: kern_pairs(&font) })
    }

    /// Whether the face has a glyph for `ch`.
    #[must_use]
    pub fn covers(&self, ch: char) -> bool {
        self.glyphs.contains_key(&(ch as u32))
    }

    #[expect(clippy::cast_possible_truncation, clippy::cast_precision_loss, reason = "pixel, glyph and count arithmetic on small non-negative values that f64, i64 and usize hold exactly")]
    /// Width of `text` at `size` px, measured the way Pillow does at 10x (see the module docs).
    #[must_use]
    pub fn length(&self, text: &str, size: f64) -> f64 {
        let ppem = (size * 10.0).round().max(1.0) as i64;
        // FreeType's 16.16 fixed-point scale and 26.6 pixel rounding, so advances match Pillow to the unit
        let x_scale = div_fix(ppem * 64, self.upem as i64);
        let (mut total, mut last) = (0i64, 0u32);
        for ch in text.chars() {
            let (gid, units) = self.glyphs.get(&(ch as u32)).copied().unwrap_or((0, self.notdef));
            total += pix_round(mul_fix(units, x_scale));
            if last != 0 && gid != 0 {
                if let Some(&k) = self.kern.get(&(last, gid)) {
                    // Pillow adds the grid-fitted kerning in whole pixels to a 26.6 advance, so it counts 1/64
                    total += pix_round(mul_fix(k, x_scale)) >> 6;
                }
            }
            last = gid;
        }
        total as f64 / 64.0 / 10.0
    }
}

fn pix_round(x: i64) -> i64 {
    (x + 32) & !63
}

/// Pairs of the horizontal format 0 subtables of the legacy `kern` table, summed like `FreeType` does.
fn kern_pairs(font: &FontRef) -> HashMap<(u32, u32), i64> {
    use skrifa::raw::tables::kern::SubtableKind;
    let mut pairs = HashMap::new();
    let Ok(kern) = font.kern() else { return pairs };
    for sub in kern.subtables().flatten() {
        if !sub.is_horizontal() || sub.is_cross_stream() {
            continue;
        }
        if let Ok(SubtableKind::Format0(f0)) = sub.kind() {
            for p in f0.pairs() {
                *pairs.entry((p.left().to_u32(), p.right().to_u32())).or_insert(0) += i64::from(p.value());
            }
        }
    }
    pairs
}

/// `FT_DivFix`: (a << 16) / b, rounded.
fn div_fix(a: i64, b: i64) -> i64 {
    ((a << 16) + b / 2) / b
}

/// `FT_MulFix`: (a * b) >> 16, rounded half away from zero.
fn mul_fix(a: i64, b: i64) -> i64 {
    let p = a * b;
    if p >= 0 { (p + 0x8000) >> 16 } else { -((-p + 0x8000) >> 16) }
}

fn cache() -> &'static Mutex<HashMap<String, Arc<Face>>> {
    static FACES: OnceLock<Mutex<HashMap<String, Arc<Face>>>> = OnceLock::new();
    FACES.get_or_init(Default::default)
}

/// The first face of the file at `path`, parsed once per process.
///
/// # Errors
///
/// [`FontError`] when the file cannot be read or parsed.
pub fn load(path: &str) -> Result<Arc<Face>, FontError> {
    if let Some(face) = cache().lock().unwrap_or_else(PoisonError::into_inner).get(path) {
        return Ok(face.clone());
    }
    read_file(path)
}

#[cfg(not(target_arch = "wasm32"))]
fn read_file(path: &str) -> Result<Arc<Face>, FontError> {
    let data = std::fs::read(path).map_err(|e| FontError::Read { path: path.to_owned(), reason: e.to_string() })?;
    register(path, &data)
}

/// There is no file system on wasm32: fonts arrive through [`register`] only.
#[cfg(target_arch = "wasm32")]
fn read_file(path: &str) -> Result<Arc<Face>, FontError> {
    Err(FontError::NotRegistered(path.to_owned()))
}

/// Parse the first face of `data` and store it under `name`, so [`load`] finds it without touching the file
/// system. This is how the browser supplies fonts.
///
/// # Errors
///
/// [`FontError`] when the bytes are not a font the metrics reader accepts.
pub fn register(name: &str, data: &[u8]) -> Result<Arc<Face>, FontError> {
    let face = Arc::new(Face::from_bytes(data, 0).map_err(|e| FontError::Named { name: name.to_owned(), source: Box::new(e) })?);
    cache().lock().unwrap_or_else(PoisonError::into_inner).insert(name.to_owned(), face.clone());
    Ok(face)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::text::{Font, Measurer};

    #[test]
    fn the_face_cache_recovers_from_a_poisoned_lock() {
        let poisoner = std::thread::spawn(|| {
            let _guard = cache().lock().unwrap();
            panic!("poison the cache on purpose");
        });
        assert!(poisoner.join().is_err());
        assert!(cache().is_poisoned());
        assert!(load(NOTO).is_ok());
        assert!(register("not-a-font", b"junk").is_err());
    }

    const NOTO: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/../../src/spinagram/fonts/NotoSansMath-Regular.ttf");

    #[test]
    fn measuring_with_a_font_registered_from_bytes_equals_loading_the_path() {
        let by_path = load(NOTO).unwrap();
        let bytes = std::fs::read(NOTO).unwrap();
        let by_bytes = register("from-bytes", &bytes).unwrap();
        let m = Measurer::default();
        for text in ["", "Hello, world", "\u{2211} \u{222b}x dx", "AV To 10.0.0.0/16"] {
            for size in [10.0, 13.0, 18.5] {
                let (a, b) = (Font { face: Some(by_path.clone()), size, weight: 400 }, Font { face: Some(by_bytes.clone()), size, weight: 400 });
                assert_eq!(m.measure(text, &a).to_bits(), m.measure(text, &b).to_bits(), "{text:?} at {size}");
            }
        }
        assert!(by_bytes.covers('\u{2211}'));
    }

    #[test]
    fn registered_name_is_found_by_load_and_garbage_is_rejected() {
        let bytes = std::fs::read(NOTO).unwrap();
        register("registered-name.ttf", &bytes).unwrap();
        assert!(load("registered-name.ttf").unwrap().covers('\u{2211}'));
        assert!(register("bad", b"not a font").is_err());
    }
}
