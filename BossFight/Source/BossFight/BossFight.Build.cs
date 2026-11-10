using UnrealBuildTool;

public class BossFight : ModuleRules
{
	public BossFight(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		PublicDependencyModuleNames.AddRange(new string[] {
			"Core", "CoreUObject", "Engine", "InputCore", "EnhancedInput", "AnimGraphRuntime", "Niagara", "RenderCore", "ProceduralMeshComponent", "AudioMixer"
		});
	}
}
