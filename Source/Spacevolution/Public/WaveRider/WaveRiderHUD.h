#pragma once

#include "CoreMinimal.h"
#include "SpacevolutionHUD.h"
#include "WaveRiderHUD.generated.h"

class AWaveRider;

/**
 * Speedometer, burst charge and air time for the wave rider, plus a reminder of the controls. On foot or at a helm it
 * draws the crew HUD instead, so one HUD serves a level where the player arrives by ship and rides off.
 */
UCLASS()
class SPACEVOLUTION_API AWaveRiderHUD : public ASpacevolutionHUD
{
	GENERATED_BODY()

public:
	virtual void DrawHUD() override;

	/** Seconds the controls stay on screen after the player takes the rider. */
	UPROPERTY(EditDefaultsOnly, Category = "HUD", meta = (Units = "s"))
	float ControlsHintSeconds = 25.f;

private:
	void DrawBurstMeter(const AWaveRider& Rider, float CentreX, float Y, float Scale);
};
