# Rebuilds L_Arena after the twilight flooded-temple concept (ArtSource/Landscape/boss_ref_C2.jpg): a round court of
# cracked stone slabs that a shallow river floods on its way through, glowing teal hexagram rune circle under the water,
# mossy ruined pillars, a collapsed temple gate, stepped waterfalls behind, cherry blossom trees, warm lanterns,
# fireflies and low mist under a purple-orange sky with a big moon.
# Built from the project's own packs (Dreamscape Tower, LUSH, Tripo props). The river is a live Fluid Flux
# shallow-water simulation: a source on the plateau feeds two falls, the water runs through a channel across the
# court and drains at the far end. The channel bed is Arena_Floor (top 0); the dry court is a raised floor of stone
# slabs (top +14, with collision) and earth banks guide the water outside the court.
# Arena_Floor (r 20 m) keeps its collision and the hidden Pillar_* blockers stay where the Tripo pillars stand.
# Only the court slabs collide; everything else added has no collision. Everything added is labelled "Env_".
import math
import random
import unreal

eal = unreal.EditorAssetLibrary
les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
DS = "/Game/DreamscapeSeries/DreamscapeTower"
DSR = "/Game/DreamscapeSeries/SharedResources"
TRIPO = "/Game/BossFight/Env/Tripo"
ENV = "/Game/BossFight/Env"
ARENA_R = 2000.0
random.seed(23)


def log(*a):
    unreal.log("BUILD: " + " ".join(str(x) for x in a))


def asset(path):
    a = unreal.load_asset(path)
    if not a:
        log("missing", path)
    return a


def ds(sub, name):
    return asset("%s/%s/%s" % (DS, sub, name))


def tripo(name):
    for p in eal.list_assets("%s/%s" % (TRIPO, name), recursive=True, include_folder=False):
        a = unreal.load_asset(p)
        if isinstance(a, unreal.StaticMesh):
            return a
    log("missing tripo", name)
    return None


def spawn(cls, loc, rot=(0, 0, 0), label=None):
    a = eas.spawn_actor_from_class(cls, unreal.Vector(*loc), unreal.Rotator(pitch=rot[0], yaw=rot[1], roll=rot[2]))
    if label:
        a.set_actor_label(label)
    return a


def fit(mesh, height=None, width=None):
    b = mesh.get_bounding_box()
    size = b.max - b.min
    if height:
        return height / max(size.z, 1.0), b
    return width / max(size.x, size.y, 1.0), b


def place(mesh, x, y, ground_z, yaw, height=None, width=None, scale=None, label="Env", sink=0.0, mats=None, shadow=True):
    """Stands a mesh on ground_z centred on (x, y); uniform scale from height/width/scale. No collision."""
    if not mesh:
        return None
    if scale:
        s, b = scale, mesh.get_bounding_box()
    else:
        s, b = fit(mesh, height, width)
    cx, cy = (b.min.x + b.max.x) * 0.5 * s, (b.min.y + b.max.y) * 0.5 * s
    cs, sn = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    x, y = x - (cx * cs - cy * sn), y - (cx * sn + cy * cs)
    a = spawn(unreal.StaticMeshActor, (x, y, ground_z - b.min.z * s - sink), (0, yaw, 0), label)
    c = a.static_mesh_component
    c.set_static_mesh(mesh)
    a.set_actor_scale3d(unreal.Vector(s, s, s))
    c.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    c.set_cast_shadow(shadow)
    for slot, mat in (mats or {}).items():
        c.set_material(slot, mat)
    return a


def shape(path, loc, scale, label, mat=None, rot=(0, 0, 0), shadow=True):
    a = spawn(unreal.StaticMeshActor, loc, rot, label)
    c = a.static_mesh_component
    c.set_static_mesh(asset(path))
    a.set_actor_scale3d(unreal.Vector(*scale))
    if mat:
        c.set_material(0, mat)
    c.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    c.set_cast_shadow(shadow)
    return a


