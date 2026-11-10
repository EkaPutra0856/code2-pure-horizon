# Runs one autotest and builds contact sheets of its screenshots.
# usage: bash Scripts/autotest/run.sh <name> <L_Arena|L_Training> <mode> [extra args...]
# Logs: Saved/Logs/<name>.log. Shots + sheets: Saved/Screenshots/WindowsEditor/<name>/
cd "$(dirname "$0")/../.."
# UE_ROOT: the Unreal Engine install folder (the one that holds Engine/).
UE_ROOT="${UE_ROOT:?set UE_ROOT to your Unreal Engine install folder}"
NAME=$1; MAP=$2; MODE=$3; shift 3
SH=Saved/Screenshots/WindowsEditor
rm -rf "$SH/$NAME"; mkdir -p "$SH/$NAME"
rm -f $SH/BFTest_*.png
MSYS_NO_PATHCONV=1 timeout 300 "$UE_ROOT/Engine/Binaries/Win64/UnrealEditor.exe" "$(cygpath -m "$PWD")/BossFight.uproject" /Game/BossFight/Maps/$MAP -game -windowed -ResX=1280 -ResY=720 -BFAutoTest=$MODE "$@" -log=$NAME.log > /dev/null 2>&1
echo "exit=$?"
mv -f $SH/BFTest_*.png "$SH/$NAME/" 2>/dev/null
python Scripts/autotest/sheet.py "$SH/$NAME"
