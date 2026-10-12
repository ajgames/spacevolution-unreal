#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "SpacevolutionHUD.generated.h"

class AArrivalDirector;
class UFont;

/**
 * Helm readouts while piloting, prompts for the use key (take the helm, board a wave rider), and, in a level with an
 * arrival director, the current objective with a marker on its target.
 */
UCLASS()
class SPACEVOLUTION_API ASpacevolutionHUD : public AHUD
{
	GENERATED_BODY()

public:
	virtual void DrawHUD() override;

protected:
	void DrawCentred(const FString& Text, float Y, const FLinearColor& Color, float Scale, UFont* Font = nullptr);
	/** The objective panel and target marker, if the level has an arrival director. */
	void DrawObjectives(float Scale);
	/** Short notices from the player controller. */
	void DrawNotice(float Scale);

private:
	void DrawHelm(const class UShipFlightComponent& Flight, float Scale);
	void DrawMarker(const FVector& Target, const FText& Label, float Scale);
	AArrivalDirector* FindDirector();

	TWeakObjectPtr<AArrivalDirector> Director;
	bool bLookedForDirector = false;
};
