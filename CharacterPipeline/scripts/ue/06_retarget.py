# Builds IK Rigs for the Mage set's mannequin and the character, a Retargeter between them,
# then retargets the Mage root-motion clips to /Game/Character/Mage. Safe to rerun.
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import os
import unreal

ROOT = ANIME_GAME_ROOT
LOG = os.path.join(ROOT, "scripts", "ue", "report_retarget.txt")
lines = []


def say(*a):
    lines.append(" ".join(str(x) for x in a))
    open(LOG, "w", encoding="utf-8").write("\n".join(lines))


tools = unreal.AssetToolsHelpers.get_asset_tools()
lib = unreal.EditorAssetLibrary
RIG = "/Game/Character/Retarget"
src_mesh = unreal.load_asset("/Game/MageAnimationSet/Characters/Mannequin/Mesh/SK_Mannequin")
tgt_mesh = unreal.load_asset("/Game/Character/karakter_ue")


FINGERS = [("Thumb", "thumb", "Thumb"), ("Index", "index", "Index"), ("Middle", "middle", "Middle"),
           ("Ring", "ring", "Ring"), ("Pinky", "pinky", "Little")]
SRC = [("Spine", "spine_01", "spine_03"), ("Neck", "neck_01", "neck_01"), ("Head", "head", "head")]
TGT = [("Spine", "J_Bip_C_Spine", "J_Bip_C_UpperChest"), ("Neck", "J_Bip_C_Neck", "J_Bip_C_Neck"), ("Head", "J_Bip_C_Head", "J_Bip_C_Head")]
for s, t, nm in (("l", "L", "Left"), ("r", "R", "Right")):
    SRC += [(nm + "Clavicle", f"clavicle_{s}", f"clavicle_{s}"), (nm + "Arm", f"upperarm_{s}", f"hand_{s}"), (nm + "Leg", f"thigh_{s}", f"ball_{s}")]
    TGT += [(nm + "Clavicle", f"J_Bip_{t}_Shoulder", f"J_Bip_{t}_Shoulder"), (nm + "Arm", f"J_Bip_{t}_UpperArm", f"J_Bip_{t}_Hand"),
            (nm + "Leg", f"J_Bip_{t}_UpperLeg", f"J_Bip_{t}_ToeBase")]
    for c, a, b in FINGERS:
        SRC.append((nm + c, f"{a}_01_{s}", f"{a}_03_{s}"))
        TGT.append((nm + c, f"J_Bip_{t}_{b}1", f"J_Bip_{t}_{b}3"))


def rig(name, mesh, pelvis, root, chains):
    path = f"{RIG}/{name}"
    r = unreal.load_asset(path) if lib.does_asset_exist(path) else tools.create_asset(name, RIG, unreal.IKRigDefinition, unreal.IKRigDefinitionFactory())
    c = unreal.IKRigController.get_controller(r)
    say(name, "mesh ok", c.set_skeletal_mesh(mesh))
    for ch in list(c.get_retarget_chains()):
        c.remove_retarget_chain(ch.chain_name if hasattr(ch, "chain_name") else ch)
    say(name, "root", c.set_retarget_root(pelvis))
    try:
        say(name, "motion bone", c.set_root_motion_bone(root))
    except Exception as e:
        say(name, "motion bone failed", e)
    for n, a, b in chains:
        c.add_retarget_chain(n, a, b, "")
    say(name, "chains", len(c.get_retarget_chains()))
    lib.save_loaded_asset(r)
    return r


src = rig("IK_Mage", src_mesh, "pelvis", "root", SRC)
tgt = rig("IK_Karakter", tgt_mesh, "J_Bip_C_Hips", "Root", TGT)

path = f"{RIG}/RTG_Mage_To_Karakter"
rtg = unreal.load_asset(path) if lib.does_asset_exist(path) else tools.create_asset("RTG_Mage_To_Karakter", RIG, unreal.IKRetargeter, unreal.IKRetargetFactory())
c = unreal.IKRetargeterController.get_controller(rtg)
S, T = unreal.RetargetSourceOrTarget.SOURCE, unreal.RetargetSourceOrTarget.TARGET
c.set_ik_rig(S, src)
c.set_ik_rig(T, tgt)
c.set_preview_mesh(S, src_mesh)
c.set_preview_mesh(T, tgt_mesh)
c.add_default_ops()
c.assign_ik_rig_to_all_ops(S, src)
c.assign_ik_rig_to_all_ops(T, tgt)
for i in range(c.get_num_retarget_ops()):
    c.run_op_initial_setup(i)
    say("op", i, c.get_op_name(i))
c.auto_map_chains(unreal.AutoMapChainType.EXACT, True)
c.auto_align_all_bones(T)
lib.save_loaded_asset(rtg)
say("retargeter ready")

reg = unreal.AssetRegistryHelpers.get_asset_registry()
clips = [a for a in reg.get_assets_by_path("/Game/MageAnimationSet/Animations/RootMotion", recursive=True) if a.asset_class_path.asset_name == "AnimSequence"]
say("clips", len(clips))
say("inputs doc", (getattr(unreal, "IKRetargetBatchOperationInputs", None).__doc__ or "")[:600].replace("\n", " | "))
out = unreal.IKRetargetBatchOperation.duplicate_and_retarget(clips, src_mesh, tgt_mesh, rtg, "_RM", "", "", "", "/Game/Character/Mage", False, False, True)
say("retargeted", len(out))
lib.save_directory("/Game/Character")
names = lib.list_assets("/Game/Character/Mage", recursive=True, include_folder=False)
say("on disk", len(names), names[:3])
if names:
    a = unreal.load_asset("/Game/Character/Mage/Mage_Fireball_R")
    if a:
        L = unreal.AnimationLibrary
        n = L.get_num_frames(a)
        say("fireball frames", n, "skeleton", a.get_editor_property("skeleton").get_name() if hasattr(a, "get_editor_property") else "")
        say("hips", L.get_bone_pose_for_frame(a, "J_Bip_C_Hips", n // 2, False).translation, "root end", L.get_bone_pose_for_frame(a, "Root", n - 1, False).translation)
say("DONE")
