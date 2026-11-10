# Builds the char4's hair and cloth physics, headless (-run=pythonscript). Same method as
# scripts/ue/21_physics.py for the main character: one AnimDynamics node per bone chain from
# export_unreal/ue_physics_setup.json in a post-process Animation Blueprint set on the mesh, so the
# physics runs after any animation, Montage or play_animation call. Rebuilt on every run.
# Traps kept from 21_physics.py: damping override above 1.0 turns bones into NaN, and VRoid bones point
# down local -Y, so the cone twist axis and angular target are Y.
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import json, os
import unreal

ROOT = os.path.join(ANIME_GAME_ROOT, r"char4")
LOG = os.path.join(ROOT, "renders", "_log_ue_physics.txt")
DIR, NAME = "/Game/Char4/Physics", "ABP_Char4_Physics"
lines = []


def say(*a):
    lines.append(" ".join(str(x) for x in a))
    open(LOG, "w", encoding="utf-8").write("\n".join(lines))


setup = json.load(open(os.path.join(ROOT, "export_unreal", "ue_physics_setup.json")))
colliders = {c["bone"]: c["radius_cm"] for c in setup["colliders"]}
# Cone limit per bone in degrees. Robe panels are long and hang over the legs, so keep them tighter
# than the short skirt. Sleeves only sway a little around the arm.
CONE = dict(hair_tails=16, hair_short=14, hair_bangs=8, ahoge=20, skirt=26, capelet=16, hood=12, pendant=30)
STIFF = dict(hair_tails=0.16, hair_short=0.25, hair_bangs=0.45, capelet=0.3, hood=0.4)
SPRING = 1500.0


def damping(d):
    return 0.7 + min(d, 0.5) * 0.5


LEGS = ["J_Bip_L_UpperLeg", "J_Bip_R_UpperLeg", "J_Bip_L_LowerLeg", "J_Bip_R_LowerLeg"]
BACK = ["J_Bip_C_UpperChest", "J_Bip_C_Chest", "J_Bip_C_Spine"]
ARMS = ["J_Bip_L_UpperArm", "J_Bip_R_UpperArm"]
AVOID = dict(hair_tails=BACK + ARMS, hair_short=[], hair_bangs=[], ahoge=[], skirt=LEGS, capelet=ARMS, hood=[], pendant=[])
SHRINK = 0.8

sk = unreal.load_asset("/Game/Char4/char4_ue")
skel = sk.get_editor_property("skeleton")
ss = unreal.get_editor_subsystem(unreal.SkeletalMeshEditorSubsystem)
BEL = unreal.BlueprintEditorLibrary


def chain_of(root):
    out, b = [root], root
    while True:
        ch = [str(c) for c in ss.get_bone_children(sk, b)]
        if not ch:
            return out
        b = ch[0]
        out.append(b)


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
input_name = next((a for a in available if a.replace(" ", "").lower().endswith("inputpose")), None)
say("input pose node", input_name)


def make(name, x, y=0):
    n = ed.create_node_from_name(name, unreal.Vector2D(x, y), [])
    if not n:
        raise RuntimeError("could not create " + name)
    return n


def pose_pin(node, out):
    pins = node.list_output_pins() if out else node.list_input_pins()
    pose = [p for p in pins if "pose" in str(p.get_pin_type_display_string()).lower()]
    if not pose:
        raise RuntimeError(f"no pose pin on {node.get_name()}")
    return pose[0]


def link(a, b):
    if not pose_pin(a, True).try_create_connection(pose_pin(b, False)):
        raise RuntimeError(f"could not link {a.get_name()} to {b.get_name()}")


def bone(name):
    r = unreal.BoneReference()
    r.set_editor_property("bone_name", name)
    return r


def sphere(b, radius):
    s = unreal.AnimPhysSphericalLimit()
    s.set_editor_property("driving_bone", bone(b))
    s.set_editor_property("limit_radius", radius * SHRINK)
    s.set_editor_property("limit_type", unreal.SphericalLimitType.OUTER)
    return s


x = 0
prev = make(input_name, x)
x += 300
cur = make("Animation|ConvertSpaces|LocalToComponent", x)
link(prev, cur)
prev = cur
count = 0
for gname, g in setup["groups"].items():
    for r in g["root_bones"]:
        chain = chain_of(r)
        x += 300
        node = make("Animation|Dynamics|AnimDynamics", x, 0)
        d = node.get_editor_property("node")
        d.set_editor_property("bound_bone", bone(chain[0]))
        if len(chain) > 1:
            d.set_editor_property("chain", True)
            d.set_editor_property("chain_end", bone(chain[-1]))
        d.set_editor_property("simulation_space", unreal.AnimPhysSimSpaceType.WORLD)
        d.set_editor_property("gravity_scale", g["gravity_scale"])
        d.set_editor_property("override_linear_damping", True)
        d.set_editor_property("linear_damping_override", damping(g["damping"]))
        d.set_editor_property("override_angular_damping", True)
        d.set_editor_property("angular_damping_override", damping(g["damping"]))
        d.set_editor_property("angular_spring", True)
        d.set_editor_property("angular_spring_constant", STIFF.get(gname, g["stiffness"]) * SPRING)
        body = unreal.AnimPhysBodyDefinition()
        rad = g["collision_radius_cm"]
        body.set_editor_property("box_extents", unreal.Vector(rad, rad, rad))
        body.set_editor_property("collision_type", unreal.AnimPhysCollisionType.CUSTOM_SPHERE)
        body.set_editor_property("sphere_collision_radius", rad)
        con = body.get_editor_property("constraint_setup")
        con.set_editor_property("angular_constraint_type", unreal.AnimPhysAngularConstraintType.CONE)
        con.set_editor_property("cone_angle", float(CONE[gname]))
        con.set_editor_property("twist_axis", unreal.AnimPhysTwistAxis.AXIS_Y)
        con.set_editor_property("angular_target", unreal.Vector(0, 1, 0))
        con.set_editor_property("angular_target_axis", unreal.AnimPhysTwistAxis.AXIS_Y)
        body.set_editor_property("constraint_setup", con)
        d.set_editor_property("physics_body_definitions", [body])
        limits = [sphere(b, colliders[b]) for b in AVOID[gname] if b in colliders]
        if limits:
            d.set_editor_property("spherical_limits", limits)
            d.set_editor_property("use_spherical_limits", True)
        node.set_editor_property("node", d)
        link(prev, node)
        prev = node
        count += 1
        say(gname, chain[0], "to", chain[-1], "bones", len(chain), "limits", len(limits))
x += 300
cur = make("Animation|ConvertSpaces|ComponentToLocal", x)
link(prev, cur)
link(cur, root_node)
root_node.set_node_pos(unreal.IntPoint(int(x + 300), 0))
BEL.compile_blueprint(bp)
errors = ed.list_nodes_with_errors()
say("nodes", count, "errors", [n.get_name() + ": " + str(n.get_editor_property("error_msg")) for n in errors][:5])
sk.set_editor_property("post_process_anim_blueprint", BEL.generated_class(bp))
unreal.EditorAssetLibrary.save_loaded_asset(bp, False)
unreal.EditorAssetLibrary.save_loaded_asset(sk, False)
say("post process set", sk.get_editor_property("post_process_anim_blueprint"))
say("DONE")
