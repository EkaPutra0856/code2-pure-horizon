# Poster characters (Nova = /Game/CharCustom/Tes/Proj1Rev from the Decyra project, Char2 = /Game/Model/model1/ACCchar/
# autorigCharTpose from TestModelFF; both copied in as UE 5.4 assets). Both rigs use UE4-mannequin bone names, so the
# poster rig is the same as the player's: a hidden IAC mannequin plays any IAC/Lucy/Mage clip and the visible mesh copies
# it through an IK retargeter (Retarget Pose From Mesh, source = parent mesh).
# Builds /Game/BossFight/Poster: IK_Nova, IK_Char2, RTG_IAC_To_Nova, RTG_IAC_To_Char2, ABP_Nova_Poster, ABP_Char2_Poster.
# Headless: UnrealEditor-Cmd BossFight.uproject -run=pythonscript -script=<this file>. Log Saved/poster_chars.txt.
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import unreal

LOG = os.path.join(ANIME_GAME_ROOT, r"BossFight/Saved/poster_chars.txt")
D = "/Game/BossFight/Poster"
SRC_RIG = "/Game/Swordswoman/Retarget/IK_IACMannequin"
SRC_MESH = "/Game/InsaneAirCombo/Animation/Skeleton/SK_Mannequin"
CHARS = {
    "Nova": "/Game/CharCustom/Tes/Proj1Rev",
    "Char2": "/Game/Model/model1/ACCchar/autorigCharTpose",
}
lines = []


def say(*a):
    lines.append(" ".join(str(x) for x in a))
    open(LOG, "w", encoding="utf-8").write("\n".join(lines))


lib = unreal.EditorAssetLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()
if not lib.does_directory_exist(D):
    lib.make_directory(D)
src_rig = unreal.load_asset(SRC_RIG)
src_mesh = unreal.load_asset(SRC_MESH)
say("source", src_rig, src_mesh)
# Same chain layout as IK_IACMannequin (swordswoman/scripts/19_bf_combo_setup.py).
src_chains = [("Spine", "spine_01", "spine_03"), ("Neck", "neck_01", "neck_01"), ("Head", "head", "head")]
for s, nm in (("l", "Left"), ("r", "Right")):
    src_chains += [(nm + "Clavicle", f"clavicle_{s}", f"clavicle_{s}"), (nm + "Arm", f"upperarm_{s}", f"hand_{s}"), (nm + "Leg", f"thigh_{s}", f"ball_{s}")]
    for c in ("Thumb", "Index", "Middle", "Ring", "Pinky"):
        src_chains.append((nm + c, f"{c.lower()}_01_{s}", f"{c.lower()}_03_{s}"))
say("source chains", src_chains)

P = unreal.AnimPoseExtensions


def bone_names(sk):
    comp = unreal.SkeletalMeshComponent()
    comp.set_skinned_asset_and_update(sk)
    return [str(comp.get_bone_name(i)) for i in range(comp.get_num_bones())]


def mat_report(sk):
    for i, sm in enumerate(sk.materials):
        mi = sm.material_interface
        par = mi.get_editor_property("parent") if isinstance(mi, unreal.MaterialInstance) else None
        base = mi.get_base_material() if mi else None
        tex = []
        if isinstance(mi, unreal.MaterialInstance):
            for tp in mi.get_editor_property("texture_parameter_values"):
                tex.append("%s=%s" % (tp.parameter_info.name, tp.parameter_value.get_name() if tp.parameter_value else None))
        say("  mat%d %s parent=%s base=%s tex=%s" % (i, sm.material_slot_name, par.get_path_name() if par else None,
                                                    base.get_path_name() if base else None, ",".join(tex)[:300]))


def make_rig(name, sk, names):
    path = f"{D}/IK_{name}"
    r = unreal.load_asset(path) if lib.does_asset_exist(path) else tools.create_asset("IK_" + name, D, unreal.IKRigDefinition, unreal.IKRigDefinitionFactory())
    c = unreal.IKRigController.get_controller(r)
    c.set_skeletal_mesh(sk)
    for ch in list(c.get_retarget_chains()):
        c.remove_retarget_chain(ch.chain_name)
    c.set_retarget_root("pelvis")
    try:
        c.set_root_motion_bone("root")
    except Exception as e:
        say(name, "motion bone failed", e)
    ok = 0
    for n, a, b in src_chains:
        if a in names and b in names:
            c.add_retarget_chain(n, a, b, "")
            ok += 1
        else:
            say(name, "chain skipped", n, a, b)
    say(name, "chains", ok, "of", len(src_chains))
    lib.save_loaded_asset(r)
    return r


