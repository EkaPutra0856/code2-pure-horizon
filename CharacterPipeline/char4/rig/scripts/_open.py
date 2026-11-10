import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import bpy, bmesh, numpy as np
bpy.ops.wm.open_mainfile(filepath=os.path.join(ANIME_GAME_ROOT, r"char4\rig\rig_v3.blend"))
me = bpy.data.objects['Body'].data
part = np.zeros(len(me.polygons), np.int32); me.attributes['part'].data.foreach_get('value', part)
bm = bmesh.new(); bm.from_mesh(me)
bnd = [e for e in bm.edges if len(e.link_faces) == 1]
print('open edges', len(bnd))
seen = set(); loops = []
for e in bnd:
    if e.index in seen: continue
    st = [e]; comp = []
    while st:
        x = st.pop()
        if x.index in seen: continue
        seen.add(x.index); comp.append(x)
        for v in x.verts:
            for y in v.link_edges:
                if len(y.link_faces) == 1 and y.index not in seen: st.append(y)
    P = np.array([v.co[:] for x in comp for v in x.verts])
    pc = np.bincount([part[x.link_faces[0].index] for x in comp], minlength=15)
    loops.append((sum(x.calc_length() for x in comp), len(comp), P.mean(0), P.min(0), P.max(0), int(pc.argmax()), round(pc.max() / len(comp), 2)))
loops.sort(key=lambda t: -t[0])
for L, n, c, lo, hi, k, fr in loops[:25]:
    print('len %.3f e %3d part %2d (%.2f) c %s  z %.3f-%.3f' % (L, n, k, fr, np.round(c, 3), lo[2], hi[2]))
