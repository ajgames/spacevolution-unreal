#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "SpacevolutionGameMode.generated.h"

/** Spawns the first-person crew character and its controller. A Blueprint subclass picks the configured Blueprints. */
UCLASS()
class SPACEVOLUTION_API ASpacevolutionGameMode : public AGameModeBase
{
	GENERATED_BODY()

public:
	ASpacevolutionGameMode();
};
