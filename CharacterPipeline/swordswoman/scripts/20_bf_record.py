# Records the swordswoman doing the BossFight player's combos in Play In Editor (BossFight project).
# Run through: UnrealEditor.exe BossFight.uproject -ExecCmds="py <this file>".
# Light combo (combo01_1-3), heavy combo (combo02_1-3), jump into the air combo (Air_Combo01_Z0_1-2 +
# Air_Attack04_Z0) and the plunge (Air_Down_Attack_Z0 from 0.5 s at 1.4x), chained at the player's
# CancelTime and play rates from BFPlayerCharacter.cpp, as dynamic montages on DefaultSlot so they blend.
# She is a Character, so the clips' root motion lunges move her like the player. Frames go to
# renders/bf_combo/f_NNNN.png at 30 fps of game time; 21 makes the video. Log renders/_log_bf_record.txt.
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import glob, json, math, os, time
import unreal

ROOT = os.path.join(ANIME_GAME_ROOT, r"swordswoman")
OUT = os.path.join(ROOT, "renders", "bf_combo")
os.makedirs(OUT, exist_ok=True)
for f in glob.glob(os.path.join(OUT, "*.png")):
    os.remove(f)
LOG = os.path.join(ROOT, "renders", "_log_bf_record.txt")
SETUP = json.load(open(os.path.join(ROOT, "export_unreal", "bf_combo_setup.json")))
WARMUP, SLOMO, FPS, W, H = 40.0, 0.12, 30.0, 1280, 720
D = "/Game/Swordswoman"
lines = []
MODE = os.environ.get("SW_MODE", "rec")  # "probe": exposure stills + trajectory log at normal speed, no video frames


def say(*a):
    lines.append(" ".join(str(x) for x in a))
    open(LOG, "w", encoding="utf-8").write("\n".join(lines))


say("start")
les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
# The player's training map (lit meadow). Nothing is saved: the spawned actors live only in this session.
les.load_level("/Game/BossFight/Maps/L_Training")


def spawn(cls, loc=(0, 0, 0), rot=None):
    return eas.spawn_actor_from_class(cls, unreal.Vector(*loc), rot or unreal.Rotator())


GROUND_Z = 92.0
# Open ground north of the PlayerStart (-900, 0); the combos travel about +4.5 m x, -7.3 m y from here,
# which ends clear of the scarecrows (y -700..-850) and the crates (-76, 999)
START = (-300, 600, 100)  # spawned low: from z 400 she slid ~9 m down a sloped collider before landing
char = spawn(unreal.Character, START)
char.tags = ["SW"]
mesh = char.get_editor_property("mesh")
sk = unreal.load_asset(D + "/sw_ue")
mesh.set_skinned_asset_and_update(sk)
mesh.set_relative_location_and_rotation(unreal.Vector(0, 0, -90), unreal.Rotator(yaw=-90), False, False)
mesh.set_animation_mode(unreal.AnimationMode.ANIMATION_BLUEPRINT)
mesh.set_anim_instance_class(unreal.load_asset(D + "/ABP_Swordswoman_Show").generated_class())
idx = mesh.get_material_index(SETUP["hidden_slot"])
mesh.set_material(idx, unreal.load_asset(D + "/M_SW_Hidden"))
say("hidden slot", idx)
cmc = char.get_editor_property("character_movement")
cmc.set_editor_property("run_physics_with_no_controller", True)

sword = spawn(unreal.StaticMeshActor)
sword.tags = ["SWSword"]
smc = sword.static_mesh_component
smc.set_mobility(unreal.ComponentMobility.MOVABLE)
smc.set_static_mesh(unreal.load_asset(D + "/SM_SwordswomanSword"))
smc.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
sword.attach_to_component(mesh, "J_Bip_R_Hand", unreal.AttachmentRule.SNAP_TO_TARGET, unreal.AttachmentRule.SNAP_TO_TARGET,
                          unreal.AttachmentRule.KEEP_WORLD, False)
r = SETUP["sword_rot"]
smc.set_relative_location_and_rotation(unreal.Vector(*SETUP["sword_loc"]), unreal.Rotator(roll=r[0], pitch=r[1], yaw=r[2]), False, False)
cam = spawn(unreal.SceneCapture2D, (300, -300, 160))
cam.tags = ["cam"]

