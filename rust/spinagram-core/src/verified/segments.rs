//! Safe-break cut points of a token, proved with Verus (VER-02). `text::segments` calls `cuts` and `bounds`.
//!
//! The caller marks the byte offsets where a cut may go (just after a break character, always on a char boundary)
//! and the protected `(start, end)` ranges (IPv4/CIDR runs). A cut `p` is valid when `0 < p < len`, it is marked,
//! and no protected range strictly contains it. `cuts` returns exactly the valid cuts, in increasing order;
//! `bounds` turns them into contiguous pieces that concatenate to the token.

#![expect(clippy::semicolon_if_nothing_returned, reason = "Verus proof blocks are erased and take no semicolon")]

use vstd::prelude::*;

verus! {

pub open spec fn protected_at(prot: Seq<(usize, usize)>, p: int) -> bool {
    exists|k: int| 0 <= k < prot.len() && (prot[k].0 as int) < p && p < (prot[k].1 as int)
}

pub open spec fn is_cut(len: int, cand: Seq<bool>, prot: Seq<(usize, usize)>, p: int) -> bool {
    0 < p && p < len && p < cand.len() && cand[p] && !protected_at(prot, p)
}

fn in_protected(prot: &[(usize, usize)], p: usize) -> (r: bool)
    ensures
        r == protected_at(prot@, p as int),
{
    let mut k = 0;
    while k < prot.len()
        invariant
            0 <= k <= prot.len(),
            forall|j: int| 0 <= j < k ==> !((prot@[j].0 as int) < p && p < (prot@[j].1 as int)),
        decreases prot.len() - k,
    {
        if prot[k].0 < p && p < prot[k].1 {
            assert(protected_at(prot@, p as int)) by {
                assert(0 <= k as int && (k as int) < prot@.len() && (prot@[k as int].0 as int) < p && p < (prot@[k as int].1 as int));
            }
            return true;
        }
        k += 1;
    }
    assert(!protected_at(prot@, p as int));
    false
}

#[must_use]
pub fn cuts(len: usize, cand: &[bool], prot: &[(usize, usize)]) -> (out: Vec<usize>)
    requires
        cand.len() == len + 1,
    ensures
        forall|i: int| 0 <= i < out.len() ==> is_cut(len as int, cand@, prot@, out@[i] as int),
        forall|i: int, j: int| 0 <= i < j < out.len() ==> out@[i] < out@[j],
        forall|p: int| is_cut(len as int, cand@, prot@, p) ==> exists|i: int| 0 <= i < out.len() && out@[i] as int == p,
{
    let mut out: Vec<usize> = Vec::new();
    let mut p: usize = 1;
    while p < len
        invariant
            1 <= p,
            p <= len || len == 0,
            cand.len() == len + 1,
            forall|i: int| 0 <= i < out.len() ==> is_cut(len as int, cand@, prot@, out@[i] as int) && (out@[i] as int) < p,
            forall|i: int, j: int| 0 <= i < j < out.len() ==> out@[i] < out@[j],
            forall|q: int| 0 < q < p && is_cut(len as int, cand@, prot@, q) ==> exists|i: int| 0 <= i < out.len() && out@[i] as int == q,
        decreases len - p,
    {
        let ghost old = out@;
        if cand[p] && !in_protected(prot, p) {
            out.push(p);
            proof {
                assert forall|q: int| 0 < q < p + 1 && is_cut(len as int, cand@, prot@, q) implies exists|i: int|
                    0 <= i < out.len() && out@[i] as int == q by {
                    if q < p {
                        let i = choose|i: int| 0 <= i < old.len() && old[i] as int == q;
                        assert(out@[i] == old[i]);
                    } else {
                        assert(out@[old.len() as int] == p);
                    }
                }
            }
        } else {
            proof {
                assert forall|q: int| 0 < q < p + 1 && is_cut(len as int, cand@, prot@, q) implies exists|i: int|
                    0 <= i < out.len() && out@[i] as int == q by {
                    assert(q < p);
                    let i = choose|i: int| 0 <= i < old.len() && old[i] as int == q;
                    assert(out@[i] == old[i]);
                }
            }
        }
        p += 1;
    }
    out
}

/// Contiguous `[start, end)` pieces of a token of `len` bytes cut at `cuts`: they start at 0, end at `len`, each
/// begins where the previous one ends (so the pieces concatenate to the token) and none is empty unless the token is.
#[must_use]
pub fn bounds(len: usize, cuts: &[usize]) -> (out: Vec<(usize, usize)>)
    requires
        forall|i: int| 0 <= i < cuts.len() ==> 0 < cuts@[i] && cuts@[i] < len,
        forall|i: int, j: int| 0 <= i < j < cuts.len() ==> cuts@[i] < cuts@[j],
    ensures
        out.len() == cuts.len() + 1,
        out@[0].0 == 0,
        out@[out.len() - 1].1 == len,
        forall|i: int| 0 <= i && i + 1 < out.len() ==> out@[i].1 == out@[i + 1].0,
        forall|i: int| 0 <= i < out.len() ==> out@[i].0 <= out@[i].1,
        len > 0 ==> forall|i: int| 0 <= i < out.len() ==> out@[i].0 < out@[i].1,
{
    let mut out: Vec<(usize, usize)> = Vec::new();
    let mut start: usize = 0;
    let mut k: usize = 0;
    while k < cuts.len()
        invariant
            0 <= k <= cuts.len(),
            out.len() == k,
            start == (if k == 0 { 0 } else { cuts@[k - 1] }),
            start < len || len == 0,
            forall|i: int| 0 <= i < cuts.len() ==> 0 < cuts@[i] && cuts@[i] < len,
            forall|i: int, j: int| 0 <= i < j < cuts.len() ==> cuts@[i] < cuts@[j],
            forall|i: int| 0 <= i && i + 1 < out.len() ==> out@[i].1 == out@[i + 1].0,
            forall|i: int| 0 <= i < out.len() ==> out@[i].0 < out@[i].1,
            k > 0 ==> out@[0].0 == 0,
            k > 0 ==> out@[k - 1].1 == start,
        decreases cuts.len() - k,
    {
        let end = cuts[k];
        out.push((start, end));
        start = end;
        k += 1;
    }
    out.push((start, len));
    out
}

} // verus!

#[cfg(test)]
mod tests {
    use super::{bounds, cuts};

    #[test]
    fn token_without_break_characters_has_no_cuts() {
        let cand = vec![false; 7];
        assert_eq!(cuts(6, &cand, &[]), [] as [usize; 0]);
        assert_eq!(bounds(6, &[]), vec![(0, 6)]);
    }

    #[test]
    fn marked_offsets_become_cuts_except_protected_and_the_ends() {
        // "a.b.c": a cut after each dot (offsets 2 and 4) and one marked at the end (5), which is not a cut
        let mut cand = vec![false; 6];
        for p in [2, 4, 5] {
            cand[p] = true;
        }
        assert_eq!(cuts(5, &cand, &[]), vec![2, 4]);
        assert_eq!(cuts(5, &cand, &[(1, 3)]), vec![4]); // 2 lies strictly inside (1, 3)
        assert_eq!(cuts(5, &cand, &[(2, 4)]), vec![2, 4]); // the ends of a range are not inside it
    }

    #[test]
    fn pieces_are_contiguous_and_cover_the_token() {
        assert_eq!(bounds(5, &[2, 4]), vec![(0, 2), (2, 4), (4, 5)]);
        assert_eq!(bounds(0, &[]), vec![(0, 0)]);
    }
}
