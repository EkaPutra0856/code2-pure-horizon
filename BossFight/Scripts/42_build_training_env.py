# Dresses L_Training after the training-ground concept (ArtSource/Landscape/landscape_training.jpg): a worn dirt
# clearing in a flowery meadow, ruined ivy-covered stone walls, scarecrow dummies and weapon racks, big leafy trees,
# a stream on the right, rolling hills and hazy mountains under a warm afternoon sky.
# The training dummy, player start and game mode are untouched. The floor disc grows to a 45 m meadow, the blockout
# pillars go away (they have no place here), and an invisible ring wall keeps the player inside the dressed area.
# Everything added here is labelled "Env_" and is rebuilt on every run.
import math
import random
import unreal

eal = unreal.EditorAssetLibrary
les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
TRIPO = "/Game/BossFight/Env/Tripo"
LUSH = "/Game/LUSH_StylizedEnvironmentSet"
CENTER = (-400.0, 0.0)  # middle of the dirt clearing (matches M_TrainGround's Center)
CLEAR_R = 1100.0
WALL_R = 3800.0
random.seed(11)


def log(*a):
    unreal.log("BUILD: " + " ".join(str(x) for x in a))


LUSH_ASSETS = {}
for p in eal.list_assets(LUSH, recursive=True, include_folder=False):
    LUSH_ASSETS[p.split("/")[-1].split(".")[0]] = p


def lush(name):
    p = LUSH_ASSETS.get(name)
    if not p:
        log("missing lush", name)
        return None
    return unreal.load_asset(p)


def tripo(name):
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


def fit_scale(mesh, height=None, width=None):
    b = mesh.get_bounding_box()
    size = b.max - b.min
    if height:
        return height / max(size.z, 1.0), b
    return width / max(size.x, size.y, 1.0), b


def place(mesh, x, y, ground_z, yaw, height=None, width=None, label="Env", collide=False, sink=0.0):
    """Stands a mesh on ground_z at (x, y), scaled uniformly to the given height (or footprint width)."""
    if not mesh:
        return None
    s, b = fit_scale(mesh, height, width)
    cx, cy = (b.min.x + b.max.x) * 0.5 * s, (b.min.y + b.max.y) * 0.5 * s
    cs, sn = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    x, y = x - (cx * cs - cy * sn), y - (cx * sn + cy * cs)
    a = spawn(unreal.StaticMeshActor, (x, y, ground_z - b.min.z * s - sink), (0, yaw, 0), label)
    a.static_mesh_component.set_static_mesh(mesh)
    a.set_actor_scale3d(unreal.Vector(s, s, s))
    if not collide:
        a.static_mesh_component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    return a


def shape(path, loc, scale, label, mat=None, yaw=0.0, collide=False):
    a = spawn(unreal.StaticMeshActor, loc, (0, yaw, 0), label)
    a.static_mesh_component.set_static_mesh(unreal.load_asset(path))
    a.set_actor_scale3d(unreal.Vector(*scale))
    if mat:
        a.static_mesh_component.set_material(0, mat)
    if not collide:
        a.static_mesh_component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    return a


def scatter(label, mesh, points, size_range, by_height=True, sink=0.0, cull=0.0, shadow=True):
    """One instanced actor for many copies of a small mesh standing on z=0."""
    if not mesh or not points:
        return
    xs = []
    for (x, y) in points:
        target = random.uniform(*size_range)
        s, b = fit_scale(mesh, target if by_height else None, None if by_height else target)
        xs.append(unreal.Transform(unreal.Vector(x, y, -b.min.z * s - sink),
                                   unreal.Rotator(pitch=0, yaw=random.uniform(0, 360), roll=0),
                                   unreal.Vector(s, s, s)))
    unreal.BFEditorTools.spawn_instanced_mesh_actor(label, mesh, xs, False, cull * 0.8, cull, shadow)
    log("scatter", label, len(xs))


def polar(r, deg, c=(0.0, 0.0)):
    return c[0] + r * math.cos(math.radians(deg)), c[1] + r * math.sin(math.radians(deg))