A = D + "/Combat/SW_"
anims = {n: unreal.load_asset(A + n) for n in ["jump", "jump_landing", "combo01_1", "combo01_2", "combo01_3", "combo02_1", "combo02_2",
                                              "combo02_3", "Air_Combo01_Z0_1", "Air_Combo01_Z0_2", "Air_Attack04_Z0", "Air_Down_Attack_Z0"]}
say("anims", {k: bool(v) for k, v in anims.items()})
# (kind, clip, cancel time in clip seconds, play rate) - BFPlayerCharacter.cpp LightChain/HeavyChain/AirChain
PLAN = [("wait", None, 1.0, 1.0),
        ("atk", "combo01_1", 0.50, 1.15), ("atk", "combo01_2", 0.60, 1.15), ("atk", "combo01_3", 2.2, 1.1),
        ("wait", None, 0.5, 1.0),
        ("atk", "combo02_1", 0.60, 1.0), ("atk", "combo02_2", 0.80, 1.0), ("atk", "combo02_3", 2.2, 1.0),
        ("wait", None, 0.5, 1.0),
        ("jump", "jump", 0.42, 1.0),
        ("air", "Air_Combo01_Z0_1", 0.50, 1.2), ("air", "Air_Combo01_Z0_2", 0.75, 1.2), ("air", "Air_Attack04_Z0", 0.90, 1.0),
        ("plunge", "Air_Down_Attack_Z0", 2.0, 1.4),
        ("wait", None, 1.2, 1.0)]
S = dict(start=time.time(), phase="warm", handle=None, t0=0, world=None, char=None, cmc=None, ai=None, cap=None, rt=None,
         step=-1, step_t=0.0, base=0.0, frame=0, missed=0, cam_pos=None, plunge_from=None)


def attach():
    w = ues.get_game_world()
    if not w:
        return False
    found = [a for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Character) if "SW" in [str(t) for t in a.tags]]
    caps = [a for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.SceneCapture2D) if "cam" in [str(t) for t in a.tags]]
    if not found or not caps:
        return False
    for p in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Pawn):
        if p != found[0]:
            p.set_actor_hidden_in_game(True)
            p.set_actor_enable_collision(False)
            p.set_actor_tick_enabled(False)
            p.set_actor_location(unreal.Vector(0, 5000, 300), False, True)
    S["world"], S["char"], S["cap"] = w, found[0], caps[0]
    # Props that can stand between the camera and her (bushes, rocks, crates, trees); floor-sized actors and the
    # grass/flower instance actors are left out. update_camera hides the ones crossing the line of sight.
    occ = []
    for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor):
        if a in (found[0], caps[0]) or "SWSword" in [str(t) for t in a.tags] or isinstance(a, unreal.Pawn):
            continue
        o, e = a.get_actor_bounds(True)
        if 5 < max(e.x, e.y, e.z) < 1500 and e.z > 15:
            occ.append((a, o, e))
    S["occ"] = occ
    say("occluder candidates", len(occ))
    S["cmc"] = found[0].get_editor_property("character_movement")
    m = found[0].get_editor_property("mesh")
    m.set_editor_property("visibility_based_anim_tick_option", unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES)
    S["ai"] = m.get_anim_instance()
    S["rt"] = unreal.RenderingLibrary.create_render_target2d(w, W, H, unreal.TextureRenderTargetFormat.RTF_RGBA8)
    cc = caps[0].capture_component2d
    cc.set_editor_property("texture_target", S["rt"])
    cc.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
    cc.set_editor_property("capture_every_frame", False)
    cc.set_editor_property("fov_angle", 55.0)
    say("anim instance", S["ai"], "post process", m.get_post_process_instance())
    return True


def play(clip, rate, start=0.0, blend_in=0.12, blend_out=0.25):
    return S["ai"].play_slot_animation_as_dynamic_montage(anims[clip], "DefaultSlot", blend_in, blend_out, rate, 1, -1.0, start)


