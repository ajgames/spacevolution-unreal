#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "LandingPad.generated.h"

/**
 * Where a ship flying in the world can set down. The actor's location is where the ship's origin (its deck) comes to
 * rest, less the gear height; its yaw is the heading the ship lands on. A ship inside the zone above it can call
 * for the landing autopilot.
 */
UCLASS()
class SPACEVOLUTION_API ALandingPad : public AActor
{
	GENERATED_BODY()

public:
	ALandingPad();

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Landing Pad")
	FText DisplayName = NSLOCTEXT("LandingPad", "DefaultName", "Landing pad");

	/** How far out from the pad, horizontally, a ship can call for the autopilot. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Landing Pad", meta = (Units = "cm"))
	float ZoneRadius = 30000.f;

	/** How high above the pad a ship can call for the autopilot. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Landing Pad", meta = (Units = "cm"))
	float ZoneHeight = 60000.f;

	UFUNCTION(BlueprintPure, Category = "Landing Pad")
	bool IsInZone(const FVector& WorldLocation) const;
};