def river_y(x):
    # A stream winding down the right-hand side (+Y is screen-right when the player faces the dummy).
    return 2500.0 + 520.0 * math.sin(x / 1700.0 + 0.6) + 260.0 * math.sin(x / 640.0)


RIVER_W = 420.0


def in_clearing(x, y, pad=0.0):
    return math.hypot(x - CENTER[0], y - CENTER[1]) < CLEAR_R + pad


def in_river(x, y, pad=0.0):
    return abs(y - river_y(x)) < RIVER_W * 0.5 + pad


les.load_level("/Game/BossFight/Maps/L_Training")
for actor in eas.get_all_level_actors():
    if actor.get_actor_label().startswith("Env_"):
        eas.destroy_actor(actor)

# ---- Ground: the floor disc becomes a 45 m meadow; a big lower disc carries the grass out to the hills.
ground_mat = unreal.load_asset("/Game/BossFight/Env/M_TrainGround")
for actor in eas.get_all_level_actors():
    label = actor.get_actor_label()
    if label == "Arena_Floor":
        actor.set_actor_scale3d(unreal.Vector(90, 90, 1))
        actor.static_mesh_component.set_material(0, ground_mat)
    elif label.startswith("Pillar_"):
        actor.set_actor_hidden_in_game(True)
        actor.set_is_temporarily_hidden_in_editor(True)
        actor.static_mesh_component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        actor.static_mesh_component.set_cast_shadow(False)
    elif label == "Abyss_Floor":
        actor.set_actor_hidden_in_game(True)
shape("/Engine/BasicShapes/Cylinder", (0, 0, -56), (700, 700, 1), "Env_OuterGround", ground_mat)

# Invisible ring wall (player only; the camera passes through).
for i in range(36):
    deg = i * 10
    x, y = polar(WALL_R, deg)
    w = shape("/Engine/BasicShapes/Cube", (x, y, 250), (1.0, 2 * math.pi * WALL_R / 36 / 100 + 0.3, 6), "Env_Bounds_%d" % i, yaw=deg, collide=True)
    w.set_actor_hidden_in_game(True)
    w.static_mesh_component.set_cast_shadow(False)
    w.static_mesh_component.set_collision_profile_name("InvisibleWall")
    w.static_mesh_component.set_collision_response_to_channel(unreal.CollisionChannel.ECC_CAMERA, unreal.CollisionResponseType.ECR_IGNORE)

# ---- Rolling hills (squashed spheres) and hazy mountains, with the valley open straight ahead (+X).
sphere = "/Engine/BasicShapes/Sphere"
hills = [(-30, 6200, 90, 55, 14), (-62, 5600, 70, 45, 11), (-100, 6400, 110, 60, 16), (-150, 6800, 120, 70, 15),
         (160, 7000, 120, 70, 14), (115, 6300, 100, 55, 13), (70, 6600, 80, 50, 10), (35, 7600, 90, 55, 9),
         (12, 9800, 110, 60, 10), (-12, 10200, 120, 60, 11), (200, 6500, 110, 60, 12), (-180, 6000, 100, 60, 12)]
for k, (deg, r, sx, sy, sz) in enumerate(hills):
    x, y = polar(r, deg)
    shape(sphere, (x, y, -sz * 18), (sx, sy, sz), "Env_Hill_%d" % k, ground_mat, yaw=deg + 90)
rocks = [lush("SM_Rock_01"), lush("SM_Rock_02"), lush("SM_Rock_03")]
for i in range(16):
    deg = i * (360 / 16) + random.uniform(-6, 6)
    x, y = polar(random.uniform(22000, 30000), deg)
    place(random.choice(rocks), x, y, -2500, random.uniform(0, 360), height=random.uniform(6000, 9500), label="Env_Mountain_%d" % i)

