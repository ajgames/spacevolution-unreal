#include "Ship/SpaceEnvironment.h"
#include "Ship/Ship.h"
#include "Ship/ShipFlightComponent.h"
#include "Spacevolution.h"
#include "Camera/PlayerCameraManager.h"
#include "GameFramework/PlayerController.h"
#include "Components/StaticMeshComponent.h"
#include "Components/VolumetricCloudComponent.h"
#include "Engine/DirectionalLight.h"
#include "EngineUtils.h"
#include "Materials/MaterialInstanceDynamic.h"

namespace
{
	constexpr double CmPerKm = 1.0e5;

	FLinearColor AsColor(const FVector& V)
	{
		return FLinearColor(static_cast<float>(V.X), static_cast<float>(V.Y), static_cast<float>(V.Z), 0.f);
	}

	// Backdrop parameters that brighten it, faded together through the atmosphere.
	const FName BrightnessParameters[] = {TEXT("StarBrightness"), TEXT("MilkyWay"), TEXT("Nebula"), TEXT("DustBrightness"), TEXT("StarIntensity")};
}

ASpaceEnvironment::ASpaceEnvironment()
{
	PrimaryActorTick.bCanEverTick = true;
	// After the ship has flown this frame, before anything renders.
	PrimaryActorTick.TickGroup = TG_PostUpdateWork;
	SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("Root")));
}

void ASpaceEnvironment::BeginPlay()
{
	Super::BeginPlay();

	if (!Ship)
	{
		TActorIterator<AShip> It(GetWorld());
		Ship = It ? *It : nullptr;
	}
	Flight = Ship ? Ship->GetFlight() : nullptr;
	if (bPlanetFixed)
	{
		if (Backdrop)
		{
			if (UStaticMeshComponent* Mesh = Backdrop->FindComponentByClass<UStaticMeshComponent>())
			{
				BackdropMaterial = Mesh->CreateDynamicMaterialInstance(0);
				for (const FName& Name : BrightnessParameters)
				{
					BackdropBrightness.Add(Name, BackdropMaterial->K2_GetScalarParameterValue(Name));
				}
			}
		}
		ApplyPlanetFixed();
		return;
	}
	if (!Flight)
	{
		UE_LOG(LogShip, Warning, TEXT("%s: no ship with a flight component; the universe will stay put"), *GetName());
		return;
	}

	if (Planet && Planet->GetRootComponent())
	{
		Planet->GetRootComponent()->SetMobility(EComponentMobility::Movable);
	}
	if (Clouds)
	{
		if (UVolumetricCloudComponent* CloudComponent = Clouds->FindComponentByClass<UVolumetricCloudComponent>())
		{
			CloudMaterial = UMaterialInstanceDynamic::Create(CloudComponent->GetMaterial(), this);
			CloudComponent->SetMaterial(CloudMaterial);
		}
	}
	if (Backdrop)
	{
		if (UStaticMeshComponent* Mesh = Backdrop->FindComponentByClass<UStaticMeshComponent>())
		{
			BackdropMaterial = Mesh->CreateDynamicMaterialInstance(0);
		}
	}
	Apply();
}

void ASpaceEnvironment::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (bPlanetFixed)
	{
		ApplyPlanetFixed();
	}
	else if (Flight)
	{
		Apply();
	}
}

void ASpaceEnvironment::ApplyPlanetFixed()
{
	if (!BackdropMaterial)
	{
		return;
	}
	const APlayerController* Player = GetWorld()->GetFirstPlayerController();
	if (!Player || !Player->PlayerCameraManager)
	{
		return;
	}
	// The space frame is the world's axes with the planet's centre a radius below the origin.
	const FVector CameraKm = Player->PlayerCameraManager->GetCameraLocation() / CmPerKm + FVector(0.0, 0.0, PlanetRadiusKm);
	BackdropMaterial->SetVectorParameterValue(TEXT("SpaceOrigin"), AsColor(CameraKm));
	BackdropMaterial->SetVectorParameterValue(TEXT("SpaceAxisX"), AsColor(FVector::XAxisVector));
	BackdropMaterial->SetVectorParameterValue(TEXT("SpaceAxisY"), AsColor(FVector::YAxisVector));
	BackdropMaterial->SetVectorParameterValue(TEXT("SpaceAxisZ"), AsColor(FVector::ZAxisVector));
	BackdropMaterial->SetVectorParameterValue(TEXT("DustVelocity"), AsColor(Flight ? Flight->GetVelocityKmPerSecond() : FVector::ZeroVector));

	const double Altitude = CameraKm.Size() - PlanetRadiusKm;
	const float Fade = FMath::SmoothStep(static_cast<float>(StarFadeAltitudeKm.X), static_cast<float>(StarFadeAltitudeKm.Y), static_cast<float>(Altitude));
	for (const TPair<FName, float>& Parameter : BackdropBrightness)
	{
		BackdropMaterial->SetScalarParameterValue(Parameter.Key, Parameter.Value * Fade);
	}
	if (Backdrop)
	{
		Backdrop->SetActorHiddenInGame(Fade <= 0.f);
	}
}

void ASpaceEnvironment::Apply()
{
	const FTransform ShipTransform = Ship->GetActorTransform();
	const FVector ShipPositionKm = Flight->GetPositionKm();

	// World directions and world km mapped into the space frame.
	const FQuat SpaceFromWorld = Flight->GetSpaceQuat() * ShipTransform.GetRotation().Inverse();
	const FVector SpaceOrigin = ShipPositionKm - SpaceFromWorld.RotateVector(ShipTransform.GetLocation() / CmPerKm);
	auto ToWorldPosition = [&](const FVector& SpaceKm) { return SpaceFromWorld.UnrotateVector(SpaceKm - SpaceOrigin) * CmPerKm; };
	auto ToWorldDirection = [&](const FVector& SpaceDirection) { return SpaceFromWorld.UnrotateVector(SpaceDirection); };

	if (Planet)
	{
		Planet->SetActorLocation(ToWorldPosition(FVector::ZeroVector));
	}
	if (Sun)
	{
		// A directional light shines along its forward vector, away from the sun.
		Sun->SetActorRotation((-ToWorldDirection(SunDirection.GetSafeNormal())).Rotation());
	}

	const FVector AxisX = SpaceFromWorld.RotateVector(FVector::XAxisVector);
	const FVector AxisY = SpaceFromWorld.RotateVector(FVector::YAxisVector);
	const FVector AxisZ = SpaceFromWorld.RotateVector(FVector::ZAxisVector);
	for (UMaterialInstanceDynamic* Material : { CloudMaterial.Get(), BackdropMaterial.Get() })
	{
		if (Material)
		{
			Material->SetVectorParameterValue(TEXT("SpaceOrigin"), AsColor(SpaceOrigin));
			Material->SetVectorParameterValue(TEXT("SpaceAxisX"), AsColor(AxisX));
			Material->SetVectorParameterValue(TEXT("SpaceAxisY"), AsColor(AxisY));
			Material->SetVectorParameterValue(TEXT("SpaceAxisZ"), AsColor(AxisZ));
		}
	}
	if (BackdropMaterial)
	{
		BackdropMaterial->SetVectorParameterValue(TEXT("DustVelocity"), AsColor(Flight->GetVelocityKmPerSecond()));
	}
}
