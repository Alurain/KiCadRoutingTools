#!/usr/bin/env python3
"""#622 escape-face census: which EDGE of the U1/DU1 package each
K-net's copper crosses, and on what layer -- ours vs human. The
boundary is the bbox of the footprint's pads inflated by MARGIN; the
crossing nearest the net's own ball wins.

usage: escape_census.py OURS.kicad_pcb HUMAN.kicad_pcb K
"""
import math
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'py_router'))
from kicad_parser import parse_kicad_pcb  # noqa: E402

ours_p, human_p, K = sys.argv[1], sys.argv[2], sys.argv[3]
MARGIN = 0.4
nets = subprocess.run(
    [sys.executable, os.path.join(HERE, 'coherent_nets.py'), K],
    capture_output=True, text=True).stdout.strip().split(',')


def bbox(fp):
    xs = [p.global_x for p in fp.pads]
    ys = [p.global_y for p in fp.pads]
    return (min(xs) - MARGIN, min(ys) - MARGIN,
            max(xs) + MARGIN, max(ys) + MARGIN)


def inside(x, y, bb):
    return bb[0] <= x <= bb[2] and bb[1] <= y <= bb[3]


def edge_of(x, y, bb):
    # nearest edge for a point ON/near the boundary; KiCad y grows down
    d = {'W': x - bb[0], 'E': bb[2] - x, 'N': y - bb[1],
         'S': bb[3] - y}
    return min(d, key=d.get)


def cross(pcb, want, fp):
    bb = bbox(fp)
    out = {}
    id2short = {nid: n.name.rsplit('/', 1)[-1]
                for nid, n in pcb.nets.items()}
    ball = {}
    for p in fp.pads:
        nm = p.net_name.rsplit('/', 1)[-1] if p.net_name else ''
        if nm in want:
            ball[nm] = (p.global_x, p.global_y)
    for s in pcb.segments:
        nm = id2short.get(s.net_id)
        if nm not in want or nm not in ball:
            continue
        i0 = inside(s.start_x, s.start_y, bb)
        i1 = inside(s.end_x, s.end_y, bb)
        if i0 == i1:
            continue
        # crossing point: clip the segment to the box edge (walk t)
        (ix, iy), (ox, oy) = ((s.start_x, s.start_y),
                              (s.end_x, s.end_y)) if i0 else \
            ((s.end_x, s.end_y), (s.start_x, s.start_y))
        lo, hi = 0.0, 1.0
        for _ in range(40):
            t = (lo + hi) / 2
            if inside(ix + t * (ox - ix), iy + t * (oy - iy), bb):
                lo = t
            else:
                hi = t
        px, py = ix + lo * (ox - ix), iy + lo * (oy - iy)
        bx, by = ball[nm]
        dist = math.hypot(px - bx, py - by)
        prev = out.get(nm)
        if prev is None or dist < prev[2]:
            out[nm] = (edge_of(px, py, bb), s.layer[0], dist,
                       round(px, 1), round(py, 1))
    return out


def censu(path):
    pcb = parse_kicad_pcb(path)
    want = set(nets)
    return (cross(pcb, want, pcb.footprints['U1']),
            cross(pcb, want, pcb.footprints['DU1']))


osrc, odst = censu(ours_p)
hsrc, hdst = censu(human_p)


def fmt(d, n):
    v = d.get(n)
    return f'{v[0]}{v[1]}' if v else '--'


print(f'{"net":8s} | {"o.src":5s} {"o.dst":5s} | '
      f'{"h.src":5s} {"h.dst":5s} |')
mism = []
for n in nets:
    o, h = osrc.get(n), hsrc.get(n)
    mark = ''
    if o and h and (o[0] != h[0] or o[1] != h[1]):
        mark = ' <<'
        mism.append(n)
    print(f'{n:8s} | {fmt(osrc, n):5s} {fmt(odst, n):5s} | '
          f'{fmt(hsrc, n):5s} {fmt(hdst, n):5s} |{mark}')
print(f'\nsrc face+layer mismatches ({len(mism)}): {",".join(mism)}')
for tag, d in (('ours SRC', osrc), ('human SRC', hsrc),
               ('ours DST', odst), ('human DST', hdst)):
    cnt = {}
    for n in nets:
        v = d.get(n)
        if v:
            cnt[v[0] + v[1]] = cnt.get(v[0] + v[1], 0) + 1
    print(f'{tag:10s}: '
          + ' '.join(f'{k}={v}' for k, v in sorted(cnt.items())))
