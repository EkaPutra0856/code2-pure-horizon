import bpy, math
from mathutils import Matrix, Vector

ob = bpy.data.objects["Hair_New"]
if not ob.get("uv_inset"):
    for d in ob.data.uv_layers[0].data:
        d.uv[1] = 0.012 + 0.976 * d.uv[1]
    ob["uv_inset"] = 1

ears = bpy.data.objects["Ears_Elf"]
if not ears.get("turned"):
    for s in (1, -1):
        base = Vector((s * .120, .035, 1.440))
        tip = Vector((s * .212, .056, 1.500))
        rot = Matrix.Rotation(math.radians(48) * s, 4, (tip - base).normalized())
        for v in ears.data.vertices:
            if v.co.x * s > 0:
                v.co = base + (rot @ (v.co - base))
    ears["turned"] = 1
ears.data.update()
print("done")
