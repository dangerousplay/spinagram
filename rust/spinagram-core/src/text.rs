//! Text measurement and wrapping, a port of `spinagram/text.py` and the wrapping half of
//! `spinagram/engine/textfit.py`. Same rules, same results: the Python tests are the spec.

use std::sync::{Arc, LazyLock};

use regex::Regex;

use crate::font::Face;
use crate::verified;

/// The characters after which a long token may be broken.
pub const BREAK_ON: &str = "-./:·";

/// A font at a size. Without a face the width is estimated from an average advance per character.
#[derive(Clone, Debug)]
pub struct Font {
    /// The face the metrics come from; `None` measures without one.
    pub face: Option<Arc<Face>>,
    /// Size in px.
    pub size: f64,
    /// Font weight.
    pub weight: u16,
}

impl Font {
    /// The same font at another size.
    #[must_use]
    pub fn with_size(&self, size: f64) -> Font {
        Font { size, ..self.clone() }
    }

    fn covers(&self, ch: char) -> bool {
        self.face.as_ref().is_none_or(|f| f.covers(ch))
    }

    #[expect(clippy::cast_precision_loss, reason = "pixel, glyph and count arithmetic on small non-negative values that f64, i64 and usize hold exactly")]
    fn plain(&self, text: &str) -> f64 {
        match &self.face {
            Some(face) => face.length(text, self.size),
            // average advance / size; bold is wider
            None => text.chars().count() as f64 * self.size * if self.weight >= 600 { 0.60 } else { 0.53 },
        }
    }
}

/// Python's `str.isspace`, which also counts the ASCII separators U+001C..U+001F.
#[must_use]
pub fn is_space(ch: char) -> bool {
    ch.is_whitespace() || ('\u{1c}'..='\u{1f}').contains(&ch)
}

fn words(text: &str) -> impl Iterator<Item = &str> {
    text.split(is_space).filter(|w| !w.is_empty())
}

fn blank(text: &str) -> bool {
    text.chars().all(is_space)
}

/// Measures text with a font and the fallback faces for characters it lacks.
#[derive(Clone, Debug, Default)]
pub struct Measurer {
    /// Faces tried, in order, for characters the main face lacks.
    pub fallbacks: Vec<Arc<Face>>,
}

impl Measurer {
    /// Width of `text`; characters the font lacks are measured with the first fallback that has them.
    #[must_use]
    pub fn measure(&self, text: &str, font: &Font) -> f64 {
        let (mut width, mut run) = (0.0, String::new());
        for ch in text.chars() {
            if is_space(ch) || font.covers(ch) {
                run.push(ch);
                continue;
            }
            width += font.plain(&run);
            run.clear();
            width += match self.fallbacks.iter().find(|f| f.covers(ch)) {
                Some(fb) => fb.length(&ch.to_string(), font.size),
                None => font.size * 0.5,
            };
        }
        width + font.plain(&run)
    }

    /// Greedy word wrap to `width` pixels. Words longer than a line stay whole.
    #[must_use]
    pub fn wrap(&self, text: &str, font: &Font, width: f64) -> Vec<String> {
        let mut lines = Vec::new();
        let mut cur = String::new();
        for word in words(text) {
            let cand = if cur.is_empty() { word.to_owned() } else { format!("{cur} {word}") };
            if !cur.is_empty() && self.measure(&cand, font) > width {
                lines.push(std::mem::replace(&mut cur, word.to_owned()));
            } else {
                cur = cand;
            }
        }
        if !cur.is_empty() {
            lines.push(cur);
        }
        lines
    }

    /// Wrap each paragraph; an empty paragraph keeps an empty line.
    #[must_use]
    pub fn wrap_paragraphs(&self, paragraphs: &[String], font: &Font, width: f64) -> Vec<String> {
        paragraphs
            .iter()
            .flat_map(|p| if blank(p) { vec![String::new()] } else { self.wrap(p, font, width) })
            .collect()
    }

