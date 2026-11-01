//! The router's A* neighbour step, proved with Verus (VER-07). `route::search` calls `neighbour` for each of the four
//! directions, so a produced cell is always inside the grid and no index arithmetic can wrap or go negative.

use vstd::prelude::*;

verus! {

/// The cell one step from `(i, j)` in direction `(di, dj)` (each -1, 0 or 1) on an `nx` by `ny` grid, or `None`
/// when that step leaves the grid.
#[must_use]
pub fn neighbour(i: usize, j: usize, di: i32, dj: i32, nx: usize, ny: usize) -> (r: Option<(usize, usize)>)
    requires
        i < nx,
        j < ny,
        -1 <= di <= 1,
        -1 <= dj <= 1,
    ensures
        match r {
            Some((a, b)) => a < nx && b < ny && (a as int) == (i as int + di as int) && (b as int) == (j as int + dj as int),
            None => (i as int + di as int) < 0 || (i as int + di as int) >= (nx as int) || (j as int + dj as int) < 0
                || (j as int + dj as int) >= (ny as int),
        },
{
    let a: usize = if di == -1 {
        if i == 0 {
            return None;
        }
        i - 1
    } else if di == 0 {
        i
    } else {
        if i + 1 >= nx {
            return None;
        }
        i + 1
    };
    let b: usize = if dj == -1 {
        if j == 0 {
            return None;
        }
        j - 1
    } else if dj == 0 {
        j
    } else {
        if j + 1 >= ny {
            return None;
        }
        j + 1
    };
    Some((a, b))
}

} // verus!

#[cfg(test)]
mod tests {
    use super::neighbour;

    const DIRS: [(i32, i32); 4] = [(1, 0), (-1, 0), (0, 1), (0, -1)];

    #[test]
    fn interior_cells_have_four_neighbours() {
        let got: Vec<_> = DIRS.iter().map(|&(di, dj)| neighbour(2, 3, di, dj, 5, 6)).collect();
        assert_eq!(got, vec![Some((3, 3)), Some((1, 3)), Some((2, 4)), Some((2, 2))]);
    }

    #[test]
    fn corners_and_edges_lose_the_outward_steps() {
        assert_eq!(neighbour(0, 0, -1, 0, 5, 6), None);
        assert_eq!(neighbour(0, 0, 0, -1, 5, 6), None);
        assert_eq!(neighbour(4, 5, 1, 0, 5, 6), None);
        assert_eq!(neighbour(4, 5, 0, 1, 5, 6), None);
        assert_eq!(neighbour(4, 5, -1, 0, 5, 6), Some((3, 5)));
    }

    #[test]
    fn a_one_cell_grid_has_no_neighbours() {
        assert!(DIRS.iter().all(|&(di, dj)| neighbour(0, 0, di, dj, 1, 1).is_none()));
    }

    #[test]
    fn every_produced_cell_is_inside_the_grid() {
        for (nx, ny) in [(1, 1), (1, 4), (3, 1), (3, 5)] {
            for i in 0..nx {
                for j in 0..ny {
                    for (di, dj) in DIRS {
                        if let Some((a, b)) = neighbour(i, j, di, dj, nx, ny) {
                            assert!(a < nx && b < ny);
                        }
                    }
                }
            }
        }
    }
}