# ---- Stream: water strips following the curve, stones along both banks.
water = lush("SM_WaterSurface")
river_mat = unreal.load_asset("/Game/BossFight/Env/M_RiverWater")
if water:
    wb = water.get_bounding_box()
    wsize = wb.max - wb.min
    step = 300.0
    x = -9000.0
    k = 0
    while x < 9000.0:
        y0, y1 = river_y(x), river_y(x + step)
        yaw = math.degrees(math.atan2(y1 - y0, step))
        length = math.hypot(step, y1 - y0) * 1.04
        a = spawn(unreal.StaticMeshActor, (x + step * 0.5, (y0 + y1) * 0.5, 3), (0, yaw, 0), "Env_River_%d" % k)
        a.static_mesh_component.set_static_mesh(water)
        a.static_mesh_component.set_material(0, river_mat)
        a.set_actor_scale3d(unreal.Vector(length / max(wsize.x, 1), RIVER_W / max(wsize.y, 1), 1))
        a.static_mesh_component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        x += step
        k += 1
bank = []
x = -6000.0
while x < 6000.0:
    for side in (-1, 1):
        if random.random() < 0.7:
            bank.append((x + random.uniform(-60, 60), river_y(x) + side * (RIVER_W * 0.5 + random.uniform(-10, 40))))
    x += 110.0
random.shuffle(bank)
for k, name in enumerate(("SM_Stone_A_01", "SM_Stone_A_02", "SM_Stone_B_01", "SM_Stone_B_02")):
    scatter("Env_Bank" + name[3:], lush(name), bank[k::4], (35, 80), by_height=False, sink=8, cull=12000)

# ---- Ruined stone walls in broken arcs around the clearing, ivy bushes along them.
stone_sets = [lush("SM_StoneSet_A"), lush("SM_StoneSet_B")]
bushes = [lush(n) for n in ("SM_Bush_Medium_01", "SM_Bush_Medium_02", "SM_Bush_Medium_03", "SM_Bush_Medium_04")]
k = 0
for (a0, a1) in ((105, 165), (195, 250), (285, 330), (20, 62)):
    deg = a0
    while deg <= a1:
        x, y = polar(CLEAR_R + 320 + random.uniform(-30, 30), deg, CENTER)
        place(random.choice(stone_sets), x, y, 0, deg + 90 + random.uniform(-12, 12), width=random.uniform(230, 300), label="Env_Wall_%d" % k, collide=True, sink=6)
        if random.random() < 0.55:
            bx, by = polar(CLEAR_R + 380 + random.uniform(0, 60), deg + random.uniform(-3, 3), CENTER)
            place(random.choice(bushes), bx, by, 0, random.uniform(0, 360), height=random.uniform(90, 150), label="Env_WallBush_%d" % k, sink=10)
        deg += 9.5
        k += 1

# ---- Training props (Tripo): scarecrows and racks on the left, fence and crates at the back.
scarecrow = tripo("train_dummy")
rack = tripo("train_weapon_rack")
fence = tripo("train_fence")
crates = tripo("train_crates")
for k, deg in enumerate((235, 262, 300)):
    x, y = polar(860, deg, CENTER)
    place(scarecrow, x, y, 0, deg + 180 + random.uniform(-10, 10), height=200, label="Env_Scarecrow_%d" % k, collide=True, sink=8)
for k, deg in enumerate((248, 283)):
    x, y = polar(1010, deg, CENTER)
    place(rack, x, y, 0, deg + 180, height=170, label="Env_Rack_%d" % k, collide=True, sink=4)
for k in range(5):
    deg = 18 + k * 10.5
    x, y = polar(CLEAR_R + 650, deg, CENTER)
    place(fence, x, y, 0, deg + 90, width=330, label="Env_Fence_%d" % k, collide=True, sink=6)
x, y = polar(1050, 72, CENTER)
place(crates, x, y, 0, 200, width=260, label="Env_Crates_0", collide=True, sink=4)
x, y = polar(1150, 190, CENTER)
place(crates, x, y, 0, 40, width=220, label="Env_Crates_1", collide=True, sink=4)

# ---- Trees: a big oak at the back-left of the clearing, a few around it, a tree line on the hills.
trees = [lush("SM_Tree_Large_01"), lush("SM_Tree_Medium_01"), lush("SM_Tree_Medium_02")]
hero_trees = [(225, 1900, 0, 1500), (160, 2500, 1, 1100), (35, 2300, 2, 1150), (330, 2600, 1, 1050),
              (95, 2700, 2, 1000), (270, 2800, 0, 1300), (190, 3200, 2, 1150)]
