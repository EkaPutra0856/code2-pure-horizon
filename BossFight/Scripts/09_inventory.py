import unreal
ar = unreal.AssetRegistryHelpers.get_asset_registry()
ar.scan_paths_synchronous(["/Game"], True)
def lst(path, cls):
    f = unreal.ARFilter(package_paths=[path], recursive_paths=True, class_paths=[unreal.TopLevelAssetPath("/Script/Engine" if cls not in ("NiagaraSystem",) else "/Script/Niagara", cls)])
    return ar.get_assets(f)
for a in lst("/Game/InsaneAirCombo", "AnimSequence"):
    s = a.get_asset()
    print("BFI SEQ %s len=%.2f" % (a.package_name, s.get_play_length()))
for a in lst("/Game/InsaneAirCombo", "AnimMontage"):
    m = a.get_asset()
    secs = [str(x.get_editor_property("section_name")) for x in m.get_editor_property("composite_sections")]
    nts = []
    for n in m.get_editor_property("notifies"):
        nm = n.get_editor_property("notify_name")
        obj = n.get_editor_property("notify") or n.get_editor_property("notify_state_class")
        nts.append("%s@%.2f+%.2f(%s)" % (nm, n.get_editor_property("link_value") if False else n.get_editor_property("trigger_time_offset") if False else 0, n.get_editor_property("duration"), obj.get_class().get_name() if obj else "-"))
    print("BFI MON %s len=%.2f sections=%s notifies=%s" % (a.package_name, m.get_play_length(), secs, nts))
for p in ["/Game/SlashHitVFX", "/Game/Hack_And_Slash_FX", "/Game/InsaneAirCombo"]:
    for a in lst(p, "NiagaraSystem"):
        print("BFI NS", a.package_name)
    for a in lst(p, "ParticleSystem"):
        print("BFI PS", a.package_name)
for a in lst("/Game/Sounds", "SoundWave")[:400]:
    print("BFI SW", a.package_name)
for a in lst("/Game/Sounds", "SoundCue")[:200]:
    print("BFI SC", a.package_name)
for a in lst("/Game/InsaneAirCombo", "Blueprint"):
    print("BFI BP", a.package_name)
