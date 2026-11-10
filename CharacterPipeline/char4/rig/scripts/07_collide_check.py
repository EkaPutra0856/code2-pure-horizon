"""Penetration check on rig_v3 (or the blend given after --): hair vs head/body, cloth parts vs body parts,
in rest and test poses. Vertex 'inside' = nearest surface point within 3 cm and behind its face normal by
more than TOL. Writes rig/collide_report.txt and red-marked x-ray renders in debug/collide/."""
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import bpy, os, sys, math, json
import numpy as np
from mathutils import Vector, Quaternion
from mathutils.bvhtree import BVHTree

R = os.path.join(ANIME_GAME_ROOT, r"char4\rig")
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
BLEND = argv[0] if argv else os.path.join(R, 'rig_v3.blend')
TAG = argv[1] if len(argv) > 1 else 'v3'
RENDER = '--norender' not in argv
TOL = 0.002
bpy.ops.wm.open_mainfile(filepath=BLEND)
arm = bpy.data.objects['Char4_Armature']; PB = arm.pose.bones
body = bpy.data.objects['Body']; hair = bpy.data.objects['Hair']; face = bpy.data.objects['Face']; neck = bpy.data.objects['Neck']
for md in hair.modifiers:
    if md.type == 'SOLIDIFY': md.show_viewport = False; md.show_render = False

def rot_world(pb, axis, deg):
    pb.rotation_mode = 'QUATERNION'
    M = arm.matrix_world.to_3x3() @ pb.bone.matrix_local.to_3x3()
    ax = (M.inverted() @ Vector(axis)).normalized()
    pb.rotation_quaternion = Quaternion(ax, math.radians(deg)) @ pb.rotation_quaternion

def reset():
    for pb in PB:
        pb.rotation_mode = 'QUATERNION'; pb.rotation_quaternion = (1, 0, 0, 0); pb.location = (0, 0, 0)

POSES = {
    'rest': [],
    'run': [('J_Bip_L_UpperLeg', (-1, 0, 0), 55), ('J_Bip_L_LowerLeg', (1, 0, 0), 80), ('J_Bip_R_UpperLeg', (1, 0, 0), 30),
            ('J_Bip_R_LowerLeg', (1, 0, 0), 60), ('J_Bip_C_Spine', (1, 0, 0), 12),
            ('J_Bip_L_UpperArm', (1, 0, 0), 40), ('J_Bip_L_LowerArm', (-1, 0, 0), 60),
            ('J_Bip_R_UpperArm', (-1, 0, 0), 45), ('J_Bip_R_LowerArm', (-1, 0, 0), 70)],
    'bow_draw': [('J_Bip_L_UpperArm', (0, -1, 0), 52), ('J_Bip_L_UpperArm', (0, 0, -1), 65),
                 ('J_Bip_R_UpperArm', (0, 1, 0), 55), ('J_Bip_R_UpperArm', (0, 0, 1), 55), ('J_Bip_R_LowerArm', (0, 0, 1), 125),
                 ('J_Bip_C_Spine', (0, 0, 1), 25), ('J_Bip_C_Neck', (0, 0, 1), -30)],
    'heal_cast': [('J_Bip_L_UpperArm', (1, 0, 0), -70), ('J_Bip_L_UpperArm', (0, -1, 0), 20),
                  ('J_Bip_R_UpperArm', (1, 0, 0), -70), ('J_Bip_R_UpperArm', (0, 1, 0), 20),
                  ('J_Bip_C_Chest', (1, 0, 0), -8), ('J_Bip_C_Head', (1, 0, 0), -10)],
    'jump': [('J_Bip_L_UpperLeg', (-1, 0, 0), 70), ('J_Bip_L_LowerLeg', (1, 0, 0), 110), ('J_Bip_R_UpperLeg', (-1, 0, 0), 30),
             ('J_Bip_R_LowerLeg', (1, 0, 0), 90), ('J_Bip_L_UpperArm', (0, -1, 0), 35), ('J_Bip_R_UpperArm', (0, 1, 0), 35)],
    'look_down_side': [('J_Bip_C_Neck', (1, 0, 0), 25), ('J_Bip_C_Head', (0, 0, 1), 45), ('J_Bip_C_Head', (0, 1, 0), 15)],
}
GROUPS = {'skirt': (0,), 'capelet': (1,), 'torso': (4,), 'boots': (5, 6), 'arm_L': (7,), 'arm_R': (11, 12, 13), 'thigh_L': (8,),
          'thigh_R': (9,), 'pendant': (14,)}
PAIRS = [('hair', 'head'), ('hair', 'torso'), ('hair', 'capelet'), ('hair', 'arm_L'), ('hair', 'arm_R'), ('hair', 'skirt'),
         ('capelet', 'torso'), ('capelet', 'arm_L'), ('capelet', 'arm_R'), ('capelet', 'head'), ('skirt', 'thigh_L'), ('skirt', 'thigh_R'),
         ('arm_L', 'torso'), ('arm_R', 'torso'), ('arm_L', 'skirt'), ('arm_R', 'skirt'), ('head', 'capelet'), ('thigh_L', 'thigh_R')]

