# Exports the swordswoman's own sword as a separate static mesh for holding in the hand:
# export_unreal/sw_sword_hand.fbx, in cm. SW_Sword on the character is only the hilt (06_tripo.py cuts
# the blade off inside the scabbard), so the full Tripo sword comes from tripo/E_sword_lo.blend, scaled
# by the same KW factor 06_tripo.py used (read from renders/fit_log.txt) so it matches the sheathed hilt.
# Canonical frame (Blender axes, written so the FBX lands the same in Unreal): grip centre at the
# origin, blade along +X towards the tip, blade width along Y, flat side facing Z.
# Also writes sw_sword_hand.json with the blade length and the hilt layout. Never saves the .blend.
import bpy, bmesh, json, os
import numpy as np
from mathutils import Matrix, Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "export_unreal")
import re
KW = float(re.search(r"sword f_guard \S+ KW (\S+)", open(os.path.join(ROOT, "renders", "fit_log.txt")).read()).group(1))
with bpy.data.libraries.load(os.path.join(ROOT, "tripo", "E_sword_lo.blend")) as (lib_src, lib_dst):
    lib_dst.objects = ["E_sword_00"]
src = lib_dst.objects[0]
bpy.context.scene.collection.objects.link(src)
src.matrix_world = Matrix()
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
me = bpy.data.meshes.new_from_object(src.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
me.transform(Matrix.Scale(KW, 4))
print("RESULT KW", KW)
P = np.array([v.co for v in me.vertices])
c = P.mean(0)
w, V = np.linalg.eigh(np.cov((P - c).T))
ax_long = V[:, 2]
# refine the axes on the blade alone (the tassel skews a whole-sword fit): middle 60 % of the length
t0 = (P - c) @ ax_long
blade = P[np.abs(t0) < 0.3 * np.ptp(t0)]
w, V = np.linalg.eigh(np.cov((blade - blade.mean(0)).T))
ax_long = V[:, 2] if V[:, 2] @ ax_long > 0 else -V[:, 2]
ax_wide, ax_thin = V[:, 1], V[:, 0]
t = (P - c) @ ax_long
wide = np.abs((P - c) @ ax_wide)
# width profile along the length: the crossguard is the widest slice, near the hilt end
bins = np.linspace(t.min(), t.max(), 61)
idx = np.clip(np.digitize(t, bins) - 1, 0, 59)
prof = np.array([wide[idx == i].max() if np.any(idx == i) else 0 for i in range(60)])
g = int(prof.argmax())
guard_t = (bins[g] + bins[g + 1]) / 2
# the hilt is the shorter side of the guard
if guard_t - t.min() < t.max() - guard_t:
    hilt_end, tip_end, sign = t.min(), t.max(), 1.0
else:
    hilt_end, tip_end, sign = t.max(), t.min(), -1.0
x_axis = Vector(ax_long * sign)
grip_t = guard_t + (hilt_end - guard_t) * 0.45  # middle of the handle, a little toward the guard
grip = Vector(c + ax_long * grip_t)
y_axis = Vector(ax_wide)
z_axis = x_axis.cross(y_axis).normalized()
y_axis = z_axis.cross(x_axis).normalized()
R = Matrix((x_axis, y_axis, z_axis))  # rows: world -> canonical
M = R.to_4x4() @ Matrix.Translation(-grip)
me.transform(M)
me.transform(Matrix.Diagonal((100, 100, 100, 1)))  # metres -> cm
Q = np.array([v.co for v in me.vertices])
info = dict(blade_tip_cm=float(Q[:, 0].max()), pommel_cm=float(Q[:, 0].min()), guard_cm=float((guard_t - grip_t) * sign * 100),
            width_cm=float(Q[:, 1].max() - Q[:, 1].min()), thick_cm=float(Q[:, 2].max() - Q[:, 2].min()),
            curve_cm=float(np.abs(Q[Q[:, 0] > 5, 1]).max()))
print("RESULT sword", {k: round(v, 2) for k, v in info.items()})

for o in list(bpy.context.scene.objects):
    o.hide_set(True)
    o.select_set(False)
ob = bpy.data.objects.new("SM_SwordswomanSword", me)
bpy.context.scene.collection.objects.link(ob)
ob.hide_set(False)
ob.select_set(True)
bpy.context.view_layer.objects.active = ob
sc = bpy.context.scene
sc.unit_settings.system = "METRIC"
sc.unit_settings.scale_length = 0.01
# Tripo material: point its images at the PNGs 12_export_ue.py already wrote
TEX = os.path.join(OUT, "textures")
for slot in ob.material_slots:
    m = slot.material
    for n in m.node_tree.nodes:
        if n.type == "TEX_IMAGE" and n.image:
            name = re.sub(r"[^A-Za-z0-9_]+", "_", os.path.splitext(n.image.name)[0]).strip("_") + ".png"
            p = os.path.join(TEX, name)
            if os.path.isfile(p):
                n.image = bpy.data.images.load(p, check_existing=True)
r = bpy.ops.export_scene.fbx(filepath=os.path.join(OUT, "sw_sword_hand.fbx"), use_selection=True, object_types={"MESH"},
                             mesh_smooth_type="FACE", use_tspace=True, axis_forward="-Y", axis_up="Z",
                             apply_scale_options="FBX_SCALE_NONE", apply_unit_scale=True, global_scale=1.0,
                             path_mode="COPY", embed_textures=True)
json.dump(info, open(os.path.join(OUT, "sw_sword_hand.json"), "w"), indent=1)
print("RESULT exported", r)