def begin_step(i, g):
    S["step"], S["step_t"] = i, g
    kind, clip, cancel, rate = PLAN[i]
    c, m = S["char"], S["cmc"]
    if kind == "atk":
        play(clip, rate)
    elif kind == "jump":
        play(clip, rate, 0.0, 0.08, 0.2)
        c.launch_character(unreal.Vector(0, 0, 680), False, True)
    elif kind == "air":
        if m.movement_mode != unreal.MovementMode.MOVE_FLYING:
            m.set_movement_mode(unreal.MovementMode.MOVE_FLYING)
            m.stop_movement_immediately()
        play(clip, rate)
    elif kind == "plunge":
        play(clip, rate, 0.5, 0.05, 0.3)
        S["plunge_from"] = c.get_actor_location()
        m.stop_movement_immediately()
    say("step", i, kind, clip, "at", round(g, 2), "z", round(c.get_actor_location().z - GROUND_Z, 1))


def step_length(i):
    kind, clip, cancel, rate = PLAN[i]
    return cancel / rate if kind != "wait" else cancel


def update_step(g):
    i = S["step"]
    kind = PLAN[i][0]
    c = S["char"]
    if kind == "plunge":
        # hang a moment, then dive onto the floor (BFPlayerCharacter::TickPlunge does a timed drop)
        tt = g - S["step_t"]
        a = S["plunge_from"]
        k = min(max((tt - 0.10) / 0.22, 0.0), 1.0)
        z = a.z + (GROUND_Z - a.z) * (k * k)
        c.set_actor_location(unreal.Vector(a.x, a.y, z), False, True)
        if k >= 1.0 and S["cmc"].movement_mode == unreal.MovementMode.MOVE_FLYING:
            S["cmc"].set_movement_mode(unreal.MovementMode.MOVE_WALKING)
            say("plunge landed at", round(g, 2))
    if g - S["step_t"] >= step_length(i):
        if i + 1 < len(PLAN):
            begin_step(i + 1, g)
            return False
        return True
    return False


def seg_hits_box(p, q, o, e, pad=25.0):
    # slab test: does the segment p-q cross the box (centre o, half size e + pad)?
    t0, t1 = 0.0, 1.0
    for a in ("x", "y", "z"):
        pa, da = getattr(p, a), getattr(q, a) - getattr(p, a)
        lo, hi = getattr(o, a) - getattr(e, a) - pad, getattr(o, a) + getattr(e, a) + pad
        if abs(da) < 1e-6:
            if pa < lo or pa > hi:
                return False
            continue
        u0, u1 = (lo - pa) / da, (hi - pa) / da
        if u0 > u1:
            u0, u1 = u1, u0
        t0, t1 = max(t0, u0), min(t1, u1)
        if t0 > t1:
            return False
    return True


def update_camera(dt):
    c = S["char"].get_actor_location()
    # front-right three-quarter, raised over the bushes and looking slightly down
    want = unreal.Vector(c.x + 230, c.y - 280, GROUND_Z + 120 + (c.z - GROUND_Z) * 0.9)
    p = S["cam_pos"] or want
    k = min(1.0, dt * 10.0)
    p = unreal.Vector(p.x + (want.x - p.x) * k, p.y + (want.y - p.y) * k, p.z + (want.z - p.z) * k)
    S["cam_pos"] = p
    look = unreal.Vector(c.x, c.y, c.z + 5)
    S["cap"].set_actor_location_and_rotation(p, unreal.MathLibrary.find_look_at_rotation(p, look), False, True)
    hide = []
    for a, o, e in S.get("occ", []):
        if any(seg_hits_box(p, unreal.Vector(c.x, c.y, c.z + dz), o, e) for dz in (-80, 0, 80)):
            hide.append(a)
    S["cap"].capture_component2d.set_editor_property("hidden_actors", hide)