def scatter(label, mesh, points, size_range, by_height=True, z=0.0, sink=0.0, cull=0.0, shadow=False, random_yaw=True, yaw_step=0.0):
    if not mesh or not points:
        return
    xs = []
    for (x, y) in points:
        s, b = fit(mesh, *((random.uniform(*size_range), None) if by_height else (None, random.uniform(*size_range))))
        yaw = random.uniform(0, 360) if random_yaw else random.randint(0, 3) * yaw_step
        xs.append(unreal.Transform(unreal.Vector(x, y, z - b.min.z * s - sink),
                                   unreal.Rotator(pitch=0, yaw=yaw, roll=0), unreal.Vector(s, s, s)))
    unreal.BFEditorTools.spawn_instanced_mesh_actor(label, mesh, xs, False, cull * 0.8, cull, shadow)
    log("scatter", label, len(xs))


def emitter(path, loc, label, scale=1.0):
    ps = asset(path)
    if not ps:
        return None
    a = eas.spawn_actor_from_object(ps, unreal.Vector(*loc))
    a.set_actor_label(label)
    a.set_actor_scale3d(unreal.Vector(scale, scale, scale))
    return a


def polar(r, deg, c=(0.0, 0.0)):
    return c[0] + r * math.cos(math.radians(deg)), c[1] + r * math.sin(math.radians(deg))


# ---- River path: from the waterfalls at the back right (+X, +Y) through the court to the front left.
def river_y(x):
    return 0.37 * x + 300.0 * math.sin(x / 1100.0)


def river_w(x):
    # Wide through the court, narrowing to the outer channel near the court edge.
    t = min(max((abs(x) - 1500.0) / 600.0, 0.0), 1.0)
    return 1350.0 + (760.0 - 1350.0) * t


def river_z(x):
    if x > 2900:
        return 222.0
    if x > 2550:
        return 112.0
    return 4.0 if abs(x) < ARENA_R else -1.0


def in_river(x, y, pad=0.0):
    return abs(y - river_y(x)) < river_w(x) * 0.5 + pad


les.load_level("/Game/BossFight/Maps/L_Arena")
for actor in eas.get_all_level_actors():
    label = actor.get_actor_label()
    if label.startswith("Env_") or isinstance(actor, (unreal.SkyAtmosphere, unreal.VolumetricCloud)):
        eas.destroy_actor(actor)

mud = asset(ENV + "/M_Mud")
grass_ground = asset(ENV + "/M_TrainGround")
for actor in eas.get_all_level_actors():
    label = actor.get_actor_label()
    if label == "Arena_Floor":
        actor.static_mesh_component.set_material(0, mud)
    elif label.startswith("Pillar_"):
        actor.set_actor_hidden_in_game(True)
        actor.set_is_temporarily_hidden_in_editor(True)
        actor.static_mesh_component.set_cast_shadow(False)
    elif label == "Abyss_Floor":
        actor.set_actor_hidden_in_game(True)

# ---- Ground around the court: wet mud ring, then grass out to the forest.
shape("/Engine/BasicShapes/Cylinder", (0, 0, -53), (52, 52, 1), "Env_MudRing", mud)
shape("/Engine/BasicShapes/Cylinder", (0, 0, -57), (900, 900, 1), "Env_OuterGround", grass_ground)

# ---- Court floor: cracked stone slabs (Dreamscape floor tiles), instanced. Slabs beside the river form the raised dry
# court (top +14 cm, with collision, so the river channel between them is 14 cm deep); slabs in the channel lie
# sunken under the water (top about +1, no collision).
COURT_Z = 14.0
floors = [ds("Meshes/Structures", n) for n in ("SM_Floor_01", "SM_Floor_03")]
tiles = {(0, True): [], (1, True): [], (0, False): [], (1, False): []}
step = 400.0
gx = -ARENA_R - 200
while gx <= ARENA_R + 200:
    gy = -ARENA_R - 200
    while gy <= ARENA_R + 200:
        x, y = gx + random.uniform(-25, 25), gy + random.uniform(-25, 25)
        court = not in_river(x, y, 50)
        if math.hypot(x, y) < (ARENA_R + 60 if court else ARENA_R - 120) and random.random() > (0.03 if court else 0.08):
            tiles[(random.randint(0, 1), court)].append((x, y))
        gy += step
    gx += step
