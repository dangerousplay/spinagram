//! Orthogonal edge routing around obstacles: a line-by-line port of `spinagram/autolayout/route.py`.
//!
//! Results must equal the Python router's: the A* open set is ordered like Python's `heapq` on
//! `(f, g, (i, j), dir, prev)` tuples, costs are summed in the same order, and `simplify` rounds
//! like Python's `round(x, 2)`.

use std::cmp::{Ordering, Reverse};
use std::collections::BinaryHeap;

pub type Pt = (f64, f64);
/// `(x, y, w, h)`
pub type Rect = (f64, f64, f64, f64);

pub const MARGIN: f64 = 14.0;
pub const BEND: f64 = 60.0;
pub const BUSY: f64 = 400.0;
pub const CLOSE: f64 = 4.0;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Side {
    Top,
    Bottom,
    Left,
    Right,
}

impl Side {
    /// Python's dict order: top, bottom, left, right.
    pub const ALL: [Side; 4] = [Side::Top, Side::Bottom, Side::Left, Side::Right];

    #[must_use]
    pub fn from_name(s: &str) -> Option<Side> {
        match s {
            "top" => Some(Side::Top),
            "bottom" => Some(Side::Bottom),
            "left" => Some(Side::Left),
            "right" => Some(Side::Right),
            _ => None,
        }
    }
}

/// A fixed cost per strict crossing with already drawn segments (`engine.route.Crossings`).
#[derive(Clone, Debug)]
pub struct Crossings {
    pub cost: f64,
    pub drawn: Vec<(Pt, Pt)>,
}

type Dir = (i32, i32);

/// Strict crossing of segment p-q with a-b, as `engine.route.crosses`.
#[must_use]
pub fn crosses(p: Pt, q: Pt, a: Pt, b: Pt) -> bool {
    let orient = |u: Pt, v: Pt, w: Pt| (v.0 - u.0) * (w.1 - u.1) - (v.1 - u.1) * (w.0 - u.0);
    let (d1, d2, d3, d4) = (orient(a, b, p), orient(a, b, q), orient(p, q, a), orient(p, q, b));
    d1 * d2 < 0.0 && d3 * d4 < 0.0
}

impl Crossings {
    #[expect(clippy::cast_precision_loss, reason = "pixel, glyph and count arithmetic on small non-negative values that f64, i64 and usize hold exactly")]
    fn at(&self, p: Pt, q: Pt) -> f64 {
        let n = self.drawn.iter().filter(|s| crosses(p, q, s.0, s.1)).count();
        self.cost * n as f64
    }
}

#[expect(clippy::many_single_char_names, reason = "geometry names (x, y, w, h, a, b) mirror the Python port")]
fn ports(b: Rect, f: Option<f64>) -> [(Pt, Dir); 4] {
    let (x, y, w, h) = b;
    let f = f.unwrap_or(0.5);
    [
        ((x + w * f, y), (0, -1)),
        ((x + w * f, y + h), (0, 1)),
        ((x, y + h * f), (-1, 0)),
        ((x + w, y + h * f), (1, 0)),
    ]
}

fn port(p: &[(Pt, Dir); 4], s: Side) -> (Pt, Dir) {
    p[s as usize]
}

#[expect(clippy::many_single_char_names, reason = "geometry names (x, y, w, h, a, b) mirror the Python port")]
fn inside(px: f64, py: f64, b: Rect) -> bool {
    let (x, y, w, h) = b;
    let pad = 0.5;
    x + pad < px && px < x + w - pad && y + pad < py && py < y + h - pad
}

/// Python `round(x, 2)`: the exact binary value rounded to two decimals, ties to even.
#[must_use]
pub fn round2(x: f64) -> f64 {
    if !x.is_finite() {
        return x;
    }
    format!("{x:.2}").parse().unwrap_or(x)
}

#[expect(clippy::float_cmp, reason = "exact equality with the Python results is the contract")]
fn simplify(pts: &[Pt]) -> Vec<Pt> {
    let mut out: Vec<Pt> = Vec::new();
    for &(px, py) in pts {
        let p = (round2(px), round2(py));
        if out.last() == Some(&p) {
            continue;
        }
        if out.len() >= 2 {
            let (a, b) = (out[out.len() - 2], out[out.len() - 1]);
            if (a.0 == b.0 && b.0 == p.0) || (a.1 == b.1 && b.1 == p.1) {
                *out.last_mut().unwrap() = p;
                continue;
            }
        }
        out.push(p);
    }
    out
}

