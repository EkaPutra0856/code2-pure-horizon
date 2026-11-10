# BossFight project: retargets the player's sword combos (InsaneAirCombo, UE4 mannequin) onto the
# swordswoman and prepares what 20_bf_record.py needs. Run with UnrealEditor-Cmd -run=pythonscript on
# BossFight.uproject after 13_import_ue / 15_ue_physics / 17_ue_face_mats. Safe to rerun.
#  - imports export_unreal/sw_sword_hand.fbx (18_export_sword.py) as /Game/Swordswoman/SM_SwordswomanSword
#  - M_SW_Hidden: masked-out material that hides the sheathed hilt while the sword is in the hand
#  - IK_IACMannequin, IK_Swordswoman, RTG_IAC_To_Swordswoman; retargeted clips in /Game/Swordswoman/Combat
#  - the hand-sword offset on J_Bip_R_Hand, solved so her sword follows the player's sword frame
#  - ABP_Swordswoman_Show: idle + DefaultSlot, so montages blend like the player's
# Writes export_unreal/bf_combo_setup.json and renders/_log_bf_setup.txt.
import json, math, os
import unreal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXP = os.path.join(ROOT, "export_unreal")
LOG = os.path.join(ROOT, "renders", "_log_bf_setup.txt")
D = "/Game/Swordswoman"
COMBAT = D + "/Combat"
RIG = D + "/Retarget"
IAC = "/Game/InsaneAirCombo/Animation/"
lines = []


def say(*a):
    lines.append(" ".join(str(x) for x in a))
    open(LOG, "w", encoding="utf-8").write("\n".join(lines))


unreal.SystemLibrary.execute_console_command(None, "Interchange.FeatureFlags.Import.FBX 0")
tools = unreal.AssetToolsHelpers.get_asset_tools()
lib = unreal.EditorAssetLibrary
mel = unreal.MaterialEditingLibrary

# ---- hand sword static mesh
o = unreal.FbxImportUI()
o.set_editor_property("import_mesh", True)
o.set_editor_property("import_as_skeletal", False)
o.set_editor_property("import_materials", True)
o.set_editor_property("import_textures", True)
o.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_STATIC_MESH)
smd = o.get_editor_property("static_mesh_import_data")
smd.set_editor_property("convert_scene", True)
smd.set_editor_property("convert_scene_unit", False)
smd.set_editor_property("combine_meshes", True)
t = unreal.AssetImportTask()
t.set_editor_property("filename", os.path.join(EXP, "sw_sword_hand.fbx"))
t.set_editor_property("destination_path", D)
t.set_editor_property("destination_name", "SM_SwordswomanSword")
t.set_editor_property("automated", True)
t.set_editor_property("save", True)
t.set_editor_property("replace_existing", True)
t.set_editor_property("options", o)
tools.import_asset_tasks([t])
sword = unreal.load_asset(D + "/SM_SwordswomanSword")
b = sword.get_bounding_box()
say("hand sword bounds", b.min, b.max)

# ---- hidden material
hp = D + "/M_SW_Hidden"
hid = unreal.load_asset(hp) if lib.does_asset_exist(hp) else tools.create_asset("M_SW_Hidden", D, unreal.Material, unreal.MaterialFactoryNew())
hid.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
hid.set_editor_property("used_with_skeletal_mesh", True)
if mel.get_material_property_input_node(hid, unreal.MaterialProperty.MP_OPACITY_MASK) is None:
    c0 = mel.create_material_expression(hid, unreal.MaterialExpressionConstant, -300, 200)
    mel.connect_material_property(c0, "", unreal.MaterialProperty.MP_OPACITY_MASK)
mel.recompile_material(hid)
lib.save_loaded_asset(hid, False)

# ---- IK rigs and retargeter (same chain layout as scripts/ue/06_retarget.py)
src_mesh = unreal.load_asset(IAC + "Skeleton/SK_Mannequin")
tgt_mesh = unreal.load_asset(D + "/sw_ue")
FINGERS = [("Thumb", "thumb", "Thumb"), ("Index", "index", "Index"), ("Middle", "middle", "Middle"),
           ("Ring", "ring", "Ring"), ("Pinky", "pinky", "Little")]
SRC = [("Spine", "spine_01", "spine_03"), ("Neck", "neck_01", "neck_01"), ("Head", "head", "head")]
TGT = [("Spine", "J_Bip_C_Spine", "J_Bip_C_UpperChest"), ("Neck", "J_Bip_C_Neck", "J_Bip_C_Neck"), ("Head", "J_Bip_C_Head", "J_Bip_C_Head")]
for s, tt, nm in (("l", "L", "Left"), ("r", "R", "Right")):
    SRC += [(nm + "Clavicle", f"clavicle_{s}", f"clavicle_{s}"), (nm + "Arm", f"upperarm_{s}", f"hand_{s}"), (nm + "Leg", f"thigh_{s}", f"ball_{s}")]
    TGT += [(nm + "Clavicle", f"J_Bip_{tt}_Shoulder", f"J_Bip_{tt}_Shoulder"), (nm + "Arm", f"J_Bip_{tt}_UpperArm", f"J_Bip_{tt}_Hand"),
            (nm + "Leg", f"J_Bip_{tt}_UpperLeg", f"J_Bip_{tt}_ToeBase")]
    for c, a, bb in FINGERS:
        SRC.append((nm + c, f"{a}_01_{s}", f"{a}_03_{s}"))
        TGT.append((nm + c, f"J_Bip_{tt}_{bb}1", f"J_Bip_{tt}_{bb}3"))


