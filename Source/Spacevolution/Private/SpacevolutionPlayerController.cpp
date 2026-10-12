#include "SpacevolutionPlayerController.h"
#include "Ship/Ship.h"
#include "Ship/ShipFlightComponent.h"
#include "Ship/ShipModule.h"
#include "Spacevolution.h"
#include "UI/PerformanceOverlaySubsystem.h"
#include "WaveRider/WaveRider.h"
#include "Camera/CameraComponent.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "Engine/GameInstance.h"
#include "Engine/LocalPlayer.h"
#include "EngineUtils.h"
#include "InputActionValue.h"

namespace
{
	AShip* FindShip(UWorld* World)
	{
		TActorIterator<AShip> It(World);
		return It ? *It : nullptr;
	}

	constexpr double NoticeSeconds = 3.0;
}

ASpacevolutionPlayerController::ASpacevolutionPlayerController()
{
	PrimaryActorTick.bCanEverTick = true;
}

void ASpacevolutionPlayerController::BeginPlay()
{
	Super::BeginPlay();

	if (IsLocalPlayerController() && InterfaceMappingContext)
	{
		if (UEnhancedInputLocalPlayerSubsystem* Subsystem = ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(GetLocalPlayer()))
		{
			Subsystem->AddMappingContext(InterfaceMappingContext, 1);
		}
	}
}

void ASpacevolutionPlayerController::SetupInputComponent()
{
	Super::SetupInputComponent();

	UEnhancedInputComponent* Input = Cast<UEnhancedInputComponent>(InputComponent);
	if (!Input)
	{
		return;
	}
	if (TogglePerformanceOverlayAction)
	{
		Input->BindAction(TogglePerformanceOverlayAction, ETriggerEvent::Started, this, &ThisClass::TogglePerformanceOverlay);
	}
	if (ToggleHelmAction)
	{
		Input->BindAction(ToggleHelmAction, ETriggerEvent::Started, this, &ThisClass::Interact);
	}
	if (HelmLandAction)
	{
		Input->BindAction(HelmLandAction, ETriggerEvent::Started, this, &ThisClass::HelmLand);
	}
	if (HelmMoveAction)
	{
		Input->BindAction(HelmMoveAction, ETriggerEvent::Triggered, this, &ThisClass::HelmMove);
		Input->BindAction(HelmMoveAction, ETriggerEvent::Completed, this, &ThisClass::HelmStop);
	}
	if (HelmSteerAction)
	{
		Input->BindAction(HelmSteerAction, ETriggerEvent::Triggered, this, &ThisClass::HelmSteer);
	}
	if (HelmRollAction)
	{
		Input->BindAction(HelmRollAction, ETriggerEvent::Triggered, this, &ThisClass::HelmRoll);
		Input->BindAction(HelmRollAction, ETriggerEvent::Completed, this, &ThisClass::HelmRollStop);
	}
	if (HelmSurgeAction)
	{
		Input->BindAction(HelmSurgeAction, ETriggerEvent::Started, this, &ThisClass::HelmSurgeStart);
		Input->BindAction(HelmSurgeAction, ETriggerEvent::Completed, this, &ThisClass::HelmSurgeStop);
	}
}

void ASpacevolutionPlayerController::TogglePerformanceOverlay()
{
	if (UPerformanceOverlaySubsystem* Overlay = UGameInstance::GetSubsystem<UPerformanceOverlaySubsystem>(GetGameInstance()))
	{
		Overlay->CycleMode();
	}
}

AShip* ASpacevolutionPlayerController::GetShip() const
{
	return FindShip(GetWorld());
}

bool ASpacevolutionPlayerController::CanPilot() const
{
	const AShip* Ship = FindShip(GetWorld());
	const APawn* Crew = GetPawn();
	return Ship && Ship->GetFlight() && Crew && !Cast<AWaveRider>(Crew) && Ship->ContainsLocation(Crew->GetActorLocation());
}

