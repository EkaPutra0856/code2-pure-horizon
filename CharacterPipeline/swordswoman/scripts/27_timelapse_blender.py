# Making-of timelapse, Blender part: replays the swordswoman build in the Blender 4.0 UI so it can be screen
# recorded (the real build ran headless through scripts 01-08, which leaves nothing to film). Opens
# sw_outfit_v4.blend in the GUI: base VRoid body -> rig -> each outfit/prop layer appears and is selected
# (outliner highlight, a few edit-mode peeks) -> material preview -> final orbit.
# Run: blender.exe sw_outfit_v4.blend --python scripts/27_timelapse_blender.py
# Handshake for the recorder: writes renders/_tl_ready.flag when the scene is set, waits for
# renders/_tl_go.flag, writes renders/_tl_done.flag at the end and quits (file is never saved).
import math, os, time
import bpy
from mathutils import Euler, Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FLAG = lambda n: os.path.join(ROOT, "renders", f"_tl_{n}.flag")
for n in ("ready", "go", "done"):
    if os.path.exists(FLAG(n)):
        os.remove(FLAG(n))

BASE = ["Body", "Face", "Hair"]
ORDER = [
    "SW_InnerTop", "SW_Top", "SW_Collar", "SW_Vest", "SW_VestTrim", "SW_UnderSleeve", "SW_Sleeve_L", "SW_Sleeve_R",
    "SW_SleeveLining_L", "SW_SleeveLining_R", "SW_SleeveTrim_L", "SW_SleeveTrim_R", "SW_Skirt", "SW_Robe",
    "SW_Obi", "SW_ObiCord", "SW_KnotBack", "SW_BowBack+1", "SW_BowBack-1", "SW_TailBack0", "SW_TailBack1",
    "SW_TassetL", "SW_TassetR", "SW_Gloves", "SW_Vambrace", "SW_VambraceRimA_L", "SW_VambraceRimA_R",
    "SW_VambraceRimB_L", "SW_VambraceRimB_R", "SW_Boots", "SW_BootRimL", "SW_BootRimR",
    "SW_Pauldron_L", "SW_Pauldron_R", "SW_ObiMedallion", "SW_JadeCord", "SW_JadePendant",
    "SW_Topknot", "SW_Crown", "SW_Kanzashi_L", "SW_Kanzashi_R", "SW_SwordStrap0", "SW_SwordStrap1",
    "SW_Scabbard", "SW_Sword",
]
EDIT_PEEK = {"SW_Top", "SW_Robe", "SW_Boots", "SW_Pauldron_L", "SW_Scabbard"}

T_RIG, T_RIG_END, T_OUT = 3.0, 7.5, 8.0
STEP = 0.95
T_MAT = T_OUT + len(ORDER) * STEP + 1.0
T_END = T_MAT + 16.0

view_layer = bpy.context.view_layer
objs = {o.name: o for o in bpy.data.objects}
arm = objs["Armature"]


def ctx():
    win = bpy.context.window_manager.windows[0]
    area = max((a for a in win.screen.areas if a.type == "VIEW_3D"), key=lambda a: a.width * a.height)
    region = next(r for r in area.regions if r.type == "WINDOW")
    return win, area, region


def setup():
    # colliders are only VRM spring-bone helpers; drop them so the outliner shows the build (never saved)
    col = bpy.data.collections.get("Colliders")
    if col:
        for o in list(col.objects):
            bpy.data.objects.remove(o)
        bpy.data.collections.remove(col)
    for o in bpy.data.objects:
        o.select_set(False)
        o.hide_set(o.name not in BASE)
    win, area, region = ctx()
    sp = area.spaces.active
    sp.shading.type = "SOLID"
    sp.shading.color_type = "MATERIAL"
    sp.overlay.show_wireframes = True
    sp.overlay.wireframe_threshold = 1.0
    sp.overlay.show_floor = True
    sp.lens = 50
    rv = sp.region_3d
    rv.view_perspective = "PERSP"
    arm.show_in_front = True
    open(FLAG("ready"), "w").write("1")


state = {"t0": None, "shown": 0, "edit": None, "mat": False, "rig": 0, "fs": False}


def set_view(t):
    win, area, region = ctx()
    rv = area.spaces.active.region_3d
    yaw = math.radians(15 + (t - T_END) * 9.0)  # ends facing her front (yaw 15)
    pitch = math.radians(78 if t < T_MAT else 82)
    if t < T_RIG_END:
        target, dist = Vector((0, 0, 0.95)), 3.0
    elif t < T_MAT:
        target, dist = Vector((0, 0, 0.95)), 2.9
    else:
        k = min(1.0, (t - T_MAT - 9.0) / 5.0) if t > T_MAT + 9.0 else 0.0
        target = Vector((0, 0, 0.95 + 0.5 * k))
        dist = 2.9 - 1.9 * k
    rv.view_location = target
    rv.view_distance = dist
    rv.view_rotation = Euler((pitch, 0, yaw)).to_quaternion()


def mode(m):
    win, area, region = ctx()
    with bpy.context.temp_override(window=win, area=area, region=region):
        if bpy.context.object and bpy.context.object.mode != m:
            bpy.ops.object.mode_set(mode=m)


def select_only(o):
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        mode("OBJECT")
    for s in bpy.context.selected_objects:
        s.select_set(False)
    o.select_set(True)
    view_layer.objects.active = o


def tick():
    if state["t0"] is None:
        if not os.path.exists(FLAG("go")):
            return 0.1
        state["t0"] = time.time()
    t = time.time() - state["t0"]
    set_view(t)
    if t >= T_RIG and state["rig"] == 0:
        arm.hide_set(False)
        select_only(arm)
        mode("POSE")
        state["rig"] = 1
    if t >= T_RIG_END and state["rig"] == 1:
        mode("OBJECT")
        arm.hide_set(True)
        state["rig"] = 2
    if state["edit"] and t >= state["edit"][1]:
        mode("OBJECT")
        state["edit"] = None
    while state["shown"] < len(ORDER) and t >= T_OUT + state["shown"] * STEP:
        name = ORDER[state["shown"]]
        state["shown"] += 1
        o = objs.get(name)
        if not o:
            continue
        o.hide_set(False)
        if state["edit"]:
            mode("OBJECT")
            state["edit"] = None
        select_only(o)
        if name in EDIT_PEEK:
            mode("EDIT")
            state["edit"] = (name, t + STEP * 0.9)
    if t >= T_MAT and not state["mat"]:
        mode("OBJECT")
        for s in bpy.context.selected_objects:
            s.select_set(False)
        win, area, region = ctx()
        sp = area.spaces.active
        sp.overlay.show_wireframes = False
        sp.shading.type = "MATERIAL"
        state["mat"] = True
    if t >= T_END:
        open(FLAG("done"), "w").write("1")
        bpy.ops.wm.quit_blender()
        return None
    return 1.0 / 30.0


def start():
    win, area, region = ctx()
    with bpy.context.temp_override(window=win, area=area, region=region):
        bpy.ops.wm.window_fullscreen_toggle()
    setup()
    bpy.app.timers.register(tick, first_interval=0.5)
    return None


bpy.app.timers.register(start, first_interval=2.0)
