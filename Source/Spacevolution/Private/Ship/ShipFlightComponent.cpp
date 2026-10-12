#include "Ship/ShipFlightComponent.h"
#include "Ship/LandingPad.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Actor.h"

namespace
{
	constexpr double CmPerKm = 1.0e5;
	constexpr double CmPerM = 100.0;
	// Below this the autopilot counts as arrived.
	constexpr double ArriveCm = 40.0;
	constexpr double AlignedDegrees = 2.0;
}

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
	if (bFlyInWorld)
	{
		SyncFromOwner();
	}
}

void UShipFlightComponent::BeginPlay()
{
	Super::BeginPlay();
	if (bFlyInWorld)
	{
		SyncFromOwner();
	}
}

void UShipFlightComponent::SyncFromOwner()
{
	if (const AActor* Owner = GetOwner())
	{
		PositionKm = SpaceFromWorld(Owner->GetActorLocation());
		Rotation = Owner->GetActorQuat();
	}
}

FVector UShipFlightComponent::WorldFromSpace(const FVector& SpaceKm) const
{
	// The planet's top sits at the world origin, so its centre is a radius below it.
	return (SpaceKm - FVector(0.0, 0.0, PlanetRadiusKm)) * CmPerKm;
}

FVector UShipFlightComponent::SpaceFromWorld(const FVector& WorldCm) const
{
	return WorldCm / CmPerKm + FVector(0.0, 0.0, PlanetRadiusKm);
}

void UShipFlightComponent::SetCollision(const FBox& LocalBox, const TArray<AActor*>& IgnoredActors)
{
	CollisionBox = LocalBox;
	CollisionIgnored.Reset();
	for (AActor* Actor : IgnoredActors)
	{
		CollisionIgnored.Add(Actor);
	}
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

ALandingPad* UShipFlightComponent::FindPadInRange() const
{
	const AActor* Owner = GetOwner();
	UWorld* World = GetWorld();
	if (!bFlyInWorld || !Owner || !World)
	{
		return nullptr;
	}
	ALandingPad* Best = nullptr;
	double BestDistance = UE_BIG_NUMBER;
	for (TActorIterator<ALandingPad> It(World); It; ++It)
	{
		const double Distance = FVector::Dist(It->GetActorLocation(), Owner->GetActorLocation());
		if (It->IsInZone(Owner->GetActorLocation()) && Distance < BestDistance)
		{
			Best = *It;
			BestDistance = Distance;
		}
	}
	return Best;
}

bool UShipFlightComponent::ToggleLanding()
{
	if (!bFlyInWorld)
	{
		return false;
	}
	switch (LandingState)
	{
	case EShipLandingState::Landed:
		LandingState = EShipLandingState::Lifting;
		OnLiftingOff.Broadcast();
		return true;
	case EShipLandingState::Approaching:
	case EShipLandingState::Descending:
		// Pilot takes back over.
		LandingState = EShipLandingState::Flying;
		Pad.Reset();
		return true;
	case EShipLandingState::Lifting:
		return false;
	default:
		break;
	}
	if (ALandingPad* InRange = FindPadInRange())
	{
		Pad = InRange;
		LandingState = EShipLandingState::Approaching;
		ReleaseControls();
		return true;
	}
	return false;
}

void UShipFlightComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);

	if (bFlyInWorld && LandingState != EShipLandingState::Flying)
	{
		TickAutopilot(DeltaTime);
		return;
	}

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

	if (bFlyInWorld)
	{
		MoveOwner();
	}
}