for (k, court), pts in tiles.items():
    mesh = floors[k]
    if not mesh or not pts:
        continue
    b = mesh.get_bounding_box()
    xs = []
    for (x, y) in pts:
        s = random.uniform(0.92, 1.0)
        if court:
            top, zs = COURT_Z + (random.uniform(1, 4) if random.random() < 0.4 else random.uniform(-1, 1)), 0.8
        else:
            top, zs = random.uniform(-1.5, 1.5), 0.35
        xs.append(unreal.Transform(unreal.Vector(x, y, top - b.max.z * s * zs),
                                   unreal.Rotator(pitch=0, yaw=random.randint(0, 3) * 90 + random.uniform(-4, 4), roll=0),
                                   unreal.Vector(s, s, s * zs)))
    label = ("Env_CourtTiles_%d" if court else "Env_BedTiles_%d") % k
    ta = unreal.BFEditorTools.spawn_instanced_mesh_actor(label, mesh, xs, court, 0, 0, True)
    ta.get_component_by_class(unreal.HierarchicalInstancedStaticMeshComponent).set_material(0, asset(ENV + ("/MI_FloorWet_01", "/MI_FloorWet_03")[k]))
    log("tiles", label, len(xs))
# Broken rim of slabs just past the edge.
rim = []
for i in range(46):
    deg = i * (360 / 46) + random.uniform(-3, 3)
    x, y = polar(ARENA_R + random.uniform(90, 230), deg)
    if not in_river(x, y, 80):
        rim.append((x, y))
scatter("Env_RimSlabs", floors[0], rim, (220, 330), by_height=False, z=-4, sink=12, cull=0, shadow=True)

# ---- Water: Fluid Flux river. Splash and spray at the two falls.
for k, (fx, bottom) in enumerate(((2550.0, 4.0), (2900.0, 112.0))):
    emitter(DS + "/Effects/P_WaterSplash_Wide", (fx - 40, river_y(fx), bottom + 5), "Env_FallSplash_%d" % k)
    emitter(DS + "/Effects/P_WaterFog", (fx - 80, river_y(fx), bottom + 30), "Env_FallFog_%d" % k)
# Raised ground the falls come down from: a terrace and a high plateau, edged with rocks.
shape("/Engine/BasicShapes/Cube", (2725, river_y(2725), 52), (3.6, 18, 1.2), "Env_Terrace", mud)
shape("/Engine/BasicShapes/Cube", (6400, 2600, 108), (70, 90, 2.3), "Env_Plateau", grass_ground)
rocks_big = [ds("Meshes/Stones", n) for n in ("SM_RockLarge_01", "SM_RockLarge_02", "SM_RockMedium_01", "SM_RockMedium_02")]
for k in range(16):
    t = (k - 7.5) / 7.5
    fx = 2900.0 + random.uniform(-40, 60)
    fy = river_y(fx) + t * 3400.0
    if abs(fy - river_y(fx)) < river_w(fx) * 0.5 + 40:
        continue
    place(random.choice(rocks_big), fx, fy, -10, random.uniform(0, 360), height=random.uniform(330, 470), label="Env_Cliff_%d" % k, sink=40)
for k, fx in enumerate((2550.0, 2900.0)):
    for side in (-1, 1):
        fy = river_y(fx) + side * (river_w(fx) * 0.5 + 120)
        place(random.choice(rocks_big[2:]), fx, fy, -10, random.uniform(0, 360), height=260 + 110 * k, label="Env_FallRock_%d_%d" % (k, side), sink=30)

# ---- Rune circle glowing under the water, with a teal light.
# Tagged for the boss, which shows it only at his entrance and while he casts (ABFEnemyBase::TickRuneCircle).
# z 19: just above both the river (z 8) and the dry court slabs (top 14-18), since it now follows the boss in X/Y.
rune = shape("/Engine/BasicShapes/Plane", (0, 0, 19.0), (12.5, 12.5, 1), "Env_RuneCircle", asset(ENV + "/M_RuneCircle"), shadow=False)
rune.set_editor_property("tags", ["BFRuneCircle"])
# Movable: at runtime the boss carries the circle and its light under him (ABFEnemyBase::TickRuneCircle).
rune.root_component.set_mobility(unreal.ComponentMobility.MOVABLE)
# No collision at all: shape()'s NO_COLLISION did not stick (it saved as BlockAll), and a moving 12 m collision
# plane shoved and snagged the player.
rune.static_mesh_component.set_collision_profile_name("NoCollision")
rl = spawn(unreal.PointLight, (0, 0, 90), label="Env_RuneLight")
rl.set_editor_property("tags", ["BFRuneLight"])
rl.root_component.set_mobility(unreal.ComponentMobility.MOVABLE)
rl.light_component.set_editor_property("intensity", 18.0)
rl.light_component.set_editor_property("light_color", unreal.Color(r=90, g=255, b=210, a=255))
rl.light_component.set_editor_property("attenuation_radius", 1700.0)
rl.light_component.set_editor_property("cast_shadows", False)

