import bpy
m = bpy.data.materials["N00_000_00_HairBack_00_HAIR (Instance)"]
print("blend", m.blend_method, "keys", list(m.keys())[:20])
for n in m.node_tree.nodes:
    print(n.type, n.name, getattr(n, "label", ""), (n.node_tree.name if n.type == "GROUP" else ""),
          (n.image.name if n.type == "TEX_IMAGE" and n.image else ""))
g = next(n for n in m.node_tree.nodes if n.type == "GROUP")
for i in g.inputs:
    linked = i.links[0].from_node.name if i.is_linked else None
    val = None
    if not i.is_linked and hasattr(i, "default_value"):
        try:
            val = list(i.default_value)
        except TypeError:
            val = i.default_value
    print(" in:", i.name, "->", linked, val)
