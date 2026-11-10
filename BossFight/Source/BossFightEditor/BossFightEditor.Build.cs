using UnrealBuildTool;

public class BossFightEditor : ModuleRules
{
	public BossFightEditor(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine" });
		PrivateDependencyModuleNames.AddRange(new string[] {
			"BossFight", "BossFightAnimGraph", "UnrealEd", "AnimGraph", "AnimGraphRuntime", "BlueprintGraph", "Kismet",
			"KismetCompiler", "AssetTools", "AssetRegistry", "EditorScriptingUtilities", "Niagara"
		});
	}
}
