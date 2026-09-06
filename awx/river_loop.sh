#!/bin/bash
# river_loop.sh TAG BASE K : plain fanout -> river plan -> B berths for the B river -> river braid
TAG=$1; BASE=$2; K=$3; shift 3
cd "$(dirname "$0")"
NETS=$(python3 coherent_nets.py "$K")
export TWO_PAGE=1 TP_SCOPE=split
RV="BRAID_RIVERS=face BRAID_RIVER_XT=0.05 BRAID_RIVER_MIN=6 BRAID_XRES_END=0.6 BRAID_STAY_PAGE=1 BRAID_END_CLASH=min"
echo "== stage 1: plain fanout"
python3 fanout_from_plan.py tmp/${TAG}_fo0_k${K}.kicad_pcb "$K" --board="$BASE" --no-lines --two-page --no-plane-drop > tmp/${TAG}_fo0_k${K}.log 2>&1
grep -E "^wrote|obeyed|split GATE" tmp/${TAG}_fo0_k${K}.log | cut -c1-120
echo "== stage 2: river plan (plan-only braid)"
env $RV python3 braid.py --board tmp/${TAG}_fo0_k${K}.kicad_pcb --dest DU1 --nets "$NETS" --out /dev/null --plan-json tmp/${TAG}_plan_k${K}.json > tmp/${TAG}_plan_k${K}.log 2>&1
grep -E "^rivers:|folded" tmp/${TAG}_plan_k${K}.log | cut -c1-160
BNETS=$(python3 - tmp/${TAG}_fo0_k${K}.rivers.json <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
b=[nm for gi,g in enumerate(d['corridors']) if d['pages'][str(gi)]=='B.Cu' for nm in g]
print(','.join(b))
PY
)
echo "  B river nets ($(echo $BNETS | tr ',' '\n' | grep -c .)): $BNETS"
echo "== stage 3: fanout with B berths for the B river"
TP_SPLIT_NETS="$BNETS" TP_SPLIT_ONLY=1 python3 fanout_from_plan.py tmp/${TAG}_fo_k${K}.kicad_pcb "$K" --board="$BASE" --no-lines --two-page --no-plane-drop > tmp/${TAG}_fo_k${K}.log 2>&1
grep -E "^wrote|obeyed|split GATE|split B pass|berths" tmp/${TAG}_fo_k${K}.log | cut -c1-160
python3 ../py_router/check_drc.py tmp/${TAG}_fo_k${K}.kicad_pcb --clearance 0.1 --clearance-margin 0.1 2>&1 | grep -E "FOUND|NO DRC"
python3 escape_census.py tmp/${TAG}_fo_k${K}.kicad_pcb ~/Downloads/bus/00_human_original.kicad_pcb "$K" 2>&1 | grep -E "ours DST|human DST"
echo "== stage 4: river braid"
env $RV ./measure_braid.sh ${TAG} tmp/${TAG}_fo_k${K}.kicad_pcb "$K" $RV
grep -E "^rivers:|folded" tmp/${TAG}_k${K}.log | cut -c1-160
