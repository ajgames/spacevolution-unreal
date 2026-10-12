#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "ShipModule.generated.h"

class AShipFixture;
class UShipFixtureDefinition;
class UShipHardpointComponent;
class UShipModuleDefinition;

/**
 * Base for a structural ship module. Blueprint subclasses hold the meshes, lights and
 * hardpoints; they are authored with the origin cell centred on the actor and the deck at Z = 0.
 */
UCLASS(Blueprintable)
class SPACEVOLUTION_API AShipModule : public AActor
{
	GENERATED_BODY()

public:
	AShipModule();

	UFUNCTION(BlueprintPure, Category = "Module")
	UShipModuleDefinition* GetDefinition() const { return Definition; }

	UFUNCTION(BlueprintPure, Category = "Module")
	FIntVector GetCell() const { return Cell; }

	UFUNCTION(BlueprintPure, Category = "Module")
	int32 GetQuarterTurns() const { return QuarterTurns; }

	UFUNCTION(BlueprintPure, Category = "Module")
	TArray<UShipHardpointComponent*> GetHardpoints() const;

	UFUNCTION(BlueprintPure, Category = "Module")
	UShipHardpointComponent* FindHardpoint(FName HardpointName) const;

	UFUNCTION(BlueprintPure, Category = "Module")
	AShipFixture* GetFixture(FName HardpointName) const;

	/** Replaces whatever is mounted on a hardpoint. Pass None to leave it empty. */
	UFUNCTION(BlueprintCallable, Category = "Module")
	AShipFixture* MountFixture(FName HardpointName, UShipFixtureDefinition* Fixture);

	/** Mounts every hardpoint: the override when the map has one, otherwise the hardpoint's default. */
	void MountFixtures(const TMap<FName, TObjectPtr<UShipFixtureDefinition>>& Overrides);

	void ClearFixtures();

	void InitModule(UShipModuleDefinition* InDefinition, FIntVector InCell, int32 InQuarterTurns);

	virtual void Destroyed() override;

private:
	UPROPERTY(VisibleInstanceOnly, Category = "Module")
	TObjectPtr<UShipModuleDefinition> Definition;

	UPROPERTY(VisibleInstanceOnly, Category = "Module")
	FIntVector Cell = FIntVector::ZeroValue;

	UPROPERTY(VisibleInstanceOnly, Category = "Module")
	int32 QuarterTurns = 0;

	/**
	 * Lives on the actor rather than the hardpoints so it survives construction-script reruns.
	 * Not carried over by editor duplication, so a copied module never destroys the original's fixtures.
	 */
	UPROPERTY(VisibleInstanceOnly, NonPIEDuplicateTransient, TextExportTransient, Category = "Module")
	TMap<FName, TObjectPtr<AShipFixture>> Fixtures;
};
