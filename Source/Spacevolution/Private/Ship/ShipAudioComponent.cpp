#include "Ship/ShipAudioComponent.h"
#include "Ship/Ship.h"
#include "Ship/ShipFlightComponent.h"
#include "SpacevolutionPlayerController.h"
#include "Components/AudioComponent.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"

UShipAudioComponent::UShipAudioComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.TickGroup = TG_PostUpdateWork;
}

void UShipAudioComponent::BeginPlay()
{
	Super::BeginPlay();

	Flight = GetOwner()->FindComponentByClass<UShipFlightComponent>();
	Presence = IsListenerAboard() ? 1.f : OutsideVolume;
	HumLevel = HumIdleVolume;
	bWasPiloted = IsPilotedLocally();

	Ambience = StartLoop(InteriorAmbience, AmbienceVolume * Presence);
	Hum = StartLoop(DriveHum, HumLevel * Presence);
}

void UShipAudioComponent::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	for (UAudioComponent* Loop : { Ambience.Get(), Hum.Get() })
	{
		if (Loop)
		{
			Loop->Stop();
		}
	}
	Super::EndPlay(EndPlayReason);
}

UAudioComponent* UShipAudioComponent::StartLoop(USoundBase* Sound, float Volume)
{
	if (!Sound)
	{
		return nullptr;
	}
	// The fade is a percentage of the component's volume, which the tick keeps updating.
	UAudioComponent* Loop = UGameplayStatics::CreateSound2D(this, Sound, Volume, 1.f, 0.f, nullptr, false, false);
	if (Loop)
	{
		Loop->FadeIn(2.f);
	}
	return Loop;
}

bool UShipAudioComponent::IsListenerAboard() const
{
	const AShip* Ship = Cast<AShip>(GetOwner());
	const APlayerController* Player = GetWorld()->GetFirstPlayerController();
	if (!Ship || !Player)
	{
		return true;
	}
	FVector Location, Front, Right;
	Player->GetAudioListenerPosition(Location, Front, Right);
	return Ship->ContainsLocation(Location);
}

bool UShipAudioComponent::IsPilotedLocally() const
{
	const ASpacevolutionPlayerController* Player = Cast<ASpacevolutionPlayerController>(GetWorld()->GetFirstPlayerController());
	return Player && Flight.IsValid() && Player->GetPilotedFlight() == Flight.Get();
}

void UShipAudioComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);

	const UShipFlightComponent* Drive = Flight.Get();
	if (!Drive)
	{
		return;
	}

	// Helm chime as the pilot takes or leaves the helm.
	const bool bPiloted = IsPilotedLocally();
	if (bPiloted != bWasPiloted)
	{
		if (USoundBase* Chime = bPiloted ? HelmEngageSound : HelmLeaveSound)
		{
			UGameplayStatics::PlaySound2D(this, Chime, HelmVolume, bPiloted ? 1.f : HelmLeavePitch);
		}
		bWasPiloted = bPiloted;
	}

	// Surge reads as above 1 from its first frame and drops straight back to 1 when let go.
	const float Surge = Drive->GetSurge();
	const bool bSurging = Surge > 1.0001f;
	if (bSurging != bWasSurging)
	{
		if (UAudioComponent* Engage = SurgeSound.Get())
		{
			Engage->FadeOut(0.3f, 0.f);
		}
		SurgeSound.Reset();
		if (bSurging && SurgeEngageSound)
		{
			SurgeSound = UGameplayStatics::SpawnSound2D(this, SurgeEngageSound, SurgeVolume, 1.f, SurgeEngageStartTime);
		}
		else if (!bSurging && SurgeReleaseSound)
		{
			UGameplayStatics::PlaySound2D(this, SurgeReleaseSound, SurgeVolume);
		}
		bWasSurging = bSurging;
	}

	// Throttle: speed against what full input would give at this altitude, before surge.
	const double Cruise = FMath::Max(FMath::Max(Drive->GetAltitudeKm(), 0.0) * Drive->CruisePerSecond, Drive->MinCruiseKmPerSecond);
	const float Throttle = FMath::Clamp(float(Drive->GetSpeedKmPerSecond() / (Cruise * Surge)), 0.f, 1.f);
	// Surge multiplies exponentially over its ramp, so its log climbs steadily while the key is held.
	const float SurgeAlpha = Drive->MaxSurge > 1.f ? FMath::Clamp(FMath::Loge(Surge) / FMath::Loge(Drive->MaxSurge), 0.f, 1.f) : 0.f;

	const float HumTarget = FMath::Lerp(HumIdleVolume, HumFullVolume, FMath::Max(Throttle, SurgeAlpha));
	const float PitchTarget = FMath::Lerp(1.f, HumPitchAtFullThrottle, Throttle) * FMath::Lerp(1.f, HumPitchAtFullSurge, SurgeAlpha);
	HumLevel = FMath::FInterpTo(HumLevel, HumTarget, DeltaTime, HumResponse);
	HumPitch = FMath::FInterpTo(HumPitch, PitchTarget, DeltaTime, HumResponse);
	Presence = FMath::FInterpTo(Presence, IsListenerAboard() ? 1.f : OutsideVolume, DeltaTime, 2.f);

	if (Hum)
	{
		Hum->SetVolumeMultiplier(HumLevel * Presence);
		Hum->SetPitchMultiplier(HumPitch);
	}
	if (Ambience)
	{
		Ambience->SetVolumeMultiplier(AmbienceVolume * Presence);
	}
}
