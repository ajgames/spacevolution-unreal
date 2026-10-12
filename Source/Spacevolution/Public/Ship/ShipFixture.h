#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "ShipFixture.generated.h"

class UShipFixtureDefinition;

/** Base for equipment mounted on a module hardpoint. Blueprint subclasses add the meshes and lights. */
UCLASS(Blueprintable)
class SPACEVOLUTION_API AShipFixture : public AActor
{
	GENERATED_BODY()

public:
	AShipFixture();

	UFUNCTION(BlueprintPure, Category = "Fixture")
	UShipFixtureDefinition* GetDefinition() const { return Definition; }

	UFUNCTION(BlueprintPure, Category = "Fixture")
	FName GetHardpointName() const { return HardpointName; }

	void InitFixture(UShipFixtureDefinition* InDefinition, FName InHardpointName);

private:
	UPROPERTY(VisibleInstanceOnly, Category = "Fixture")
	TObjectPtr<UShipFixtureDefinition> Definition;

	UPROPERTY(VisibleInstanceOnly, Category = "Fixture")
	FName HardpointName;
};
