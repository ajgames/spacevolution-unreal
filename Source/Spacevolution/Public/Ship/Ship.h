#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Ship/ShipTypes.h"
#include "Ship.generated.h"

class AShipModule;
class UShipFixtureDefinition;
class UShipFlightComponent;
class UShipModuleDefinition;

DECLARE_DYNAMIC_MULTICAST_DELEGATE(FShipLayoutChangedSignature);

/**
 * Owns a ship layout and keeps spawned module actors in sync with it.
 * In the editor, edit Layout and press Rebuild. At runtime, build mode should go through
 * AddModule / RemoveModuleAt / SetFixture so the layout stays the thing that gets saved.
 *
 * Grid: cell (X, Y, Z) is centred at (X, Y) * CellSize in ship space, with its deck at Z * CellSize.
 */
UCLASS()
class SPACEVOLUTION_API AShip : public AActor
{
	GENERATED_BODY()

public:
	AShip();

	/** Edge length of one grid cell in cm. Modules are authored to this size. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Ship", meta = (ClampMin = 100))
	double CellSize = 600.0;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Ship")
	FShipLayout Layout;

	UPROPERTY(BlueprintAssignable, Category = "Ship")
	FShipLayoutChangedSignature OnLayoutChanged;

	/** Destroys the spawned modules and respawns them from Layout. */
	UFUNCTION(CallInEditor, BlueprintCallable, Category = "Ship")
	void Rebuild();

	/** True when the module fits: no overlaps, every shared face matches, and it joins the ship if the ship isn't empty. */
	UFUNCTION(BlueprintCallable, Category = "Ship|Editing")
	bool CanPlaceModule(const UShipModuleDefinition* Module, FIntVector Cell, int32 QuarterTurns, FText& OutReason) const;

	UFUNCTION(BlueprintCallable, Category = "Ship|Editing")
	AShipModule* AddModule(UShipModuleDefinition* Module, FIntVector Cell, int32 QuarterTurns);

	UFUNCTION(BlueprintCallable, Category = "Ship|Editing")
	bool RemoveModuleAt(FIntVector Cell);

	/** Swaps the fixture on one hardpoint of the module covering Cell. None empties the hardpoint. */
	UFUNCTION(BlueprintCallable, Category = "Ship|Editing")
	bool SetFixture(FIntVector Cell, FName Hardpoint, UShipFixtureDefinition* Fixture);

	UFUNCTION(BlueprintPure, Category = "Ship|Grid")
	AShipModule* GetModuleAt(FIntVector Cell) const;

	/** World transform for a module placed at Cell with the given rotation. */
	UFUNCTION(BlueprintPure, Category = "Ship|Grid")
	FTransform GetCellTransform(FIntVector Cell, int32 QuarterTurns) const;

	UFUNCTION(BlueprintPure, Category = "Ship|Grid")
	FIntVector WorldToCell(FVector WorldLocation) const;

	UFUNCTION(BlueprintPure, Category = "Ship|Flight")
	UShipFlightComponent* GetFlight() const { return Flight; }

	/** Module holding the helm viewpoint (a camera component named HelmView), or null if none is fitted. */
	UFUNCTION(BlueprintPure, Category = "Ship|Flight")
	AShipModule* FindHelmModule() const;

	UFUNCTION(BlueprintCallable, Category = "Ship|Save")
	bool SaveLayout(const FString& SlotName, int32 UserIndex = 0) const;

	/** Replaces the layout with a saved one and rebuilds. */
	UFUNCTION(BlueprintCallable, Category = "Ship|Save")
	bool LoadLayout(const FString& SlotName, int32 UserIndex = 0);

protected:
	virtual void BeginPlay() override;
	virtual void Destroyed() override;

private:
	UPROPERTY(VisibleAnywhere, Category = "Ship|Flight")
	TObjectPtr<UShipFlightComponent> Flight;

	/**
	 * Spawned actor for each entry in Layout.Modules, by index. Not carried over when the ship is duplicated or
	 * pasted in the editor, so a copy never owns the original's modules. Press Rebuild on the copy (it also
	 * rebuilds itself at BeginPlay when this is empty).
	 */
	UPROPERTY(VisibleInstanceOnly, NonPIEDuplicateTransient, TextExportTransient, Category = "Ship")
	TArray<TObjectPtr<AShipModule>> ModuleActors;

	TMap<FIntVector, int32> BuildOccupancy() const;
	int32 FindPlacementIndex(FIntVector Cell) const;
	AShipModule* SpawnModule(const FShipModulePlacement& Placement);
	void DestroyModules();
};