for k, (deg, r, t, h) in enumerate(hero_trees):
    x, y = polar(r, deg, CENTER)
    if in_river(x, y, 250):
        y -= 600
    place(trees[t], x, y, 0, random.uniform(0, 360), height=h, label="Env_Tree_%d" % k, collide=True, sink=20)
for k in range(26):
    deg = random.choice((random.uniform(-160, -40), random.uniform(60, 170)))
    x, y = polar(random.uniform(4300, 7000), deg)
    place(random.choice(trees), x, y, -10, random.uniform(0, 360), height=random.uniform(1000, 1600), label="Env_FarTree_%d" % k, sink=30)
bush_pts = []
while len(bush_pts) < 40:
    x, y = polar(random.uniform(1700, 3700), random.uniform(0, 360))
    if not in_river(x, y, 120) and not in_clearing(x, y, 400):
        bush_pts.append((x, y))
for k, (x, y) in enumerate(bush_pts):
    place(random.choice(bushes + [lush("SM_Bush_Large")]), x, y, 0, random.uniform(0, 360), height=random.uniform(100, 220), label="Env_Bush_%d" % k, sink=12)

# ---- Grass and wildflowers (instanced), kept off the clearing and the water.
def meadow_points(n, rmin, rmax, clear_pad, river_pad):
    pts = []
    while len(pts) < n:
        x, y = polar(math.sqrt(random.uniform(rmin * rmin, rmax * rmax)), random.uniform(0, 360))
        if not in_clearing(x, y, clear_pad + random.uniform(-80, 80)) and not in_river(x, y, river_pad):
            pts.append((x, y))
    return pts


grass = lush("SM_Grass_Generic")
pts = meadow_points(7000, 0, 5200, 40, 10)
scatter("Env_Grass", grass, pts, (35, 70), sink=2, cull=7000, shadow=False)
tiny = lush("SM_Grass_Tiny")
scatter("Env_GrassTiny", tiny, meadow_points(3000, 0, 3800, -150, 0), (15, 30), sink=1, cull=4000, shadow=False)
for name in ("SM_FlowerClump_A_01", "SM_FlowerClump_A_02", "SM_FlowerClump_B_01", "SM_FlowerClump_B_02",
             "SM_FlowerClump_C_01", "SM_FlowerClump_C_02", "SM_FlowerClump_D_01", "SM_FlowerClump_D_02"):
    pts = []
    for _ in range(8):  # patches
        cx, cy = polar(random.uniform(1500, 4800), random.uniform(0, 360))
        for _ in range(28):
            x, y = cx + random.gauss(0, 260), cy + random.gauss(0, 260)
            if not in_clearing(x, y, 120) and not in_river(x, y, 30):
                pts.append((x, y))
    scatter("Env_" + name[3:], lush(name), pts, (25, 45), sink=2, cull=6000, shadow=False)

# ---- Warm afternoon: sun low behind the right, soft blue sky, light haze, puffy clouds.
for actor in eas.get_all_level_actors():
    label = actor.get_actor_label()
    if label == "Sun":
        actor.set_actor_rotation(unreal.Rotator(pitch=-26, yaw=-140, roll=0), False)
        lc = actor.light_component
        lc.set_editor_property("intensity", 7.0)
        lc.set_editor_property("light_color", unreal.Color(r=255, g=228, b=196, a=255))
    elif label == "SkyLight":
        actor.light_component.set_editor_property("intensity", 1.2)
    elif label == "Fog":
        fc = actor.get_component_by_class(unreal.ExponentialHeightFogComponent)
        fc.set_editor_property("fog_density", 0.012)
        fc.set_editor_property("fog_height_falloff", 0.15)
        fc.set_editor_property("fog_inscattering_luminance", unreal.LinearColor(0.45, 0.55, 0.75, 1.0))
        fc.set_editor_property("start_distance", 3000.0)
spawn(unreal.VolumetricCloud, (0, 0, 0), label="Env_Clouds")
les.save_current_level()
log("training env saved")