def rig(name, mesh, pelvis, root, chains):
    path = f"{RIG}/{name}"
    r = unreal.load_asset(path) if lib.does_asset_exist(path) else tools.create_asset(name, RIG, unreal.IKRigDefinition, unreal.IKRigDefinitionFactory())
    c = unreal.IKRigController.get_controller(r)
    c.set_skeletal_mesh(mesh)
    for ch in list(c.get_retarget_chains()):
        c.remove_retarget_chain(ch.chain_name if hasattr(ch, "chain_name") else ch)
    c.set_retarget_root(pelvis)
    try:
        c.set_root_motion_bone(root)
    except Exception as e:
        say(name, "motion bone failed", e)
    for n, a, bb in chains:
        c.add_retarget_chain(n, a, bb, "")
    say(name, "chains", len(c.get_retarget_chains()))
    lib.save_loaded_asset(r)
    return r


src = rig("IK_IACMannequin", src_mesh, "pelvis", "root", SRC)
tgt = rig("IK_Swordswoman", tgt_mesh, "J_Bip_C_Hips", "Root", TGT)
path = f"{RIG}/RTG_IAC_To_Swordswoman"
rtg = unreal.load_asset(path) if lib.does_asset_exist(path) else tools.create_asset("RTG_IAC_To_Swordswoman", RIG, unreal.IKRetargeter, unreal.IKRetargetFactory())
c = unreal.IKRetargeterController.get_controller(rtg)
S, T = unreal.RetargetSourceOrTarget.SOURCE, unreal.RetargetSourceOrTarget.TARGET
c.set_ik_rig(S, src)
c.set_ik_rig(T, tgt)
c.set_preview_mesh(S, src_mesh)
c.set_preview_mesh(T, tgt_mesh)
if c.get_num_retarget_ops() == 0:
    c.add_default_ops()
c.assign_ik_rig_to_all_ops(S, src)
c.assign_ik_rig_to_all_ops(T, tgt)
for i in range(c.get_num_retarget_ops()):
    c.run_op_initial_setup(i)
c.auto_map_chains(unreal.AutoMapChainType.EXACT, True)
c.auto_align_all_bones(T)
lib.save_loaded_asset(rtg)
say("retargeter ops", [c.get_op_name(i) for i in range(c.get_num_retarget_ops())])

CLIPS = ["Idle", "jump", "jump_loop", "jump_landing", "combo01_1", "combo01_2", "combo01_3", "combo02_1", "combo02_2", "combo02_3",
         "Air_Combo01_Z0_1", "Air_Combo01_Z0_2", "Air_Attack04_Z0", "Air_Down_Attack_Z0"]
if lib.does_directory_exist(COMBAT):
    lib.delete_directory(COMBAT)
reg = unreal.AssetRegistryHelpers.get_asset_registry()
datas = [reg.get_asset_by_object_path(IAC + n + "." + n) for n in CLIPS]
datas = [d for d in datas if d.is_valid()]
out = unreal.IKRetargetBatchOperation.duplicate_and_retarget(datas, src_mesh, tgt_mesh, rtg, "", "", "SW_", "", COMBAT, False, False, True)
lib.save_directory(D)
say("retargeted", len(out), "of", len(CLIPS))
L = unreal.AnimationLibrary
for n in CLIPS:
    a = unreal.load_asset(f"{COMBAT}/SW_{n}")
    if not a:
        say("MISSING", n)
        continue
    src_a = unreal.load_asset(IAC + n)
    # Every attack keeps its root motion (the air ones too: here the lunge carries her through the air).
    rm = n.startswith(("combo", "Air_")) and n != "Air_Down_Attack_Z0"
    a.set_editor_property("enable_root_motion", rm)
    lib.save_loaded_asset(a, False)
    nf = L.get_num_frames(a)
    say(n, "len", round(L.get_sequence_length(a), 2), "root motion", rm, "root end",
        L.get_bone_pose_for_frame(a, "Root", nf - 1, False).translation, "src root end", L.get_bone_pose_for_frame(src_a, "root", nf - 1, False).translation)

# ---- hand sword offset. The player's sword sits on hand_r at the pack's offset; its blade runs along
# its local -Z, guard along X, flat along Y, grip at the origin. Ours: blade +X, guard Y, flat Z.
P = unreal.AnimPoseExtensions
opts = unreal.AnimPoseEvaluationOptions()


def qmat(q):
    x, y, z, w = q.x, q.y, q.z, q.w
    return [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]