def set_exposure(bias):
    cc = S["cap"].capture_component2d
    pps = cc.get_editor_property("post_process_settings")
    pps.set_editor_property("override_auto_exposure_method", True)
    pps.set_editor_property("auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL)
    pps.set_editor_property("override_auto_exposure_apply_physical_camera_exposure", True)
    pps.set_editor_property("auto_exposure_apply_physical_camera_exposure", False)
    pps.set_editor_property("override_auto_exposure_bias", True)
    pps.set_editor_property("auto_exposure_bias", bias)
    cc.set_editor_property("post_process_settings", pps)
    cc.set_editor_property("post_process_blend_weight", 1.0)


def brightness():
    S["cap"].capture_component2d.capture_scene()
    vals = []
    for i in range(10):
        for j in range(6):
            col = unreal.RenderingLibrary.read_render_target_pixel(S["world"], S["rt"], int(W * (i + 0.5) / 10), int(H * (j + 0.5) / 6))
            vals.append((0.3 * col.r + 0.59 * col.g + 0.11 * col.b) / 255.0)
    vals.sort()
    return vals[len(vals) // 2]


def set_gain(g):
    # The capture's exposure is fixed (bias / min-max brightness are ignored, probed 2026-11-08), but the
    # scene colour tint is a linear multiplier before the tone curve, so it works as an exposure gain.
    cc = S["cap"].capture_component2d
    pps = cc.get_editor_property("post_process_settings")
    pps.set_editor_property("override_scene_color_tint", True)
    pps.set_editor_property("scene_color_tint", unreal.LinearColor(g, g, g, 1))
    cc.set_editor_property("post_process_settings", pps)
    cc.set_editor_property("post_process_blend_weight", 1.0)


def set_fixed_exposure(ev, eye=False):
    # A SceneCapture has no eye adaptation history, so the renderer uses a fixed exposure taken from the
    # middle of the min/max brightness range; the exposure bias is not part of that path.
    cc = S["cap"].capture_component2d
    pps = cc.get_editor_property("post_process_settings")
    for k, v in [("auto_exposure_method", unreal.AutoExposureMethod.AEM_HISTOGRAM), ("auto_exposure_bias", 0.0),
                 ("auto_exposure_min_brightness", ev), ("auto_exposure_max_brightness", ev)]:
        pps.set_editor_property("override_" + k, True)
        pps.set_editor_property(k, v)
    cc.set_editor_property("post_process_settings", pps)
    cc.set_editor_property("post_process_blend_weight", 1.0)
    if eye:
        cc.set_editor_property("show_flag_settings", [unreal.EngineShowFlagsSetting(show_flag_name="EyeAdaptation", enabled=True)])


PROBES = ["g2", "g4", "g8", "g16", "g32"]


def probe_one(name):
    # one capture per tick, so each setting has a full frame to take effect
    cc = S["cap"].capture_component2d
    pps = cc.get_editor_property("post_process_settings")
    if name.startswith("g"):
        set_gain(float(name[1:]))
    elif name == "tint":
        pps.set_editor_property("override_scene_color_tint", True)
        pps.set_editor_property("scene_color_tint", unreal.LinearColor(1, 0, 0, 1))
        cc.set_editor_property("post_process_settings", pps)
    elif name == "bias4":
        pps.set_editor_property("override_scene_color_tint", False)
        cc.set_editor_property("post_process_settings", pps)
        set_exposure(4.0)
    elif name in ("ev0", "ev8"):
        set_fixed_exposure(float(name[2:]))
    elif name == "hdr":
        S["rt_hdr"] = unreal.RenderingLibrary.create_render_target2d(S["world"], W, H, unreal.TextureRenderTargetFormat.RTF_RGBA16F)
        cc.set_editor_property("texture_target", S["rt_hdr"])
        cc.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_SCENE_COLOR_HDR)
    back = cc.get_editor_property("post_process_settings")
    say("probe", name, "readback bias", back.get_editor_property("override_auto_exposure_bias"), back.get_editor_property("auto_exposure_bias"),
        "method", back.get_editor_property("auto_exposure_method"), "tint", back.get_editor_property("override_scene_color_tint"),
        "weight", cc.get_editor_property("post_process_blend_weight"), "cam", S["cap"].get_actor_location())
    cc.capture_scene()
    rt = S.get("rt_hdr") if name == "hdr" else S["rt"]
    unreal.RenderingLibrary.export_render_target(S["world"], rt, OUT, "cal2_" + name)


def probe_exposure():
    update_camera(1.0)
    for ev in [-4, -2, 0, 2, 4, 6, 8, 10]:
        set_fixed_exposure(float(ev))
        v = brightness()
        unreal.RenderingLibrary.export_render_target(S["world"], S["rt"], OUT, f"cal_hist_{ev:+d}.png")
        say("fixed ev", ev, "median", round(v, 3))
    set_exposure(4.0)
    cc = S["cap"].capture_component2d
    cc.set_editor_property("show_flag_settings", [unreal.EngineShowFlagsSetting(show_flag_name="EyeAdaptation", enabled=True)])
    v = brightness()
    unreal.RenderingLibrary.export_render_target(S["world"], S["rt"], OUT, "cal_eye_bias4.png")
    say("eye flag + bias 4 median", round(v, 3))


def calibrate_exposure():
    # SceneCapture has no eye adaptation, so the first take was nearly black: pick a manual
    # exposure bias whose median pixel lands near a mid grey.
    update_camera(1.0)
    best = None
    for bias in [x * 0.5 for x in range(-4, 17)]:
        set_exposure(bias)
        v = brightness()
        say("exposure bias", bias, "median", round(v, 3))
        if best is None or abs(v - 0.42) < abs(best[1] - 0.42):
            best = (bias, v)
    set_exposure(best[0])
    say("exposure chosen", best)


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
                S["phase"], S["t0"] = "settle", now
        elif ph == "settle":
            if MODE == "probe2":
                l = S["char"].get_actor_location()
                say("settle t", round(now - S["t0"], 2), "xyz", round(l.x), round(l.y), round(l.z), "vel", S["cmc"].velocity)
                if now - S["t0"] > 3.0:
                    update_camera(1.0)
                    S["phase"], S["pi"], S["t0"] = "probe2", 0, now
                return
            # let her land on the floor and the physics settle before recording
            if now - S["t0"] > 3.0:
                if MODE == "probe":
                    probe_exposure()
                else:
                    set_gain(float(os.environ.get("SW_GAIN", "4")))
                    say("exposure gain", os.environ.get("SW_GAIN", "4"))
                    unreal.SystemLibrary.execute_console_command(S["world"], f"slomo {SLOMO}")
                S["base"] = unreal.GameplayStatics.get_time_seconds(S["world"])
                GROUND = S["char"].get_actor_location().z
                globals()["GROUND_Z"] = GROUND
                say("ground z", round(GROUND, 1))
                begin_step(0, 0.0)
                S["phase"], S["last_g"] = "rec", 0.0
        elif ph == "rec":
            g = unreal.GameplayStatics.get_time_seconds(S["world"]) - S["base"]
            done = update_step(g)
            update_camera(g - S["last_g"])
            S["last_g"] = g
            f = int(g * FPS)
            if MODE == "probe":
                if f >= S["frame"]:
                    if f % 10 == 0:
                        l = S["char"].get_actor_location()
                        say("pos t", round(g, 2), "xyz", round(l.x), round(l.y), round(l.z - GROUND_Z), "yaw", round(S["char"].get_actor_rotation().yaw))
                    S["frame"] = f + 1
            elif f >= S["frame"]:
                S["missed"] += f - S["frame"]
                S["cap"].capture_component2d.capture_scene()
                unreal.RenderingLibrary.export_render_target(S["world"], S["rt"], OUT, f"f_{f:04d}.png")
                S["frame"] = f + 1
            if done:
                say("frames", S["frame"], "missed", S["missed"], "seconds", round(g, 2))
                unreal.SystemLibrary.execute_console_command(S["world"], "slomo 1")
                les.editor_request_end_play()
                S["phase"], S["t0"] = "quit", now
        elif ph == "probe2":
            if now - S["t0"] > 0.5:
                if S["pi"] < len(PROBES):
                    probe_one(PROBES[S["pi"]])
                    S["pi"] += 1
                    S["t0"] = now
                else:
                    les.editor_request_end_play()
                    S["phase"], S["t0"] = "quit", now
        elif ph == "quit" and now - S["t0"] > 3:
            unreal.unregister_slate_post_tick_callback(S["handle"])
            say("DONE")
            unreal.SystemLibrary.quit_editor()
    except Exception as e:
        say("ERROR", S["phase"], repr(e))
        S["phase"], S["t0"] = "quit", time.time()


S["handle"] = unreal.register_slate_post_tick_callback(tick)
