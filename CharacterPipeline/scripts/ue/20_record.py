# Records every clip that has effects, in Play In Editor through -ExecCmds="py <path>". Game time is
# slowed so each 1/30 s of animation gets its own captured frame. Root motion is turned off in memory
# only, so the root bone moves the mesh on screen, and the camera follows it. Nothing here is saved.
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import glob, json, os, shutil, time
import unreal

ROOT = ANIME_GAME_ROOT
FRAMES = os.path.join(ROOT, "scripts", "ue", "frames")
# Frames already on disk are kept and skipped, so an interrupted recording can resume.
# Delete the folder's PNG files by hand to record from scratch.
os.makedirs(FRAMES, exist_ok=True)
for f in glob.glob(os.path.join(FRAMES, "*.png")):
    if os.path.getsize(f) == 0:
        os.remove(f)
LOG = os.path.join(ROOT, "scripts", "ue", "report_record.txt")
WARMUP, SLOMO, GAP, FPS = 45.0, 0.12, 0.7, 30.0
lines = []


def say(*a):
    lines.append(" ".join(str(x) for x in a))
    open(LOG, "w", encoding="utf-8").write("\n".join(lines))


say("start")
L = unreal.AnimationLibrary
les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
les.new_level("/Game/Preview/L_Preview")


def spawn(cls, loc=(0, 0, 0), rot=(0, 0, 0)):
    return eas.spawn_actor_from_class(cls, unreal.Vector(*loc), unreal.Rotator(*rot))


spawn(unreal.DirectionalLight, rot=(0, -35, -90)).light_component.set_intensity(6.0)
char = spawn(unreal.SkeletalMeshActor)
char.skeletal_mesh_component.set_skinned_asset_and_update(unreal.load_asset("/Game/Character/karakter_ue"))
cap = spawn(unreal.SceneCapture2D, (0, 330, 95), (0, 0, -90))

A = "/Game/Character/Anim/A_"
M = "/Game/Character/Mage/"
NEAR, WIDE, FAR = (0, 330, 100), (0, 480, 110), (0, 780, 190)
ORDER = [("Attack_N1", NEAR), ("Attack_N2", NEAR), ("Attack_N3", NEAR), ("Attack_N4", NEAR), ("Charge_Start", NEAR), ("Charge_Release", NEAR),
         ("Skill_BloomField", WIDE), ("Skill_Heal", NEAR), ("Skill_Buff", WIDE), ("Skill_Hold_Start", NEAR), ("Skill_Hold_Release", NEAR),
         ("Dodge_Back", WIDE), ("Dodge_Forward", WIDE), ("Dodge_Left", WIDE), ("Dodge_Right", WIDE), ("Dodge_Counter", WIDE),
         ("Swap_In", NEAR), ("Swap_Out", NEAR), ("Plunge_Land", WIDE)]
MAGE = [("Mage_Fireball_R", NEAR), ("Mage_Fireball_L", NEAR), ("Mage_GroundSlam", WIDE), ("Mage_Shout", NEAR)]
items = [(A + n, n, c) for n, c in ORDER] + [(M + n, n, c) for n, c in MAGE] + [(A + "Ultimate_EternalBloom", "Ultimate_EternalBloom", FAR)]
idle = unreal.load_asset(A + "Idle_Combat")
idle.set_editor_property("enable_root_motion", False)
timeline, labels = [], []
t = 0.5
for path, name, cam in items:
    a = unreal.load_asset(path)
    a.set_editor_property("enable_root_motion", False)
    length = L.get_sequence_length(a)
    timeline.append((t, a, cam))
    labels.append(dict(name=name, start=round(t, 3), end=round(t + length, 3)))
    t += length
    timeline.append((t, idle, cam))
    t += GAP
TOTAL = t
say("clips", len(items), "seconds", round(TOTAL, 1))
json.dump(dict(fps=FPS, total=TOTAL, labels=labels), open(os.path.join(ROOT, "scripts", "ue", "record_labels.json"), "w"), indent=1)
S = dict(start=time.time(), phase="warm", handle=None, t0=0, i=0, base=0, frame=0, saved=0, world=None, comp=None, cc=None, rt=None, cap=None, cam=NEAR, real=0)


def attach():
    w = ues.get_game_world()
    if not w:
        return False
    chars = unreal.GameplayStatics.get_all_actors_of_class(w, unreal.SkeletalMeshActor)
    caps = unreal.GameplayStatics.get_all_actors_of_class(w, unreal.SceneCapture2D)
    if not chars or not caps:
        return False
    for p in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Pawn):
        p.set_actor_hidden_in_game(True)
    S["world"], S["cap"], S["comp"] = w, caps[0], chars[0].skeletal_mesh_component
    S["comp"].set_editor_property("visibility_based_anim_tick_option", unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES)
    cc = caps[0].capture_component2d
    S["rt"] = unreal.RenderingLibrary.create_render_target2d(w, 1280, 720, unreal.TextureRenderTargetFormat.RTF_RGBA8)
    cc.set_editor_property("texture_target", S["rt"])
    cc.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
    cc.set_editor_property("capture_every_frame", False)
    cc.set_editor_property("fov_angle", 45.0)
    S["cc"] = cc
    return True


def gtime():
    return unreal.GameplayStatics.get_time_seconds(S["world"])


def console(cmd):
    unreal.SystemLibrary.execute_console_command(S["world"], cmd)


def advance(now_t):
    while S["i"] < len(timeline) and now_t >= timeline[S["i"]][0]:
        _, a, cam = timeline[S["i"]]
        S["i"] += 1
        S["cam"] = cam
        S["comp"].play_animation(a, False)


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
                S["base"], S["phase"] = gtime(), "dry"
                say("pie running, warm pass")
        elif ph == "dry":
            g = gtime() - S["base"]
            advance(g)
            if g >= TOTAL:
                S["i"], S["phase"] = 0, "rec"
                S["comp"].play_animation(idle, False)
                console(f"slomo {SLOMO}")
                S["base"], S["real"] = gtime(), now
                say("recording")
        elif ph == "rec":
            g = gtime() - S["base"]
            advance(g)
            r = S["comp"].get_socket_location("Root")
            c = S["cam"]
            S["cap"].set_actor_location(unreal.Vector(c[0] + r.x, c[1] + r.y, c[2] + r.z * 0.85), False, False)
            f = int(g * FPS)
            if f >= S["frame"]:
                if not os.path.exists(os.path.join(FRAMES, f"f_{f:05d}.png")):
                    S["cc"].capture_scene()
                    unreal.RenderingLibrary.export_render_target(S["world"], S["rt"], FRAMES, f"f_{f:05d}.png")
                    S["saved"] += 1
                S["frame"] = f + 1
                if S["saved"] % 300 == 0:
                    say("saved", S["saved"], "at", round(g, 1), "real", round(now - S["real"]))
            if g >= TOTAL:
                console("slomo 1")
                les.editor_request_end_play()
                say("frames", S["saved"], "of", int(TOTAL * FPS), "real seconds", round(now - S["real"]))
                S["phase"], S["t0"] = "quit", now
        elif ph == "quit" and now - S["t0"] > 3:
            unreal.unregister_slate_post_tick_callback(S["handle"])
            say("DONE")
            unreal.SystemLibrary.quit_editor()
    except Exception as e:
        say("ERROR", S["phase"], e)


S["handle"] = unreal.register_slate_post_tick_callback(tick)
