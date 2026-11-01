//! `bisect_left` over a sorted slice of integer keys, proved with Verus (VER-04). The router's grid lookup calls it.
//!
//! The router's grid lines are `f64`; Verus keeps floats out of proofs, so `order_key` maps a coordinate to a `u64`
//! whose integer order is the float order (tested here, not proved), and `lower_bound` does the lookup on the keys.

use vstd::prelude::*;

verus! {

pub open spec fn sorted(keys: Seq<u64>) -> bool {
    forall|i: int, j: int| 0 <= i <= j < keys.len() ==> keys[i] <= keys[j]
}

/// The first index whose key is `>= x` (`keys.len()` when there is none), for sorted `keys`.
#[must_use]
pub fn bisect_left(keys: &[u64], x: u64) -> (r: usize)
    requires
        sorted(keys@),
    ensures
        r <= keys.len(),
        forall|i: int| 0 <= i < r ==> keys@[i] < x,
        forall|i: int| r <= i < keys.len() ==> keys@[i] >= x,
{
    let mut lo: usize = 0;
    let mut hi: usize = keys.len();
    while lo < hi
        invariant
            0 <= lo <= hi <= keys.len(),
            sorted(keys@),
            forall|i: int| 0 <= i < lo ==> keys@[i] < x,
            forall|i: int| hi <= i < keys.len() ==> keys@[i] >= x,
        decreases hi - lo,
    {
        let mid = lo + (hi - lo) / 2;
        if keys[mid] < x {
            lo = mid + 1;
        } else {
            hi = mid;
        }
    }
    lo
}

} // verus!

/// An integer whose order is the order of the floats under `<` (`-0.0` and `0.0` are equal, as in Python).
#[must_use]
pub fn order_key(x: f64) -> u64 {
    let bits = if x == 0.0 { 0.0_f64 } else { x }.to_bits();
    if bits >> 63 == 1 { !bits } else { bits | (1 << 63) }
}

/// `bisect.bisect_left(lines, x)` for ascending `lines`, given their `order_key`s.
#[must_use]
pub fn lower_bound(keys: &[u64], x: f64) -> usize {
    bisect_left(keys, order_key(x))
}

#[cfg(test)]
mod tests {
    use super::{bisect_left, lower_bound, order_key};

    fn keys(lines: &[f64]) -> Vec<u64> {
        lines.iter().map(|&v| order_key(v)).collect()
    }

    // Expected indices come from Python's bisect.bisect_left over the same lists.
    #[test]
    fn lookup_matches_python_bisect_left() {
        let lines = keys(&[-3.5, -1.0, 0.0, 2.0, 7.25]);
        let queries = [-4.0, -3.5, -2.0, -1.0, -0.0, 0.0, 1.0, 2.0, 7.25, 8.0];
        let want = [0, 0, 1, 1, 2, 2, 3, 3, 4, 5];
        for (q, w) in queries.iter().zip(want) {
            assert_eq!(lower_bound(&lines, *q), w, "bisect_left(..., {q})");
        }
        assert_eq!(lower_bound(&keys(&[1.0]), 1.0), 0);
        assert_eq!(lower_bound(&keys(&[1.0, 1.5]), 1.25), 1);
        assert_eq!(lower_bound(&keys(&[-0.0]), 0.0), 0);
        assert_eq!(lower_bound(&keys(&[0.0]), -0.0), 0);
    }

    #[test]
    fn empty_slice_gives_zero() {
        assert_eq!(bisect_left(&[], 5), 0);
        assert_eq!(lower_bound(&[], 1.0), 0);
    }

    #[test]
    fn keys_preserve_the_float_order() {
        let values = [-1e300, -2.5, -1.0, -f64::MIN_POSITIVE, -0.0, 0.0, f64::MIN_POSITIVE, 1.0, 1.0, 2.5, 1e300];
        for a in values {
            for b in values {
                let by_value = a.partial_cmp(&b).unwrap();
                assert_eq!(order_key(a).cmp(&order_key(b)), by_value, "{a} vs {b}");
            }
        }
    }

    #[test]
    fn keys_agree_with_total_cmp_away_from_zero() {
        let values = [-7.5, -0.25, 0.125, 3.0, 1e-9, -1e-9];
        for a in values {
            for b in values {
                assert_eq!(order_key(a).cmp(&order_key(b)), a.total_cmp(&b));
            }
        }
    }
}
