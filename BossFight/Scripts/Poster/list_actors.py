"""Lists a map's actors (name, label, location, bounds) to Saved/poster_actors[_<tag>].txt for poster staging.
Map comes from env BF_POSTER_MAP (default L_Cinematic); output tag from BF_POSTER_TAG."""
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import os
import unreal
m = os.environ.get("BF_POSTER_MAP", "/Game/BossFight/Maps/L_Cinematic")
tag = os.environ.get("BF_POSTER_TAG", "")
w = unreal.EditorLoadingAndSavingUtils.load_map(m)
out = []
for a in unreal.EditorLevelLibrary.get_all_level_actors():
    l = a.get_actor_location()
    o, e = a.get_actor_bounds(False)
    out.append("%-40s %-40s %8.0f %8.0f %7.0f  ext %6.0f %6.0f %6.0f" % (a.get_name()[:40], a.get_actor_label()[:40], l.x, l.y, l.z, e.x, e.y, e.z))
p = os.path.join(ANIME_GAME_ROOT, r"BossFight/Saved/poster_actors%s.txt") % (("_" + tag) if tag else "")
open(p, "w").write("\n".join(sorted(out, key=lambda s: s[41:])))
