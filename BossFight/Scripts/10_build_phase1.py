# Phase 1 builder: player Anim Blueprint (via C++ tool) and the arena level.
import unreal

import sys
log = "" if "--skip-abp" in sys.argv else unreal.BFEditorTools.build_player_anim_blueprint()
for line in log.splitlines():
    unreal.log("BUILD: " + line)

MAP = "/Game/BossFight/Maps/L_Arena"
eal = unreal.EditorAssetLibrary
les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

if eal.does_asset_exist(MAP):
    eal.delete_asset(MAP)
les.new_level(MAP)

def spawn(cls, loc, rot=(0, 0, 0), label=None):
    # rot is (pitch, yaw, roll); unreal.Rotator's positional order is (roll, pitch, yaw), so pass keywords.
    a = eas.spawn_actor_from_class(cls, unreal.Vector(*loc), unreal.Rotator(pitch=rot[0], yaw=rot[1], roll=rot[2]))
    if label:
        a.set_actor_label(label)
    return a

def mesh_actor(mesh_path, loc, scale, label, rot=(0, 0, 0)):
    a = spawn(unreal.StaticMeshActor, loc, rot, label)
    comp = a.static_mesh_component
    comp.set_static_mesh(unreal.load_asset(mesh_path))
    a.set_actor_scale3d(unreal.Vector(*scale))
    return a

# Arena: 40 m wide stone disc, raised so the player can fall off the edge.
mesh_actor("/Engine/BasicShapes/Cylinder", (0, 0, -50), (40, 40, 1), "Arena_Floor")
mesh_actor("/Engine/BasicShapes/Cylinder", (0, 0, -2600), (200, 200, 1), "Abyss_Floor")
import math
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

# Phase 2 training dummy (replaced by the Sevarog boss later), facing the player.
dummy_cls = unreal.load_class(None, "/Script/BossFight.BFEnemyBase")
if dummy_cls:
    spawn(dummy_cls, (-620, 0, 100), (0, 180, 0), "TrainingDummy")

ws = unreal.EditorLevelLibrary.get_editor_world().get_world_settings()
ws.set_editor_property("default_game_mode", unreal.load_class(None, "/Script/BossFight.BFGameMode"))
ws.set_editor_property("kill_z", -2000.0)

les.save_current_level()
unreal.log("BUILD: arena saved %s" % MAP)