# ---- Ruins: Tripo pillars on the old pillar spots (hidden blockers keep the collision), vines on top.
rune_p = tripo("arena_pillar_rune")
ruin_p = tripo("arena_pillar_ruined")
vines = [ds("Meshes/Foliage", n) for n in ("SM_Vines_Large_01", "SM_Vines_Tall_01", "SM_Vines_Wide_01")]
for i in range(8):
    x, y = polar(1700, i * 45)
    h = random.uniform(900, 1050) if i % 2 == 0 else random.uniform(560, 760)
    place(rune_p if i % 2 == 0 else ruin_p, x, y, 0, i * 45 + random.uniform(-25, 25), height=h, label="Env_Pillar_%d" % i, sink=8)
    v = random.choice(vines)
    if v:
        vs, vb = fit(v, height=h * 0.55)
        a = spawn(unreal.StaticMeshActor, (x, y, h - 25 - vb.max.z * vs), (0, random.uniform(0, 360), 0), "Env_PillarVines_%d" % i)
        a.static_mesh_component.set_static_mesh(v)
        a.set_actor_scale3d(unreal.Vector(vs, vs, vs))
        a.static_mesh_component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
# Collapsed temple gate at the back left, ruined walls and standing rune stones along the rim.
arch = tripo("arena_arch")
place(arch, *polar(2450, -38), 0, -38 + 90, height=1150, label="Env_TempleGate", sink=20)
walls = [ds("Meshes/Structures", n) for n in ("SM_Wall_Ruin_01", "SM_Wall_Ruin_02", "SM_Wall_Ruin_03_Final")]
for k, deg in enumerate((-70, -85, -100, -125, -150, 60, 78, 95, 125, 145)):
    x, y = polar(2300 + random.uniform(-60, 120), deg + random.uniform(-4, 4))
    place(random.choice(walls), x, y, -6, deg + 90 + random.uniform(-15, 15), scale=random.uniform(1.4, 1.9), label="Env_Wall_%d" % k, sink=10)
for k, deg in enumerate((-15, 110, -110)):
    x, y = polar(2550, deg)
    place(ds("Meshes/Stones", "SM_RuneStone_0%d" % (k % 2 + 1)), x, y, -10, random.uniform(0, 360), height=random.uniform(650, 900), label="Env_RuneStone_%d" % k, sink=60)
small_rocks = [ds("Meshes/Stones", n) for n in ("SM_RockSmall_01", "SM_RockSmall_02", "SM_RockSmall_03")]
pts = []
while len(pts) < 70:
    x, y = polar(random.uniform(1950, 3200), random.uniform(0, 360))
    if not in_river(x, y, -60):
        pts.append((x, y))
for k, m in enumerate(small_rocks):
    scatter("Env_Rocks_%d" % k, m, pts[k::3], (60, 170), by_height=False, z=-5, sink=10, cull=0, shadow=True)

# ---- Trees: cherry blossoms around the court, dark forest beyond.
sakura = asset(ENV + "/MI_TreeLeaves_Sakura")
tree_meshes = [ds("Meshes/Trees", n) for n in ("SM_Tree_A_02", "SM_Tree_A_03", "SM_Tree_B_01", "SM_Tree_B_02", "SM_Tree_F_01_WIP")]
for k, (deg, r, h) in enumerate(((42, 2850, 1150), (68, 2650, 1000), (112, 3000, 1250), (150, 2750, 1050),
                                 (-150, 2900, 1150), (-60, 3100, 1300), (15, 3600, 1200), (-170, 3500, 1300))):
    x, y = polar(r, deg)
    if in_river(x, y, 300):
        y += 900
    t = place(random.choice(tree_meshes), x, y, -5, random.uniform(0, 360), height=h, label="Env_Sakura_%d" % k, sink=15,
              mats={1: sakura})
    emitter(DS + "/Effects/P_FallingLeaves_Red", (x, y, h * 0.7), "Env_Petals_%d" % k, 0.8)
