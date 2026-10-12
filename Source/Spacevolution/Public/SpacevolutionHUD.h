#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "SpacevolutionHUD.generated.h"

/** Helm readouts while piloting, and the prompt to take the helm while walking. */
UCLASS()
class SPACEVOLUTION_API ASpacevolutionHUD : public AHUD
{
	GENERATED_BODY()

public:
	virtual void DrawHUD() override;

private:
	void DrawHelm(const class UShipFlightComponent& Flight, float Scale);
	void DrawCentred(const FString& Text, float Y, const FLinearColor& Color, float Scale);
};
