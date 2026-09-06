#!/usr/bin/env python3
"""#622 fanout OBEDIENCE audit at the track level: what the plan asked
per net at each array (side, gap line, layer, page) versus what the
fanout delivered (read off the copper by surgical.stub_asks), each
miss classified and measured:

  exact      same side, same gap (|delivered - line| <= tol), same layer
  gap        same side, another gap            (distance in gaps)
  side       another side
  layer      same side and gap, other layer
  none       no copper at that end

and, for a gap miss, whether the ASKED gap was taken by another net's
delivered copper (a contention miss) or is empty (an engine refusal).

usage: audit_fanout.py ASKS.json FO.kicad_pcb K [--tol 0.3]
"""
import argparse
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)
import surgical as sg  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument('asks')
ap.add_argument('fo')
ap.add_argument('k')
ap.add_argument('--tol', type=float, default=0.3,
                help='fraction of a pitch that still counts as the '
                     'asked gap')
ap.add_argument('--refs', default='', help='audit only these arrays '
                '(default: both; the plain arm never applies the source, '
                'so pass --refs DU1 there)')
ap.add_argument('--src', default='U1')
ap.add_argument('--dst', default='DU1')
a = ap.parse_args()
nets = sg.k_nets(a.k).split(',')
asks = json.load(open(a.asks))
for _n, _ends in asks.items():
    for _r, _ask in _ends.items():
        _ask.setdefault('line', _ask.get('coord'))
got = sg.stub_asks(a.fo, nets, (a.src, a.dst))
pcb = sg.parse_kicad_pcb(a.fo)


def pitch_of(ref):
    xs = sorted(set(round(q.global_x, 3) for q in pcb.footprints[ref].pads))
    return min(b - c for b, c in zip(xs[1:], xs))


rows = []
by_ref_gap = {}      # (ref, side, gap) -> [nets delivered there]
for nm, ends in got.items():
    for ref, (side, coord, lay) in ends.items():
        by_ref_gap.setdefault((ref, side, round(coord / pitch_of(ref))), []).append(nm)
summ = collections.Counter()
REFS = a.refs.split(',') if a.refs else [a.src, a.dst]
for nm in nets:
    for ref in REFS:
        ask = asks.get(nm, {}).get(ref)
        if not ask:
            continue
        d = got.get(nm, {}).get(ref)
        p = pitch_of(ref)
        if d is None:
            cls, detail = 'none', ''
        elif d[0] != ask['side']:
            cls, detail = 'side', f'{ask["side"]}->{d[0]}'
        else:
            off = abs(d[1] - ask['line']) / p
            if off <= a.tol:
                # the split scope fans a B-PAGE berth on B by design,
                # whatever layer the ask carried: judge against that
                want_L = ('B.Cu' if ask.get('page') == 'B.Cu' and ref == a.dst
                          else ask.get('layer'))
                cls = 'exact' if (not want_L or d[2] == want_L) else 'layer'
                detail = '' if cls == 'exact' else f'{ask["layer"]}->{d[2]}'
            else:
                cls = 'gap'
                takers = [o for o in by_ref_gap.get(
                    (ref, ask['side'], round(ask['line'] / p)), []) if o != nm]
                # a taker that ASKED this gap = plan contention (two
                # asks on one gap); one displaced into it = cascade
                who = []
                for o in takers:
                    oa = asks.get(o, {}).get(ref)
                    same = (oa and oa['side'] == ask['side']
                            and abs(oa['line'] - ask['line']) / p <= a.tol)
                    who.append(f'{o}({"asked it" if same else "displaced"})')
                detail = (f'{off:+.1f} gaps; asked gap '
                          + (f'taken by {who}' if who else 'EMPTY'))
        summ[(ref, cls)] += 1
        rows.append((ref, cls, nm, ask, d, detail))

for ref in (a.src, a.dst):
    tot = sum(v for (r, c), v in summ.items() if r == ref)
    if not tot:
        continue
    print(f'{ref}: ' + ', '.join(f'{c} {summ[(ref, c)]}' for c in
                                  ('exact', 'gap', 'side', 'layer', 'none')
                                  if summ[(ref, c)]) + f'  (of {tot})')
for ref, cls, nm, ask, d, detail in rows:
    if cls == 'exact':
        continue
    print(f'  {ref} {nm:7s} {cls:5s} asked {ask["side"]}/{ask.get("layer", "?")}'
          f'@{ask["line"]:.2f}'
          + (f'  got {d[0]}/{d[2]}@{d[1]:.2f}' if d else '  got nothing')
          + (f'  {detail}' if detail else '')
          + (f'  page {ask["page"]}' if ask.get('page') else ''))
