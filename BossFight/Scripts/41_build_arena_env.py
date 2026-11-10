# Dresses L_Arena after the boss-arena concept (ArtSource/Landscape/landscape_boss_arena.jpg): a rune-carved stone
# disc on a cliff plateau, ruined gothic pillars, arches, dead trees, graves and banners, misty mountains, stormy dusk.
# Gameplay geometry is untouched: the floor disc keeps its collision, and the eight blockout pillars stay as invisible
# blockers (the Tripo pillars standing in their place have no collision), so movement, camera traces and the boss AI
# behave exactly as before. Everything added here is labelled "Env_" and is rebuilt on every run.
import math
import random
import unreal

eal = unreal.EditorAssetLibrary
les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
TRIPO = "/Game/BossFight/Env/Tripo"
LUSH = "/Game/LUSH_StylizedEnvironmentSet"
random.seed(7)


def log(*a):
    unreal.log("BUILD: " + " ".join(str(x) for x in a))


def find_mesh(name):
    for p in eal.list_assets("%s/%s" % (TRIPO, name), recursive=True, include_folder=False):
        a = unreal.load_asset(p)
        if isinstance(a, unreal.StaticMesh):
            return a
    log("missing mesh", name)
    return None


def spawn(cls, loc, rot=(0, 0, 0), label=None):
    a = eas.spawn_actor_from_class(cls, unreal.Vector(*loc), unreal.Rotator(pitch=rot[0], yaw=rot[1], roll=rot[2]))
    if label:
        a.set_actor_label(label)
    return a


def place(mesh, x, y, ground_z, yaw, height=None, width=None, label="Env", collide=False, sink=0.0):
    """Stands a mesh on ground_z at (x, y), scaled uniformly to the given height (or footprint width)."""
    if not mesh:
        return None
    b = mesh.get_bounding_box()
    size = b.max - b.min
    if height:
        s = height / max(size.z, 1.0)
    else:
        s = width / max(size.x, size.y, 1.0)
    cx, cy = (b.min.x + b.max.x) * 0.5 * s, (b.min.y + b.max.y) * 0.5 * s
    cs, sn = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    x, y = x - (cx * cs - cy * sn), y - (cx * sn + cy * cs)
    a = spawn(unreal.StaticMeshActor, (x, y, ground_z - b.min.z * s - sink), (0, yaw, 0), label)
    a.static_mesh_component.set_static_mesh(mesh)
    a.set_actor_scale3d(unreal.Vector(s, s, s))
    if not collide:
        a.static_mesh_component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    return a


def polar(r, deg):
    return r * math.cos(math.radians(deg)), r * math.sin(math.radians(deg))


les.load_level("/Game/BossFight/Maps/L_Arena")
for actor in eas.get_all_level_actors():
    if actor.get_actor_label().startswith("Env_"):
        eas.destroy_actor(actor)

# ---- Floor and pillars
floor_mat = unreal.load_asset("/Game/BossFight/Env/M_ArenaFloor")
for actor in eas.get_all_level_actors():
    label = actor.get_actor_label()
    if label == "Arena_Floor":
        actor.static_mesh_component.set_material(0, floor_mat)
    elif label.startswith("Pillar_"):
        actor.set_actor_hidden_in_game(True)
        actor.static_mesh_component.set_cast_shadow(False)
    elif label == "Abyss_Floor":
        actor.set_actor_hidden_in_game(True)

rune = find_mesh("arena_pillar_rune")
ruined = find_mesh("arena_pillar_ruined")
for i in range(8):
    x, y = polar(1700, i * 45)
    if i % 2 == 0:
        place(rune, x, y, 0, i * 45 + random.uniform(-20, 20), height=980, label="Env_PillarRune_%d" % i, sink=10)
    else:
        place(ruined, x, y, 0, i * 45 + random.uniform(-40, 40), height=random.uniform(640, 760), label="Env_PillarRuined_%d" % i, sink=10)

# ---- Cliff plateau under the disc: two rings of LUSH rocks, the top ring flush with the floor edge.
rocks = [unreal.load_asset(LUSH + "/Meshes/Rocks/SM_Rock_0%d" % k) for k in (1, 2, 3)]
for i in range(18):
    deg = i * 20 + random.uniform(-6, 6)
    x, y = polar(2080 + random.uniform(-60, 60), deg)
    a = place(random.choice(rocks), x, y, -1500, random.uniform(0, 360), height=random.uniform(1450, 1650), label="Env_CliffTop_%d" % i, collide=True)