    /// Lines of `token` no wider than `width`, cut only after `break_on` characters (no hyphen added).
    #[must_use]
    pub fn break_token(&self, token: &str, font: &Font, width: f64, break_on: &str) -> Vec<String> {
        let mut lines = Vec::new();
        let mut cur = String::new();
        for seg in segments(token, break_on) {
            if !cur.is_empty() && self.measure(&format!("{cur}{seg}"), font) > width {
                lines.push(std::mem::replace(&mut cur, seg.to_owned()));
            } else {
                cur.push_str(seg);
            }
        }
        if !cur.is_empty() {
            lines.push(cur);
        }
        lines
    }

    /// Greedy wrap at spaces; a word wider than `width` is broken at safe points and its pieces join the
    /// flow like words with no space between them. An empty paragraph keeps a line.
    #[must_use]
    pub fn wrap_fit(&self, paragraphs: &[String], font: &Font, width: f64, break_on: &str) -> Vec<String> {
        let mut out = Vec::new();
        for p in paragraphs {
            if blank(p) {
                out.push(String::new());
                continue;
            }
            let mut pieces: Vec<(String, &str)> = Vec::new(); // (text, separator before it)
            for word in words(p) {
                let parts = if self.measure(word, font) > width {
                    self.break_token(word, font, width, break_on)
                } else {
                    vec![word.to_owned()]
                };
                let mut parts = parts.into_iter();
                if let Some(first) = parts.next() {
                    pieces.push((first, " "));
                }
                pieces.extend(parts.map(|q| (q, "")));
            }
            let mut cur = String::new();
            for (text, sep) in pieces {
                let cand = if cur.is_empty() { text.clone() } else { format!("{cur}{sep}{text}") };
                if !cur.is_empty() && self.measure(&cand, font) > width {
                    out.push(std::mem::replace(&mut cur, text));
                } else {
                    cur = cand;
                }
            }
            out.push(cur);
        }
        out
    }
}

/// `token` cut after each break character that is not inside an IPv4/CIDR run. The cut points and the piece
/// bounds come from the verified kernel in `verified::segments`.
fn segments<'a>(token: &'a str, break_on: &str) -> Vec<&'a str> {
    static ATOMIC: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"\d{1,3}(?:\.\d{1,3}){3}(?:/\d{1,2})?").expect("the pattern is a constant"));
    let atomic = &*ATOMIC;
    let protected: Vec<(usize, usize)> = atomic.find_iter(token).map(|m| (m.start(), m.end())).collect();
    let mut can_cut = vec![false; token.len() + 1];
    for (i, ch) in token.char_indices() {
        if break_on.contains(ch) {
            can_cut[i + ch.len_utf8()] = true;
        }
    }
    let cuts = verified::segments::cuts(token.len(), &can_cut, &protected);
    verified::segments::bounds(token.len(), &cuts).into_iter().map(|(a, b)| &token[a..b]).filter(|s| !s.is_empty()).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn est() -> Font {
        Font { face: None, size: 10.0, weight: 400 }
    }

    #[test]
    fn segments_keep_cidr_whole() {
        assert_eq!(segments("10.0.0.0/16-subnet", BREAK_ON), ["10.0.0.0/16-", "subnet"]);
        assert_eq!(segments("a.b/c", BREAK_ON), ["a.", "b/", "c"]);
    }

    #[test]
    fn wrap_uses_estimate_without_face() {
        let m = Measurer::default();
        assert_eq!(m.measure("abcd", &est()), 4.0 * 10.0 * 0.53);
        assert_eq!(m.wrap("aa bb cc", &est(), 60.0), ["aa bb cc"]);
        assert_eq!(m.wrap("aa bb cc", &est(), 30.0), ["aa bb", "cc"]);
        assert_eq!(m.wrap_paragraphs(&[String::new(), "x".into()], &est(), 60.0), ["", "x"]);
    }

    #[test]
    fn wrap_fit_breaks_long_tokens() {
        let m = Measurer::default();
        let lines = m.wrap_fit(&["see api.example.com/v1/orders now".into()], &est(), 60.0, BREAK_ON);
        assert_eq!(lines, ["see api.", "example.", "com/v1/", "orders now"]); // same as the Python port
    }
}
