//! Python's number formatting and HTML escaping, so the SVG bytes match the Python writer.

use compensated_summation::KahanBabuskaNeumaier;

/// `format(x, ".1f")`
#[must_use]
pub fn f1(x: f64) -> String {
    if !x.is_finite() {
        return special(x);
    }
    format!("{x:.1}")
}

fn special(x: f64) -> String {
    if x.is_nan() {
        "nan".into()
    } else if x > 0.0 {
        "inf".into()
    } else {
        "-inf".into()
    }
}

/// Digits and decimal exponent of `x` from Rust's `{:e}` output (`1.234e-5` -> ("1234", -5)), sign stripped.
fn split_e(s: &str) -> (String, i32) {
    let (mant, exp) = s.trim_start_matches('-').split_once('e').expect("exponent form");
    (mant.replace('.', ""), exp.parse().expect("exponent"))
}

fn sci(digits: &str, exp: i32) -> String {
    let mant = if digits.len() > 1 { format!("{}.{}", &digits[..1], &digits[1..]) } else { digits.to_string() };
    format!("{mant}e{}{:02}", if exp < 0 { '-' } else { '+' }, exp.abs())
}

fn strip_zeros(s: &str) -> &str {
    if s.contains('.') {
        s.trim_end_matches('0').trim_end_matches('.')
    } else {
        s
    }
}

/// `format(x, "g")`: six significant digits, trailing zeros removed, exponent form below 1e-4 and from 1e6.
#[must_use]
pub fn g(x: f64) -> String {
    if !x.is_finite() {
        return special(x);
    }
    let sign = if x.is_sign_negative() { "-" } else { "" };
    let (digits, exp) = split_e(&format!("{:.5e}", x.abs()));
    let body = if (-4..6).contains(&exp) {
        strip_zeros(&format!("{:.*}", usize::try_from(5 - exp).unwrap_or(0), x.abs())).to_string()
    } else {
        let d = digits.trim_end_matches('0');
        sci(if d.is_empty() { "0" } else { d }, exp)
    };
    format!("{sign}{body}")
}

/// Python `repr(float)`: shortest round-trip digits, exponent form below 1e-4 and from 1e16.
#[must_use]
pub fn repr_f64(x: f64) -> String {
    if !x.is_finite() {
        return special(x);
    }
    let sign = if x.is_sign_negative() { "-" } else { "" };
    let (digits, exp) = split_e(&format!("{:e}", x.abs()));
    let body = if !(-4..16).contains(&exp) {
        sci(&digits, exp)
    } else if exp < 0 {
        format!("0.{}{digits}", "0".repeat(usize::try_from(-exp - 1).unwrap_or(0)))
    } else {
        let int_len = usize::try_from(exp).unwrap_or(0) + 1;
        if digits.len() <= int_len {
            format!("{digits}{}.0", "0".repeat(int_len - digits.len()))
        } else {
            format!("{}.{}", &digits[..int_len], &digits[int_len..])
        }
    };
    format!("{sign}{body}")
}

/// Python's `sum()` of floats. `compensated`: Python 3.12+ uses Neumaier compensated summation (the
/// `compensated-summation` crate gives bit-identical totals); older versions add left to right. The caller passes what the running interpreter does.
#[must_use]
pub fn py_sum(xs: &[f64], compensated: bool) -> f64 {
    if !compensated {
        return xs.iter().fold(0.0, |acc, x| acc + x);
    }
    xs.iter().copied().sum::<KahanBabuskaNeumaier<f64>>().total()
}

/// `html.escape(s, quote=False)`
#[must_use]
pub fn esc(s: &str) -> String {
    html_escape::encode_text(s).into_owned()
}

/// `html.escape(s, quote=True)`
#[must_use]
pub fn attr(s: &str) -> String {
    html_escape::encode_quoted_attribute(s).into_owned()
}

#[cfg(test)]
mod tests {
    use super::*;

