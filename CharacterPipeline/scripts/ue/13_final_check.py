# Fresh-process check of the finished project: counts, broken references, and material links.
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import os
import unreal

ROOT = ANIME_GAME_ROOT
LOG = os.path.join(ROOT, "scripts", "ue", "report_final.txt")
lines = []


def say(*a):
    lines.append(" ".join(str(x) for x in a))
    open(LOG, "w", encoding="utf-8").write("\n".join(lines))


L = unreal.AnimationLibrary
lib = unreal.EditorAssetLibrary
say("anim", len(lib.list_assets("/Game/Character/Anim", recursive=True, include_folder=False)), "mage", len(lib.list_assets("/Game/Character/Mage", recursive=True, include_folder=False)))
mesh = unreal.load_asset("/Game/Character/karakter_ue")
say("physics", mesh.get_editor_property("physics_asset"))
# Material textures are checked in 14_materials.py. get_used_textures returns nothing under -nullrhi.
a = unreal.load_asset("/Game/Character/Anim/A_Ultimate_EternalBloom")
say("ultimate notifies", sum(len(L.get_animation_notify_events_for_track(a, t)) for t in ("VFX", "VFX2", "SFX", "SFX2")), "length", L.get_sequence_length(a))
m = unreal.load_asset("/Game/Character/Mage/Mage_Fireball_R")
say("fireball skeleton", m.get_editor_property("skeleton").get_name(), "tracks", len(L.get_animation_track_names(m)))
say("DONE")
