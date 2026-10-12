#include "Ship/ShipTypes.h"

namespace ShipGrid
{
	static int32 NormalizeTurns(int32 QuarterTurns)
	{
		return ((QuarterTurns % 4) + 4) % 4;
	}

	FIntVector RotateCell(const FIntVector& Cell, int32 QuarterTurns)
	{
		switch (NormalizeTurns(QuarterTurns))
		{
		case 1:		return FIntVector(-Cell.Y, Cell.X, Cell.Z);
		case 2:		return FIntVector(-Cell.X, -Cell.Y, Cell.Z);
		case 3:		return FIntVector(Cell.Y, -Cell.X, Cell.Z);
		default:	return Cell;
		}
	}

	EShipCellFace RotateFace(EShipCellFace Face, int32 QuarterTurns)
	{
		if (Face == EShipCellFace::Up || Face == EShipCellFace::Down)
		{
			return Face;
		}
		return static_cast<EShipCellFace>((static_cast<int32>(Face) + NormalizeTurns(QuarterTurns)) % 4);
	}

	EShipCellFace OppositeFace(EShipCellFace Face)
	{
		switch (Face)
		{
		case EShipCellFace::Up:		return EShipCellFace::Down;
		case EShipCellFace::Down:	return EShipCellFace::Up;
		default:					return RotateFace(Face, 2);
		}
	}

	FIntVector FaceOffset(EShipCellFace Face)
	{
		switch (Face)
		{
		case EShipCellFace::Forward:	return FIntVector(1, 0, 0);
		case EShipCellFace::Right:		return FIntVector(0, 1, 0);
		case EShipCellFace::Back:		return FIntVector(-1, 0, 0);
		case EShipCellFace::Left:		return FIntVector(0, -1, 0);
		case EShipCellFace::Up:			return FIntVector(0, 0, 1);
		default:						return FIntVector(0, 0, -1);
		}
	}
}
