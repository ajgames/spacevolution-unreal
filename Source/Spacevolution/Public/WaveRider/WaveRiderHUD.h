#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "WaveRiderHUD.generated.h"

class AWaveRider;

/** Speedometer, burst charge and air time for the wave rider, plus a reminder of the controls. */
UCLASS()
class SPACEVOLUTION_API AWaveRiderHUD : public AHUD
{
	GENERATED_BODY()

public:
	virtual void DrawHUD() override;

	/** Seconds the controls stay on screen after the rider spawns. */
	UPROPERTY(EditDefaultsOnly, Category = "HUD", meta = (Units = "s"))
	float ControlsHintSeconds = 25.f;

private:
	void DrawCentred(const FString& Text, float Y, const FLinearColor& Color, class UFont* Font, float Scale);
	void DrawBurstMeter(const AWaveRider& Rider, float CentreX, float Y, float Scale);
};
