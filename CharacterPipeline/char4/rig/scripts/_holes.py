import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import bpy, bmesh, numpy as np
bpy.ops.wm.open_mainfile(filepath=os.path.join(ANIME_GAME_ROOT, r"char4\rig\rig_v3.blend"))
me = bpy.data.objects['Body'].data
part = np.zeros(len(me.polygons), np.int32); me.attributes['part'].data.foreach_get('value', part)
bm = bmesh.new(); bm.from_mesh(me); bm.edges.ensure_lookup_table()
for K in (11, 1, 4):
    fs = {f.index for f in bm.faces if part[f.index] == K}
    bnd = [e for e in bm.edges if sum(1 for f in e.link_faces if f.index in fs) == 1]
    # loops via connectivity
    adj = {}
    for e in bnd:
        a, b = e.verts; adj.setdefault(a.index, []).append((b.index, e)); adj.setdefault(b.index, []).append((a.index, e))
    seen = set(); loops = []
    for e in bnd:
        if e.index in seen: continue
        st = [e]; comp = []
        while st:
            x = st.pop()
            if x.index in seen: continue
            seen.add(x.index); comp.append(x)
            for v in x.verts:
                for _, y in adj[v.index]:
                    if y.index not in seen: st.append(y)
        L = sum(x.calc_length() for x in comp); c = np.mean([np.array(v.co[:]) for x in comp for v in x.verts], 0)
        loops.append((L, len(comp), c))
    loops.sort(key=lambda t: -t[0])
    print('PART', K, 'boundary loops', len(loops))
    for L, n, c in loops[:12]: print('   len %.3f edges %d centre %s' % (L, n, np.round(c, 3)))
