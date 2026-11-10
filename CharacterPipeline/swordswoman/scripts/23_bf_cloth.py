# Rebuilds the swordswoman's hair and cloth physics in BossFight (replaces 15_ue_physics.py's AnimDynamics
# setup, which swung the strands wildly and let them pass through the body: each strand was its own rigid
# body chain, legs were only spheres at the joints, and the hair had no collision at all).
# Now: one FAnimNode_BFClothSway per group (verlet particle chains, pulled back toward the animated shape,
# so the cloth keeps following the body) with capsule colliders measured from the body and the fixed outfit
# layers by 22_measure_colliders.py (export_unreal/sw_colliders.json). bRestRadius keeps each particle's
# rest gap to a capsule, so a skirt hanging against the thigh is pushed by a raised knee instead of
# ignoring it; bSegmentCollision also pushes segment midpoints off thin limbs.
# Headless: UnrealEditor-Cmd BossFight.uproject -run=pythonscript -script=<this file>. Log renders/_log_bf_cloth.txt.
import json, os
import unreal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "renders", "_log_bf_cloth.txt")
DIR, NAME = "/Game/Swordswoman/Physics", "ABP_Swordswoman_Physics"
lines = []


def say(*a):
    lines.append(" ".join(str(x) for x in a))
    open(LOG, "w", encoding="utf-8").write("\n".join(lines))


data = json.load(open(os.path.join(ROOT, "export_unreal", "sw_colliders.json")))
COL = {c["name"]: c for c in data["colliders"]}
CHAINS = data["chains"]

# Per group: colliders and solver settings (per-1/60 s factors, see BFClothSwayNode.h).
LEGS = ["pelvis", "thigh_l", "thigh_r", "calf_l", "calf_r"]
TORSO = ["torso_l", "torso_r"]
GROUPS = {
    # fringe: only the head, or the chest pushes it around whenever she looks down
    "hair_front": dict(cols=["head"], damping=0.15, root=0.45, tip=0.25, gravity=-400, inertia=0.30, angle=20, speed=600, wind=40),
    "hair": dict(cols=["head", "neck"] + TORSO + ["pauldron_l", "pauldron_r", "upperarm_l", "upperarm_r"], damping=0.12, root=0.30,
                 tip=0.10, gravity=-500, inertia=0.40, angle=40, speed=900, wind=90),
    "skirt": dict(cols=LEGS, damping=0.12, root=0.32, tip=0.14, gravity=-600, inertia=0.45, angle=45, speed=900, wind=70),
    "robe": dict(cols=LEGS + ["foot_l", "foot_r"], damping=0.10, root=0.26, tip=0.07, gravity=-650, inertia=0.50, angle=50,
                 speed=1000, wind=110),
    "obi_tails": dict(cols=LEGS[:3], damping=0.10, root=0.22, tip=0.06, gravity=-600, inertia=0.55, angle=60, speed=1000, wind=120),
    "sleeves": dict(cols=TORSO + ["forearm_l", "forearm_r"], damping=0.15, root=0.5, tip=0.3, gravity=-500, inertia=0.30, angle=25,
                    speed=800, wind=40),
    "pendant": dict(cols=LEGS[:3], damping=0.12, root=0.30, tip=0.10, gravity=-650, inertia=0.50, angle=50, speed=900, wind=60),
}

sk = unreal.load_asset("/Game/Swordswoman/sw_ue")
skel = sk.get_editor_property("skeleton")
BEL = unreal.BlueprintEditorLibrary

# Blender armature space -> Unreal component space: pick the axis flip that matches the reference pose.
ref = unreal.AnimPoseExtensions.get_reference_pose(skel)


def ue_pos(b):
    t = unreal.AnimPoseExtensions.get_bone_pose(ref, b, unreal.AnimPoseSpaces.WORLD).translation
    return [t.x, t.y, t.z]


probe = ["J_Bip_L_Hand", "J_Bip_R_Foot", "J_Bip_C_Head", "J_Bip_L_UpperLeg", "J_Sec_Cloth_Robe00_01"]
blend_rest = {}
for c in CHAINS.values():
    for b, p in zip(c["bones"], c["rest"]):
        blend_rest[b] = p
for c in data["colliders"]:
    blend_rest[c["bone"]] = c["bone_a"]
    if c.get("end"):
        blend_rest[c["end"]] = c["bone_b"]
