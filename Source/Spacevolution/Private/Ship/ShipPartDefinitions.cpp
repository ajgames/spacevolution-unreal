#include "Ship/ShipPartDefinitions.h"

const FPrimaryAssetType UShipModuleDefinition::AssetType = TEXT("ShipModule");
const FPrimaryAssetType UShipFixtureDefinition::AssetType = TEXT("ShipFixture");

TArray<FIntVector> UShipModuleDefinition::GetPlacedCells(FIntVector Origin, int32 QuarterTurns) const
{
	TArray<FIntVector> Cells;
	Cells.Reserve(OccupiedCells.Num());
	for (const FIntVector& Cell : OccupiedCells)
	{
		Cells.Add(Origin + ShipGrid::RotateCell(Cell, QuarterTurns));
	}
	return Cells;
}

FName UShipModuleDefinition::GetConnectorAt(FIntVector Origin, int32 QuarterTurns, FIntVector Cell, EShipCellFace Face) const
{
	for (const FShipConnector& Connector : Connectors)
	{
		if (Origin + ShipGrid::RotateCell(Connector.Cell, QuarterTurns) == Cell
			&& ShipGrid::RotateFace(Connector.Face, QuarterTurns) == Face)
		{
			return Connector.ConnectorType;
		}
	}
	return NAME_None;
}

FPrimaryAssetId UShipModuleDefinition::GetPrimaryAssetId() const
{
	return FPrimaryAssetId(AssetType, GetFName());
}

FPrimaryAssetId UShipFixtureDefinition::GetPrimaryAssetId() const
{
	return FPrimaryAssetId(AssetType, GetFName());
}
