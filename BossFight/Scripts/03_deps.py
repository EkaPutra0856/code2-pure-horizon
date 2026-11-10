# Read-only: package dependencies of the copied Manny assets and ABP variables.
import unreal
ar = unreal.AssetRegistryHelpers.get_asset_registry()
ar.scan_paths_synchronous(["/Game", "/MoverExamples"], True)
opt = unreal.AssetRegistryDependencyOptions(include_soft_package_references=True, include_hard_package_references=True)
for p in ["/Game/Characters/Mannequins/Animations/ABP_Manny", "/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple",
          "/Game/Characters/Mannequins/Meshes/SK_Mannequin", "/Game/Characters/Mannequins/Rigs/IK_Mannequin"]:
    deps = ar.get_dependencies(p, opt) or []
    unreal.log("DEPS %s: %s" % (p, ", ".join(str(d) for d in deps)))
bp = unreal.load_asset("/Game/Characters/Mannequins/Animations/ABP_Manny")
gc = bp.generated_class()
cdo = unreal.get_default_object(gc)
unreal.log("ABPCLASS super: %s" % gc.get_super_class().get_name() if hasattr(gc, "get_super_class") else "n/a")
