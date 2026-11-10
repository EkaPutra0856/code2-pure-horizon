# Close-up review renders of sw_outfit_v4.blend (for checking fit, not for presentation).
# Usage: blender -b sw_outfit_v4.blend --python scripts/08_review.py [-- tag]
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import bpy, os, sys
sys.path.insert(0, os.path.join(os.path.join(ANIME_GAME_ROOT, r"swordswoman"), "scripts"))
import sw_render

tag = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "r"
S = sw_render.sheet
print("SHEET", S(f"rv_{tag}_full", res=560, views=("front", "q34l", "right", "back", "left")))
print("SHEET", S(f"rv_{tag}_sword", target=(0.24, 0.05, 0.92), scale=0.8, res=560,
                 views=("q34l", "right", "front", "back_l", "top")))
print("SHEET", S(f"rv_{tag}_waist", target=(0.0, -0.05, 0.98), scale=0.55, res=520,
                 views=("front", "q34", "q34l", "low_l")))
print("SHEET", S(f"rv_{tag}_shoulder", target=(0.0, 0.02, 1.30), scale=0.62, res=520,
                 views=("front", "q34l", "back", "top")))
print("SHEET", S(f"rv_{tag}_head", target=(0.0, 0.03, 1.52), scale=0.34, res=480,
                 views=("front", "q34", "right", "back")))