def mm(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def tr(a):
    return [[a[j][i] for j in range(3)] for i in range(3)]


def mv(a, v):
    return [sum(a[i][k] * v[k] for k in range(3)) for i in range(3)]


O_S_LOC = [0.715, 8.327, 0.512]
O_S_ROT = qmat(unreal.Rotator(pitch=-20.079, yaw=-92.961, roll=-170.420).quaternion())
# columns = where our sword's X, Y, Z axes go in the player sword's frame
M = tr([[0, 0, -1], [1, 0, 0], [0, -1, 0]])
samples = []
for n in ("combo01_1", "combo02_3", "Air_Combo01_Z0_2"):
    sa, ta = unreal.load_asset(IAC + n), unreal.load_asset(f"{COMBAT}/SW_{n}")
    length = L.get_sequence_length(sa)
    for k in range(5):
        tm = length * (0.1 + 0.2 * k)
        ps = P.get_anim_pose_at_time(sa, tm, opts) if hasattr(P, "get_anim_pose_at_time") else unreal.AnimPoseExtensions.get_anim_pose_at_time(sa, tm, opts)
        pt = P.get_anim_pose_at_time(ta, tm, opts)
        sh = P.get_bone_pose(ps, "hand_r", unreal.AnimPoseSpaces.WORLD)
        th = P.get_bone_pose(pt, "J_Bip_R_Hand", unreal.AnimPoseSpaces.WORLD)
        Rs, Rt = qmat(sh.rotation), qmat(th.rotation)
        Rw = mm(mm(Rs, O_S_ROT), M)       # our sword's world axes at this frame
        Ro = mm(tr(Rt), Rw)               # relative to her hand
        d = mv(Rs, O_S_LOC)               # hand -> grip in world, player's proportions
        lo = mv(tr(Rt), d)
        samples.append((Ro, lo, n, round(tm, 2)))
# average rotation (sum of matrices, re-orthonormalised) and spread
acc = [[sum(s[0][i][j] for s in samples) for j in range(3)] for i in range(3)]
x = [acc[i][0] for i in range(3)]
z = [acc[i][2] for i in range(3)]
rot = unreal.MathLibrary.make_rot_from_xz(unreal.Vector(*x), unreal.Vector(*z))
Rm = qmat(rot.quaternion())
spread = []
for Ro, lo, n, tm in samples:
    tr_ = sum(Rm[i][j] * Ro[i][j] for i in range(3) for j in range(3))
    spread.append(round(math.degrees(math.acos(max(-1, min(1, (tr_ - 1) / 2)))), 1))
loc = [sum(s[1][i] for s in samples) / len(samples) * 0.9 for i in range(3)]  # her hand is ~10 % smaller
say("sword offset rot", rot, "loc", [round(v, 2) for v in loc], "spread deg per sample", spread)

# ---- show AnimBP: idle -> DefaultSlot -> output
BEL = unreal.BlueprintEditorLibrary
ap = D + "/ABP_Swordswoman_Show"
if lib.does_asset_exist(ap):
    lib.delete_asset(ap)
f = unreal.AnimBlueprintFactory()
f.set_editor_property("target_skeleton", tgt_mesh.get_editor_property("skeleton"))
f.set_editor_property("preview_skeletal_mesh", tgt_mesh)
bp = tools.create_asset("ABP_Swordswoman_Show", D, unreal.AnimBlueprint, f)
ed = unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp, "AnimGraph")
avail = ed.list_available_nodes([])
slot_name = next((a for a in avail if "slot" in a.lower() and "defaultslot" in a.replace(" ", "").lower()), None) or \
    next((a for a in avail if a.lower().endswith("|slot") or "slot '" in a.lower()), None)
idle_name = next((a for a in avail if "sw_idle" in a.lower() and "play" in a.lower()), None)
say("slot node", slot_name, "idle node", idle_name, "candidates", [a for a in avail if "slot" in a.lower()][:8], [a for a in avail if "sw_idle" in a.lower()][:4])
root_node = [n for n in ed.list_all_nodes() if n.get_class().get_name() == "AnimGraphNode_Root"][0]


def pose_pin(node, out):
    pins = node.list_output_pins() if out else node.list_input_pins()
    return [p for p in pins if "pose" in str(p.get_pin_type_display_string()).lower()][0]


idle = ed.create_node_from_name(idle_name, unreal.Vector2D(-600, 0), [])
slot = ed.create_node_from_name(slot_name, unreal.Vector2D(-300, 0), [])
ok1 = pose_pin(idle, True).try_create_connection(pose_pin(slot, False))
ok2 = pose_pin(slot, True).try_create_connection(pose_pin(root_node, False))
BEL.compile_blueprint(bp)
lib.save_loaded_asset(bp, False)
say("show abp links", ok1, ok2, "errors", [n.get_name() for n in ed.list_nodes_with_errors()])

json.dump(dict(sword_rot=[rot.roll, rot.pitch, rot.yaw], sword_loc=loc, hidden_slot="M_tripo_material_17020555_5f92_4d00_87ea_e8edf533dc45",
               spread=spread), open(os.path.join(EXP, "bf_combo_setup.json"), "w"), indent=1)
say("DONE")
