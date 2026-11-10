# Imports the Tripo environment GLBs (ArtSource/TripoGLB, exported from Tripo Studio at 4k) as static meshes
# under /Game/BossFight/Env/Tripo/<name>/, caps their textures at 2048, and logs each mesh's bounds so the map
# builder can scale them to real sizes. Re-running skips meshes that already exist.
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import os
import unreal

SRC = os.path.join(ANIME_GAME_ROOT, r"BossFight/ArtSource/TripoGLB")
DST = "/Game/BossFight/Env/Tripo"
eal = unreal.EditorAssetLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()


def log(*a):
    unreal.log("BUILD: " + " ".join(str(x) for x in a))


for fn in sorted(os.listdir(SRC)):
    if not fn.lower().endswith(".glb"):
        continue
    name = os.path.splitext(fn)[0]
    folder = "%s/%s" % (DST, name)
    if not eal.list_assets(folder, recursive=True, include_folder=False):
        task = unreal.AssetImportTask()
        task.set_editor_property("filename", os.path.join(SRC, fn))
        task.set_editor_property("destination_path", folder)
        task.set_editor_property("automated", True)
        task.set_editor_property("save", True)
        task.set_editor_property("replace_existing", True)
        tools.import_asset_tasks([task])
        log("imported", name, list(task.get_editor_property("imported_object_paths")))
    for p in eal.list_assets(folder, recursive=True, include_folder=False):
        a = unreal.load_asset(p)
        if isinstance(a, unreal.Texture2D):
            if a.get_editor_property("max_texture_size") != 2048:
                a.set_editor_property("max_texture_size", 2048)
                eal.save_loaded_asset(a)
        elif isinstance(a, unreal.StaticMesh):
            b = a.get_bounding_box()
            size = b.max - b.min
            log("MESH", p, "min=(%.1f,%.1f,%.1f)" % (b.min.x, b.min.y, b.min.z), "size=(%.1f,%.1f,%.1f)" % (size.x, size.y, size.z),
                "tris=%d" % a.get_num_triangles(0), "mats=%d" % len(a.static_materials))
