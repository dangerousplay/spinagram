//! The `var(` bracket scanner, proved with Verus (VER-03). `css::substitute` calls `scan_close`.
//!
//! Starting just after an opening parenthesis (depth 1), the scanner walks forward counting `(` and `)` until the
//! depth returns to 0 or the input ends. The proof says the result is in bounds, that the depth is positive at every
//! index before it, and that it is the input length or an index where the depth is 0. The `while` loop carries a
//! `decreases` clause, so termination is proved too.

use vstd::prelude::*;

verus! {

pub open spec fn delta(c: char) -> int {
    if c == '(' { 1 } else if c == ')' { -1 } else { 0 }
}

/// Bracket depth after consuming `s[from..to)`, starting at depth 1 (inside the opening parenthesis).
pub open spec fn depth_after(s: Seq<char>, from: int, to: int) -> int
    decreases to - from,
{
    if to <= from {
        1
    } else {
        depth_after(s, from, to - 1) + delta(s[to - 1])
    }
}

/// The index after the `)` that closes the parenthesis opened just before `from`, or `s.len()` when it never closes.
#[must_use]
pub fn scan_close(s: &[char], from: usize) -> (out: usize)
    requires
        from <= s.len(),
        s.len() < usize::MAX - 1,  // a Vec never exceeds isize::MAX; the depth counter cannot overflow
    ensures
        from <= out <= s.len(),
        forall|k: int| from <= k < out ==> depth_after(s@, from as int, k) > 0,
        out == s.len() || depth_after(s@, from as int, out as int) == 0,
{
    let mut j = from;
    let mut depth: usize = 1;
    while j < s.len() && depth != 0
        invariant
            from <= j <= s.len(),
            depth as int == depth_after(s@, from as int, j as int),
            depth >= 0,
            s.len() < usize::MAX - 1,
            forall|k: int| from <= k < j ==> depth_after(s@, from as int, k) > 0,
            depth > 0 || j > from,
            depth as int <= 1 + (j as int - from as int),
        decreases s.len() - j,
    {
        let c = s[j];
        if c == '(' {
            depth += 1;
        } else if c == ')' {
            depth -= 1;
        }
        j += 1;
    }
    j
}

} // verus!

#[cfg(test)]
mod tests {
    use super::scan_close;

    fn scan(text: &str, from: usize) -> usize {
        let chars: Vec<char> = text.chars().collect();
        scan_close(&chars, from)
    }

    #[test]
    fn returns_the_index_after_the_matching_parenthesis() {
        assert_eq!(scan("(a(b))c", 1), 6); // depth 1 at 'a', 2 inside "(b)", back to 0 at index 5
        assert_eq!(scan("var(--x) tail", 4), 8);
    }

    #[test]
    fn unclosed_var_returns_the_length() {
        assert_eq!(scan("var(--x", 4), 7);
        assert_eq!(scan("var(--x, (nested)", 4), 17);
    }

    #[test]
    fn nothing_after_the_opening_parenthesis_returns_the_length() {
        assert_eq!(scan("a var(", 6), 6);
    }

    #[test]
    fn a_close_that_ends_the_input_returns_the_length() {
        assert_eq!(scan("var(--x)", 4), 8);
    }
}
