import bpy
m = bpy.data.materials["Hair_New_MToon"]
n = m.node_tree.nodes
mp = n["Mapping"]
print("mapping", mp.vector_type, [list(i.default_value) for i in mp.inputs[1:]], "uvmap", repr(n["UV Map"].uv_map))
print("link uv->", [l.to_node.name for l in n["UV Map"].outputs[0].links], "map->", [l.to_node.name for l in mp.outputs[0].links])
t = n["Image Texture"]
print("tex", t.image.name, t.extension, t.interpolation, t.image.colorspace_settings.name, t.image.size[:])
ob = bpy.data.objects["Hair_New"]
print("uv layers", [(u.name, u.active, u.active_render) for u in ob.data.uv_layers])
uv = ob.data.uv_layers[0].data
vs = [d.uv[1] for d in uv]
print("v range", min(vs), max(vs))
img = t.image
W, H = img.size
px = img.pixels[:]
for y in (0, 64, 128, 192, 255):
    i = (y * W + 32) * 4
    print("row", y, [round(px[i + k], 3) for k in range(3)])
