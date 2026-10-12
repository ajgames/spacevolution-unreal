#include "SpacevolutionPlayerController.h"
#include "Ship/Ship.h"
#include "Ship/ShipFlightComponent.h"
#include "Ship/ShipModule.h"
#include "Spacevolution.h"
#include "UI/PerformanceOverlaySubsystem.h"
#include "Camera/CameraComponent.h"
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
		Input->BindAction(ToggleHelmAction, ETriggerEvent::Started, this, &ThisClass::ToggleHelm);
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

bool ASpacevolutionPlayerController::CanPilot() const
{
	const AShip* Ship = FindShip(GetWorld());
	return Ship && Ship->GetFlight();
}

void ASpacevolutionPlayerController::ToggleHelm()
{
	SetPiloting(!IsPiloting());
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
