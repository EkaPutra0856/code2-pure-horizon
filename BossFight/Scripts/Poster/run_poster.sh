#!/bin/bash
export MSYS_NO_PATHCONV=1
# Usage: bash run_poster.sh <scene.txt> [map] [winX winY]
# Renders the stills of a poster scene file (-BFAutoTest=poster) and prints the BFPOSTER log lines.
# BOSSFIGHT_DIR: the BossFight project folder (defaults to two levels above this script).
# UE_ROOT: the Unreal Engine install folder (the one that holds Engine/).
P="${BOSSFIGHT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
UE_ROOT="${UE_ROOT:?set UE_ROOT to your Unreal Engine install folder}"
SCENE="$1"; MAP="${2:-/Game/BossFight/Maps/L_Cinematic}"; WX="${3:-480}"; WY="${4:-720}"
NAME=$(basename "$SCENE" .txt)
LOG="$P/Saved/Logs/poster_$NAME.log"
timeout 420 "$UE_ROOT/Engine/Binaries/Win64/UnrealEditor.exe" "$P/BossFight.uproject" "$MAP" -game -windowed -ResX=$WX -ResY=$WY \
  -BFAutoTest=poster "-BFPosterFile=$SCENE" -nosplash -nosound -abslog="$LOG"
echo "exit=$?"
grep -E "BFPOSTER|Error:|Ensure" "$LOG" | sed 's/^\[[^]]*\]\[[^]]*\]//' | head -60
