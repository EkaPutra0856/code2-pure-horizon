# Read-only: mesh, anim class and montage slots used by the packs' demo characters.
import unreal
eal = unreal.EditorAssetLibrary
ar = unreal.AssetRegistryHelpers.get_asset_registry()
ar.scan_paths_synchronous(["/Game"], True)
for p in ["/Game/InsaneAirCombo/AdvancedAsset/Blueprint/Sword_SK_Mannequin_Blueprint"]:
    a = eal.load_asset(p)
    unreal.log("CHAR %s class=%s" % (p, a.get_class().get_name() if a else None))
    if a and isinstance(a, unreal.AnimBlueprint):
        unreal.log("  skel=%s" % a.get_editor_property("target_skeleton").get_path_name())
# list blueprints in InsaneAirCombo and Lucy demo
for root in ["/Game/InsaneAirCombo", "/Game/Lucy/DEMO", "/Game/Lucy/Animations"]:
    for x in eal.list_assets(root, recursive=True):
        d = ar.get_asset_by_object_path(x)
        cls = str(d.asset_class_path.asset_name)
        if cls in ("Blueprint", "AnimBlueprint", "AnimMontage", "BlendSpace", "BlendSpace1D", "SkeletalMesh"):
            unreal.log("ASSET %s %s" % (cls, d.package_name))
for m in ["/Game/InsaneAirCombo/Animation/Skeleton/SK_Mannequin", "/Game/Lucy/DEMO/Mannequin/Character/Mesh/SK_Mannequin_Female"]:
    sk = eal.load_asset(m)
    unreal.log("MESH %s skel=%s mats=%d" % (m, sk.skeleton.get_path_name(), len(sk.materials)))
