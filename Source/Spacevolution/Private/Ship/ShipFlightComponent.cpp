#include "Ship/ShipFlightComponent.h"

UShipFlightComponent::UShipFlightComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.TickGroup = TG_PrePhysics;
}

void UShipFlightComponent::OnRegister()
{
	Super::OnRegister();
	PositionKm = StartPositionKm;
	Rotation = StartRotation.Quaternion();
	VelocityKmPerSecond = FVector::ZeroVector;
}

void UShipFlightComponent::SetTranslation(FVector ShipSpaceInput)
{
	TranslationInput = ShipSpaceInput.GetClampedToMaxSize(1.0);
}

void UShipFlightComponent::AddSteering(float YawDegrees, float PitchDegrees)
{
	PendingSteering += FVector2D(YawDegrees, PitchDegrees);
}

void UShipFlightComponent::SetRoll(float Input)
{
	RollInput = FMath::Clamp(Input, -1.f, 1.f);
}

void UShipFlightComponent::SetSurge(bool bSurge)
{
	bSurging = bSurge;
}

void UShipFlightComponent::ReleaseControls()
{
	TranslationInput = FVector::ZeroVector;
	PendingSteering = FVector2D::ZeroVector;
	RollInput = 0.f;
	bSurging = false;
}

void UShipFlightComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);

	// Surge builds exponentially while held and vanishes the instant it's released.
	Surge = bSurging ? FMath::Min(MaxSurge, Surge * FMath::Pow(MaxSurge, DeltaTime / SurgeRampSeconds)) : 1.f;

	// Turning: no angular momentum, the hull simply points where it's told.
	const FRotator Turn(PendingSteering.Y, PendingSteering.X, RollInput * RollDegreesPerSecond * DeltaTime);
	PendingSteering = FVector2D::ZeroVector;
	Rotation = (Rotation * Turn.Quaternion()).GetNormalized();

	// Translating: velocity converges on the command almost at once, in any direction, and stops dead on release.
	const double Altitude = FMath::Max(GetAltitudeKm(), 0.0);
	const double Cruise = FMath::Max(Altitude * CruisePerSecond, MinCruiseKmPerSecond);
	const FVector Commanded = Rotation.RotateVector(TranslationInput) * (Cruise * Surge);
	const double Blend = 1.0 - FMath::Exp(-DeltaTime / ResponseSeconds);
	VelocityKmPerSecond = FMath::Lerp(VelocityKmPerSecond, Commanded, Blend);
	PositionKm += VelocityKmPerSecond * DeltaTime;

	// Keep clear of the ground and within range; slide along the limit rather than bouncing off it.
	const double Radius = PositionKm.Size();
	const double Lowest = PlanetRadiusKm + MinAltitudeKm;
	const double Highest = PlanetRadiusKm + MaxAltitudeKm;
	if (Radius < Lowest || Radius > Highest)
	{
		const FVector Up = PositionKm / FMath::Max(Radius, 1.0);
		PositionKm = Up * FMath::Clamp(Radius, Lowest, Highest);
		const double Radial = FVector::DotProduct(VelocityKmPerSecond, Up);
		if ((Radius < Lowest && Radial < 0.0) || (Radius > Highest && Radial > 0.0))
		{
			VelocityKmPerSecond -= Up * Radial;
		}
	}
}