def make_rtg(name, tgt_rig, sk):
    path = f"{D}/RTG_IAC_To_{name}"
    rtg = unreal.load_asset(path) if lib.does_asset_exist(path) else tools.create_asset("RTG_IAC_To_" + name, D, unreal.IKRetargeter, unreal.IKRetargetFactory())
    c = unreal.IKRetargeterController.get_controller(rtg)
    S, T = unreal.RetargetSourceOrTarget.SOURCE, unreal.RetargetSourceOrTarget.TARGET
    c.set_ik_rig(S, src_rig)
    c.set_ik_rig(T, tgt_rig)
    c.set_preview_mesh(S, src_mesh)
    c.set_preview_mesh(T, sk)
    if c.get_num_retarget_ops() == 0:
        c.add_default_ops()
    c.assign_ik_rig_to_all_ops(S, src_rig)
    c.assign_ik_rig_to_all_ops(T, tgt_rig)
    for i in range(c.get_num_retarget_ops()):
        c.run_op_initial_setup(i)
    c.auto_map_chains(unreal.AutoMapChainType.EXACT, True)
    c.auto_align_all_bones(T)
    lib.save_loaded_asset(rtg)
    say(name, "rtg ops", [c.get_op_name(i) for i in range(c.get_num_retarget_ops())])
    return rtg


def make_abp(name, sk, rtg):
    path = f"{D}/ABP_{name}_Poster"
    bp = unreal.load_asset(path) if lib.does_asset_exist(path) else None
    if not bp:
        f = unreal.AnimBlueprintFactory()
        f.set_editor_property("target_skeleton", sk.get_editor_property("skeleton"))
        f.set_editor_property("preview_skeletal_mesh", sk)
        bp = tools.create_asset(f"ABP_{name}_Poster", D, unreal.AnimBlueprint, f)
    ed = unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp, "AnimGraph")
    old = [n for n in ed.list_all_nodes() if n.get_class().get_name() != "AnimGraphNode_Root"]
    if old:
        ed.remove_nodes(old)
    root_node = [n for n in ed.list_all_nodes() if n.get_class().get_name() == "AnimGraphNode_Root"][0]
    nn = next(a for a in ed.list_available_nodes([]) if "retarget" in a.lower() and "mesh" in a.lower())
    node = ed.create_node_from_name(nn, unreal.Vector2D(0, 0), [])
    d = node.get_editor_property("node")
    modes = [m for m in dir(unreal.RetargetSourceMode) if m.isupper()]
    d.set_editor_property("retarget_from", getattr(unreal.RetargetSourceMode, next(m for m in modes if "PARENT" in m)))
    d.set_editor_property("ik_retargeter_asset", rtg)
    node.set_editor_property("node", d)
    out = [p for p in node.list_output_pins() if "pose" in str(p.get_pin_type_display_string()).lower()][0]
    inp = [p for p in root_node.list_input_pins() if "pose" in str(p.get_pin_type_display_string()).lower()][0]
    linked = out.try_create_connection(inp)
    root_node.set_node_pos(unreal.IntPoint(400, 0))
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    say(name, "abp linked", linked, "errors", [n.get_name() for n in ed.list_nodes_with_errors()][:5])
    lib.save_loaded_asset(bp, False)


for name, mp in CHARS.items():
    sk = unreal.load_asset(mp)
    names = bone_names(sk)
    say("==", name, mp, "bones", len(names))
    say("  all bones:", " ".join(names))
    ref = P.get_reference_pose(sk.get_editor_property("skeleton")) if hasattr(P, "get_reference_pose") else None
    if ref:
        for b in ("root", "pelvis", "head", "hand_l", "foot_l", "Ctrl_Master"):
            if b in names:
                say("  ref", b, P.get_bone_pose(ref, b, unreal.AnimPoseSpaces.WORLD).translation)
    mat_report(sk)
    rig = make_rig(name, sk, names)
    rtg = make_rtg(name, rig, sk)
    make_abp(name, sk, rtg)
say("DONE")
