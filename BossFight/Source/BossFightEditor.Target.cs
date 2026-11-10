using UnrealBuildTool;

public class BossFightEditorTarget : TargetRules
{
	public BossFightEditorTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Editor;
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		ExtraModuleNames.AddRange(new string[] { "BossFight", "BossFightAnimGraph", "BossFightEditor" });
	}
}
