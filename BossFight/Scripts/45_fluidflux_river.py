# Adds the Fluid Flux river to L_Arena (run after 43_build_arena_twilight.py, which lays the channel: sunken bed slabs
# and the raised court). Pieces, all labelled "Env_Flux*" / "Env_Bank*" and rebuilt on every run:
#  - earth banks along the channel outside the court, on the terrace and on the plateau, so the water stays in the
#    river bed (the simulation reads the ground from a top-down height capture, so any visible mesh shapes the flow);
#  - BP_FluxSimulationDomain covering the river from the plateau source to the drain, with its BP_FluxSurface_River;
#  - a source on the plateau (Adjust mode: keeps the water there at the source height) that spills over both falls;
#  - a one-shot fill of the court channel so the river is already running when the fight starts;
#  - a drain at the downstream end.
# Fluid Flux modifier enums: BE_FluxMode 0 Add, 1 Set, 5 Adjust. BE_FluxShape 0 Rect, 1 Circle, 3 Fill.
import math
import unreal

les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
FF = "/Game/FluidFlux"
ARENA_R = 2000.0
PLATEAU_Z, TERRACE_Z = 223.0, 112.0
FALL_LOW, FALL_HIGH = 2545.0, 2905.0
# Simulation area: 512 x 256 cells of 16 cm, from x -4696 to 3496.
DOMAIN_CENTER = (-600.0, -85.0)
CELL = 16.0
RES = (512, 256)
DOMAIN_TOP, DOMAIN_HEIGHT = 650.0, 1000.0
SOURCE_X, DRAIN_X, END_X = 3300.0, -4450.0, 3460.0


def log(*a):
    unreal.log("BUILD: " + " ".join(str(x) for x in a))


def river_y(x):
    return 0.37 * x + 300.0 * math.sin(x / 1100.0)


def river_w(x):
    t = min(max((abs(x) - 1500.0) / 600.0, 0.0), 1.0)
    return 1350.0 + (760.0 - 1350.0) * t


def river_yaw(x):
    return math.degrees(math.atan2(river_y(x + 20) - river_y(x - 20), 40.0))


def ground_z(x, y):
    if x > FALL_HIGH:
        return PLATEAU_Z
    if x > FALL_LOW:
        return TERRACE_Z
    r = math.hypot(x, y)
    return 0.0 if r < ARENA_R else (-3.0 if r < 2600 else -7.0)


def spawn(cls, loc, rot=(0, 0, 0), label=None):
    a = eas.spawn_actor_from_class(cls, unreal.Vector(*loc), unreal.Rotator(pitch=rot[0], yaw=rot[1], roll=rot[2]))
    if label:
        a.set_actor_label(label)
    return a


def bp(path):
    c = unreal.EditorAssetLibrary.load_blueprint_class(path)
    if not c:
        log("missing class", path)
    return c


def setp(obj, name, value):
    try:
        obj.set_editor_property(name, value)
        return True
    except Exception as e:
        log("set failed", obj.get_name(), name, e)
        return False


def cube(loc, scale, yaw, label, mat):
    a = spawn(unreal.StaticMeshActor, loc, (0, yaw, 0), label)
    c = a.static_mesh_component
    c.set_static_mesh(unreal.load_asset("/Engine/BasicShapes/Cube"))
    a.set_actor_scale3d(unreal.Vector(*scale))
    c.set_material(0, mat)
    c.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    return a


les.load_level("/Game/BossFight/Maps/L_Arena")
for actor in eas.get_all_level_actors():
    label = actor.get_actor_label()
    if label.startswith("Env_Flux") or label.startswith("Env_Bank"):
        eas.destroy_actor(actor)

# ---- Earth banks: 40 cm berms along both sides of the channel wherever the raised court does not already hold it.
mud = unreal.load_asset("/Game/BossFight/Env/M_Mud")
stops = [-4700.0]
x = -4700.0
while x < END_X:
    x = min(x + 180.0, END_X)
    for b in (FALL_LOW, FALL_HIGH):
        if stops[-1] < b < x:
            stops.append(b)
    stops.append(x)
n = 0
for x0, x1 in zip(stops[:-1], stops[1:]):
    xm = (x0 + x1) * 0.5
    for side in (-1, 1):
        off = river_w(xm) * 0.5 + 75.0
        p0 = (x0, river_y(x0) + side * off)
        p1 = (x1, river_y(x1) + side * off)
        mx, my = (p0[0] + p1[0]) * 0.5, (p0[1] + p1[1]) * 0.5
        if math.hypot(mx, my) < ARENA_R - 150:
            continue
        length = math.hypot(p1[0] - p0[0], p1[1] - p0[1]) + 40.0
        yaw = math.degrees(math.atan2(p1[1] - p0[1], p1[0] - p0[0]))
        gz = ground_z(xm + 1.0, my)
        cube((mx, my, gz + 14.0), (length / 100.0, 1.6, 0.48), yaw, "Env_Bank_%d" % n, mud)
        n += 1
# Close the channel upstream of the source on the plateau.
cube((END_X + 40, river_y(END_X), PLATEAU_Z + 20.0), (1.6, (river_w(END_X) + 420) / 100.0, 0.8), river_yaw(END_X), "Env_Bank_End", mud)
log("banks", n + 1)

