#include "SpacevolutionHUD.h"
#include "Arrival/ArrivalDirector.h"
#include "SpacevolutionPlayerController.h"
#include "Ship/LandingPad.h"
#include "Ship/ShipFlightComponent.h"
#include "Camera/PlayerCameraManager.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/Font.h"
#include "EngineUtils.h"

namespace
{
	const FLinearColor HudHelmCyan(0.45f, 0.85f, 1.f, 0.95f);
	const FLinearColor HudHelmDim(0.70f, 0.80f, 0.90f, 0.70f);
	const FLinearColor HudPanelColor(0.f, 0.02f, 0.04f, 0.45f);
	const FLinearColor HudObjective(1.f, 0.78f, 0.42f, 0.98f);
	const FLinearColor HudMarker(1.f, 0.66f, 0.25f, 0.95f);

	FString FormatDistance(double Km)
	{
		if (Km < 1.0)
		{
			return FString::Printf(TEXT("%.0f m"), Km * 1000.0);
		}
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
	else if (Controller->FindRideableNearby())
	{
		DrawCentred(TEXT("[F]  ride the PWC-01"), Canvas->ClipY - 48.f * Scale, HudObjective, Scale);
	}
	else if (Controller->CanPilot())
	{
		DrawCentred(TEXT("[F]  take the helm"), Canvas->ClipY - 48.f * Scale, HudHelmDim, Scale);
	}
	DrawObjectives(Scale);
	DrawNotice(Scale);
}

void ASpacevolutionHUD::DrawCentred(const FString& Text, float Y, const FLinearColor& Color, float Scale, UFont* Font)
{
	Font = Font ? Font : GEngine->GetMediumFont();
	float W = 0.f, H = 0.f;
	GetTextSize(Text, W, H, Font, Scale);
	DrawText(Text, Color, (Canvas->ClipX - W) * 0.5f, Y, Font, Scale);
}

void ASpacevolutionHUD::DrawNotice(float Scale)
{
	const ASpacevolutionPlayerController* Controller = Cast<ASpacevolutionPlayerController>(PlayerOwner);
	const FText Notice = Controller ? Controller->GetNotice() : FText::GetEmpty();
	if (!Notice.IsEmpty())
	{
		DrawCentred(Notice.ToString(), Canvas->ClipY * 0.62f, HudObjective, Scale * 1.1f);
	}
}

AArrivalDirector* ASpacevolutionHUD::FindDirector()
{
	if (!bLookedForDirector)
	{
		bLookedForDirector = true;
		TActorIterator<AArrivalDirector> It(GetWorld());
		Director = It ? *It : nullptr;
	}
	return Director.Get();
}

void ASpacevolutionHUD::DrawObjectives(float Scale)
{
	const AArrivalDirector* Arrival = FindDirector();
	if (!Arrival || Arrival->GetObjective().IsEmpty())
	{
		return;
	}
	// Objective panel, top left.
	UFont* Font = GEngine->GetMediumFont();
	const FString Title = Arrival->GetObjective().ToString();
	const FString Hint = Arrival->GetHint().ToString();
	float TitleW = 0.f, TitleH = 0.f, HintW = 0.f, HintH = 0.f;
	GetTextSize(Title, TitleW, TitleH, Font, Scale * 1.25f);
	GetTextSize(Hint, HintW, HintH, Font, Scale * 0.85f);
	const float X = 36.f * Scale;
	const float Y = 34.f * Scale;
	const float PanelW = FMath::Max(TitleW, HintW) + 32.f * Scale;
	DrawRect(HudPanelColor, X - 14.f * Scale, Y - 8.f * Scale, PanelW, 78.f * Scale);
	DrawRect(HudObjective, X - 14.f * Scale, Y - 8.f * Scale, 3.f * Scale, 78.f * Scale);
	DrawText(TEXT("OBJECTIVE"), HudHelmDim, X, Y, GEngine->GetSmallFont(), Scale);
	DrawText(Title, HudObjective, X, Y + 16.f * Scale, Font, Scale * 1.25f);
	DrawText(Hint, HudHelmDim, X, Y + 46.f * Scale, Font, Scale * 0.85f);

	FVector Target;
	FText Label;
	if (Arrival->GetTarget(Target, Label))
	{
		DrawMarker(Target, Label, Scale);
	}
}

void ASpacevolutionHUD::DrawMarker(const FVector& Target, const FText& Label, float Scale)
{
	if (!PlayerOwner || !PlayerOwner->PlayerCameraManager)
	{
		return;
	}
	const APlayerCameraManager* View = PlayerOwner->PlayerCameraManager;
	const FVector Camera = View->GetCameraLocation();
	const FVector3f Local(View->GetCameraRotation().UnrotateVector(Target - Camera));  // X ahead, Y right, Z up
	const FVector2f Screen(Canvas->ClipX, Canvas->ClipY);
	const FVector2f Centre = Screen * 0.5f;
	const float Focal = Centre.X / FMath::Tan(FMath::DegreesToRadians(View->GetFOVAngle() * 0.5f));
	const FString Text = FString::Printf(TEXT("%s  %s"), *Label.ToString(), *FormatDistance((Target - Camera).Size() / 1.0e5));

	const float Margin = 60.f * Scale;
	FVector2f Point = Centre;
	bool bOnScreen = false;
	if (Local.X > 1.f)
	{
		Point = Centre + FVector2f(Local.Y, -Local.Z) / Local.X * Focal;
		bOnScreen = Point.X > Margin && Point.X < Screen.X - Margin && Point.Y > Margin && Point.Y < Screen.Y - Margin;
	}
	UFont* Font = GEngine->GetMediumFont();
	float W = 0.f, H = 0.f;
	GetTextSize(Text, W, H, Font, Scale);
	if (bOnScreen)
	{
		// A diamond on the target, its label underneath.
		const float R = 11.f * Scale;
		const FVector2f Corners[4] = {Point + FVector2f(0.f, -R), Point + FVector2f(R, 0.f), Point + FVector2f(0.f, R), Point + FVector2f(-R, 0.f)};
		for (int32 i = 0; i < 4; ++i)
		{
			DrawLine(Corners[i].X, Corners[i].Y, Corners[(i + 1) % 4].X, Corners[(i + 1) % 4].Y, HudMarker, 2.f * Scale);
		}
		DrawRect(HudMarker, Point.X - 2.f * Scale, Point.Y - 2.f * Scale, 4.f * Scale, 4.f * Scale);
		DrawText(Text, HudMarker, Point.X - W * 0.5f, Point.Y + R + 6.f * Scale, Font, Scale);
		return;
	}
	// Off screen or behind: an arrow on the screen edge pointing the way.
	FVector2f Direction(Local.Y, -Local.Z);
	if (Direction.IsNearlyZero())
	{
		Direction = FVector2f(0.f, 1.f);
	}
	Direction.Normalize();
	const FVector2f Half = Centre - FVector2f(Margin, Margin);
	const float Reach = FMath::Min(Half.X / FMath::Max(FMath::Abs(Direction.X), 1e-3f), Half.Y / FMath::Max(FMath::Abs(Direction.Y), 1e-3f));
	const FVector2f Tip = Centre + Direction * Reach;
	const FVector2f Side(-Direction.Y, Direction.X);
	const float Size = 16.f * Scale;
	const FVector2f Base = Tip - Direction * Size * 1.4f;
	DrawLine(Tip.X, Tip.Y, Base.X + Side.X * Size, Base.Y + Side.Y * Size, HudMarker, 2.5f * Scale);
	DrawLine(Tip.X, Tip.Y, Base.X - Side.X * Size, Base.Y - Side.Y * Size, HudMarker, 2.5f * Scale);
	const FVector2f LabelAt = Base - Direction * 18.f * Scale;
	DrawText(Text, HudMarker, FMath::Clamp(LabelAt.X - W * 0.5f, 8.f, Screen.X - W - 8.f),
		FMath::Clamp(LabelAt.Y - H * 0.5f, 8.f, Screen.Y - H - 8.f), Font, Scale);
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
	FString Controls = TEXT("WASD move   SPACE/CTRL rise/sink   MOUSE steer   Q/E roll   SHIFT surge   F leave helm");
	FString Status = TEXT("ZERO-POINT HELM");
	if (Flight.bFlyInWorld)
	{
		Controls += TEXT("   L land");
		switch (Flight.GetLandingState())
		{
		case EShipLandingState::Approaching:
		case EShipLandingState::Descending:
			Status = TEXT("AUTOPILOT - LANDING    [L] take back the helm");
			break;
		case EShipLandingState::Lifting:
			Status = TEXT("AUTOPILOT - LIFTING OFF");
			break;
		case EShipLandingState::Landed:
			Status = TEXT("LANDED    [L] lift off");
			break;
		default:
			if (const ALandingPad* Pad = Flight.FindPadInRange())
			{
				Status = FString::Printf(TEXT("[L]  land on %s"), *Pad->DisplayName.ToString());
			}
			break;
		}
	}

	UFont* Font = GEngine->GetMediumFont();
	float W = 0.f, H = 0.f;
	GetTextSize(Readout, W, H, Font, Scale);
	const float PanelW = FMath::Max(W, 620.f * Scale) + 40.f * Scale;
	const float PanelY = Canvas->ClipY - 96.f * Scale;
	DrawRect(HudPanelColor, CX - PanelW * 0.5f, PanelY, PanelW, 72.f * Scale);
	DrawCentred(Status, PanelY + 6.f * Scale, Status.StartsWith(TEXT("ZERO")) ? HudHelmDim : HudObjective, Scale * 0.8f);
	DrawCentred(Readout, PanelY + 24.f * Scale, HudHelmCyan, Scale);
	DrawCentred(Controls, PanelY + 50.f * Scale, HudHelmDim, Scale * 0.7f);
}