for i in range(12):
    deg = i * 30 + 15 + random.uniform(-8, 8)
    x, y = polar(1650 + random.uniform(-100, 100), deg)
    place(random.choice(rocks), x, y, -3200, random.uniform(0, 360), height=random.uniform(1700, 2000), label="Env_CliffLow_%d" % i)

# ---- Rim props between the pillars (22.5 deg + 45 k), arches beyond the edge in front of / behind the fight.
tree = find_mesh("arena_tree_dead")
grave = find_mesh("arena_gravestone")
banner = find_mesh("arena_banner")
brazier = find_mesh("arena_brazier")
altar = find_mesh("arena_rune_altar")
arch = find_mesh("arena_arch")
slots = [(tree, 760, None), (grave, None, 380), (banner, 560, None), (brazier, None, 170),
         (tree, 820, None), (altar, None, 300), (grave, None, 360), (banner, 540, None)]
for k, (mesh, h, w) in enumerate(slots):
    deg = 22.5 + 45 * k
    x, y = polar(1880, deg)
    yaw = deg + 180 + random.uniform(-15, 15)
    place(mesh, x, y, 0, yaw, height=h, width=w, label="Env_Rim_%d" % k, sink=6)
for k, deg in enumerate((0, 180)):
    x, y = polar(2250, deg)
    place(arch, x, y, 0, deg + 90, height=1050, label="Env_Arch_%d" % k, sink=20)
    for side in (-1, 1):
        bx, by = polar(2150, deg + side * 9)
        place(brazier, bx, by, 0, random.uniform(0, 360), width=150, label="Env_ArchBrazier_%d_%d" % (k, side), sink=4)
# Dead trees and graves out on the cliff tops.
for i in range(7):
    deg = random.uniform(0, 360)
    x, y = polar(random.uniform(2350, 2700), deg)
    place(tree, x, y, -20, random.uniform(0, 360), height=random.uniform(700, 1100), label="Env_FarTree_%d" % i, sink=40)

# ---- Distant mountains, lost in the fog.
long_rock = unreal.load_asset(LUSH + "/Meshes/Rocks/SM_LongRock")
for i in range(14):
    deg = i * (360 / 14) + random.uniform(-8, 8)
    x, y = polar(random.uniform(16000, 24000), deg)
    place(random.choice(rocks + [long_rock]), x, y, -6000, random.uniform(0, 360), height=random.uniform(7000, 11000), label="Env_Mountain_%d" % i)

# ---- Stormy dusk: low cold-pink sun behind the boss side, dim blue sky light, dark heavy fog, volumetric clouds.
for actor in eas.get_all_level_actors():
    label = actor.get_actor_label()
    if label == "Sun":
        actor.set_actor_rotation(unreal.Rotator(pitch=-22, yaw=-150, roll=0), False)
        lc = actor.light_component
        lc.set_editor_property("intensity", 3.5)
        lc.set_editor_property("light_color", unreal.Color(r=215, g=200, b=255, a=255))
    elif label == "SkyLight":
        actor.light_component.set_editor_property("intensity", 1.3)
        actor.light_component.set_editor_property("light_color", unreal.Color(r=150, g=170, b=255, a=255))
    elif label == "Fog":
        fc = actor.get_component_by_class(unreal.ExponentialHeightFogComponent)
        fc.set_editor_property("fog_density", 0.02)
        fc.set_editor_property("fog_height_falloff", 0.15)
        fc.set_editor_property("fog_inscattering_luminance", unreal.LinearColor(0.05, 0.06, 0.11, 1.0))
        fc.set_editor_property("start_distance", 2000.0)
        fc.set_editor_property("enable_volumetric_fog", True)
        fc.set_editor_property("volumetric_fog_extinction_scale", 0.5)
        actor.set_actor_location(unreal.Vector(0, 0, -900), False, False)
pp = spawn(unreal.PostProcessVolume, (0, 0, 0), label="Env_PostProcess")
pp.set_editor_property("unbound", True)
ps = pp.get_editor_property("settings")
ps.set_editor_property("override_auto_exposure_bias", True)
ps.set_editor_property("auto_exposure_bias", 0.0)
ps.set_editor_property("override_vignette_intensity", True)
ps.set_editor_property("vignette_intensity", 0.55)
ps.set_editor_property("override_color_saturation", True)
ps.set_editor_property("color_saturation", unreal.Vector4(0.85, 0.9, 1.05, 1.0))
pp.set_editor_property("settings", ps)
cloud = spawn(unreal.VolumetricCloud, (0, 0, 0), label="Env_Clouds")
les.save_current_level()
log("arena env saved")
