import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import bpy, numpy as np
from mathutils.kdtree import KDTree
bpy.ops.wm.open_mainfile(filepath=os.path.join(ANIME_GAME_ROOT, r"char4\rig\rig_v3.blend"))
me = bpy.data.objects['Body'].data; N = len(me.vertices)
V = np.array([v.co[:] for v in me.vertices])
kd = KDTree(N)
for i, v in enumerate(V): kd.insert(v, i)
kd.balance()
gn = len(bpy.data.objects['Body'].vertex_groups)
W = np.zeros((N, gn), np.float32)
for v in me.vertices:
    for g in v.groups: W[v.index, g.group] = g.weight
pairs = 0; bad = []; 
for i in range(N):
    for co, j, d in kd.find_range(V[i], 1e-5):
        if j > i:
            pairs += 1; diff = np.abs(W[i] - W[j]).sum()
            if diff > 0.05: bad.append((diff, i, j))
bad.sort(reverse=True)
print('VERTS', N, 'coincident pairs', pairs, 'differing >0.05', len(bad), '>0.3', sum(1 for b in bad if b[0] > 0.3))
for d, i, j in bad[:8]: print('  diff %.2f at %s' % (d, np.round(V[i], 3)))