forest = [ds("Meshes/Trees", n) for n in ("SM_Tree_C_01", "SM_Tree_D_01_WIP", "SM_Tree_E_01_WIP", "SM_Tree_E_02_wip", "SM_Tree_B_02")]
for k in range(34):
    x, y = polar(random.uniform(4300, 8000), random.uniform(0, 360))
    on_plateau = 2900 < x < 9900 and -1900 < y < 7100
    if in_river(x, y, 600):
        continue
    place(random.choice(forest), x, y, 223 if on_plateau else -5, random.uniform(0, 360), height=random.uniform(1700, 2600), label="Env_Forest_%d" % k, sink=20)
bushes = [ds("Meshes/Foliage", n) for n in ("SM_Bush_02_WIP", "SM_Bush_03_WIP", "SM_Bush_05_WIp", "SM_HazelBush_01_WIP")]
for k in range(22):
    x, y = polar(random.uniform(2250, 3800), random.uniform(0, 360))
    if in_river(x, y, 150):
        continue
    place(random.choice(bushes), x, y, -5, random.uniform(0, 360), height=random.uniform(140, 300), label="Env_Bush_%d" % k, sink=15)

# ---- Background beyond the court (user asked for more pillars, buildings and trees out there): a broken colonnade,
# crystal clusters, arches and tall forest silhouettes. Nothing in the river.
def clear_spot(x, y, pad=350.0):
    return not in_river(x, y, pad) and not (2300 < x < 3700 and abs(y - river_y(x)) < 1600)


def ground_at(x, y):
    on_plateau = 2900 < x < 9900 and -1900 < y < 7100
    return 223.0 if on_plateau else -5.0


# Broken colonnade ring just past the lanterns.
for k in range(18):
    deg = k * 20 + random.uniform(-5, 5)
    x, y = polar(random.uniform(3150, 3450), deg)
    if not clear_spot(x, y):
        continue
    tall = k % 3 != 1
    place(rune_p if tall and k % 2 == 0 else ruin_p, x, y, ground_at(x, y), random.uniform(0, 360),
          height=random.uniform(1000, 1350) if tall else random.uniform(420, 650), label="Env_BgColumn_%d" % k, sink=12)
# (No FantasyBundle gate pillars: they read as brick towers and the user asked for the towers to go.)
# Glowing crystal clusters among the ruins (purple and blue, they pick up the twilight).
crystals = [ds("Meshes/Crystals", n) for n in ("SM_CrystalGroup_01_Purple", "SM_CrystalGroup_02_Purple", "SM_CrystalGroup_01_Blue", "SM_CrystalGroup_02_Blue")]
for k in range(14):
    x, y = polar(random.uniform(2800, 5200), random.uniform(0, 360))
    if clear_spot(x, y):
        place(random.choice(crystals), x, y, ground_at(x, y), random.uniform(0, 360), height=random.uniform(180, 520),
              label="Env_BgCrystal_%d" % k, sink=25)
# (No towers: the user asked for the stacked ruined towers to be removed.)
# Huge broken arches far out, half lost in the mist.
for k, (deg, r) in enumerate(((145, 6200), (-75, 6600), (215, 7200))):
    x, y = polar(r, deg)
    if clear_spot(x, y, 900):
        place(arch, x, y, ground_at(x, y), deg + 90 + random.uniform(-20, 20), height=random.uniform(2300, 2900), label="Env_BgArch_%d" % k, sink=40)
# More trees: a mid ring of blossoms and greens for depth, then tall dark silhouettes on the horizon.
for k in range(26):
    x, y = polar(random.uniform(3000, 5600), random.uniform(0, 360))
    if not clear_spot(x, y, 450):
        continue
    if random.random() < 0.35:
        place(random.choice(tree_meshes), x, y, ground_at(x, y), random.uniform(0, 360), height=random.uniform(1100, 1500),
              label="Env_BgSakura_%d" % k, sink=15, mats={1: sakura})
    else:
        place(random.choice(forest), x, y, ground_at(x, y), random.uniform(0, 360), height=random.uniform(1400, 2200),
              label="Env_BgTree_%d" % k, sink=20)
