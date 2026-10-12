#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "Ship/ShipTypes.h"
#include "ShipPartDefinitions.generated.h"

class AShipModule;
class AShipFixture;
class UTexture2D;

/** Shared catalogue data for anything the player can place: what a build menu lists. */
UCLASS(Abstract, BlueprintType)
class SPACEVOLUTION_API UShipPartDefinition : public UPrimaryDataAsset
{
	GENERATED_BODY()

public:
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Catalogue", AssetRegistrySearchable)
	FText DisplayName;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Catalogue", meta = (MultiLine = true))
	FText Description;

	/** Grouping for build menus, e.g. "Corridor", "Bulkhead", "Console". */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Catalogue", AssetRegistrySearchable)
	FName Category;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Catalogue")
	TSoftObjectPtr<UTexture2D> Icon;
};

/** A structural piece that fills one or more ship-grid cells. */
UCLASS(BlueprintType)
class SPACEVOLUTION_API UShipModuleDefinition : public UShipPartDefinition
{
	GENERATED_BODY()

public:
	static const FPrimaryAssetType AssetType;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Module")
	TSoftClassPtr<AShipModule> ModuleClass;

	/** Cells the module fills, relative to its origin cell before rotation. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Module")
	TArray<FIntVector> OccupiedCells = { FIntVector::ZeroValue };

	/** Openings onto neighbouring cells. Faces without one are solid. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Module")
	TArray<FShipConnector> Connectors;

	/** Occupied cells in layout space for a module placed at Origin with the given rotation. */
	UFUNCTION(BlueprintPure, Category = "Module")
	TArray<FIntVector> GetPlacedCells(FIntVector Origin, int32 QuarterTurns) const;

	/** Type of the opening on a layout-space cell face, or None if that face is solid. */
	UFUNCTION(BlueprintPure, Category = "Module")
	FName GetConnectorAt(FIntVector Origin, int32 QuarterTurns, FIntVector Cell, EShipCellFace Face) const;

	virtual FPrimaryAssetId GetPrimaryAssetId() const override;
};

/** A swappable piece of equipment that mounts on a module hardpoint. */
UCLASS(BlueprintType)
class SPACEVOLUTION_API UShipFixtureDefinition : public UShipPartDefinition
{
	GENERATED_BODY()

public:
	static const FPrimaryAssetType AssetType;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Fixture")
	TSoftClassPtr<AShipFixture> FixtureClass;

	/** Hardpoint slot types this fixture can mount on, e.g. "Wall", "Chamfer", "Ceiling". */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Fixture")
	TArray<FName> SlotTypes;

	UFUNCTION(BlueprintPure, Category = "Fixture")
	bool FitsSlot(FName SlotType) const { return SlotTypes.Contains(SlotType); }

	virtual FPrimaryAssetId GetPrimaryAssetId() const override;
};
