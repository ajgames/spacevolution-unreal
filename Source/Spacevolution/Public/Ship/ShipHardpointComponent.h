#pragma once

#include "CoreMinimal.h"
#include "Components/SceneComponent.h"
#include "ShipHardpointComponent.generated.h"

class UShipFixtureDefinition;

/**
 * A named mounting point inside a module that holds one swappable fixture.
 * Fixtures are authored with +X pointing out of the surface and +Z up along it,
 * so the same fixture fits any hardpoint of its slot type regardless of the surface angle.
 */
UCLASS(ClassGroup = (Ship), meta = (BlueprintSpawnableComponent))
class SPACEVOLUTION_API UShipHardpointComponent : public USceneComponent
{
	GENERATED_BODY()

public:
	UShipHardpointComponent();

	/** Which fixtures fit here, matched against UShipFixtureDefinition::SlotTypes. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Hardpoint")
	FName SlotType = TEXT("Wall");

	/** Mounted when the layout doesn't override this hardpoint. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Hardpoint")
	TObjectPtr<UShipFixtureDefinition> DefaultFixture;

	/** Usable mounting area: X along the corridor (local Y), Y up the surface (local Z). For build-mode previews. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Hardpoint")
	FVector2D Extent = FVector2D(100.0, 100.0);
};
