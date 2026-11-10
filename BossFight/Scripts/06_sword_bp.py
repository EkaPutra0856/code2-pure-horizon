# Read-only: components of the InsaneAirCombo sword character BP and skeleton sockets.
import unreal
bp = unreal.load_asset("/Game/InsaneAirCombo/AdvancedAsset/Blueprint/Sword_SK_Mannequin_Blueprint")
sub = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
handles = sub.k2_gather_subobject_data_for_blueprint(bp)
for h in handles:
    d = unreal.SubobjectDataBlueprintFunctionLibrary.get_data(h)
    o = unreal.SubobjectDataBlueprintFunctionLibrary.get_object(d)
    if not o: continue
    info = o.get_class().get_name()
    if isinstance(o, unreal.SceneComponent):
        info += " socket=%s rel=%s rot=%s scale=%s" % (o.get_attach_socket_name(), o.get_editor_property("relative_location"), o.get_editor_property("relative_rotation"), o.get_editor_property("relative_scale3d"))
    if isinstance(o, unreal.StaticMeshComponent):
        info += " mesh=%s" % (o.static_mesh.get_path_name() if o.static_mesh else None)
    if isinstance(o, unreal.SkeletalMeshComponent):
        info += " skm=%s anim=%s mode=%s" % (o.get_skeletal_mesh_asset().get_path_name() if o.get_skeletal_mesh_asset() else None, o.get_editor_property("anim_class"), o.get_editor_property("animation_mode"))
    unreal.log("COMP %s: %s" % (o.get_name(), info))
sk = unreal.load_asset("/Game/InsaneAirCombo/Animation/Skeleton/UE4_Mannequin_Skeleton")
mesh = unreal.load_asset("/Game/InsaneAirCombo/Animation/Skeleton/SK_Mannequin")
unreal.log("SOCKETS: %s" % [s.get_editor_property("socket_name") for s in mesh.skeleton.get_editor_property("sockets")] if hasattr(mesh.skeleton, "sockets") else "n/a")
for n in range(mesh.get_num_sockets() if hasattr(mesh, "get_num_sockets") else 0):
    pass