best = None
for sx in (1, -1):
    for sy in (1, -1):
        for swap in (False, True):
            def f(p, sx=sx, sy=sy, swap=swap):
                x, y = (p[1], p[0]) if swap else (p[0], p[1])
                return [sx * x, sy * y, p[2]]
            err = 0.0
            for b in probe:
                if b in blend_rest:
                    u, q = ue_pos(b), f(blend_rest[b])
                    err += sum((u[i] - q[i]) ** 2 for i in range(3)) ** 0.5
            if best is None or err < best[0]:
                best = (err, f, (sx, sy, swap))
say("axis map", best[2], "error cm", round(best[0], 2))
if best[0] > 2.0 * len(probe):
    raise RuntimeError("axis map does not fit the reference pose")
to_ue = best[1]


def vec(p):
    return unreal.Vector(*p)


# Extra radius per group: the capsules sit inside the skin, while the cloth must clear the boots, the
# outfit layers and its own thickness (the robe mesh between two strands sags further in than the strands).
MARGIN = dict(hair_front=1.0, hair=1.5, skirt=3.0, robe=4.0, obi_tails=3.0, sleeves=1.5, pendant=3.0)


def collider(name, margin=0.0):
    c = COL[name]
    col = unreal.BFClothCollider()
    col.set_editor_property("bone", c["bone"])
    col.set_editor_property("end_bone", c.get("end") or c["bone"])
    col.set_editor_property("radius", float(c["radius"]) + margin)
    a = to_ue([c["a"][i] - c["bone_a"][i] for i in range(3)])
    b = to_ue([c["b"][i] - c["bone_b"][i] for i in range(3)])
    col.set_editor_property("offset_a", vec(a))
    col.set_editor_property("offset_b", vec(b))
    return col


path = f"{DIR}/{NAME}"
bp = unreal.load_asset(path)
ed = unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp, "AnimGraph")
old = [n for n in ed.list_all_nodes() if n.get_class().get_name() != "AnimGraphNode_Root"]
if old:
    ed.remove_nodes(old)
root_node = [n for n in ed.list_all_nodes() if n.get_class().get_name() == "AnimGraphNode_Root"][0]
available = ed.list_available_nodes([])
input_name = next(a for a in available if a.replace(" ", "").lower().endswith("inputpose"))
sway_name = next(a for a in available if "cloth" in a.lower() and "sway" in a.lower())
say("nodes", input_name, "|", sway_name)


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


x = 0
prev = make(input_name, x)
x += 300
cur = make("Animation|ConvertSpaces|LocalToComponent", x)
link(prev, cur)
prev = cur
for gname, g in GROUPS.items():
    chains = []
    for root, c in CHAINS.items():
        if c["group"] != gname:
            continue
        ch = unreal.BFClothChain()
        ch.set_editor_property("start_bone", c["bones"][0])
        ch.set_editor_property("end_bone", c["bones"][-1])
        chains.append(ch)
    x += 300
    node = make(sway_name, x)
    d = node.get_editor_property("node")
    d.set_editor_property("chains", chains)
    d.set_editor_property("colliders", [collider(n, MARGIN[gname]) for n in g["cols"]])
    for k, v in [("damping", g["damping"]), ("stiffness_root", g["root"]), ("stiffness_tip", g["tip"]),
                 ("inertia", g["inertia"]), ("max_angle_deg", float(g["angle"])), ("max_speed", float(g["speed"])),
                 ("wind_strength", float(g["wind"])), ("limit_friction", 0.7), ("rest_radius", True),
                 ("rest_radius_scale", 0.9), ("segment_collision", True), ("collision_iterations", 2)]:
        d.set_editor_property(k, v)
    d.set_editor_property("gravity", unreal.Vector(0, 0, g["gravity"]))
    d.set_editor_property("drop_arms", [])
    d.set_editor_property("drop_hands", [])
    node.set_editor_property("node", d)
    back = node.get_editor_property("node")
    say(gname, "chains", len(back.get_editor_property("chains")), "colliders",
        [(str(c.get_editor_property("bone")), round(c.get_editor_property("radius"), 1)) for c in back.get_editor_property("colliders")],
        "rest_radius", back.get_editor_property("rest_radius"))
    link(prev, node)
    prev = node
x += 300
cur = make("Animation|ConvertSpaces|ComponentToLocal", x)
link(prev, cur)
link(cur, root_node)
root_node.set_node_pos(unreal.IntPoint(int(x + 300), 0))
BEL.compile_blueprint(bp)
errors = ed.list_nodes_with_errors()
say("errors", [n.get_name() + ": " + str(n.get_editor_property("error_msg")) for n in errors][:5])
sk.set_editor_property("post_process_anim_blueprint", BEL.generated_class(bp))
unreal.EditorAssetLibrary.save_loaded_asset(bp, False)
unreal.EditorAssetLibrary.save_loaded_asset(sk, False)
say("DONE")
