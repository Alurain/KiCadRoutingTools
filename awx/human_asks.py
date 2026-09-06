#!/usr/bin/env python3
"""Boundary-crossing census: for each net, the point where its copper
first LEAVES an array's boundary box (pads inflated by half a pitch),
as an ask (side, coord along that side, layer). Segment-boundary
INTERSECTION, not the outside endpoint: a diagonal exit through a
corner otherwise reports a coordinate outside the array.
usage: human_asks.py BOARD K OUT.json [--refs U1,DU1]"""
import argparse, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'py_router')); sys.path.insert(0, HERE)
from kicad_parser import parse_kicad_pcb  # noqa: E402
import surgical as sg  # noqa: E402
ap = argparse.ArgumentParser(); ap.add_argument('board'); ap.add_argument('k'); ap.add_argument('out')
ap.add_argument('--refs', default='U1,DU1'); ap.add_argument('--mf', type=float, default=0.5)
a = ap.parse_args()
nets = sg.k_nets(a.k).split(',')
p = parse_kicad_pcb(a.board); short = {i: n.name.rsplit('/', 1)[-1] for i, n in p.nets.items()}
out = {}
for ref in a.refs.split(','):
    fp = p.footprints[ref]
    xs = sorted(set(round(q.global_x, 3) for q in fp.pads)); ys = sorted(set(round(q.global_y, 3) for q in fp.pads))
    px = min(b - c for c, b in zip(xs, xs[1:])); py = min(b - c for c, b in zip(ys, ys[1:]))
    x0, y0, x1, y1 = xs[0] - px * a.mf, ys[0] - py * a.mf, xs[-1] + px * a.mf, ys[-1] + py * a.mf
    def inside(x, y): return x0 <= x <= x1 and y0 <= y <= y1
    for s in p.segments:
        nm = short.get(s.net_id)
        if nm not in nets or ref in out.get(nm, {}):
            continue
        ai, bi = inside(s.start_x, s.start_y), inside(s.end_x, s.end_y)
        if ai == bi:
            continue
        (ix, iy), (ox, oy) = ((s.start_x, s.start_y), (s.end_x, s.end_y)) if ai else ((s.end_x, s.end_y), (s.start_x, s.start_y))
        # first edge crossed walking from the inside point out
        best = None
        for side, (ex, axis) in (('left', (x0, 'x')), ('right', (x1, 'x')), ('up', (y0, 'y')), ('down', (y1, 'y'))):
            if axis == 'x':
                if (ix - ex) * (ox - ex) > 0 or ox == ix: continue
                t = (ex - ix) / (ox - ix); cy = iy + t * (oy - iy)
                if y0 - 1e-6 <= cy <= y1 + 1e-6 and (best is None or t < best[0]): best = (t, side, cy)
            else:
                if (iy - ex) * (oy - ex) > 0 or oy == iy: continue
                t = (ex - iy) / (oy - iy); cx = ix + t * (ox - ix)
                if x0 - 1e-6 <= cx <= x1 + 1e-6 and (best is None or t < best[0]): best = (t, side, cx)
        if best is None:
            continue
        out.setdefault(nm, {})[ref] = dict(side=best[1], coord=round(best[2], 3), layer=s.layer)
json.dump(out, open(a.out, 'w'), indent=1)
import collections
for ref in a.refs.split(','):
    c = collections.Counter((v[ref]['side'], v[ref]['layer'][0]) for v in out.values() if ref in v)
    print(ref, sum(c.values()), 'asks', dict(c))
