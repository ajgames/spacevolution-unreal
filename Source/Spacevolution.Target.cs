using UnrealBuildTool;
using System.Collections.Generic;

public class SpacevolutionTarget : TargetRules
{
	public SpacevolutionTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Game;
		DefaultBuildSettings = BuildSettingsVersion.V7;
		IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_8;
		ExtraModuleNames.Add("Spacevolution");
	}
}