void UShipFlightComponent::MoveOwner()
{
	AActor* Owner = GetOwner();
	UWorld* World = GetWorld();
	if (!Owner || !World)
	{
		return;
	}
	const FVector From = Owner->GetActorLocation();
	FVector To = WorldFromSpace(PositionKm);

	// Sweep the ship's box along the move; stop at anything solid and lose the speed going into it.
	if (CollisionBox.IsValid && !From.Equals(To, 0.1))
	{
		FCollisionQueryParams Params(SCENE_QUERY_STAT(ShipFlight), false, Owner);
		for (const TWeakObjectPtr<AActor>& Ignored : CollisionIgnored)
		{
			if (Ignored.IsValid())
			{
				Params.AddIgnoredActor(Ignored.Get());
			}
		}
		const FVector Centre = Rotation.RotateVector(CollisionBox.GetCenter());
		FHitResult Hit;
		if (World->SweepSingleByObjectType(Hit, From + Centre, To + Centre, Rotation, FCollisionObjectQueryParams(ECC_WorldStatic),
				FCollisionShape::MakeBox(CollisionBox.GetExtent()), Params)
			&& !Hit.bStartPenetrating)
		{
			To = Hit.Location - Centre + Hit.Normal * 2.0;
			PositionKm = SpaceFromWorld(To);
			const double Into = FVector::DotProduct(VelocityKmPerSecond, Hit.Normal);
			if (Into < 0.0)
			{
				VelocityKmPerSecond -= Hit.Normal * Into;
			}
		}
	}
	Owner->SetActorLocationAndRotation(To, Rotation);
}

void UShipFlightComponent::TickAutopilot(float DeltaTime)
{
	AActor* Owner = GetOwner();
	const ALandingPad* Target = Pad.Get();
	if (!Owner || !Target)
	{
		LandingState = EShipLandingState::Flying;
		return;
	}
	if (LandingState == EShipLandingState::Landed)
	{
		VelocityKmPerSecond = FVector::ZeroVector;
		return;
	}

	// Level out onto the pad's heading.
	const FQuat Heading = FRotator(0.0, Target->GetActorRotation().Yaw, 0.0).Quaternion();
	Rotation = FQuat::Slerp(Rotation, Heading, 1.0 - FMath::Exp(-DeltaTime * 1.6)).GetNormalized();

	const FVector Here = Owner->GetActorLocation();
	const FVector Rest = Target->GetActorLocation() + FVector(0.0, 0.0, GearHeight);
	const FVector Hover = Rest + FVector(0.0, 0.0, ApproachHeight * CmPerM);
	FVector Goal = Rest;
	double Speed = TouchdownSpeed * CmPerM;
	switch (LandingState)
	{
	case EShipLandingState::Approaching:
		Goal = Hover;
		// Cross to the pad at height first, so nothing on the way gets clipped.
		if (FVector::Dist2D(Here, Hover) > 5000.0)
		{
			Goal.Z = FMath::Max(Goal.Z, Here.Z);
		}
		Speed = ApproachSpeed * CmPerM;
		break;
	case EShipLandingState::Lifting:
		Goal = Hover + FVector(0.0, 0.0, 1000.0);
		Speed = 8.0 * CmPerM;
		break;
	default:
		break;
	}

	// Ease in: never faster than the speed, and slowing as the goal nears.
	const FVector ToGoal = Goal - Here;
	const double Distance = ToGoal.Size();
	const double Step = FMath::Min(Distance, FMath::Min(Speed, FMath::Max(Distance * 0.9, TouchdownSpeed * CmPerM)) * DeltaTime);
	const FVector Next = Distance > UE_KINDA_SMALL_NUMBER ? Here + ToGoal / Distance * Step : Goal;
	VelocityKmPerSecond = (Next - Here) / FMath::Max(DeltaTime, 1e-4f) / CmPerKm;
	PositionKm = SpaceFromWorld(Next);
	Owner->SetActorLocationAndRotation(Next, Rotation);

	const bool bArrived = FVector::Dist(Next, Goal) < (LandingState == EShipLandingState::Descending ? 1.0 : ArriveCm);
	const bool bAligned = Rotation.AngularDistance(Heading) < FMath::DegreesToRadians(AlignedDegrees);
	if (!bArrived)
	{
		return;
	}
	switch (LandingState)
	{
	case EShipLandingState::Approaching:
		if (bAligned)
		{
			LandingState = EShipLandingState::Descending;
		}
		break;
	case EShipLandingState::Descending:
		Rotation = Heading;
		Owner->SetActorLocationAndRotation(Rest, Rotation);
		PositionKm = SpaceFromWorld(Rest);
		VelocityKmPerSecond = FVector::ZeroVector;
		LandingState = EShipLandingState::Landed;
		OnLanded.Broadcast();
		break;
	case EShipLandingState::Lifting:
		LandingState = EShipLandingState::Flying;
		Pad.Reset();
		ReleaseControls();
		break;
	default:
		break;
	}
}
