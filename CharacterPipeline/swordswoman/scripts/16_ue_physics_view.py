# Swordswoman copy of scripts/ue/22_physics_view.py. Checks the hair and cloth physics in Play In Editor. Run through -ExecCmds="py <path>".
# Plays a few lively clips twice, first with the post-process physics blueprint switched off and then on,
# and captures a front and a rear three-quarter view of each pass to scripts/ue/physics_frames as
# off_front_NNNN.png and so on. It logs how far each chain tip moves away from the plain animation, which
# shows whether the physics does anything, and the chain stretch, which shows a chain that explodes.
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import glob, math, os, time
import unreal

ROOT = os.path.join(ANIME_GAME_ROOT, r"swordswoman")
OUT = os.path.join(ROOT, "renders", "ue_phys")
os.makedirs(OUT, exist_ok=True)
for f in glob.glob(os.path.join(OUT, "*.png")):
    os.remove(f)
LOG = os.path.join(ROOT, "renders", "_log_ue_physics_view.txt")
WARMUP, SLOMO, FPS = 45.0, 0.08, 15.0
lines = []


def say(*a):
    lines.append(" ".join(str(x) for x in a))
    open(LOG, "w", encoding="utf-8").write("\n".join(lines))


say("start")
L = unreal.AnimationLibrary
les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
les.new_level("/Game/Preview/L_PreviewSW")


def spawn(cls, loc=(0, 0, 0), rot=(0, 0, 0)):
    return eas.spawn_actor_from_class(cls, unreal.Vector(*loc), unreal.Rotator(*rot))


spawn(unreal.DirectionalLight, rot=(0, -35, -90)).light_component.set_intensity(6.0)
# fill light from behind, so the rear view is not black
spawn(unreal.DirectionalLight, rot=(0, -30, 135)).light_component.set_intensity(3.0)
char = spawn(unreal.SkeletalMeshActor)
char.skeletal_mesh_component.set_skinned_asset_and_update(unreal.load_asset("/Game/Swordswoman/sw_ue"))
# SW_CLOSE=1 moves the front camera to a head-and-chest shot for checking the face and materials.
if os.environ.get("SW_CLOSE"):
    spawn(unreal.SceneCapture2D, (0, 95, 130), (0, -8, -90)).tags = ["front"]
else:
    spawn(unreal.SceneCapture2D, (0, 330, 100), (0, 0, -90)).tags = ["front"]
spawn(unreal.SceneCapture2D, (-230, -230, 115), (0, -5, 45)).tags = ["rear"]

A = "/Game/Swordswoman/Anim/A_"
CLIPS = ["Idle_Combat", "Dodge_Back", "Dodge_Left", "Attack_N4", "Swap_In", "Plunge_Land", "Run_F", "Run_F"]
# Set PHYS_QUICK=1 in the environment that starts the editor for a short run with two clips.
if os.environ.get("PHYS_QUICK"):
    CLIPS = CLIPS[:2]
import json
SETUP = json.load(open(os.path.join(ROOT, "export_unreal", "ue_physics_setup.json")))
_ss = unreal.get_editor_subsystem(unreal.SkeletalMeshEditorSubsystem)
_sk = unreal.load_asset("/Game/Swordswoman/sw_ue")


def _end(b):
    while True:
        ch = [str(c) for c in _ss.get_bone_children(_sk, b)]
        if not ch:
            return b
        b = ch[0]


TIPS = {k: (r, _end(r)) for k, r in (("hair", "J_Sec_Hair1_01"), ("skirt", "J_Sec_Cloth_Skirt00_01"), ("robe", "J_Sec_Cloth_Robe06_01"),
                                     ("tail", "J_Sec_Cloth_TailBack0_01"), ("sleeve", "J_Sec_Cloth_SleeveL_01"))}
timeline, t = [], 0.3
for n in CLIPS:
    a = unreal.load_asset(A + n)
    a.set_editor_property("enable_root_motion", False)
    timeline.append((t, a, n))
    t += max(L.get_sequence_length(a), 1.2) + 0.3
TOTAL = t
S = dict(start=time.time(), phase="warm", handle=None, t0=0, i=0, base=0, frame=0, world=None, comp=None, caps={}, rt=None, ref={}, worst={}, label="",
         run="off", tips={}, diff={}, missed=0)


def attach():
    w = ues.get_game_world()
    if not w:
        return False
    chars = unreal.GameplayStatics.get_all_actors_of_class(w, unreal.SkeletalMeshActor)
    caps = unreal.GameplayStatics.get_all_actors_of_class(w, unreal.SceneCapture2D)
    if not chars or len(caps) < 2:
        return False
    for p in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Pawn):
        p.set_actor_hidden_in_game(True)
    S["world"], S["comp"] = w, chars[0].skeletal_mesh_component
    S["comp"].set_editor_property("visibility_based_anim_tick_option", unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES)
    S["rt"] = unreal.RenderingLibrary.create_render_target2d(w, 640, 640, unreal.TextureRenderTargetFormat.RTF_RGBA8)
    for c in caps:
        tag = str(c.tags[0]) if c.tags else "front"
        cc = c.capture_component2d
        cc.set_editor_property("texture_target", S["rt"])
        cc.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
        cc.set_editor_property("capture_every_frame", False)
        cc.set_editor_property("fov_angle", 50.0)
        S["caps"][tag] = (c, c.get_actor_location())
    say("post process instance", S["comp"].get_post_process_instance())
    return True


