import bpy, json
arm = bpy.data.objects["Armature"]
print("bones", len(arm.data.bones), "hairnew", len([b for b in arm.data.bones if "HairNew" in b.name]))
print("obj props", list(arm.keys())[:40])
print("data props", list(arm.data.keys())[:40])
print("texts", [(t.name, len(t.as_string())) for t in bpy.data.texts])
t = bpy.data.texts.get(arm.get("spring_bone", "")) if isinstance(arm.get("spring_bone"), str) else None
if t:
    print(t.as_string()[:900])
print("export", [n for n in dir(bpy.ops.export_scene)], [n for n in dir(bpy.ops.vrm)][:30])
for n in ("Hair_New", "Ears_Elf", "Flowers", "Hair_Band"):
    o = bpy.data.objects[n]
    print(n, o.parent.name if o.parent else None, len(o.vertex_groups), [m.type for m in o.modifiers])