def evaluated(o):
    dg = bpy.context.evaluated_depsgraph_get(); e = o.evaluated_get(dg); m = e.to_mesh()
    V = np.array([o.matrix_world @ v.co for v in m.vertices]); P = [list(p.vertices) for p in m.polygons]
    attr = None
    if 'part' in m.attributes:
        attr = np.zeros(len(m.polygons), np.int32); m.attributes['part'].data.foreach_get('value', attr)
    e.to_mesh_clear(); return V, P, attr

def sets():
    S = {}
    V, P, part = evaluated(body)
    for g, ks in GROUPS.items():
        polys = [p for p, k in zip(P, part) if k in ks]
        vi = sorted({i for p in polys for i in p})
        S[g] = dict(V=V, P=polys, vi=vi)
    hv, hp, _ = evaluated(hair); S['hair'] = dict(V=hv, P=hp, vi=list(range(len(hv))))
    fv, fp, _ = evaluated(face); nv, np_, _ = evaluated(neck)
    off = len(fv); S['head'] = dict(V=np.vstack([fv, nv]), P=fp + [[i + off for i in p] for p in np_], vi=list(range(len(fv) + len(nv))))
    return S

def inside(S, a, b):
    B = S[b]; bvh = BVHTree.FromPolygons([Vector(x) for x in B['V']], B['P'], all_triangles=False)
    A = S[a]; bad = []
    for i in A['vi']:
        p = Vector(A['V'][i]); hit = bvh.find_nearest(p, 0.03)
        if hit[0] is None: continue
        q, n, _, d = hit
        if n.dot(p - q) < -TOL: bad.append((i, d))
    return bad

report = []; marks = {}; base = {}
# Tripo parts interlock by design (capelet tucked into the torso, skirt under the belt): rest-pose overlaps are the
# baseline, every pose reports only vertices that are NEW inside compared with rest.
for pose, ops in POSES.items():
    reset()
    for b, ax, d in ops: rot_world(PB[b], ax, d)
    bpy.context.view_layer.update()
    S = sets()
    for a, b in PAIRS:
        bad = inside(S, a, b)
        if pose == 'rest':
            base[(a, b)] = {i for i, _ in bad}
            report.append(f'baseline {a} in {b}: {len(bad)}'); continue
        bad = [(i, d) for i, d in bad if i not in base[(a, b)]]
        if bad:
            dep = np.array([d for _, d in bad]); pts = S[a]['V'][[i for i, _ in bad]]
            line = f'{pose:15s} {a:8s} in {b:8s} n={len(bad):5d} depth max {dep.max()*1000:5.1f}mm p90 {np.percentile(dep,90)*1000:5.1f}mm  centre {np.round(pts.mean(0),3).tolist()}'
            report.append(line); print('HIT', line)
            marks.setdefault(pose, []).extend(pts[dep > 0.004].tolist())
open(os.path.join(R, f'collide_report_{TAG}.txt'), 'w').write('\n'.join(report))
json.dump({k: v[:4000] for k, v in marks.items()}, open(os.path.join(R, f'collide_marks_{TAG}.json'), 'w'))

if RENDER:
    sys.path.insert(0, os.path.join(ANIME_GAME_ROOT, r"char4\face_compare\scripts"))
    import common as C
    out = os.path.join(R, 'debug', 'collide'); os.makedirs(out, exist_ok=True)
    sc = bpy.context.scene; sc.render.engine = 'BLENDER_WORKBENCH'
    sh = sc.display.shading; sh.light = 'STUDIO'; sh.color_type = 'OBJECT'; sh.show_xray = True; sh.xray_alpha = 0.6
    for o in bpy.data.objects:
        if o.type == 'MESH': o.color = (0.85, 0.85, 0.88, 1)
    hair.color = (0.6, 0.7, 1.0, 1)
    cam = bpy.data.objects.new('cc', bpy.data.cameras.new('cc')); sc.collection.objects.link(cam); sc.camera = cam; cam.data.type = 'ORTHO'
    sc.render.resolution_x = 700; sc.render.resolution_y = 900
    me = bpy.data.meshes.new('marks'); mo = bpy.data.objects.new('marks', me); sc.collection.objects.link(mo); mo.color = (1, 0, 0, 1)
    for pose, ops in POSES.items():
        reset()
        for b, ax, d in ops: rot_world(PB[b], ax, d)
        bpy.context.view_layer.update()
        import bmesh
        bm = bmesh.new()
        for p in marks.get(pose, [])[:4000]:
            bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.004, matrix=__import__('mathutils').Matrix.Translation(p))
        bm.to_mesh(me); bm.free()
        for yaw, t in ((0, 'f'), (90, 's'), (180, 'b')):
            C.aim(cam, Vector((0, 0, 0.85)), 1.8, yaw)
            sc.render.filepath = os.path.join(out, f'{TAG}_{pose}_{t}.png'); bpy.ops.render.render(write_still=True)
print('DONE')
