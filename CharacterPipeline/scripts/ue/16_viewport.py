# Run in the real editor through -ExecCmds="py <path>", because -ExecutePythonScript quits when the
# script returns. Plays clips in Play In Editor so notifies really fire, and captures frames to
# scripts/ue/shots. Every clip plays once to warm up effects, then again for the captures.
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import glob, math, os, time
import unreal

ROOT = ANIME_GAME_ROOT
SHOTS = os.path.join(ROOT, "scripts", "ue", "shots")
os.makedirs(SHOTS, exist_ok=True)
for f in glob.glob(os.path.join(SHOTS, "*.png")):
    os.remove(f)
LOG = os.path.join(ROOT, "scripts", "ue", "report_viewport.txt")
WARMUP = 120.0
lines = []


def say(*a):
    lines.append(" ".join(str(x) for x in a))
    open(LOG, "w", encoding="utf-8").write("\n".join(lines))


say("start")
les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
les.new_level("/Game/Preview/L_Preview")


def spawn(cls, loc=(0, 0, 0), rot=(0, 0, 0)):
    return eas.spawn_actor_from_class(cls, unreal.Vector(*loc), unreal.Rotator(*rot))


key = spawn(unreal.DirectionalLight, rot=(0, -35, -90))
key.light_component.set_intensity(6.0)
char = spawn(unreal.SkeletalMeshActor)
char.skeletal_mesh_component.set_skinned_asset_and_update(unreal.load_asset("/Game/Character/karakter_ue"))
cap = spawn(unreal.SceneCapture2D, (0, 330, 95), (0, 0, -90))

A = "/Game/Character/Anim/A_"
M = "/Game/Character/Mage/"
NEAR = ((0, 300, 95), (0, 0, -90))
SIDE = ((300, 0, 95), (0, 0, 180))
FAR = ((0, 620, 170), (0, 0, -90))
FACE = ((0, 115, 122), (0, 0, -90))
# clip, length, camera, capture offsets in seconds
BACK = ((0, -300, 95), (0, 0, 90))
CLIPS = [(A + "Idle_Combat", 1.0, NEAR, [0.5]), (A + "Idle_Relaxed", 1.0, NEAR, [0.5]), (A + "Run_F", 1.0, NEAR, [0.3]),
         (A + "Attack_N1", 1.0, NEAR, [0.1, 0.25]), (A + "Attack_N2", 1.0, NEAR, [0.25]), (A + "Ultimate_EternalBloom", 17.4, FAR, [6.7, 12.8])]
timeline = []
state = dict(start=time.time(), phase="warm", handle=None, t0=0, i=0, fired=0, comp=None, cc=None, rt=None, world=None, count=0)


def build():
    t = 2.0
    for rep in (0, 1):
        for n, (clip, length, cam, offs) in enumerate(CLIPS):
            timeline.append((t, "play", clip, cam))
            if rep:
                for o in offs:
                    timeline.append((t + o, "shot", f"{n:02d}_{clip.split('/')[-1]}_{o}".replace(".", "p"), None))
            t += length + 0.4
    timeline.append((t, "end", None, None))
    timeline.sort(key=lambda x: x[0])
    say("timeline seconds", round(t, 1), "events", len(timeline))


def attach():
    w = ues.get_game_world()
    if not w:
        return False
    chars = unreal.GameplayStatics.get_all_actors_of_class(w, unreal.SkeletalMeshActor)
    caps = unreal.GameplayStatics.get_all_actors_of_class(w, unreal.SceneCapture2D)
    if not chars or not caps:
        return False
    state["world"], state["cap"] = w, caps[0]
    state["comp"] = chars[0].skeletal_mesh_component
    state["comp"].set_editor_property("visibility_based_anim_tick_option", unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES)
    cc = caps[0].capture_component2d
    rt = unreal.RenderingLibrary.create_render_target2d(w, 960, 720, unreal.TextureRenderTargetFormat.RTF_RGBA8)
    cc.set_editor_property("texture_target", rt)
    cc.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
    cc.set_editor_property("capture_every_frame", False)
    cc.set_editor_property("fov_angle", 45.0)
    state["cc"], state["rt"] = cc, rt
    return True


def tick(dt):
    try:
        now = time.time()
        if state["phase"] == "warm":
            if now - state["start"] > WARMUP:
                les.editor_request_begin_play()
                state["phase"], state["t0"] = "wait_pie", now
                say("pie requested")
        elif state["phase"] == "wait_pie":
            if now - state["t0"] > 90:
                say("ERROR pie never started")
                state["phase"] = "quit"
            elif attach():
                build()
                state["phase"], state["t0"] = "run", now
                say("pie running", state["world"].get_name())
        elif state["phase"] == "run":
            while state["i"] < len(timeline) and now - state["t0"] >= timeline[state["i"]][0]:
                _, kind, a, cam = timeline[state["i"]]
                state["i"] += 1
                if kind == "play":
                    state["cap"].set_actor_location_and_rotation(unreal.Vector(*cam[0]), unreal.Rotator(*cam[1]), False, False)
                    state["comp"].play_animation(unreal.load_asset(a), False)
                elif kind == "shot":
                    state["cc"].capture_scene()
                    unreal.RenderingLibrary.export_render_target(state["world"], state["rt"], SHOTS, a + ".png")
                    state["count"] += 1
                    c = state["comp"]
                    d = c.get_socket_location("J_Bip_L_UpperArm") - c.get_socket_location("J_Bip_R_UpperArm")
                    say("shot", a, "shoulder yaw", round(math.degrees(math.atan2(d.y, d.x))), "root", c.get_socket_rotation("Root").yaw, "actor", c.get_owner().get_actor_rotation().yaw,
                        "hips", c.get_socket_location("J_Bip_C_Hips"), "cam", state["cap"].get_actor_location())
                else:
                    les.editor_request_end_play()
                    state["phase"], state["t0"] = "quit", now
                    break
        elif state["phase"] == "quit" and now - state["t0"] > 3:
            unreal.unregister_slate_post_tick_callback(state["handle"])
            say("DONE shots", state["count"])
            unreal.SystemLibrary.quit_editor()
    except Exception as e:
        say("ERROR", state["phase"], e)
        state["i"] += 1


state["handle"] = unreal.register_slate_post_tick_callback(tick)
say("waiting", WARMUP)
