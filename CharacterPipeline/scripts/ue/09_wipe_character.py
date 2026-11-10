# Removes everything generated under /Game/Character so the mesh can come back with a clean
# centimetre skeleton. Every asset there is rebuilt by 10_import_cm.py and 06_retarget.py.
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import unreal

lib = unreal.EditorAssetLibrary
out = []
for d in ("/Game/Character/Mage", "/Game/Character/Retarget", "/Game/Character/Anim", "/Game/Character"):
    if lib.does_directory_exist(d):
        out.append(f"{d} {lib.delete_directory(d)}")
out.append(f"left {lib.does_directory_exist('/Game/Character')}")
open(os.path.join(ANIME_GAME_ROOT, r"scripts\ue\report_wipe.txt"), "w", encoding="utf-8").write("\n".join(out))
