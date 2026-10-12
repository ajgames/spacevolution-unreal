#include "WaveRider/WaveRiderHUD.h"
#include "WaveRider/WaveRider.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/Font.h"
#include "GameFramework/PlayerController.h"

namespace
{
	// The PWC-01's amber trim.
	const FLinearColor HudAmber(1.f, 0.62f, 0.22f, 0.95f);
	const FLinearColor HudHot(1.f, 0.86f, 0.55f, 1.f);
	const FLinearColor HudLow(1.f, 0.28f, 0.16f, 0.95f);
	const FLinearColor HudDim(0.92f, 0.88f, 0.82f, 0.75f);
	const FLinearColor HudPanel(0.02f, 0.02f, 0.03f, 0.45f);
}

void AWaveRiderHUD::DrawCentred(const FString& Text, float Y, const FLinearColor& Color, UFont* Font, float Scale)
{
	float W = 0.f, H = 0.f;
	GetTextSize(Text, W, H, Font, Scale);
	DrawText(Text, Color, (Canvas->ClipX - W) * 0.5f, Y, Font, Scale);
}

void AWaveRiderHUD::DrawHUD()
{
	Super::DrawHUD();

	const AWaveRider* Rider = PlayerOwner ? Cast<AWaveRider>(PlayerOwner->GetPawn()) : nullptr;
	if (!Rider || !Canvas)
	{
		return;
	}
	const float Scale = FMath::Clamp(Canvas->ClipY / 1080.f, 0.85f, 2.5f);
	const float CX = Canvas->ClipX * 0.5f;
	UFont* Large = GEngine->GetLargeFont();
	UFont* Medium = GEngine->GetMediumFont();

	// Speed and burst charge in a panel at the bottom.
	const float PanelW = 300.f * Scale;
	const float PanelH = 92.f * Scale;
	const float PanelY = Canvas->ClipY - PanelH - 28.f * Scale;
	DrawRect(HudPanel, CX - PanelW * 0.5f, PanelY, PanelW, PanelH);
	const FString Speed = FString::Printf(TEXT("%d km/h"), FMath::RoundToInt(Rider->GetSpeedKmh()));
	DrawCentred(Speed, PanelY + 8.f * Scale, Rider->IsBoosting() ? HudHot : HudAmber, Large, Scale * 1.6f);
	DrawBurstMeter(*Rider, CX, PanelY + 58.f * Scale, Scale);

	// Air time while airborne, and the last and best jumps.
	if (Rider->IsAirborne() && Rider->GetAirTime() > 0.25f)
	{
		const FString Air = FString::Printf(TEXT("AIR  %.1f s   %.1f m"), Rider->GetAirTime(), FMath::Max(Rider->GetHeightAboveSurface(), 0.f));
		DrawCentred(Air, PanelY - 40.f * Scale, Rider->IsBursting() ? HudHot : HudAmber, Medium, Scale * 1.3f);
	}
	else if (Rider->GetBestAirTime() > 0.f)
	{
		const FString Record = FString::Printf(TEXT("last air %.1f s    best %.1f s"), Rider->GetLastAirTime(), Rider->GetBestAirTime());
		DrawCentred(Record, PanelY - 28.f * Scale, HudDim, Medium, Scale);
	}

	if (Rider->GetGameTimeSinceCreation() < ControlsHintSeconds)
	{
		const FString Controls = TEXT("W/S throttle    A/D steer    SPACE jump, hold in the air to burst    SHIFT boost    MOUSE look    R reset");
		DrawCentred(Controls, 24.f * Scale, HudDim, Medium, Scale * 0.85f);
	}
}

void AWaveRiderHUD::DrawBurstMeter(const AWaveRider& Rider, float CentreX, float Y, float Scale)
{
	const float W = 240.f * Scale;
	const float H = 10.f * Scale;
	const float X = CentreX - W * 0.5f;
	const float Charge = Rider.GetBurstCharge();
	const FLinearColor Fill = Rider.IsBursting() ? HudHot : (Charge < 0.2f ? HudLow : HudAmber);

	DrawRect(FLinearColor(0.f, 0.f, 0.f, 0.5f), X, Y, W, H);
	DrawRect(Fill, X, Y, W * Charge, H);
	// Ticks every quarter, so the charge reads at a glance.
	for (int32 i = 1; i < 4; ++i)
	{
		DrawRect(HudPanel, X + W * i / 4.f - Scale, Y, 2.f * Scale, H);
	}
	DrawCentred(TEXT("BURST"), Y + H + 3.f * Scale, HudDim, GEngine->GetSmallFont(), Scale);
}
