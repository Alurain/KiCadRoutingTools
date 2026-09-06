#!/usr/bin/env python3
"""band_dump.py -- the world ONE lane's router saw, as a picture and a census (#622).
usage: band_dump.py BOARD NETS DEST NET OUT.png [scale px/mm] [x0 y0 x1 y1]
(run with the same env as the braid, e.g. TWO_PAGE=1)
Builds the braid's corridors exactly as the attempt-0 plan does (spine,
offsets, schedule, planned lanes), then for NET draws: static copper of
other nets (F red / B blue, dim), the VIRTUAL copper the lane routes
against (F orange / B cyan), the lane's BAND cells on F (green) and on B
(magenta), its planned centreline (white), tooth (T) and stub (S).
Prints whether the tooth and stub cells lie inside the band on their layers."""
import os, sys, math
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'py_router'))
import numpy as np
from PIL import Image, ImageDraw
import braid
from schedule import Schedule

board, nets, dest, NET, out = sys.argv[1:6]
S = float(sys.argv[6]) if len(sys.argv) > 6 else 80.0
WIN = tuple(map(float, sys.argv[7:11])) if len(sys.argv) > 10 else None
names = [n for n in nets.split(',') if n]
logs = []
ctx, groups = braid.setup(board, names, dest, logs.append)
corridors = [braid.Corridor(ci, g, ctx, logs.append) for ci, g in enumerate(groups)]
ctx.corridors = corridors
target = next(c for c in corridors if NET in c.members)
for c in corridors:                       # plan phase, as main() does
    try:
        c.run(plan_only=True)
    except Exception as e:
        print('plan failed for corridor', c.idx, e)
c = target
sched = c.sched_cur
others = [om for om in c.members if om != NET]
virt = c.virtual_of(others) + braid.reserve(ctx, NET)
vvias = c.virtual_vias_of(others)
band = c.band_of(NET)
lane = c.lane_xy.get(NET) or [c.teeth[NET], c.stubs[NET]]
xs_all = [p[0] for p in lane] + [c.teeth[NET][0], c.stubs[NET][0]]
ys_all = [p[1] for p in lane] + [c.teeth[NET][1], c.stubs[NET][1]]
M = 1.2
x0, x1 = min(xs_all) - M, max(xs_all) + M
y0, y1 = min(ys_all) - M, max(ys_all) + M
if WIN:
    x0, y0, x1, y1 = WIN
G = 0.025
gx = np.arange(math.floor(x0 / G) * G, x1, G)
gy = np.arange(math.floor(y0 / G) * G, y1, G)
maskF = band(gx, gy, 'F.Cu')
maskB = band(gx, gy, 'B.Cu')
W, H = int((x1 - x0) * S), int((y1 - y0) * S)
im = Image.new('RGB', (W, H), (18, 20, 18)); d = ImageDraw.Draw(im)
P = lambda x, y: ((x - x0) * S, (y - y0) * S)
name = {i: n.name.rsplit('/', 1)[-1] for i, n in ctx.pcb.nets.items()}
nid = ctx.byname[NET][0]
for s in ctx.base_segments:
    if s.net_id == nid: continue
    col = (120, 50, 50) if s.layer == 'F.Cu' else (50, 70, 130)
    d.line([P(s.start_x, s.start_y), P(s.end_x, s.end_y)], fill=col, width=max(1, int(s.width * S)))
for v in ctx.base_vias:
    cx, cy = P(v.x, v.y); r = v.size / 2 * S
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(160, 160, 160), width=1)
for fp in ctx.pcb.footprints.values():
    for q in fp.pads:
        if not (x0 < q.global_x < x1 and y0 < q.global_y < y1): continue
        cx, cy = P(q.global_x, q.global_y); r = max(q.size_x, q.size_y) / 2 * S
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(90, 90, 40), width=1)
# band cells
for i, x in enumerate(gx):
    for j, y in enumerate(gy):
        if maskF[i, j] or maskB[i, j]:
            cx, cy = P(x, y)
            colr = (40, 160, 60) if maskF[i, j] and not maskB[i, j] else (170, 50, 170) if maskB[i, j] and not maskF[i, j] else (200, 200, 90)
            d.rectangle([cx, cy, cx + G * S, cy + G * S], fill=colr)
for (p, q, L) in virt:
    col = (255, 150, 40) if L == 'F.Cu' else (40, 220, 255)
    d.line([P(*p), P(*q)], fill=col, width=2)
