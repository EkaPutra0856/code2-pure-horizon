import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import sys
sys.path.insert(0, os.path.join(ANIME_GAME_ROOT, r"swordswoman\scripts"))
import sw_render
print("SHEET", sw_render.sheet("base_body"))
print("SHEET", sw_render.sheet("base_head", target=(0, 0.02, 1.35), scale=0.6, res=500))
