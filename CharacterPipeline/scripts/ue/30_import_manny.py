# Copies Manny (UE5 mannequin) from the MoverExamples engine plugin into /Game/Characters/Mannequins.
# Needs MoverExamples + Mover enabled in AnimeGame.uproject while it runs.
import unreal

SRC = "/MoverExamples/Characters/Mannequins"
DST = "/Game/Characters/Mannequins"
eal = unreal.EditorAssetLibrary
ar = unreal.AssetRegistryHelpers.get_asset_registry()
ar.scan_paths_synchronous(["/MoverExamples", "/Game"], True)
unreal.log("MANNY: src assets %d" % len(eal.list_assets(SRC, recursive=True)))

if eal.list_assets(DST, recursive=True):
    unreal.log_warning("MANNY: target already exists, skipped")
else:
    ok = eal.duplicate_directory(SRC, DST)
    unreal.log("MANNY: duplicate_directory -> %s" % ok)
    eal.save_directory(DST, only_if_is_dirty=False, recursive=True)

assets = eal.list_assets(DST, recursive=True)
bad = [a for a in assets if "/MoverExamples/" in " ".join(
    str(d) for d in unreal.AssetRegistryHelpers.get_asset_registry().get_dependencies(
        a.split(".")[0], unreal.AssetRegistryDependencyOptions()) or [])]
unreal.log("MANNY: %d assets, %d still point to plugin" % (len(assets), len(bad)))
for b in bad[:20]:
    unreal.log("MANNY_BAD: " + b)
