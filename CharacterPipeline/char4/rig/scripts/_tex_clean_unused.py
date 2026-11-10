"""Tripo base-colour cleanup (system python, cv2). Regions hidden at rest (sleeve tops under the capelet, shirt
under the sleeves, capelet under the hair) got hair-blue / white smears in the Tripo bake; posed, they show
(owner screenshot 2026-11-10, bow_draw). Per part UV mask, smear texels are found by colour and inpainted from the
same part. Input: debug/uvparts.npz (written by 04), tex/<base>.png. Output: tex/basecolor_clean.png + debug mask."""
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import sys, os, numpy as np, cv2
R = os.path.join(ANIME_GAME_ROOT, r"char4\rig")
SRC = os.path.join(R, 'tex', 'anime_character_3d_model_basecolor_jpg.png')
OUT = os.path.join(R, 'tex', 'basecolor_clean.png')
d = np.load(os.path.join(R, 'debug', 'uvparts.npz'))
uv, fpart = d['uv'], d['part']                                  # (F,3,2) triangles, (F,)
img = cv2.imread(SRC, cv2.IMREAD_COLOR); H, W = img.shape[:2]
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV_FULL).astype(np.float32) / 255.0
h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
blue = (h > 0.52) & (h < 0.74) & (s > 0.12) & (v > 0.25)        # hair tone
white = (s < 0.10) & (v > 0.86)
RULES = {1: blue | white, 4: blue, 11: blue, 13: blue}           # capelet, torso, R sleeve, R cuff
bad = np.zeros((H, W), np.uint8); allm = np.zeros((H, W), np.uint8)
for k, rule in RULES.items():
    m = np.zeros((H, W), np.uint8)
    tris = np.round(np.stack([uv[fpart == k][..., 0] * W, (1 - uv[fpart == k][..., 1]) * H], -1)).astype(np.int32)
    cv2.fillPoly(m, list(tris), 1)
    m = cv2.erode(m, np.ones((3, 3), np.uint8))                  # stay off island edges
    # a smear is a blob, not single noisy texels
    b = (rule & (m > 0)).astype(np.uint8)
    b = cv2.morphologyEx(b, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    b = cv2.dilate(b, np.ones((5, 5), np.uint8)) & m
    print('part', k, 'island px', int(m.sum()), 'smear px', int(b.sum()))
    bad |= b; allm |= m
clean = cv2.inpaint(img, bad * 255, 6, cv2.INPAINT_TELEA)
cv2.imwrite(OUT, clean)
dbg = img.copy(); dbg[bad > 0] = (0, 0, 255)
cv2.imwrite(os.path.join(R, 'debug', 'tex_clean_mask.jpg'), cv2.resize(dbg, (2048, 2048)))
print('WROTE', OUT)
