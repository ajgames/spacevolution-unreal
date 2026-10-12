using UnrealBuildTool;

public class Spacevolution : ModuleRules
{
	public Spacevolution(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine" });
		PrivateDependencyModuleNames.AddRange(new string[] { "EnhancedInput", "RenderCore", "RHI" });
	}
}
