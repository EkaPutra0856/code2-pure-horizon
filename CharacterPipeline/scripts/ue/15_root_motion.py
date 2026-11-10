# Turns on root motion for clips flagged in moves.json and for all Mage clips, which come from the
# pack's RootMotion folder. Safe to rerun.
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import json, os
import unreal

ROOT = ANIME_GAME_ROOT
LOG = os.path.join(ROOT, "scripts", "ue", "report_root_motion.txt")
lib = unreal.EditorAssetLibrary
moves = json.load(open(os.path.join(ROOT, "export_unreal", "anim", "moves.json")))["moves"]
on = off = 0
for name, m in moves.items():
    a = unreal.load_asset("/Game/Character/Anim/A_" + name)
    want = bool(m.get("root_motion"))
    a.set_editor_property("enable_root_motion", want)
    lib.save_loaded_asset(a, False)
    on += want
    off += not want
mage = 0
for p in lib.list_assets("/Game/Character/Mage", recursive=True, include_folder=False):
    a = unreal.load_asset(p.split(".")[0])
    a.set_editor_property("enable_root_motion", True)
    lib.save_loaded_asset(a, False)
    mage += 1
d = unreal.load_asset("/Game/Character/Anim/A_Dodge_Back")
r = unreal.load_asset("/Game/Character/Anim/A_Run_F")
out = [f"blender on {on} off {off} mage {mage}", f"check dodge {d.get_editor_property('enable_root_motion')} run {r.get_editor_property('enable_root_motion')}", "DONE"]
open(LOG, "w", encoding="utf-8").write("\n".join(out))
