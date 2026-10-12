#include "Ship/LandingPad.h"
#include "Components/ArrowComponent.h"

ALandingPad::ALandingPad()
{
	USceneComponent* Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	Root->SetMobility(EComponentMobility::Static);
	SetRootComponent(Root);

#if WITH_EDITORONLY_DATA
	// Shows the landing heading in the editor.
	UArrowComponent* Arrow = CreateEditorOnlyDefaultSubobject<UArrowComponent>(TEXT("Heading"));
	if (Arrow)
	{
		Arrow->SetupAttachment(Root);
		Arrow->ArrowSize = 8.f;
		Arrow->ArrowColor = FColor(255, 170, 40);
	}
#endif
}

bool ALandingPad::IsInZone(const FVector& WorldLocation) const
{
	const FVector Offset = WorldLocation - GetActorLocation();
	return Offset.Size2D() <= ZoneRadius && Offset.Z >= -500.0 && Offset.Z <= ZoneHeight;
}
