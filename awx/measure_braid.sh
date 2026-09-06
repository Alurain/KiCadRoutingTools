#!/bin/bash
# measure.sh TAG BOARD K [ENV...]: braid on a fanout board, grade, in-band tally
TAG=$1; BOARD=$2; K=$3; shift 3
cd "$(dirname "$0")"
NETS=$(python3 coherent_nets.py "$K")
env "$@" TWO_PAGE=1 python3 -u braid.py --board "$BOARD" --dest DU1 --nets "$NETS" --out "tmp/${TAG}_k${K}" > "tmp/${TAG}_k${K}.log" 2>&1
python3 grade_k.py "tmp/${TAG}_k${K}.kicad_pcb" "$NETS" | tail -1
python3 - "tmp/${TAG}_k${K}.log" "$K" <<'PY'
import re, sys
t=open(sys.argv[1],errors='replace').read(); K=int(sys.argv[2])
a=t.split('attempt 0:')[1].split('attempt 1:')[0] if 'attempt 0:' in t else ''
lc=set(re.findall(r'last call routed: (\S+)',t))|set(re.findall(r'last call: (\S+) still refused',t))
print(f'  attempt-0 refusals {len(set(re.findall(r"refused: (\S+)",a)))} | in-band {K-len(lc)}/{K}')
PY
