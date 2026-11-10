# Runs in a separate background Blender. Reimports the FBX and reports what it really contains.
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import bpy

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=os.path.join(ANIME_GAME_ROOT, r"export_unreal\karakter_ue.fbx"))
arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
mesh = [o for o in bpy.data.objects if o.type == "MESH"]
a = arms[0]
print("RESULT armatures", len(arms), a.name, "scale", tuple(round(x, 3) for x in a.scale), "bones", len(a.data.bones))
print("RESULT roots", [b.name for b in a.data.bones if b.parent is None])
print("RESULT cloth", sum("J_Sec_Cloth" in b.name for b in a.data.bones), "hair", sum("HairNew" in b.name for b in a.data.bones))
print("RESULT meshes", len(mesh), "tris", sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in mesh))
zs = [(o.matrix_world @ v.co).z for o in mesh for v in o.data.vertices]
print("RESULT height", round(min(zs), 3), round(max(zs), 3))
face = next((o for o in mesh if o.name.startswith("Face")), None)
print("RESULT face morphs", len(face.data.shape_keys.key_blocks) if face and face.data.shape_keys else 0)
body = next(o for o in mesh if o.name.startswith("Body"))
print("RESULT body verts", len(body.data.vertices))
over = sum(1 for o in mesh for v in o.data.vertices if sum(1 for g in v.groups if g.weight > 0.001) > 4)
none = sum(1 for o in mesh for v in o.data.vertices if not v.groups)
print("RESULT verts over 4 weights", over, "unweighted", none)
print("RESULT materials", len(bpy.data.materials), "with texture",
      sum(1 for m in bpy.data.materials if m.use_nodes and any(n.type == "TEX_IMAGE" and n.image for n in m.node_tree.nodes)))