for k in range(46):
    x, y = polar(random.uniform(8500, 15000), random.uniform(0, 360))
    if not clear_spot(x, y, 900):
        continue
    place(random.choice(forest), x, y, ground_at(x, y), random.uniform(0, 360), height=random.uniform(2800, 4600),
          label="Env_FarTree_%d" % k, sink=30, shadow=False)

# ---- Grass, reeds and flowers (instanced).
def ring_points(n, rmin, rmax, river_pad, ok=None):
    out = []
    tries = 0
    while len(out) < n and tries < n * 20:
        tries += 1
        x, y = polar(math.sqrt(random.uniform(rmin * rmin, rmax * rmax)), random.uniform(0, 360))
        if in_river(x, y, river_pad) or (ok and not ok(x, y)):
            continue
        out.append((x, y))
    return out


scatter("Env_GrassMed", ds("Meshes/Foliage", "SM_Grass_Medium"), ring_points(1600, 2050, 6000, 40), (45, 85), z=-5, sink=3, cull=9000)
scatter("Env_GrassSmall", ds("Meshes/Foliage", "SM_Grass_SmallGroup"), ring_points(1400, 2000, 5000, 20), (25, 45), z=-5, sink=2, cull=6000)
# Tufts poking out of the cracks inside the court.
scatter("Env_CourtTufts", ds("Meshes/Foliage", "SM_Grass_Scattered"), ring_points(160, 300, ARENA_R - 150, 120), (18, 34), z=COURT_Z, sink=2, cull=5000)
bank = []
x = -6500.0
while x < 2500.0:
    for side in (-1, 1):
        if random.random() < 0.75:
            yb = river_y(x) + side * (river_w(x) * 0.5 + random.uniform(-30, 70))
            if math.hypot(x, yb) > ARENA_R - 100 or random.random() < 0.35:
                bank.append((x + random.uniform(-50, 50), yb))
    x += 85.0
scatter("Env_Reeds", ds("Meshes/Foliage", "SM_Weed_01"), bank[0::2], (90, 150), z=0, sink=4, cull=8000)
scatter("Env_ReedsB", ds("Meshes/Foliage", "SM_Wheat_01"), bank[1::2], (100, 160), z=0, sink=4, cull=8000)
scatter("Env_Flowers", ds("Meshes/Foliage", "SM_FlowerGroup_03"), ring_points(220, 2100, 4500, 80), (30, 50), z=-5, sink=2, cull=6000)

# ---- Puddles and wet patches on the court and the mud ring (decals).
puddle = asset(DSR + "/Materials/Effects/M_Puddle")
for k in range(30):
    x, y = polar(math.sqrt(random.uniform(0, 2300 ** 2)), random.uniform(0, 360))
    r = random.uniform(140, 420)
    d = spawn(unreal.DecalActor, (x, y, 5), (-90, random.uniform(0, 360), 0), "Env_Puddle_%d" % k)
    d.get_editor_property("decal").set_decal_material(puddle)
    d.set_actor_scale3d(unreal.Vector(0.4, r / 256.0, r / 256.0 * random.uniform(0.6, 1.0)))

# ---- Lanterns: wooden posts with a glowing box and a warm light.
glow = asset(ENV + "/M_LanternGlow")
wood = asset(DS + "/Materials/Structures/MI_Fence")
for k, deg in enumerate((5, 52, 100, 140, 235, 262, 300, 330)):
    x, y = polar(2120, deg)
    if in_river(x, y, 120):
        continue
    out = unreal.Vector(math.cos(math.radians(deg)), math.sin(math.radians(deg)), 0)
    shape("/Engine/BasicShapes/Cube", (x, y, 120), (0.16, 0.16, 2.6), "Env_LanternPost_%d" % k, wood)
    shape("/Engine/BasicShapes/Cube", (x - out.x * 45, y - out.y * 45, 245), (0.9, 0.1, 0.1), "Env_LanternArm_%d" % k, wood, rot=(0, deg, 0))
    lx, ly = x - out.x * 80, y - out.y * 80
    shape("/Engine/BasicShapes/Cube", (lx, ly, 205), (0.24, 0.24, 0.34), "Env_Lantern_%d" % k, glow, shadow=False)
    pl = spawn(unreal.PointLight, (lx, ly, 200), label="Env_LanternLight_%d" % k)
    pl.light_component.set_editor_property("intensity", 22.0)
    pl.light_component.set_editor_property("light_color", unreal.Color(r=255, g=170, b=90, a=255))
    pl.light_component.set_editor_property("attenuation_radius", 1100.0)
    pl.light_component.set_editor_property("cast_shadows", False)

