using UnrealBuildTool;

// Anim graph editor nodes for the project's custom anim nodes. UncookedOnly so it also loads in
// "-game" runs of the editor binary (an Editor module does not, and ABP_Sevarog then fails to load).
public class BossFightAnimGraph : ModuleRules
{
	public BossFightAnimGraph(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine", "BossFight", "AnimGraph", "AnimGraphRuntime", "BlueprintGraph" });
	}
}
