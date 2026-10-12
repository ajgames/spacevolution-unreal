#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "ShipAudioComponent.generated.h"

class AShip;
class UAudioComponent;
class USoundBase;
class UShipFlightComponent;

/**
 * The ship's own sound: the interior ambience, the zero-point drive's hum (swelling and rising in pitch with throttle,
 * climbing further under surge), the surge kicking in and dropping out, and a chime as someone takes or leaves the
 * helm. It watches the flight drive and the local pilot, so nothing has to call in. Doors play their own sounds.
 */
UCLASS(ClassGroup = (Ship), meta = (BlueprintSpawnableComponent))
class SPACEVOLUTION_API UShipAudioComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UShipAudioComponent();

	/** Looping bed heard everywhere aboard. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Sound|Ambience")
	TObjectPtr<USoundBase> InteriorAmbience;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Sound|Ambience", meta = (ClampMin = 0))
	float AmbienceVolume = 0.5f;

	/** Scales the ambience and the drive once the listener steps off the ship (onto a landing pad, say). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Sound|Ambience", meta = (ClampMin = 0, ClampMax = 1))
	float OutsideVolume = 0.15f;

	/** Looping hum of the drive. Needs a looping sound. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Sound|Drive")
	TObjectPtr<USoundBase> DriveHum;

	/** Hum volume with the ship at rest... */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Sound|Drive", meta = (ClampMin = 0))
	float HumIdleVolume = 0.12f;

	/** ...and at full throttle or under surge. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Sound|Drive", meta = (ClampMin = 0))
	float HumFullVolume = 0.6f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Sound|Drive", meta = (ClampMin = 0.4, ClampMax = 2))
	float HumPitchAtFullThrottle = 1.12f;

	/** Further pitch multiplier at maximum surge; it climbs steadily while surge builds. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Sound|Drive", meta = (ClampMin = 0.4, ClampMax = 2))
	float HumPitchAtFullSurge = 1.4f;

	/** How quickly the hum follows the drive. The drive itself has no lag, so keep this brisk. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Sound|Drive", meta = (ClampMin = 0.1))
	float HumResponse = 6.f;

	/** Played as surge kicks in; faded out if surge is let go before it finishes. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Sound|Surge")
	TObjectPtr<USoundBase> SurgeEngageSound;

	/** Seconds into the engage sound to start, skipping a slow fade-in so it lands with the key press. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Sound|Surge", meta = (ClampMin = 0, Units = "s"))
	float SurgeEngageStartTime = 1.f;

	/** Played the moment surge is let go. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Sound|Surge")
	TObjectPtr<USoundBase> SurgeReleaseSound;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Sound|Surge", meta = (ClampMin = 0))
	float SurgeVolume = 0.8f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Sound|Helm")
	TObjectPtr<USoundBase> HelmEngageSound;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Sound|Helm")
	TObjectPtr<USoundBase> HelmLeaveSound;

	/** Pitch of the leave sound, so the same chime can serve both ways, lower on the way out. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Sound|Helm", meta = (ClampMin = 0.4, ClampMax = 2))
	float HelmLeavePitch = 0.85f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Sound|Helm", meta = (ClampMin = 0))
	float HelmVolume = 0.7f;

	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

protected:
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

private:
	UAudioComponent* StartLoop(USoundBase* Sound, float Volume);
	bool IsListenerAboard() const;
	bool IsPilotedLocally() const;

	TWeakObjectPtr<UShipFlightComponent> Flight;

	UPROPERTY(Transient)
	TObjectPtr<UAudioComponent> Ambience;

	UPROPERTY(Transient)
	TObjectPtr<UAudioComponent> Hum;

	TWeakObjectPtr<UAudioComponent> SurgeSound;
	float Presence = 1.f;
	float HumLevel = 0.f;
	float HumPitch = 1.f;
	bool bWasSurging = false;
	bool bWasPiloted = false;
};
