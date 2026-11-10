import unreal
for p in ["/Game/SlashHitVFX/NS/NS_Hit_Sword", "/Game/SlashHitVFX/NS/NS_Hit_Block",
          "/Game/Hack_And_Slash_FX/VFX_Niagara/Impacts/NS_Prestige_Slash_Impact",
          "/Game/Hack_And_Slash_FX/VFX_Niagara/Impacts/NS_Lightning_Slash_Impact",
          "/Game/Hack_And_Slash_FX/VFX_Niagara/Impacts/NS_Cyber_Slash_Impact",
          "/Game/Hack_And_Slash_FX/VFX_Niagara/Impacts/NS_Holy_Slash_Impact"]:
    for line in unreal.BFEditorTools.dump_niagara_user_params(p).splitlines():
        unreal.log("BFV %s | %s" % (p.split("/")[-1], line))
