//! Kernels proved with Verus. The functions here are the ones production code calls; the proofs are erased in a
//! normal build, so `cargo build` and the wheel compile on stable Rust. Verify with
//! `PATH=$HOME/.local/verus:$PATH cargo verus verify -p spinagram-core` (see `rust/README.md`).

use vstd::prelude::*;

pub mod brackets;
pub mod segments;

verus! {

/// The setup lemma: integer arithmetic is available to the solver.
pub proof fn lemma_setup()
    ensures
        1int + 1int == 2int,
{
}

} // verus!
