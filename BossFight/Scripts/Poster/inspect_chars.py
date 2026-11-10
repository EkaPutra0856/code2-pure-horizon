"""Inspect imported poster characters: skeletons, materials, missing dependencies. Run via UnrealEditor-Cmd -run=pythonscript."""
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import unreal

OUT = os.path.join(ANIME_GAME_ROOT, r"BossFight/Saved/poster_inspect.txt")
MESHES = [
    "/Game/Swordswoman/sw_ue",
]
reg = unreal.AssetRegistryHelpers.get_asset_registry()
lines = []
for p in ["/Game/CharCustom", "/Game/Model"]:
    for a in reg.get_assets_by_path(p, recursive=True):
        pkg = str(a.package_name)
        opts = unreal.AssetRegistryDependencyOptions(True, True, False, False, False)
        for d in reg.get_dependencies(pkg, opts) or []:
            d = str(d)
            if d.startswith("/Script") or d.startswith("/Engine"):
                continue
            if not unreal.EditorAssetLibrary.does_asset_exist(d) and not reg.get_assets_by_package_name(d):
                lines.append("MISSING %s <- %s" % (d, pkg))
        lines.append("ASSET %s %s" % (a.asset_class_path.asset_name, pkg))
for a in reg.get_assets_by_path("/Game/CharCustom", recursive=True) + reg.get_assets_by_path("/Game/Model", recursive=True):
    if str(a.asset_class_path.asset_name) == "SkeletalMesh":
        MESHES.append(str(a.package_name))
for m in dict.fromkeys(MESHES):
    sk = unreal.load_asset(m)
    if not isinstance(sk, unreal.SkeletalMesh):
        lines.append("SKIP %s %s" % (m, type(sk).__name__))
        continue
    skel = sk.skeleton
    bounds = sk.get_bounds()
    lines.append("MESH %s skel=%s box=%s" % (m, skel.get_path_name() if skel else None, bounds.box_extent))
    comp = unreal.SkeletalMeshComponent()
    comp.set_skinned_asset_and_update(sk) if hasattr(comp, "set_skinned_asset_and_update") else comp.set_skeletal_mesh(sk)
    names = [str(comp.get_bone_name(i)) for i in range(comp.get_num_bones())]
    lines.append("  bones(%d): %s" % (len(names), " ".join(names[:200])))
    for i, sm in enumerate(sk.materials):
        mi = sm.material_interface
        chain = []
        x = mi
        while x is not None and len(chain) < 5:
            chain.append(x.get_path_name())
            x = x.get_editor_property("parent") if isinstance(x, unreal.MaterialInstance) else None
        lines.append("  mat%d %s : %s" % (i, sm.material_slot_name, " -> ".join(chain)))
open(OUT, "w", encoding="utf-8").write("\n".join(lines))
unreal.log("POSTER_INSPECT done %d lines" % len(lines))
