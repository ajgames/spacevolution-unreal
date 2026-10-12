#pragma once

#include "CoreMinimal.h"
#include "GameFramework/SaveGame.h"
#include "Ship/ShipTypes.h"
#include "ShipSaveGame.generated.h"

/** A saved ship layout. Module and fixture definitions are stored as asset paths. */
UCLASS()
class SPACEVOLUTION_API UShipSaveGame : public USaveGame
{
	GENERATED_BODY()

public:
	UPROPERTY()
	int32 Version = 1;

	UPROPERTY()
	FShipLayout Layout;
};
