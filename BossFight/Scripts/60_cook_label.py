# Packaging helper: builds /Game/BossFight/Cook/DA_CookManifest (UBFCookManifest), a data asset that
# hard-references every asset the C++ loads by path at runtime (LoadObject / LoadClass / FindAsset /
# ConstructorHelpers). The package cooks only L_Arena plus what it references, so without it those assets
# would be missing from the build. /Game/BossFight/Cook is in DirectoriesToAlwaysCook (Config/DefaultGame.ini)
# and the cooker follows the hard references, so only these exact assets are added (not whole folders).
# A Primary Asset Label with CookRule AlwaysCook was tried first (UE 5.8): the cooker ignored it.
# Rerun after adding a new path-loaded asset to the source (it re-reads the "/Game/..." strings from Source/).
# Headless: UnrealEditor-Cmd BossFight.uproject -run=pythonscript -script=<this file>. Log Saved/Logs/cook_label.txt.
import os, re
import unreal

PROJ = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
LOG = os.path.join(PROJ, "Saved", "Logs", "cook_label.txt")
lines = []


def say(*a):
    lines.append(" ".join(str(x) for x in a))
    open(LOG, "w", encoding="utf-8").write("\n".join(lines))


EAL = unreal.EditorAssetLibrary
# Names built at runtime (FindAnim / SevarogAnimPath) all come from constructors, which the cooker runs, so
# those already get cooked; whole folders are not added.
FOLDERS = []
# Test-only loads (autotest modes), not needed in the shipped game.
SKIP = ("/Game/Lucy/Animations/%s",)

paths = set()
src = os.path.join(PROJ, "Source")
for root, _, files in os.walk(src):
    for f in files:
        if f.endswith((".cpp", ".h")):
            for m in re.findall(r'"(/Game/[^"]+)"', open(os.path.join(root, f), encoding="utf-8", errors="ignore").read()):
                if "%" in m or m.endswith("/") or m.startswith(SKIP):
                    continue
                pkg = m.split(".")[0]
                if EAL.does_asset_exist(pkg):
                    paths.add(pkg)
                else:
                    say("not an asset (skipped):", m)
for folder in FOLDERS:
    for a in EAL.list_assets(folder, recursive=True, include_folder=False):
        paths.add(a.split(".")[0])

objs = []
for p in sorted(paths):
    o = unreal.load_asset(p)
    if o:
        objs.append(o)
    else:
        say("load failed:", p)
say("assets", len(objs))

DIR, NAME = "/Game/BossFight/Cook", "DA_CookManifest"
old_label = f"{DIR}/PAL_BossFightRuntime"
if EAL.does_asset_exist(old_label):
    EAL.delete_asset(old_label)
path = f"{DIR}/{NAME}"
da = unreal.load_asset(path) if EAL.does_asset_exist(path) else None
if not da:
    f = unreal.DataAssetFactory()
    f.set_editor_property("data_asset_class", unreal.BFCookManifest)
    da = unreal.AssetToolsHelpers.get_asset_tools().create_asset(NAME, DIR, unreal.BFCookManifest, f)
da.set_editor_property("assets", objs)
EAL.save_loaded_asset(da, False)
say("manifest", path, "assets", len(da.get_editor_property("assets")))
say("DONE")
