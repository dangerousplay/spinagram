//! The cascade order, proved with Verus (VER-05). `css::cascade` sorts its declarations with `stable_order`.
//!
//! Declarations sort by `(level, specificity, rule order, declaration index)`; the key is made of integers so the
//! proofs stay out of floating point. `kle` is a total order (reflexive, antisymmetric, transitive and total: the
//! four lemmas), `key_le` is its executable form, and `stable_order` returns the positions of the input in
//! ascending key order with equal keys in input order, as a permutation (each position exactly once).

use vstd::prelude::*;

verus! {

/// The cascade sort key `(level, specificity a, b, c, rule order, declaration index)`.
#[derive(Clone, Copy)]
pub struct Key {
    pub level: u64,
    pub a: u64,
    pub b: u64,
    pub c: u64,
    pub order: i64,
    pub index: u64,
}

/// `x <= y` in lexicographic order.
pub open spec fn kle(x: Key, y: Key) -> bool {
    if x.level != y.level {
        x.level < y.level
    } else if x.a != y.a {
        x.a < y.a
    } else if x.b != y.b {
        x.b < y.b
    } else if x.c != y.c {
        x.c < y.c
    } else if x.order != y.order {
        x.order < y.order
    } else {
        x.index <= y.index
    }
}

pub proof fn lemma_reflexive(x: Key)
    ensures
        kle(x, x),
{
}

pub proof fn lemma_antisymmetric(x: Key, y: Key)
    requires
        kle(x, y),
        kle(y, x),
    ensures
        x == y,
{
}

pub proof fn lemma_transitive(x: Key, y: Key, z: Key)
    requires
        kle(x, y),
        kle(y, z),
    ensures
        kle(x, z),
{
}

pub proof fn lemma_total(x: Key, y: Key)
    ensures
        kle(x, y) || kle(y, x),
{
}

#[must_use]
pub fn key_le(x: &Key, y: &Key) -> (r: bool)
    ensures
        r == kle(*x, *y),
{
    if x.level != y.level {
        return x.level < y.level;
    }
    if x.a != y.a {
        return x.a < y.a;
    }
    if x.b != y.b {
        return x.b < y.b;
    }
    if x.c != y.c {
        return x.c < y.c;
    }
    if x.order != y.order {
        return x.order < y.order;
    }
    x.index <= y.index
}

/// `perm` lists positions of `keys` in ascending key order, equal keys in their input order.
pub open spec fn stably_sorted(keys: Seq<Key>, perm: Seq<usize>) -> bool {
    forall|p: int, q: int|
        0 <= p < q < perm.len() ==> kle(keys[perm[p] as int], keys[perm[q] as int]) && (keys[perm[p] as int]
            == keys[perm[q] as int] ==> perm[p] < perm[q])
}

/// A stable sort of `keys` as a permutation: the positions in sorted order.
#[must_use]
pub fn stable_order(keys: &[Key]) -> (perm: Vec<usize>)
    ensures
        perm.len() == keys.len(),
        forall|p: int| 0 <= p < perm.len() ==> perm[p] < keys.len(),
        forall|p: int, q: int| 0 <= p < q < perm.len() ==> perm[p] != perm[q],
        stably_sorted(keys@, perm@),
{
    let mut perm: Vec<usize> = Vec::new();
    let mut i: usize = 0;
    while i < keys.len()
        invariant
            i <= keys.len(),
            perm.len() == i,
            forall|p: int| 0 <= p < perm.len() ==> perm[p] < i,
            forall|p: int, q: int| 0 <= p < q < perm.len() ==> perm[p] != perm[q],
            stably_sorted(keys@, perm@),
        decreases keys.len() - i,
    {
        let mut pos: usize = 0;
        while pos < perm.len() && key_le(&keys[perm[pos]], &keys[i])
            invariant
                pos <= perm.len(),
                i < keys.len(),
                forall|p: int| 0 <= p < perm.len() ==> perm[p] < i,
                forall|q: int| 0 <= q < pos ==> kle(keys[perm[q] as int], keys[i as int]),
            decreases perm.len() - pos,
        {
            pos += 1;
        }
        proof {
            // everything from `pos` on is strictly after keys[i]: it is >= the first one, which is not <= keys[i]
            assert forall|q: int| pos <= q < perm.len() implies !kle(keys[perm[q] as int], keys[i as int]) by {
                if pos < perm.len() {
                    assert(!kle(keys[perm[pos as int] as int], keys[i as int]));
                    if pos < q && kle(keys[perm[q] as int], keys[i as int]) {
                        assert(kle(keys[perm[pos as int] as int], keys[perm[q] as int]));
                        lemma_transitive(keys[perm[pos as int] as int], keys[perm[q] as int], keys[i as int]);
                    }
                }
            }
        }
        let ghost old = perm@;
        perm.insert(pos, i);
        proof {
            assert forall|p: int, q: int| 0 <= p < q < perm.len() implies kle(keys[perm[p] as int], keys[perm[q] as int])
                && (keys[perm[p] as int] == keys[perm[q] as int] ==> perm[p] < perm[q]) by {
                if q < pos {
                    assert(perm[p] == old[p]);
                    assert(perm[q] == old[q]);
                } else if p < pos && q == pos {
                    assert(perm[p] == old[p]);
                    assert(perm[q] == i);
                } else if p < pos {
                    assert(perm[p] == old[p]);
                    assert(perm[q] == old[q - 1]);
                    lemma_total(keys[i as int], keys[old[q - 1] as int]);
                    lemma_transitive(keys[old[p] as int], keys[i as int], keys[old[q - 1] as int]);
                } else if p == pos {
                    assert(perm[p] == i);
                    assert(perm[q] == old[q - 1]);
                    lemma_total(keys[i as int], keys[old[q - 1] as int]);
                } else {
                    assert(perm[p] == old[p - 1]);
                    assert(perm[q] == old[q - 1]);
                }
            }
        }
        i += 1;
    }
    perm
}

} // verus!