/// Sorted, de-duplicated by `==` (Python set semantics: the first inserted of equal values survives).
fn grid_lines(mut v: Vec<f64>) -> Vec<f64> {
    v.sort_by(|a, b| a.partial_cmp(b).unwrap_or(Ordering::Equal));
    v.dedup();
    v
}

fn lower_bound(v: &[f64], x: f64) -> usize {
    v.partition_point(|&a| a < x)
}

type Key = (usize, usize, Dir);

#[derive(PartialEq)]
struct Node {
    f: f64,
    g: f64,
    ij: (usize, usize),
    d: Dir,
    prev: Option<Key>,
}

impl Eq for Node {}

impl Ord for Node {
    fn cmp(&self, o: &Self) -> Ordering {
        self.f
            .total_cmp(&o.f)
            .then(self.g.total_cmp(&o.g))
            .then(self.ij.cmp(&o.ij))
            .then(self.d.cmp(&o.d))
            .then(self.prev.cmp(&o.prev))
    }
}

impl PartialOrd for Node {
    fn partial_cmp(&self, o: &Self) -> Option<Ordering> {
        Some(self.cmp(o))
    }
}

fn dir_index(d: Dir) -> usize {
    match d {
        (1, 0) => 0,
        (-1, 0) => 1,
        (0, 1) => 2,
        _ => 3,
    }
}

#[expect(clippy::cast_possible_truncation, clippy::cast_possible_wrap, clippy::cast_sign_loss, reason = "pixel, glyph and count arithmetic on small non-negative values that f64, i64 and usize hold exactly")]
fn search(sport: (Pt, Dir), dport: (Pt, Dir), obs: &[Rect], margin: f64, penalty: Option<&Crossings>, guides: &[Pt]) -> Option<(f64, Vec<Pt>)> {
    let ((sx, sy), (sdx, sdy)) = sport;
    let ((tx, ty), (tdx, tdy)) = dport;
    let s_stub = (sx + f64::from(sdx) * margin, sy + f64::from(sdy) * margin);
    let t_stub = (tx + f64::from(tdx) * margin, ty + f64::from(tdy) * margin);
    if obs.iter().any(|&b| inside(s_stub.0, s_stub.1, b)) || obs.iter().any(|&b| inside(t_stub.0, t_stub.1, b)) {
        return None;
    }
    let mut xs = vec![s_stub.0, t_stub.0];
    let mut ys = vec![s_stub.1, t_stub.1];
    for &(x, y, w, h) in obs {
        xs.extend([x - margin, x + w + margin]);
        ys.extend([y - margin, y + h + margin]);
    }
    for &(gx, gy) in guides {
        xs.push(gx);
        ys.push(gy);
    }
    let (xs, ys) = (grid_lines(xs), grid_lines(ys));
    let (nx, ny) = (xs.len(), ys.len());
    let blocked: Vec<bool> = (0..nx * ny).map(|k| obs.iter().any(|&b| inside(xs[k / ny], ys[k % ny], b))).collect();

    let seg_ok = |i1: usize, j1: usize, i2: usize, j2: usize| {
        let (mx, my) = (f64::midpoint(xs[i1], xs[i2]), f64::midpoint(ys[j1], ys[j2]));
        !obs.iter().any(|&b| inside(mx, my, b))
    };
    let grown: Vec<Rect> = obs[..obs.len() - 2].iter().map(|&(x, y, w, h)| (x - margin, y - margin, w + 2.0 * margin, h + 2.0 * margin)).collect();
    let seg_close = |i1: usize, j1: usize, i2: usize, j2: usize| {
        let (mx, my) = (f64::midpoint(xs[i1], xs[i2]), f64::midpoint(ys[j1], ys[j2]));
        grown.iter().any(|&b| inside(mx, my, b))
    };

    let start = (lower_bound(&xs, s_stub.0), lower_bound(&ys, s_stub.1));
    let goal = (lower_bound(&xs, t_stub.0), lower_bound(&ys, t_stub.1));
    let h0 = (xs[start.0] - xs[goal.0]).abs() + (ys[start.1] - ys[goal.1]).abs();
    let mut heap = BinaryHeap::new();
    heap.push(Reverse(Node { f: h0, g: 0.0, ij: start, d: (sdx, sdy), prev: None }));
    let slot = |i: usize, j: usize, d: Dir| (i * ny + j) * 4 + dir_index(d);
    let mut seen = vec![false; nx * ny * 4];
    let mut came: Vec<Option<Key>> = vec![None; nx * ny * 4];
    let mut end: Option<(Key, f64)> = None;
    while let Some(Reverse(Node { g, ij: (i, j), d, prev, .. })) = heap.pop() {
        let mut g = g;
        let k = slot(i, j, d);
        if seen[k] {
            continue;
        }
        seen[k] = true;
        came[k] = prev;
        if (i, j) == goal {
            if d != (-tdx, -tdy) {
                g += BEND;
            }
            end = Some(((i, j, d), g));
            break;
        }
        for (di, dj) in [(1i32, 0i32), (-1, 0), (0, 1), (0, -1)] {
            let (ni, nj) = (i as i64 + i64::from(di), j as i64 + i64::from(dj));
            if ni < 0 || nj < 0 || ni >= nx as i64 || nj >= ny as i64 {
                continue;
            }
            let (ni, nj) = (ni as usize, nj as usize);
            if blocked[ni * ny + nj] || !seg_ok(i, j, ni, nj) {
                continue;
            }
            if (di, dj) == (-d.0, -d.1) {
                continue;
            }
            let step = (xs[ni] - xs[i]).abs() + (ys[nj] - ys[j]).abs();
            let mut ng = g + step + if (di, dj) == d { 0.0 } else { BEND } + if seg_close(i, j, ni, nj) { CLOSE * step } else { 0.0 };
            if let Some(p) = penalty {
                ng += p.at((xs[i], ys[j]), (xs[ni], ys[nj]));
            }
            if seen[slot(ni, nj, (di, dj))] {
                continue;
            }
            let hh = (xs[ni] - xs[goal.0]).abs() + (ys[nj] - ys[goal.1]).abs();
            heap.push(Reverse(Node { f: ng + hh, g: ng, ij: (ni, nj), d: (di, dj), prev: Some((i, j, d)) }));
        }
    }
    let (key, cost) = end?;
    let mut cells = Vec::new();
    let mut cur = Some(key);
    while let Some((i, j, d)) = cur {
        cells.push((xs[i], ys[j]));
        cur = came[slot(i, j, d)];
    }
    cells.reverse();
    let mut pts = vec![(sx, sy)];
    pts.extend(cells);
    pts.push((tx, ty));
    Some((cost, simplify(&pts)))
}