# ---- Simulation domain and river surface.
domain_loc = (DOMAIN_CENTER[0], DOMAIN_CENTER[1], DOMAIN_TOP)
size = unreal.Vector2D(RES[0] * CELL, RES[1] * CELL)
surface = spawn(bp(FF + "/Surface/Templates/River/BP_FluxSurface_River"), domain_loc, label="Env_FluxSurface")
domain = spawn(bp(FF + "/Simulation/Blueprints/BP_FluxSimulationDomain"), domain_loc, label="Env_FluxDomain")
setp(domain, "AreaResolution", unreal.IntPoint(RES[0], RES[1]))
setp(domain, "AreaWorldPixelSize", CELL)
setp(domain, "AreaWorldHeight", DOMAIN_HEIGHT)
setp(domain, "SurfaceActorReference", surface)
for actor in eas.get_all_level_actors():
    if actor.get_actor_label() == "SkyLight":
        setp(surface, "Skylight", actor)
# Visible blue-teal river. The court channel is only ~8 cm deep, and the stock presets absorb over 70-330 cm,
# so they read as bare wet floor (the user could not see the water). CP_ArenaRiver is CP_RiverBlue with short
# absorption distances and stronger scattering.
PRESET = "/Game/BossFight/Env/CP_ArenaRiver"
eal = unreal.EditorAssetLibrary
if not eal.does_asset_exist(PRESET):
    eal.duplicate_asset(FF + "/Surface/Templates/Color/CP_RiverBlue", PRESET)
preset = unreal.load_asset(PRESET)
for name, text in (("Absorption", "(R=7.0,G=16.0,B=26.0,A=2.5)"), ("Scattering", "(R=0.04,G=0.32,B=0.45,A=0.004)"),
                   ("Overlay", "(R=0.05,G=0.35,B=0.45,A=0.004)"), ("Clarity", "0.8")):
    if not unreal.BFEditorTools.set_property_text(preset, name, text):
        log("preset set failed", name)
eal.save_loaded_asset(preset)
setp(surface, "BaseColorPreset", preset)

# Ripple solver for the characters' footsteps (BP_FluxInteractionComponent, added to them at BeginPlay), over the court.
RIPPLE_AREA = 4096.0
cap = spawn(bp(FF + "/Interaction/Blueprints/BP_FluxInteractionCapture"), (0.0, 0.0, 520.0), label="Env_FluxRipples")
if not unreal.BFEditorTools.set_property_text(cap, "AreaSize", str(RIPPLE_AREA)):
    log("set failed ripples AreaSize")
cap.set_actor_scale3d(unreal.Vector(RIPPLE_AREA / 100.0, RIPPLE_AREA / 100.0, 1000.0))


def source_comp(a):
    # Each property change re-runs the actor's construction script, which replaces this component; fetch it fresh.
    for c in a.get_components_by_class(unreal.SceneComponent):
        if c.get_name() == "FluxModifierSource":
            return c
    return None


def modifier(label, loc, yaw, scale, values):
    """Spawns a BP_FluxModifierSourceActor; values are property texts for its source component."""
    a = spawn(bp(FF + "/Simulation/Modifiers/BP_FluxModifierSourceActor"), loc, (0, yaw, 0), label)
    if not source_comp(a):
        log("no source component on", label)
        return a
    source_comp(a).set_relative_scale3d(unreal.Vector(*scale))
    for name, text in values:
        if not unreal.BFEditorTools.set_property_text(source_comp(a), name, text):
            log("set failed", label, name, text)
    c = source_comp(a)
    log(label, " ".join("%s=%s" % (n, c.get_editor_property(n)) for n, _ in values), "scale", c.get_editor_property("relative_scale3d"))
    return a


ADD, ADJUST = "NewEnumerator0", "NewEnumerator5"
RECT, FILL = "NewEnumerator0", "NewEnumerator3"
modifier("Env_FluxSource", (SOURCE_X, river_y(SOURCE_X), PLATEAU_Z + 30.0), river_yaw(SOURCE_X),
         (260.0, river_w(SOURCE_X) - 60.0, 200.0),
         (("Mode", ADJUST), ("Shape", RECT), ("Volume", "0.1"), ("Edge", "10"), ("Velocity", "(X=-0.6,Y=0)")))
modifier("Env_FluxFill", (0.0, river_y(0.0), 8.0), river_yaw(0.0), (3600.0, 1400.0, 100.0),
         (("Mode", ADJUST), ("Shape", FILL), ("Volume", "0"), ("Edge", "10"), ("Duration", "0"), ("RemoveAfterUpdate", "True")))
modifier("Env_FluxDrain", (DRAIN_X, river_y(DRAIN_X), 0.0), river_yaw(DRAIN_X), (300.0, river_w(DRAIN_X) + 200.0, 200.0),
         (("Mode", ADD), ("Shape", RECT), ("Volume", "-8"), ("Edge", "1")))

# Report how the pieces wired up.
for name in ("AreaResolution", "AreaWorldSize", "AreaWorldPixelSize", "AreaWorldHeight", "SurfaceActorReference"):
    try:
        log("domain", name, domain.get_editor_property(name))
    except Exception as e:
        log("domain get failed", name, e)
for name in ("DomainSize", "SimulationState"):
    try:
        log("surface", name, surface.get_editor_property(name))
    except Exception as e:
        log("surface get failed", name, e)
les.save_current_level()
log("fluid flux river saved")