def tip_lengths():
    c = S["comp"]
    return {k: (c.get_socket_location(b) - c.get_socket_location(a)).length() for k, (a, b) in TIPS.items()}


def tip_offsets():
    c = S["comp"]
    return {k: c.get_socket_location(b) - c.get_socket_location("Root") for k, (a, b) in TIPS.items()}


def set_post_process(disabled):
    c = S["comp"]
    for name in ("set_disable_post_process_blueprint", "toggle_disable_post_process_blueprint"):
        fn = getattr(c, name, None)
        if fn and name.startswith("set"):
            fn(disabled)
            return name
    try:
        c.set_editor_property("disable_post_process_blueprint", disabled)
        return "property"
    except Exception:
        pass
    getter = getattr(c, "get_disable_post_process_blueprint", None)
    fn = getattr(c, "toggle_disable_post_process_blueprint", None)
    if fn and getter and getter() != disabled:
        fn()
        return "toggle"
    say("post process methods", [m for m in dir(c) if "post_process" in m])
    raise RuntimeError("cannot switch the post-process blueprint")


def nan_report():
    c, bad = S["comp"], {}
    for g in SETUP["groups"].values():
        for r in g["root_bones"]:
            b = r
            while b:
                v = c.get_socket_location(b)
                if not (v.x == v.x and v.y == v.y and v.z == v.z):
                    bad[r] = b
                    break
                kids = c.get_child_bones(b) if hasattr(c, "get_child_bones") else []
                b = str(kids[0]) if kids else None
    return bad


def start_pass(run):
    S["run"], S["i"], S["frame"] = run, 0, 0
    how = set_post_process(run == "off")
    unreal.SystemLibrary.execute_console_command(S["world"], f"slomo {SLOMO}")
    S["base"], S["phase"] = unreal.GameplayStatics.get_time_seconds(S["world"]), "rec"
    say("pass", run, "switched by", how)


def tick(dt):
    try:
        now = time.time()
        ph = S["phase"]
        if ph == "warm":
            if now - S["start"] > WARMUP:
                les.editor_request_begin_play()
                S["phase"], S["t0"] = "wait_pie", now
        elif ph == "wait_pie":
            if now - S["t0"] > 90:
                say("ERROR pie never started")
                S["phase"], S["t0"] = "quit", now
            elif attach():
                S["ref"] = tip_lengths()
                say("rest lengths", {k: round(v, 1) for k, v in S["ref"].items()})
                start_pass("off")
        elif ph == "rec":
            g = unreal.GameplayStatics.get_time_seconds(S["world"]) - S["base"]
            while S["i"] < len(timeline) and g >= timeline[S["i"]][0]:
                S["comp"].play_animation(timeline[S["i"]][1], False)
                S["label"] = timeline[S["i"]][2]
                S["i"] += 1
            r = S["comp"].get_socket_location("Root")
            for tag, (cap, base) in S["caps"].items():
                cap.set_actor_location(unreal.Vector(base.x + r.x, base.y + r.y, base.z + r.z * 0.85), False, False)
            f = int(g * FPS)
            if f >= S["frame"]:
                S["missed"] += f - S["frame"]
                for tag, (cap, _) in S["caps"].items():
                    cap.capture_component2d.capture_scene()
                    unreal.RenderingLibrary.export_render_target(S["world"], S["rt"], OUT, f"{S['run']}_{tag}_{f:04d}.png")
                offs = tip_offsets()
                if S["run"] == "off":
                    S["tips"][f] = offs
                else:
                    for k, v in tip_lengths().items():
                        ratio = v / max(S["ref"][k], 0.01)
                        if not ratio <= S["worst"].get(k, (0, ""))[0]:
                            S["worst"][k] = (ratio, f"{S['label']} f{f}")
                    if f in S["tips"]:
                        for k, v in offs.items():
                            d = (v - S["tips"][f][k]).length()
                            mx, total, n = S["diff"].get(k, (0.0, 0.0, 0))
                            S["diff"][k] = (max(mx, d), total + d, n + 1)
                S["frame"] = f + 1
            if g >= TOTAL:
                unreal.SystemLibrary.execute_console_command(S["world"], "slomo 1")
                if S["run"] == "off":
                    S["comp"].play_animation(timeline[0][1], False)
                    start_pass("on")
                    return
                say("worst tip stretch vs rest", {k: (round(v[0], 2), v[1]) for k, v in S["worst"].items()})
                say("tip offset from plain animation cm (max, mean)", {k: (round(v[0], 1), round(v[1] / max(v[2], 1), 1)) for k, v in S["diff"].items()})
                say("frames per pass", S["frame"], "missed", S["missed"])
                say("chains with NaN bones (chain: first bad bone)", nan_report())
                les.editor_request_end_play()
                S["phase"], S["t0"] = "quit", now
        elif ph == "quit" and now - S["t0"] > 3:
            unreal.unregister_slate_post_tick_callback(S["handle"])
            say("DONE")
            unreal.SystemLibrary.quit_editor()
    except Exception as e:
        say("ERROR", S["phase"], e)
        S["phase"], S["t0"] = "quit", time.time()


S["handle"] = unreal.register_slate_post_tick_callback(tick)
