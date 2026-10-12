#pragma once

#include "CoreMinimal.h"
#include "ShipTypes.generated.h"

class UShipModuleDefinition;
class UShipFixtureDefinition;

/** A face of a ship-grid cell. Horizontal faces are listed in yaw order so a quarter turn is +1. */
UENUM(BlueprintType)
enum class EShipCellFace : uint8
{
	Forward,	// +X
	Right,		// +Y
	Back,		// -X
	Left,		// -Y
	Up,			// +Z
	Down		// -Z
};

/** An opening on one face of a module that can join a neighbouring module's opening of the same type. */
USTRUCT(BlueprintType)
struct FShipConnector
{
	GENERATED_BODY()

	/** Cell the opening sits on, relative to the module's origin cell before rotation. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ship")
	FIntVector Cell = FIntVector::ZeroValue;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ship")
	EShipCellFace Face = EShipCellFace::Forward;

	/** Openings only join when their types match, e.g. "Corridor". */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ship")
	FName ConnectorType = TEXT("Corridor");
};

/**
 * One module in a ship layout. The layout, not the spawned actors, is the source of truth:
 * it is what gets saved, loaded and edited by build mode.
 */
USTRUCT(BlueprintType)
struct FShipModulePlacement
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ship")
	TObjectPtr<UShipModuleDefinition> Module;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ship")
	FIntVector Cell = FIntVector::ZeroValue;

	/** Yaw in 90 degree steps (+X turns toward +Y). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ship", meta = (ClampMin = 0, ClampMax = 3))
	int32 QuarterTurns = 0;

	/**
	 * Fixture swaps keyed by hardpoint name. A key mapped to None leaves that hardpoint empty;
	 * hardpoints that aren't listed keep their default fixture.
	 */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ship")
	TMap<FName, TObjectPtr<UShipFixtureDefinition>> FixtureOverrides;
};

USTRUCT(BlueprintType)
struct FShipLayout
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ship")
	TArray<FShipModulePlacement> Modules;
};

namespace ShipGrid
{
	/** Rotates a cell offset by quarter turns of yaw about the origin cell. */
	SPACEVOLUTION_API FIntVector RotateCell(const FIntVector& Cell, int32 QuarterTurns);

	SPACEVOLUTION_API EShipCellFace RotateFace(EShipCellFace Face, int32 QuarterTurns);

	SPACEVOLUTION_API EShipCellFace OppositeFace(EShipCellFace Face);

	/** Offset to the neighbouring cell across a face. */
	SPACEVOLUTION_API FIntVector FaceOffset(EShipCellFace Face);
}
