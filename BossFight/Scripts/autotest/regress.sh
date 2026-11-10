# Full regression: every autotest mode on both maps; summary in Saved/Logs/regress_summary.txt.
cd "$(dirname "$0")/../.."
OUT=Saved/Logs/regress_summary.txt; : > "$OUT"
run() { NAME=$1; shift; bash Scripts/autotest/run.sh "$NAME" "$@" > /dev/null 2>&1
  { echo "=== $NAME ($*)"; grep -E "BFTEST|Error|Ensure|Fatal|Assertion" "Saved/Logs/$NAME.log" | grep -v "shot \|LogPython\|LogInit" | sed 's/^\[[^]]*\]\[[^]]*\]//; s/LogTemp: Display: //' | sort | uniq -c | sort -rn | head -40; } >> "$OUT"; }
run rg_tr_move L_Training move
run rg_tr_combat L_Training combat
run rg_tr_parry L_Training parry
run rg_tr_hurt L_Training hurt
run rg_tr_charges L_Training charges
run rg_tr_cancel L_Training cancel
run rg_ar_dodge L_Arena dodge
run rg_ar_struggle L_Arena struggle -BFForceAttacks=3,2,0,2
# Human timing: answer the heavy slam's "now" cue 0.22 s late (reaction time), with the delayed hold forced.
run rg_ar_react_guard L_Arena struggle -BFForceAttacks=2 -BFHoldChance=1 -BFParryReact=0.22
run rg_ar_react_roll L_Arena struggle -BFForceAttacks=2 -BFHoldChance=1 -BFParryReact=0.22 -BFReactRoll
run rg_ar_parry L_Arena parry
run rg_ar_hurt L_Arena hurt
run rg_ar_combat L_Arena combat
run rg_ar_lockon L_Arena lockon
run rg_ar_perilous L_Arena perilous -BFForceAttacks=6,7,8,6,7,8
run rg_ar_phase2 L_Arena phase2 -BFBossHP=0.52
run rg_ar_camwall L_Arena camwall
run rg_ar_ledge L_Arena ledge
# Boss turn in place, backstep, stance break, spells; player air combo + plunge.
run rg_ar_turn L_Arena turn
run rg_ar_backstep L_Arena backstep
run rg_ar_stance L_Arena stance -BFStance=100
run rg_ar_magic L_Arena magic -BFForceAttacks=10,11
run rg_ar_magic_roll L_Arena magic -BFForceAttacks=10,11 -BFMagicRoll
run rg_ar_magic2 L_Arena magic -BFForceAttacks=10,11 -BFBossHP=0.45
run rg_tr_air L_Training air
run rg_ar_air L_Arena air -BFNoBackstep
echo ALLDONE >> "$OUT"
