import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import bpy
bpy.ops.wm.open_mainfile(filepath=os.path.join(ANIME_GAME_ROOT, r"char4\rig\rig_v3.blend"))
b = bpy.data.objects['Body']
for m in b.data.materials:
    for n in m.node_tree.nodes:
        if n.type == 'TEX_IMAGE': print('IMG', m.name, n.label, n.image.name, n.image.filepath, n.image.packed_file is not None, tuple(n.image.size), [l.to_socket.name for l in n.outputs[0].links])
print('UV', [u.name for u in b.data.uv_layers])
