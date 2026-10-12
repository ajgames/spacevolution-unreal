#include "SpacevolutionHUD.h"
#include "SpacevolutionPlayerController.h"
#include "Ship/ShipFlightComponent.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/Font.h"

namespace
{
	const FLinearColor HudHelmCyan(0.45f, 0.85f, 1.f, 0.95f);
	const FLinearColor HudHelmDim(0.70f, 0.80f, 0.90f, 0.70f);
	const FLinearColor HudPanelColor(0.f, 0.02f, 0.04f, 0.45f);

	FString FormatDistance(double Km)
	{
		return Km < 1000.0 ? FString::Printf(TEXT("%.1f km"), Km) : FString::Printf(TEXT("%s km"), *FText::AsNumber(FMath::RoundToInt64(Km)).ToString());
	}

	FString FormatSpeed(double KmPerSecond)
	{
		constexpr double LightKmPerSecond = 299792.458;
		if (KmPerSecond < 1.0)
		{
			return FString::Printf(TEXT("%.0f m/s"), KmPerSecond * 1000.0);
		}
		if (KmPerSecond < LightKmPerSecond * 0.01)
		{
			return FString::Printf(TEXT("%.1f km/s"), KmPerSecond);
		}
		return FString::Printf(TEXT("%.3f c"), KmPerSecond / LightKmPerSecond);
	}
}

void ASpacevolutionHUD::DrawHUD()
{
	Super::DrawHUD();

	const ASpacevolutionPlayerController* Controller = Cast<ASpacevolutionPlayerController>(PlayerOwner);
	if (!Controller || !Canvas)
	{
		return;
	}
	const float Scale = FMath::Clamp(Canvas->ClipY / 1080.f, 0.85f, 2.5f);

	if (const UShipFlightComponent* Flight = Controller->GetPilotedFlight())
	{
		DrawHelm(*Flight, Scale);
	}
	else if (Controller->CanPilot())
	{
		DrawCentred(TEXT("[F]  take the helm"), Canvas->ClipY - 48.f * Scale, HudHelmDim, Scale);
	}
}

void ASpacevolutionHUD::DrawCentred(const FString& Text, float Y, const FLinearColor& Color, float Scale)
{
	UFont* Font = GEngine->GetMediumFont();
	float W = 0.f, H = 0.f;
	GetTextSize(Text, W, H, Font, Scale);
	DrawText(Text, Color, (Canvas->ClipX - W) * 0.5f, Y, Font, Scale);
}

void ASpacevolutionHUD::DrawHelm(const UShipFlightComponent& Flight, float Scale)
{
	const float CX = Canvas->ClipX * 0.5f;
	const float CY = Canvas->ClipY * 0.5f;

	// Reticle: a broken ring with a centre dot.
	const float R = 14.f * Scale;
	for (int32 Quadrant = 0; Quadrant < 4; ++Quadrant)
	{
		const float Start = Quadrant * HALF_PI + 0.25f;
		const float End = Start + HALF_PI - 0.5f;
		constexpr int32 Segments = 6;
		for (int32 i = 0; i < Segments; ++i)
		{
			const float A0 = FMath::Lerp(Start, End, i / float(Segments));
			const float A1 = FMath::Lerp(Start, End, (i + 1) / float(Segments));
			DrawLine(CX + R * FMath::Cos(A0), CY + R * FMath::Sin(A0), CX + R * FMath::Cos(A1), CY + R * FMath::Sin(A1), HudHelmCyan, 1.5f * Scale);
		}
	}
	DrawRect(HudHelmCyan, CX - 1.5f * Scale, CY - 1.5f * Scale, 3.f * Scale, 3.f * Scale);

	// Readouts along the bottom.
	const FString Readout = FString::Printf(TEXT("ALT  %s      SPD  %s      SURGE  x%.0f"),
		*FormatDistance(Flight.GetAltitudeKm()), *FormatSpeed(Flight.GetSpeedKmPerSecond()), Flight.GetSurge());
	const FString Controls = TEXT("WASD move   SPACE/CTRL rise/sink   MOUSE steer   Q/E roll   SHIFT surge   F leave helm");

	UFont* Font = GEngine->GetMediumFont();
	float W = 0.f, H = 0.f;
	GetTextSize(Readout, W, H, Font, Scale);
	const float PanelW = FMath::Max(W, 560.f * Scale) + 40.f * Scale;
	const float PanelY = Canvas->ClipY - 96.f * Scale;
	DrawRect(HudPanelColor, CX - PanelW * 0.5f, PanelY, PanelW, 72.f * Scale);
	DrawCentred(TEXT("ZERO-POINT HELM"), PanelY + 6.f * Scale, HudHelmDim, Scale * 0.8f);
	DrawCentred(Readout, PanelY + 24.f * Scale, HudHelmCyan, Scale);
	DrawCentred(Controls, PanelY + 50.f * Scale, HudHelmDim, Scale * 0.7f);
}