AWaveRider* ASpacevolutionPlayerController::FindRideableNearby() const
{
	const APawn* Crew = GetPawn();
	if (!Crew || IsPiloting() || Cast<AWaveRider>(Crew))
	{
		return nullptr;
	}
	AWaveRider* Best = nullptr;
	double BestDistance = RideReach;
	for (TActorIterator<AWaveRider> It(GetWorld()); It; ++It)
	{
		const FVector Offset = It->GetActorLocation() - Crew->GetActorLocation();
		const double Distance = Offset.Size2D();
		if (!It->GetController() && Distance <= BestDistance && FMath::Abs(Offset.Z) < 400.0)
		{
			Best = *It;
			BestDistance = Distance;
		}
	}
	return Best;
}

bool ASpacevolutionPlayerController::BoardRider(AWaveRider* Rider)
{
	APawn* Crew = GetPawn();
	if (!Rider || Rider->GetController())
	{
		return false;
	}
	// The crew member's walking controls would fight the rider's; start the input stack afresh.
	if (UEnhancedInputLocalPlayerSubsystem* Subsystem = ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(GetLocalPlayer()))
	{
		Subsystem->ClearAllMappings();
		if (InterfaceMappingContext)
		{
			Subsystem->AddMappingContext(InterfaceMappingContext, 1);
		}
	}
	Possess(Rider);
	if (Crew)
	{
		if (ACharacter* Walker = Cast<ACharacter>(Crew))
		{
			Walker->GetCharacterMovement()->DisableMovement();
		}
		Crew->SetActorHiddenInGame(true);
		Crew->SetActorEnableCollision(false);
		// Glide from the crew member's eyes to the rider's chase camera.
		SetViewTarget(Crew);
		SetViewTargetWithBlend(Rider, 1.2f, VTBlend_EaseInOut, 2.f);
	}
	return true;
}

FText ASpacevolutionPlayerController::GetNotice() const
{
	const UWorld* World = GetWorld();
	return World && World->GetTimeSeconds() - NoticeTime < NoticeSeconds ? Notice : FText::GetEmpty();
}

void ASpacevolutionPlayerController::ShowNotice(const FText& InNotice)
{
	Notice = InNotice;
	NoticeTime = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0;
}

void ASpacevolutionPlayerController::Interact()
{
	if (AWaveRider* Rider = FindRideableNearby())
	{
		BoardRider(Rider);
		return;
	}
	if (IsPiloting() || CanPilot())
	{
		ToggleHelm();
	}
}

void ASpacevolutionPlayerController::ToggleHelm()
{
	SetPiloting(!IsPiloting());
}

void ASpacevolutionPlayerController::HelmLand()
{
	UShipFlightComponent* Flight = PilotedFlight.Get();
	if (!Flight)
	{
		return;
	}
	if (!Flight->bFlyInWorld)
	{
		ShowNotice(NSLOCTEXT("Helm", "NoPadsInSpace", "Nowhere to land out here"));
	}
	else if (!Flight->ToggleLanding())
	{
		ShowNotice(NSLOCTEXT("Helm", "NoPad", "No landing pad in range"));
	}
}

