# Writes a catalogue of effect and sound assets, and tries loading a sample from each pack.
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import collections, os
import unreal

ROOT = ANIME_GAME_ROOT
OUT = os.path.join(ROOT, "scripts", "ue", "report_fx.txt")
reg = unreal.AssetRegistryHelpers.get_asset_registry()
reg.scan_paths_synchronous(["/Game"], True)
lines = []
WANT = {"NiagaraSystem", "ParticleSystem", "SoundCue", "SoundWave"}
for root in ("MagicKit", "SlashHitVFX", "BalticVFX_MagicCirclesToolkit", "Hack_And_Slash_FX", "Casting___Loops", "Chimes___Pads", "Elements___School", "General", "Special_Attacks",
             "MageAnimationSet/FX"):
    assets = reg.get_assets_by_path("/Game/" + root, recursive=True)
    count = collections.Counter(str(a.asset_class_path.asset_name) for a in assets)
    lines.append(f"## {root} total {len(assets)} {dict(count.most_common(8))}")
    fx = [a for a in assets if str(a.asset_class_path.asset_name) in WANT]
    cue = [a for a in fx if str(a.asset_class_path.asset_name) == "SoundCue"]
    use = cue if cue else fx
    use = [a for a in use if "Demo/" not in str(a.package_name) or "NS" in str(a.package_name)]
    for a in use:
        lines.append(f"{a.asset_class_path.asset_name} {a.package_name}")
    if use:
        ok = sum(1 for a in use[:5] if unreal.load_asset(str(a.package_name)) is not None)
        lines.append(f"sample load {ok}/{min(5, len(use))}")
open(OUT, "w", encoding="utf-8").write("\n".join(lines))
