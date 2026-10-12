#include "Arrival/ArrivalGameMode.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerStart.h"

AActor* AArrivalGameMode::ChoosePlayerStart_Implementation(AController* Player)
{
	for (TActorIterator<APlayerStart> It(GetWorld()); It; ++It)
	{
		if (It->PlayerStartTag == PlayerStartTag)
		{
			return *It;
		}
	}
	return Super::ChoosePlayerStart_Implementation(Player);
}