    // Expected strings come from running Python: format(v, ".1f"), format(v, "g"), repr(v), html.escape.
    const VALUES: [(f64, &str, &str); 12] = [
        (0.0, "0.0", "0"),
        (-0.0, "-0.0", "-0"),
        (0.05, "0.1", "0.05"),
        (0.15, "0.1", "0.15"),
        (0.25, "0.2", "0.25"),
        (2.5, "2.5", "2.5"),
        (1e-5, "0.0", "1e-05"),
        (123_456.0, "123456.0", "123456"),
        (1_234_567.0, "1234567.0", "1.23457e+06"),
        (0.1 + 0.2, "0.3", "0.3"),
        (1e16, "10000000000000000.0", "1e+16"),
        (-3.75, "-3.8", "-3.75"),
    ];

    #[test]
    fn f1_matches_python() {
        for (x, want, _) in VALUES {
            assert_eq!(f1(x), want, "format({x:?}, '.1f')");
        }
    }

    #[test]
    fn g_matches_python() {
        for (x, _, want) in VALUES {
            assert_eq!(g(x), want, "format({x:?}, 'g')");
        }
    }

    #[test]
    fn g_more_python_values() {
        for (x, want) in [(100.0, "100"), (123_456_789.0, "1.23457e+08"), (1.5e-7, "1.5e-07"), (1e22, "1e+22"),
                          (0.0001, "0.0001"), (999_999.5, "1e+06"), (5e-324, "4.94066e-324")] {
            assert_eq!(g(x), want, "format({x:?}, 'g')");
        }
    }

    #[test]
    fn repr_matches_python() {
        for (x, want) in [(0.5, "0.5"), (1.0, "1.0"), (1e-5, "1e-05"), (1e16, "1e+16"),
                          (123_456_789_012_345_680.0, "1.2345678901234568e+17"), (0.0001, "0.0001"), (1e22, "1e+22"),
                          (-0.0, "-0.0"), (123_456_789.0, "123456789.0"), (0.02, "0.02"), (-1.5e-7, "-1.5e-07"),
                          (100.0, "100.0"), (0.1 + 0.2, "0.30000000000000004")] {
            assert_eq!(repr_f64(x), want, "repr({x:?})");
        }
    }

    #[test]
    #[expect(clippy::float_cmp, reason = "exact equality with the Python results is the contract")]
    fn py_sum_is_compensated_like_python_3_12() {
        assert_eq!(py_sum(&[0.1; 10], true), 1.0); // Python 3.13: sum([0.1] * 10) == 1.0
        assert_eq!(py_sum(&[0.1, 0.2, 0.3], true), 0.6);
        assert_eq!(py_sum(&[27.6, 27.6, 27.6], true), 82.800_000_000_000_01);
        assert_eq!(py_sum(&[], true), 0.0);
    }

    #[test]
    #[expect(clippy::float_cmp, reason = "exact equality with the Python results is the contract")]
    fn py_sum_adds_plainly_like_python_3_11() {
        assert_eq!(py_sum(&[0.1; 10], false), 0.999_999_999_999_999_9); // Python 3.11: sum([0.1] * 10)
        assert_eq!(py_sum(&[0.1, 0.2, 0.3], false), 0.600_000_000_000_000_1);
        assert_eq!(py_sum(&[], false), 0.0);
    }

    const TEXT: &str = "a & b < c > d \" e ' f é ✓ 日本";

    #[test]
    fn esc_matches_html_escape_without_quotes() {
        assert_eq!(esc(TEXT), "a &amp; b &lt; c &gt; d \" e ' f é ✓ 日本");
    }

    #[test]
    fn attr_matches_html_escape_with_quotes() {
        assert_eq!(attr(TEXT), "a &amp; b &lt; c &gt; d &quot; e &#x27; f é ✓ 日本");
    }

    #[test]
    fn escaping_is_not_idempotent_like_python() {
        assert_eq!(esc("&amp;"), "&amp;amp;");
    }
}