# ---- Fireflies and low mist.
for k in range(10):
    x, y = polar(random.uniform(1200, 3200), random.uniform(0, 360))
    emitter(DS + "/Effects/P_FireFly", (x, y, random.uniform(80, 220)), "Env_Fireflies_%d" % k)

# ---- Twilight sky dome, moonlight, purple mist.
sky_mesh = asset("/Engine/EngineSky/SM_SkySphere")
if sky_mesh:
    b = sky_mesh.get_bounding_box()
    s = 300000.0 / max((b.max.x - b.min.x) * 0.5, 1.0)
    shape("/Engine/EngineSky/SM_SkySphere", (0, 0, 0), (s, s, s), "Env_SkyDome", asset(ENV + "/M_TwilightSky"), shadow=False)
for actor in eas.get_all_level_actors():
    label = actor.get_actor_label()
    if label == "Sun":
        actor.set_actor_rotation(unreal.Rotator(pitch=-13, yaw=-155, roll=0), False)
        lc = actor.light_component
        lc.set_editor_property("intensity", 1.6)
        lc.set_editor_property("light_color", unreal.Color(r=165, g=160, b=255, a=255))
        lc.set_editor_property("atmosphere_sun_light", False)
    elif label == "SkyLight":
        actor.light_component.set_editor_property("intensity", 0.35)
        actor.light_component.set_editor_property("light_color", unreal.Color(r=255, g=255, b=255, a=255))
    elif label == "Fog":
        fc = actor.get_component_by_class(unreal.ExponentialHeightFogComponent)
        fc.set_editor_property("fog_density", 0.012)
        fc.set_editor_property("fog_height_falloff", 0.3)
        fc.set_editor_property("fog_inscattering_luminance", unreal.LinearColor(0.09, 0.06, 0.15, 1.0))
        fc.set_editor_property("start_distance", 1500.0)
        fc.set_editor_property("enable_volumetric_fog", False)
        fc.set_editor_property("volumetric_fog_extinction_scale", 0.35)
        actor.set_actor_location(unreal.Vector(0, 0, -150), False, False)
pp = spawn(unreal.PostProcessVolume, (0, 0, 0), label="Env_PostProcess")
pp.set_editor_property("unbound", True)
ps = pp.get_editor_property("settings")
for name, value in (("auto_exposure_bias", -0.7), ("vignette_intensity", 0.45), ("bloom_intensity", 0.9),
                    ("color_saturation", unreal.Vector4(1.08, 1.0, 1.12, 1.0))):
    ps.set_editor_property("override_" + name, True)
    ps.set_editor_property(name, value)
pp.set_editor_property("settings", ps)
# ---- Invisible barrier (user asked for one): a ring of hidden walls keeps the player and the boss inside the
# court and its rim (r 2900, just inside the colonnade). 16 m tall so the boss cannot drift over it during a cast.
# It ignores the camera, so the view never snaps in when the camera swings past it.
BARRIER_R, BARRIER_N = 2900.0, 48
for i in range(BARRIER_N):
    deg = i * 360.0 / BARRIER_N
    x, y = polar(BARRIER_R, deg)
    w = shape("/Engine/BasicShapes/Cube", (x, y, 700.0), (1.0, 2 * math.pi * BARRIER_R / BARRIER_N / 100 + 0.3, 16.0),
              "Env_Barrier_%d" % i, rot=(0, deg, 0), shadow=False)
    w.set_actor_hidden_in_game(True)
    w.static_mesh_component.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
    w.static_mesh_component.set_collision_profile_name("InvisibleWall")
    w.static_mesh_component.set_collision_response_to_channel(unreal.CollisionChannel.ECC_CAMERA, unreal.CollisionResponseType.ECR_IGNORE)
    w.static_mesh_component.set_editor_property("visible_in_scene_capture_only", False)
    w.static_mesh_component.set_editor_property("hidden_in_scene_capture", True)
    w.set_editor_property("tags", ["FluxHide"])  # Fluid Flux's ground capture skips actors with this tag
log("barrier", BARRIER_N, "walls at r", BARRIER_R)

les.save_current_level()
log("arena twilight saved")
