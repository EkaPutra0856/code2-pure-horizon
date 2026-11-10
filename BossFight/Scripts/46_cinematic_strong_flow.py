# Stronger, visible river current in L_Cinematic only (the scenery film); L_Arena keeps the calm river of 45_fluidflux_river.py.
#  - Env_FluxSource: more water and a harder downstream push.
#  - Env_FluxDrain: drains harder so the water keeps moving instead of pooling.
#  - Env_FluxPush_*: velocity-only modifiers along the channel (through the court) that push the water downstream.
# Re-runnable: Env_FluxPush_* are rebuilt each run.
import math
import unreal

les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
FF = "/Game/FluidFlux"
ADD = "NewEnumerator0"
RECT = "NewEnumerator0"
SOURCE_VELOCITY = "(X=-10.0,Y=0)"
SOURCE_VOLUME = "0.8"
DRAIN_VOLUME = "-60"
PUSH_VELOCITY = "(X=-7.0,Y=0)"
PUSH_AT = (2200.0, 900.0, -400.0, -1700.0, -3000.0)


def log(*a):
    unreal.log("BUILD: " + " ".join(str(x) for x in a))


def river_y(x):
    return 0.37 * x + 300.0 * math.sin(x / 1100.0)


def river_w(x):
    t = min(max((abs(x) - 1500.0) / 600.0, 0.0), 1.0)
    return 1350.0 + (760.0 - 1350.0) * t


def river_yaw(x):
    return math.degrees(math.atan2(river_y(x + 20) - river_y(x - 20), 40.0))


def source_comp(a):
    for c in a.get_components_by_class(unreal.SceneComponent):
        if c.get_name() == "FluxModifierSource":
            return c
    return None


def set_values(a, values):
    for name, text in values:
        c = source_comp(a)  # construction script replaces it after every change
        if not c or not unreal.BFEditorTools.set_property_text(c, name, text):
            log("set failed", a.get_actor_label(), name, text)
    c = source_comp(a)
    log(a.get_actor_label(), unreal.BFEditorTools.dump_properties(c, True).replace("\n", " | ")[:400])


les.load_level("/Game/BossFight/Maps/L_Cinematic")
cls = unreal.EditorAssetLibrary.load_blueprint_class(FF + "/Simulation/Modifiers/BP_FluxModifierSourceActor")
for actor in eas.get_all_level_actors():
    label = actor.get_actor_label()
    if label.startswith("Env_FluxPush_"):
        eas.destroy_actor(actor)
for actor in eas.get_all_level_actors():
    label = actor.get_actor_label()
    if label == "Env_FluxSource":
        set_values(actor, (("Volume", SOURCE_VOLUME), ("Velocity", SOURCE_VELOCITY)))
    elif label == "Env_FluxDrain":
        set_values(actor, (("Volume", DRAIN_VOLUME),))

for i, x in enumerate(PUSH_AT):
    z = 0.0 if abs(x) < 2500 else 0.0
    a = eas.spawn_actor_from_class(cls, unreal.Vector(x, river_y(x), z + 8.0), unreal.Rotator(pitch=0, yaw=river_yaw(x), roll=0))
    a.set_actor_label("Env_FluxPush_%d" % i)
    c = source_comp(a)
    if c:
        c.set_relative_scale3d(unreal.Vector(500.0, river_w(x) - 80.0, 100.0))
    set_values(a, (("Mode", ADD), ("Shape", RECT), ("Volume", "0"), ("Edge", "10"), ("Velocity", PUSH_VELOCITY)))
les.save_current_level()
log("strong flow done")