void ASpacevolutionPlayerController::SetPiloting(bool bPilot)
{
	if (bPilot == IsPiloting())
	{
		return;
	}
	UEnhancedInputLocalPlayerSubsystem* Subsystem = ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(GetLocalPlayer());

	if (bPilot)
	{
		AShip* Ship = FindShip(GetWorld());
		UShipFlightComponent* Flight = Ship ? Ship->GetFlight() : nullptr;
		if (!Flight)
		{
			return;
		}
		PilotedFlight = Flight;
		// The crew member rides along at the helm, held still while the ship flies.
		if (ACharacter* Walker = Cast<ACharacter>(GetPawn()))
		{
			Walker->GetCharacterMovement()->DisableMovement();
			Walker->AttachToActor(Ship, FAttachmentTransformRules::KeepWorldTransform);
		}
		if (Subsystem && HelmMappingContext)
		{
			Subsystem->AddMappingContext(HelmMappingContext, 2);
		}
		// Glide from wherever the crew member stands to the helm viewpoint.
		if (AShipModule* HelmModule = Ship->FindHelmModule())
		{
			TInlineComponentArray<UCameraComponent*> Cameras(HelmModule);
			for (UCameraComponent* Camera : Cameras)
			{
				if (Camera->GetFName() == TEXT("HelmView"))
				{
					HelmCamera = Camera;
					HelmBaseFieldOfView = Camera->FieldOfView;
				}
			}
			SetViewTargetWithBlend(HelmModule, 0.9f, VTBlend_EaseInOut, 2.f);
		}
		else
		{
			UE_LOG(LogShip, Warning, TEXT("No helm viewpoint fitted; piloting from where you stand"));
		}
	}
	else
	{
		if (UShipFlightComponent* Flight = PilotedFlight.Get())
		{
			Flight->ReleaseControls();
		}
		if (UCameraComponent* Camera = HelmCamera.Get())
		{
			Camera->SetFieldOfView(HelmBaseFieldOfView);
		}
		if (Subsystem && HelmMappingContext)
		{
			Subsystem->RemoveMappingContext(HelmMappingContext);
		}
		if (ACharacter* Walker = Cast<ACharacter>(GetPawn()))
		{
			Walker->DetachFromActor(FDetachmentTransformRules::KeepWorldTransform);
			Walker->SetActorRotation(FRotator(0.0, Walker->GetActorRotation().Yaw, 0.0));
			Walker->GetCharacterMovement()->SetMovementMode(MOVE_Walking);
		}
		PilotedFlight.Reset();
		HelmCamera.Reset();
		SetViewTargetWithBlend(GetPawn(), 0.7f, VTBlend_EaseInOut, 2.f);
	}
}

void ASpacevolutionPlayerController::PlayerTick(float DeltaTime)
{
	Super::PlayerTick(DeltaTime);

	const UShipFlightComponent* Flight = PilotedFlight.Get();
	UCameraComponent* Camera = HelmCamera.Get();
	if (Flight && Camera)
	{
		const float SurgeAlpha = FMath::Clamp((Flight->GetSurge() - 1.f) / FMath::Max(Flight->MaxSurge - 1.f, 1.f), 0.f, 1.f);
		const float Target = HelmBaseFieldOfView + SurgeFieldOfViewBoost * FMath::Sqrt(SurgeAlpha);
		Camera->SetFieldOfView(FMath::FInterpTo(Camera->FieldOfView, Target, DeltaTime, 6.f));
	}
}

void ASpacevolutionPlayerController::HelmMove(const FInputActionValue& Value)
{
	if (UShipFlightComponent* Flight = PilotedFlight.Get())
	{
		Flight->SetTranslation(Value.Get<FVector>());
	}
}

void ASpacevolutionPlayerController::HelmStop()
{
	if (UShipFlightComponent* Flight = PilotedFlight.Get())
	{
		Flight->SetTranslation(FVector::ZeroVector);
	}
}

void ASpacevolutionPlayerController::HelmSteer(const FInputActionValue& Value)
{
	if (UShipFlightComponent* Flight = PilotedFlight.Get())
	{
		const FVector2D Steer = Value.Get<FVector2D>();
		Flight->AddSteering(Steer.X, Steer.Y);
	}
}

void ASpacevolutionPlayerController::HelmRoll(const FInputActionValue& Value)
{
	if (UShipFlightComponent* Flight = PilotedFlight.Get())
	{
		Flight->SetRoll(Value.Get<float>());
	}
}

void ASpacevolutionPlayerController::HelmRollStop()
{
	if (UShipFlightComponent* Flight = PilotedFlight.Get())
	{
		Flight->SetRoll(0.f);
	}
}

void ASpacevolutionPlayerController::HelmSurgeStart()
{
	if (UShipFlightComponent* Flight = PilotedFlight.Get())
	{
		Flight->SetSurge(true);
	}
}

void ASpacevolutionPlayerController::HelmSurgeStop()
{
	if (UShipFlightComponent* Flight = PilotedFlight.Get())
	{
		Flight->SetSurge(false);
	}
}
