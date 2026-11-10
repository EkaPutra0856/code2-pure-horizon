import unreal
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level("/Game/BossFight/Maps/L_Arena")
world = unreal.EditorLevelLibrary.get_editor_world()
unreal.log("MAP world_partition=%s" % (world.get_world_settings().get_editor_property("world_partition") is not None if hasattr(world.get_world_settings(), "world_partition") else "?"))
for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    extra = ""
    if isinstance(a, unreal.StaticMeshActor):
        c = a.static_mesh_component
        extra = "mesh=%s mat=%s" % (c.static_mesh.get_name() if c.static_mesh else None, c.get_material(0).get_name() if c.get_material(0) else None)
    if isinstance(a, (unreal.DirectionalLight, unreal.SkyLight)):
        extra = "mob=%s int=%s" % (a.root_component.mobility, a.get_component_by_class(unreal.LightComponentBase).intensity)
    unreal.log("MAP %s %s %s %s" % (a.get_class().get_name(), a.get_actor_label(), a.get_actor_location(), extra))
