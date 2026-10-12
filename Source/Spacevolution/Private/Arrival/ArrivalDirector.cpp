#include "Arrival/ArrivalDirector.h"
#include "Ship/LandingPad.h"
#include "Ship/Ship.h"
#include "Ship/ShipFlightComponent.h"
#include "Ship/ShipModule.h"
#include "SpacevolutionPlayerController.h"
#include "WaveRider/WaveRider.h"
#include "Camera/CameraComponent.h"
#include "EngineUtils.h"

#define LOCTEXT_NAMESPACE "Arrival"

namespace
{
	template <typename T>
	T* FindFirst(UWorld* World)
	{
		TActorIterator<T> It(World);
		return It ? *It : nullptr;
	}
}

AArrivalDirector::AArrivalDirector()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickGroup = TG_PostUpdateWork;
	SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("Root")));
}

void AArrivalDirector::BeginPlay()
{
	Super::BeginPlay();
	if (!Ship)
	{
		Ship = FindFirst<AShip>(GetWorld());
	}
}

void AArrivalDirector::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	// The pad and the rider may live in a streamed-in sublevel; look them up until they turn up.
	if (!Pad.IsValid())
	{
		Pad = FindFirst<ALandingPad>(GetWorld());
	}
	if (!Rider.IsValid())
	{
		Rider = FindFirst<AWaveRider>(GetWorld());
	}

	const ASpacevolutionPlayerController* Player = Cast<ASpacevolutionPlayerController>(GetWorld()->GetFirstPlayerController());
	const APawn* Pawn = Player ? Player->GetPawn() : nullptr;
	const UShipFlightComponent* Flight = Ship ? Ship->GetFlight() : nullptr;
	if (!Pawn)
	{
		return;
	}
	if (const AWaveRider* Riding = Cast<AWaveRider>(Pawn))
	{
		Step = Riding->GetRiddenSeconds() < RideTipSeconds ? EArrivalStep::Ride : EArrivalStep::Done;
	}
	else if (Player->IsPiloting() && Flight)
	{
		if (Flight->IsLanded())
		{
			Step = EArrivalStep::LeaveHelm;
		}
		else if (Flight->IsUnderAutopilot())
		{
			Step = EArrivalStep::Landing;
		}
		else
		{
			Step = Flight->FindPadInRange() ? EArrivalStep::Land : EArrivalStep::Descend;
		}
	}
	else if (Flight && Flight->IsLanded())
	{
		Step = Ship->ContainsLocation(Pawn->GetActorLocation()) ? EArrivalStep::ExitShip : EArrivalStep::BoardRider;
	}
	else
	{
		Step = EArrivalStep::TakeHelm;
	}
}

FText AArrivalDirector::GetObjective() const
{
	switch (Step)
	{
	case EArrivalStep::TakeHelm: return LOCTEXT("TakeHelm", "Take the helm");
	case EArrivalStep::Descend: return LOCTEXT("Descend", "Fly down to BiodiverCity");
	case EArrivalStep::Land: return LOCTEXT("Land", "Land at the spaceport");
	case EArrivalStep::Landing: return LOCTEXT("Landing", "Landing");
	case EArrivalStep::LeaveHelm: return LOCTEXT("LeaveHelm", "Leave the helm");
	case EArrivalStep::ExitShip: return LOCTEXT("ExitShip", "Go ashore");
	case EArrivalStep::BoardRider: return LOCTEXT("BoardRider", "Ride the PWC-01");
	case EArrivalStep::Ride: return LOCTEXT("Ride", "Ride the waves");
	default: return FText::GetEmpty();
	}
}

FText AArrivalDirector::GetHint() const
{
	switch (Step)
	{
	case EArrivalStep::TakeHelm: return LOCTEXT("TakeHelmHint", "Walk forward to the porthole and press F.");
	case EArrivalStep::Descend: return LOCTEXT("DescendHint", "Follow the marker down to the spaceport beacon. CTRL sinks, SHIFT surges the drive.");
	case EArrivalStep::Land: return LOCTEXT("LandHint", "You're over the pad. Press L and the autopilot will set her down.");
	case EArrivalStep::Landing: return LOCTEXT("LandingHint", "Hands off: the autopilot has her.");
	case EArrivalStep::LeaveHelm: return LOCTEXT("LeaveHelmHint", "Press F, then head aft to the airlock. The ramp is down.");
	case EArrivalStep::ExitShip: return LOCTEXT("ExitShipHint", "Through the airlock at the stern and down the ramp.");
	case EArrivalStep::BoardRider: return LOCTEXT("BoardRiderHint", "It's moored at the end of the pier. Walk up to it and press F.");
	case EArrivalStep::Ride: return LOCTEXT("RideHint", "Open sea to the south. SPACE jumps; hold it in the air to burst.");
	default: return FText::GetEmpty();
	}
}

bool AArrivalDirector::GetTarget(FVector& OutLocation, FText& OutLabel) const
{
	switch (Step)
	{
	case EArrivalStep::TakeHelm:
		if (const AShipModule* Helm = Ship ? Ship->FindHelmModule() : nullptr)
		{
			TInlineComponentArray<UCameraComponent*> Cameras(Helm);
			for (const UCameraComponent* Camera : Cameras)
			{
				if (Camera->GetFName() == TEXT("HelmView"))
				{
					OutLocation = Camera->GetComponentLocation() - FVector(0.0, 0.0, 60.0);
					OutLabel = LOCTEXT("HelmLabel", "Helm");
					return true;
				}
			}
		}
		return false;
	case EArrivalStep::Descend:
	case EArrivalStep::Land:
	case EArrivalStep::Landing:
		if (const ALandingPad* Target = Pad.Get())
		{
			OutLocation = Target->GetActorLocation();
			OutLabel = Target->DisplayName;
			return true;
		}
		return false;
	case EArrivalStep::ExitShip:
		if (Ship)
		{
			OutLocation = Ship->GetActorTransform().TransformPosition(RampFoot);
			OutLabel = LOCTEXT("RampLabel", "Ramp");
			return true;
		}
		return false;
	case EArrivalStep::BoardRider:
		if (const AWaveRider* Target = Rider.Get())
		{
			OutLocation = Target->GetActorLocation();
			OutLabel = LOCTEXT("RiderLabel", "PWC-01");
			return true;
		}
		return false;
	default:
		return false;
	}
}

#undef LOCTEXT_NAMESPACE
