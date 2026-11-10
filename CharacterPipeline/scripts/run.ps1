param([string]$Script, [int]$TimeoutSec = 120)
# Sends a script to the running Blender bridge and prints its result.
# Bridge folder: $env:ANIME_GAME_BRIDGE, else the _bridge folder next to this script.
$d = if ($env:ANIME_GAME_BRIDGE) { $env:ANIME_GAME_BRIDGE } else { Join-Path $PSScriptRoot "_bridge" }
Remove-Item "$d\result.txt" -ErrorAction SilentlyContinue
Copy-Item $Script "$d\cmd.tmp" -Force
Move-Item "$d\cmd.tmp" "$d\cmd.py" -Force
$end = (Get-Date).AddSeconds($TimeoutSec)
while ((Get-Date) -lt $end) {
    if (Test-Path "$d\result.txt") { Get-Content "$d\result.txt"; exit 0 }
    Start-Sleep -Milliseconds 500
}
"TIMEOUT waiting for Blender"
exit 1
