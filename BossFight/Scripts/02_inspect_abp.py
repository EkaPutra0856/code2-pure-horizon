# Read-only: reports parent class, skeleton and slot names of candidate anim blueprints.
import unreal
eal = unreal.EditorAssetLibrary
ar = unreal.AssetRegistryHelpers.get_asset_registry()
ar.scan_paths_synchronous(["/Game"], True)
flt = unreal.ARFilter(class_paths=[unreal.TopLevelAssetPath("/Script/Engine", "AnimBlueprint")], package_paths=["/Game"], recursive_paths=True)
for a in ar.get_assets(flt):
    bp = a.get_asset()
    sk = bp.get_editor_property("target_skeleton")
    try:
        parent = bp.get_editor_property("parent_class").get_name()
    except Exception as e:
        parent = "?"
    unreal.log("ABP: %s | parent=%s | skel=%s" % (a.package_name, parent, sk.get_path_name() if sk else None))
for p in ["/Game/InsaneAirCombo/AdvancedAsset/Blueprint/Sword_SK_Mannequin_Blueprint"]:
    b = eal.load_asset(p)
    unreal.log("BP: %s -> %s parent=%s" % (p, b.get_class().get_name() if b else None, b.get_editor_property("parent_class").get_name() if b else None))
