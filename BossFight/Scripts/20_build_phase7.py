# Phase 7 builder: Sevarog Anim Blueprint, then two arenas:
#   L_Arena    - Sevarog boss fight (default map)
#   L_Training - humanoid training dummy (minion) for practising parry / clash
import math
import unreal

for line in unreal.BFEditorTools.build_sevarog_anim_blueprint().splitlines():
    unreal.log("BUILD: " + line)

eal = unreal.EditorAssetLibrary
les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def spawn(cls, loc, rot=(0, 0, 0), label=None):
    # rot is (pitch, yaw, roll); unreal.Rotator's positional order is (roll, pitch, yaw), so pass keywords.
    a = eas.spawn_actor_from_class(cls, unreal.Vector(*loc), unreal.Rotator(pitch=rot[0], yaw=rot[1], roll=rot[2]))
    if label:
        a.set_actor_label(label)
    return a


def mesh_actor(mesh_path, loc, scale, label, rot=(0, 0, 0)):
    a = spawn(unreal.StaticMeshActor, loc, rot, label)
    a.static_mesh_component.set_static_mesh(unreal.load_asset(mesh_path))
    a.set_actor_scale3d(unreal.Vector(*scale))
    return a


def build_arena(map_path, enemy_class_path, enemy_loc, enemy_label):
    # Reuse an existing map (deleting a loaded/referenced map fails): load it and clear its actors.
    if eal.does_asset_exist(map_path):
        les.load_level(map_path)
        for actor in eas.get_all_level_actors():
            if not isinstance(actor, (unreal.WorldSettings, unreal.Brush)):
                eas.destroy_actor(actor)
    else:
        les.new_level(map_path)
    # 40 m stone disc over an abyss, eight pillars.
    mesh_actor("/Engine/BasicShapes/Cylinder", (0, 0, -50), (40, 40, 1), "Arena_Floor")
    mesh_actor("/Engine/BasicShapes/Cylinder", (0, 0, -2600), (200, 200, 1), "Abyss_Floor")
    for i in range(8):
        ang = i * math.pi / 4
        mesh_actor("/Engine/BasicShapes/Cube", (1700 * math.cos(ang), 1700 * math.sin(ang), 400), (1.6, 1.6, 9), "Pillar_%d" % i)
    sun = spawn(unreal.DirectionalLight, (0, 0, 1000), (-40, 35, 0), "Sun")
    sun.root_component.set_mobility(unreal.ComponentMobility.MOVABLE)
    sun.light_component.set_editor_property("atmosphere_sun_light", True)
    sun.light_component.set_editor_property("intensity", 8.0)
    spawn(unreal.SkyAtmosphere, (0, 0, 0), label="SkyAtmosphere")
    sky = spawn(unreal.SkyLight, (0, 0, 500), label="SkyLight")
    sky.root_component.set_mobility(unreal.ComponentMobility.MOVABLE)
    sky.light_component.set_editor_property("real_time_capture", True)
    spawn(unreal.ExponentialHeightFog, (0, 0, -500), label="Fog")
    spawn(unreal.PlayerStart, (-900, 0, 120), label="PlayerStart")
    cls = unreal.load_class(None, enemy_class_path)
    if cls:
        spawn(cls, enemy_loc, (0, 180, 0), enemy_label)
    else:
        unreal.log_error("BUILD: missing class " + enemy_class_path)
    ws = unreal.EditorLevelLibrary.get_editor_world().get_world_settings()
    ws.set_editor_property("default_game_mode", unreal.load_class(None, "/Script/BossFight.BFGameMode"))
    ws.set_editor_property("kill_z", -2000.0)
    les.save_current_level()
    unreal.log("BUILD: arena saved %s with %s" % (map_path, enemy_label))


build_arena("/Game/BossFight/Maps/L_Training", "/Script/BossFight.BFEnemyBase", (-620, 0, 100), "TrainingDummy")
build_arena("/Game/BossFight/Maps/L_Arena", "/Script/BossFight.BFBossSevarog", (-450, 0, 160), "Sevarog")
