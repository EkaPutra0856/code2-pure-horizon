import unreal
unreal.AssetRegistryHelpers.get_asset_registry().scan_paths_synchronous(["/Game/BossFight"], True)
unreal.EditorLoadingAndSavingUtils.load_map("/Game/BossFight/Maps/L_Arena")
w = unreal.EditorLevelLibrary.get_editor_world()
print("BFI world", w.get_name(), "WP", w.get_world_settings().get_editor_property("world_partition") if hasattr(w.get_world_settings(),"world_partition") else "?")
for a in unreal.EditorLevelLibrary.get_all_level_actors():
    line = "BFI %s %s loc=%s rot=%s hidden=%s" % (a.get_class().get_name(), a.get_actor_label(), a.get_actor_location(), a.get_actor_rotation(), a.is_hidden_ed())
    for c in a.get_components_by_class(unreal.LightComponentBase):
        line += " | %s vis=%s int=%s col=%s mob=%s" % (c.get_class().get_name(), c.get_editor_property("visible"), c.get_editor_property("intensity"), c.get_editor_property("light_color"), c.get_editor_property("mobility"))
    print(line)
