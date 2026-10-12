#pragma once

#include "CoreMinimal.h"
#include "SpacevolutionGameMode.h"
#include "ArrivalGameMode.generated.h"

/**
 * Starts the player at the player start carrying PlayerStartTag (aboard the arriving ship), ignoring any other
 * starts that streamed-in sublevels bring with them.
 */
UCLASS()
class SPACEVOLUTION_API AArrivalGameMode : public ASpacevolutionGameMode
{
	GENERATED_BODY()

public:
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Arrival")
	FName PlayerStartTag = TEXT("Arrival");

	virtual AActor* ChoosePlayerStart_Implementation(AController* Player) override;
};
