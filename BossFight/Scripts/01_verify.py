# Counts assets per top folder and loads key meshes/skeletons to prove the project opens cleanly.
import unreal
eal = unreal.EditorAssetLibrary
ar = unreal.AssetRegistryHelpers.get_asset_registry()
ar.scan_paths_synchronous(["/Game"], True)
for top in ["Characters", "InsaneAirCombo", "Lucy", "sA_IceSkillPack2", "Hack_And_Slash_FX", "SlashHitVFX", "MagicKit"]:
    unreal.log("VERIFY: %s %d" % (top, len(eal.list_assets("/Game/" + top, recursive=True))))
for p in ["/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple",
          "/Game/Characters/Mannequins/Rigs/IK_Mannequin",
          "/Game/InsaneAirCombo/Animation/Skeleton/UE4_Mannequin_Skeleton",
          "/Game/InsaneAirCombo/Animation/combo01",
          "/Game/InsaneAirCombo/mesh/Sword",
          "/Game/Lucy/DEMO/Mannequin/Character/Mesh/UE4_Mannequin_Skeleton"]:
    a = eal.load_asset(p)
    unreal.log("VERIFY_LOAD: %s -> %s" % (p, a.get_class().get_name() if a else "FAILED"))
