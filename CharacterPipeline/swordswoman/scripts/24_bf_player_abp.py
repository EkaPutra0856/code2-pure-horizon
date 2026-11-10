# BossFight player body: builds /Game/Swordswoman/ABP_Swordswoman_Player, a one-node Anim Blueprint for the
# swordswoman mesh that copies the (hidden) mannequin's pose every frame through the IK retargeter
# RTG_IAC_To_Swordswoman (Retarget Pose From Mesh, source = the attached parent mesh). The mannequin keeps
# running ABP_Player, montages, root motion and the gameplay; the swordswoman is only what is seen. Her
# hair/cloth post-process ABP (23_bf_cloth.py) runs after this on her mesh by itself.
# Headless: UnrealEditor-Cmd BossFight.uproject -run=pythonscript -script=<this file>. Log renders/_log_bf_player_abp.txt.
import os
import unreal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "renders", "_log_bf_player_abp.txt")
DIR, NAME = "/Game/Swordswoman", "ABP_Swordswoman_Player"
lines = []


def say(*a):
    lines.append(" ".join(str(x) for x in a))
    open(LOG, "w", encoding="utf-8").write("\n".join(lines))


sk = unreal.load_asset(DIR + "/sw_ue")
skel = sk.get_editor_property("skeleton")
rtg = unreal.load_asset(DIR + "/Retarget/RTG_IAC_To_Swordswoman")
say("mesh", sk, "retargeter", rtg)
path = f"{DIR}/{NAME}"
bp = unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else None
if not bp:
    f = unreal.AnimBlueprintFactory()
    f.set_editor_property("target_skeleton", skel)
    f.set_editor_property("preview_skeletal_mesh", sk)
    bp = unreal.AssetToolsHelpers.get_asset_tools().create_asset(NAME, DIR, unreal.AnimBlueprint, f)
ed = unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp, "AnimGraph")
old = [n for n in ed.list_all_nodes() if n.get_class().get_name() != "AnimGraphNode_Root"]
if old:
    ed.remove_nodes(old)
root_node = [n for n in ed.list_all_nodes() if n.get_class().get_name() == "AnimGraphNode_Root"][0]
available = ed.list_available_nodes([])
name = next(a for a in available if "retarget" in a.lower() and "mesh" in a.lower())
say("node", name)
node = ed.create_node_from_name(name, unreal.Vector2D(0, 0), [])
d = node.get_editor_property("node")
# UE 5.8: the source is picked by RetargetFrom (ERetargetSourceMode); use the parent mesh it is attached to
modes = [m for m in dir(unreal.RetargetSourceMode) if m.isupper()]
say("source modes", modes)
d.set_editor_property("retarget_from", getattr(unreal.RetargetSourceMode, next(m for m in modes if "PARENT" in m)))
d.set_editor_property("ik_retargeter_asset", rtg)
node.set_editor_property("node", d)
back = node.get_editor_property("node")
say("retarget_from", back.get_editor_property("retarget_from"), "rtg", back.get_editor_property("ik_retargeter_asset"))
out = [p for p in node.list_output_pins() if "pose" in str(p.get_pin_type_display_string()).lower()][0]
inp = [p for p in root_node.list_input_pins() if "pose" in str(p.get_pin_type_display_string()).lower()][0]
say("linked", out.try_create_connection(inp))
root_node.set_node_pos(unreal.IntPoint(400, 0))
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
say("errors", [n.get_name() + ": " + str(n.get_editor_property("error_msg")) for n in ed.list_nodes_with_errors()][:5])
unreal.EditorAssetLibrary.save_loaded_asset(bp, False)
say("DONE")