for (vx, vy) in vvias:
    cx, cy = P(vx, vy); r = 0.125 * S
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(255, 255, 0), width=2)
d.line([P(*p) for p in lane], fill=(255, 255, 255), width=1)
for lab, pt in (('T', c.teeth[NET]), ('S', c.stubs[NET])):
    cx, cy = P(*pt); d.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], outline=(255, 255, 255), width=2); d.text((cx + 5, cy - 12), lab, fill=(255, 255, 255))
for g in range(int(x0), int(x1) + 1):
    d.line([P(g, y0), P(g, y1)], fill=(40, 45, 40)); d.text((P(g, y0)[0] + 2, 2), str(g), fill=(120, 120, 120))
for g in range(int(y0), int(y1) + 1):
    d.line([P(x0, g), P(x1, g)], fill=(40, 45, 40)); d.text((2, P(x0, g)[1] + 2), str(g), fill=(120, 120, 120))
im.save(out)

def at(pt, mask):
    i = int(round((pt[0] - gx[0]) / G)); j = int(round((pt[1] - gy[0]) / G))
    i = min(max(i, 0), len(gx) - 1); j = min(max(j, 0), len(gy) - 1)
    win = mask[max(0, i - 1):i + 2, max(0, j - 1):j + 2]
    return bool(mask[i, j]), int(win.sum())
tl, dl = ctx.tooth_layer[NET], ctx.dest_layer[NET]
print(f'{NET}: corridor {c.idx} page {sched.page.get(NET) if sched else "?"} tooth {c.teeth[NET]} {tl} stub {c.stubs[NET]} {dl}')
print(f'  band cells F {int(maskF.sum())} B {int(maskB.sum())}; tooth in band on {tl}: {at(c.teeth[NET], maskF if tl=="F.Cu" else maskB)} (cell, 3x3 count); stub on {dl}: {at(c.stubs[NET], maskF if dl=="F.Cu" else maskB)}')
print(f'  legs {[(round(a,2), round(b,2), round(cc,2)) for a,b,cc in c.legs.get(NET, [])]}  jogs {c.jogs.get(NET)}')
print(f'  req {[(round(a,2), round(b,2), L) for a,b,L in c.req.get(NET, [])]}  bwin {[(round(a,2), round(b,2)) for a,b in c.bwin.get(NET, [])]}')
print(f'  virtual pieces {len(virt)} (F {sum(1 for v in virt if v[2]=="F.Cu")} / B {sum(1 for v in virt if v[2]=="B.Cu")}), virtual vias {len(vvias)}; wrote {out}')

def _d(p, q, r):
    dx, dy = q[0] - p[0], q[1] - p[1]; L2 = dx * dx + dy * dy
    t_ = 0 if L2 < 1e-12 else max(0.0, min(1.0, ((r[0] - p[0]) * dx + (r[1] - p[1]) * dy) / L2))
    return math.hypot(p[0] + t_ * dx - r[0], p[1] + t_ * dy - r[1])
for lab, pt in (('tooth', c.teeth[NET]), ('stub', c.stubs[NET])):
    near = []
    for om in others:
        for (p, q, L) in c.virtual_of([om]):
            dd = _d(p, q, pt)
            if dd < 0.45: near.append((round(dd, 3), om, L))
    for (p, q, L) in braid.reserve(ctx, NET):
        dd = _d(p, q, pt)
        if dd < 0.45: near.append((round(dd, 3), 'reserve', L))
    for (vx, vy) in vvias:
        dd = math.hypot(vx - pt[0], vy - pt[1])
        if dd < 0.6: near.append((round(dd, 3), 'virtual-via', '*'))
    stat = []
    for sg in ctx.base_segments:
        if sg.net_id == nid: continue
        dd = _d((sg.start_x, sg.start_y), (sg.end_x, sg.end_y), pt)
        if dd < 0.35: stat.append((round(dd, 3), name.get(sg.net_id, '?'), sg.layer))
    for v in ctx.base_vias:
        dd = math.hypot(v.x - pt[0], v.y - pt[1])
        if dd < 0.5: stat.append((round(dd, 3), name.get(v.net_id, '?'), 'via'))
    print(f'  near {lab}: virtual {sorted(near)[:8]} | static {sorted(stat)[:8]}')
