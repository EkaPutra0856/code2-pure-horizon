import bpy
m = bpy.data.materials["N00_000_00_HairBack_00_HAIR (Instance)"]
for l in m.node_tree.links:
    print("LINK", l.from_node.name, "->", l.to_node.name, l.to_socket.name)
print("CULL", m.use_backface_culling, m.alpha_threshold if hasattr(m, "alpha_threshold") else None)
ext = m.vrm_addon_extension.mtoon1
print("MTOON", ext.double_sided if hasattr(ext, "double_sided") else "?", [p for p in dir(ext) if not p.startswith("_")][:40])