#[cfg(test)]
mod tests {
    use super::{key_le, stable_order, Key};

    fn key(level: u64, a: u64, order: i64, index: u64) -> Key {
        Key { level, a, b: 0, c: 0, order, index }
    }

    #[test]
    fn levels_then_specificity_then_order_then_index() {
        let keys = [key(1, 0, 0, 0), key(0, 5, 3, 1), key(0, 5, 2, 9), key(0, 1, 7, 2), key(3, 0, 0, 0), key(2, 0, 0, 0)];
        assert_eq!(stable_order(&keys), vec![3, 2, 1, 0, 5, 4]);
    }

    #[test]
    fn equal_keys_keep_their_input_order() {
        let keys = [key(0, 1, 0, 0), key(0, 1, 0, 0), key(0, 0, 0, 0), key(0, 1, 0, 0)];
        assert_eq!(stable_order(&keys), vec![2, 0, 1, 3]);
        assert!(key_le(&keys[0], &keys[1]) && key_le(&keys[1], &keys[0]));
    }

    #[test]
    fn empty_input_gives_an_empty_permutation() {
        assert_eq!(stable_order(&[]), [] as [usize; 0]);
    }

    #[test]
    fn matches_the_standard_stable_sort_on_pseudo_random_keys() {
        let mut state = 12_345_u64;
        let mut next = move |m: u64| {
            state = state.wrapping_mul(6_364_136_223_846_793_005).wrapping_add(1_442_695_040_888_963_407);
            (state >> 33) % m
        };
        for n in [0_usize, 1, 2, 5, 17, 60] {
            let keys: Vec<Key> = (0..n).map(|_| Key { level: next(4), a: next(3), b: next(3), c: next(2), order: i64::try_from(next(5)).unwrap(), index: next(4) }).collect();
            let mut want: Vec<usize> = (0..n).collect();
            want.sort_by_key(|&p| (keys[p].level, keys[p].a, keys[p].b, keys[p].c, keys[p].order, keys[p].index));
            assert_eq!(stable_order(&keys), want, "n = {n}");
        }
    }
}
