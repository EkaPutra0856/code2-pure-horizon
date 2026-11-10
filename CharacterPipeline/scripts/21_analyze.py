# Prints each cast clip's hand speed profile, which shows where the strike lands.
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import bpy, json, sys, importlib
import numpy as np

ROOT = ANIME_GAME_ROOT
p = ROOT + r"\mixamo\target_rest.json"
d = json.load(open(p))
arm = bpy.data.objects["Armature"]
d["heads"] = {k: list(arm.data.bones[k].head_local) for k in d["rest"]}
d["root_rest"] = list(arm.data.bones["Root"].matrix_local.to_quaternion())
json.dump(d, open(p, "w"))
sys.path.insert(0, ROOT + r"\scripts")
import animlib
importlib.reload(animlib)

NAMES = ["standing_1h_magic_attack_01", "standing_1h_magic_attack_02", "standing_1h_magic_attack_03", "standing_1h_cast_spell_01",
         "standing_2h_cast_spell_01", "standing_2h_magic_area_attack_01", "standing_2h_magic_area_attack_02",
         "standing_2h_magic_attack_01", "standing_2h_magic_attack_02", "standing_2h_magic_attack_03", "standing_2h_magic_attack_04",
         "standing_2h_magic_attack_05", "magic_heal", "spell_casting_summon", "two_hand_spell_casting", "wide_arm_spell_casting",
         "standing_jump", "standing_idle", "standing_idle_02", "dodge_back", "dodge_forward", "dodge_left"]
for n in NAMES:
    c = animlib.load(n)
    L, R, H = animlib.hand_paths(c)
    sl = np.linalg.norm(np.diff(L, axis=0), axis=1) * 30
    sr = np.linalg.norm(np.diff(R, axis=0), axis=1) * 30
    s = np.maximum(sl, sr)
    act = np.nonzero(s > 0.35 * s.max())[0]
    pk = [int(i) for i in np.argsort(s)[::-1] if s[i] >= s[max(i - 1, 0)] and s[i] >= s[min(i + 1, len(s) - 1)]][:3]
    print(n, "F", len(c), "active", int(act[0]), int(act[-1]), "peaks", sorted(pk), "maxspeed", round(float(s.max()), 1),
          "lead", "L" if sl.max() > sr.max() else "R", "handsZ", round(float(L[:, 2].max()), 2), round(float(R[:, 2].max()), 2),
          "hipZ", round(float(H[:, 2].min()), 2), round(float(H[:, 2].max()), 2))