/// Everything `route()` takes besides the boxes: `sides` fixes an end, `busy_*` list the sides other edges
/// already attach to, `crossing` is the per-crossing cost, `guides` add grid lines, `fracs` move the ports.
#[derive(Clone, Debug)]
pub struct Options<'a> {
    pub margin: f64,
    pub sides: (Option<Side>, Option<Side>),
    pub busy_src: &'a [Side],
    pub busy_dst: &'a [Side],
    pub crossing: Option<&'a Crossings>,
    pub guides: &'a [Pt],
    pub fracs: (Option<f64>, Option<f64>),
}

impl Default for Options<'_> {
    fn default() -> Self {
        Options { margin: MARGIN, sides: (None, None), busy_src: &[], busy_dst: &[], crossing: None, guides: &[], fracs: (None, None) }
    }
}

/// Orthogonal polyline from a side of `src` to a side of `dst` that enters no obstacle.
#[must_use]
pub fn route(src: Rect, dst: Rect, obstacles: &[Rect], o: &Options) -> Vec<Pt> {
    let mut obs: Vec<Rect> = obstacles.iter().copied().filter(|&b| b != src && b != dst).collect();
    obs.extend([src, dst]);
    let (sp, dp) = (ports(src, o.fracs.0), ports(dst, o.fracs.1));
    let s_sides = o.sides.0.map_or(Side::ALL.to_vec(), |s| vec![s]);
    let d_sides = o.sides.1.map_or(Side::ALL.to_vec(), |s| vec![s]);
    let mut best: Option<(f64, Vec<Pt>)> = None;
    for &ss in &s_sides {
        for &ds in &d_sides {
            let Some((cost, pts)) = search(port(&sp, ss), port(&dp, ds), &obs, o.margin, o.crossing, o.guides) else {
                continue;
            };
            let extra = BUSY * f64::from(u8::from(o.busy_src.contains(&ss)) + u8::from(o.busy_dst.contains(&ds)));
            let cost = cost + extra;
            if best.as_ref().is_none_or(|b| cost < b.0 - 1e-9) {
                best = Some((cost, pts));
            }
        }
    }
    if let Some((_, pts)) = best { pts } else {
        let ((ax, ay), _) = port(&sp, Side::Bottom);
        let ((bx, by), _) = port(&dp, Side::Top);
        vec![(ax, ay), (ax, f64::midpoint(ay, by)), (bx, f64::midpoint(ay, by)), (bx, by)]
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const SRC: Rect = (0.0, 0.0, 40.0, 40.0);

    #[test]
    #[expect(clippy::float_cmp, reason = "exact equality with the Python results is the contract")]
    fn round2_matches_python_round() {
        // values from Python: round(0.125, 2) etc.
        assert_eq!(round2(0.125), 0.12);
        assert_eq!(round2(0.375), 0.38);
        assert_eq!(round2(2.675), 2.67);
        assert_eq!(round2(1.005), 1.0);
        assert_eq!(round2(-0.125), -0.12);
    }

    #[test]
    fn boxed_in_endpoints_give_the_elbow() {
        let src = (100.0, 100.0, 40.0, 40.0);
        let dst = (100.0, 200.0, 40.0, 40.0);
        let wall = (50.0, 50.0, 200.0, 250.0);
        let pts = route(src, dst, &[wall], &Options::default());
        assert_eq!(pts, vec![(120.0, 140.0), (120.0, 170.0), (120.0, 170.0), (120.0, 200.0)]);
    }

    #[test]
    fn stub_inside_an_obstacle_rejects_the_side_pair() {
        let dst = (300.0, 0.0, 40.0, 40.0);
        let wall = (45.0, 0.0, 40.0, 40.0); // the right stub (54, 20) lies inside it
        let o = Options { sides: (Some(Side::Right), Some(Side::Left)), ..Options::default() };
        // the only requested pair is rejected, so the router falls back to the elbow
        let pts = route(SRC, dst, &[wall], &o);
        assert_eq!(pts, vec![(20.0, 40.0), (20.0, 20.0), (320.0, 20.0), (320.0, 0.0)]);
    }

    #[test]
    fn busy_side_of_src_makes_the_route_pick_another() {
        let dst = (300.0, 0.0, 40.0, 40.0);
        let free = route(SRC, dst, &[], &Options::default());
        assert_eq!(free[0], (40.0, 20.0)); // leaves by the right side
        let o = Options { busy_src: &[Side::Right], ..Options::default() };
        let pts = route(SRC, dst, &[], &o);
        assert_ne!(pts[0], (40.0, 20.0));
    }

    #[test]
    fn crossing_cost_makes_the_route_go_around() {
        let dst = (200.0, 0.0, 40.0, 40.0);
        let drawn = vec![((120.0, -100.0), (120.0, 100.0))];
        let guides = [(106.0, -114.0), (134.0, 114.0)];
        let straight = route(SRC, dst, &[], &Options { guides: &guides, ..Options::default() });
        assert_eq!(straight, vec![(40.0, 20.0), (200.0, 20.0)]);
        let c = Crossings { cost: 1000.0, drawn: drawn.clone() };
        let pts = route(SRC, dst, &[], &Options { guides: &guides, crossing: Some(&c), ..Options::default() });
        assert!(pts.len() > 2);
        assert!(!pts.windows(2).any(|w| crosses(w[0], w[1], drawn[0].0, drawn[0].1)));
    }

    #[test]
    fn frac_places_the_port_on_its_side() {
        let src = (0.0, 0.0, 100.0, 40.0);
        let dst = (0.0, 200.0, 100.0, 40.0);
        let o = Options { sides: (Some(Side::Bottom), Some(Side::Top)), fracs: (Some(0.2), None), ..Options::default() };
        let pts = route(src, dst, &[], &o);
        assert_eq!(pts[0], (20.0, 40.0));
    }

    // Busy cost is 400 (ROUTE-07). With the right side of SRC busy, the straight route costs 232 + 400 = 632.
    // Free detours: no walls: the top route costs 480 (248 more than straight, between 200 and 400);
    // walls above and below SRC's next to its right stub: the cheapest detour costs 650 (418 more, over 400).
    fn busy_right(obstacles: &[Rect]) -> Vec<Pt> {
        let dst = (300.0, 0.0, 40.0, 40.0);
        let o = Options { sides: (None, Some(Side::Left)), busy_src: &[Side::Right], ..Options::default() };
        route(SRC, dst, obstacles, &o)
    }

    #[test]
    fn detour_costing_under_the_busy_cost_wins() {
        assert_eq!(busy_right(&[])[0], (20.0, 0.0)); // leaves by the top, not the busy right side
    }

    #[test]
    fn detour_costing_over_the_busy_cost_loses() {
        let walls = [(50.0, -85.0, 20.0, 80.0), (50.0, 45.0, 20.0, 80.0)];
        assert_eq!(busy_right(&walls)[0], (40.0, 20.0)); // keeps the busy right side
    }
}
