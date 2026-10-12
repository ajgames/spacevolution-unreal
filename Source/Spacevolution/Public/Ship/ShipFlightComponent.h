#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "ShipFlightComponent.generated.h"

/**
 * Inertialess "zero-point" flight. The ship never moves in the level: it keeps a pose in a space frame
 * (kilometres from the planet's centre) and ASpaceEnvironment places the planet, sun and stars around it.
 * Velocity snaps to whatever the pilot commands within a few hundredths of a second, turns are instant,
 * and letting go stops the ship dead. Newton is not consulted.
 */
UCLASS(ClassGroup = (Ship), meta = (BlueprintSpawnableComponent))
class SPACEVOLUTION_API UShipFlightComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UShipFlightComponent();

	/** Where the ship starts, in km from the planet's centre. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Flight|Start")
	FVector StartPositionKm = FVector(0.0, 0.0, 6480.0);

	/** How the ship starts out oriented in the space frame. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Flight|Start")
	FRotator StartRotation = FRotator::ZeroRotator;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Flight|Planet")
	double PlanetRadiusKm = 6360.0;

	/** Lowest the ship will go: just above the surface, inside the cloud deck. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Flight|Planet")
	double MinAltitudeKm = 1.5;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Flight|Planet")
	double MaxAltitudeKm = 400000.0;

	/** Cruise speed as a fraction of altitude per second, so the view moves at a readable pace from the cloud tops to deep space. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Flight|Drive")
	double CruisePerSecond = 0.3;

	/** Floor on cruise speed near the surface, km/s. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Flight|Drive")
	double MinCruiseKmPerSecond = 0.08;

	/** Holding surge multiplies speed exponentially up to this. Releasing it drops back instantly. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Flight|Drive", meta = (ClampMin = 1))
	float MaxSurge = 40.f;

	/** Seconds of holding surge to reach MaxSurge. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Flight|Drive", meta = (ClampMin = 0.1))
	float SurgeRampSeconds = 1.5f;

	/** Time constant for reaching a commanded velocity. Near zero reads as no inertia; never zero, so motion stays smooth. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Flight|Drive", meta = (ClampMin = 0.005))
	float ResponseSeconds = 0.05f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Flight|Drive")
	float RollDegreesPerSecond = 75.f;

	/** Desired motion in ship space: X forward, Y right, Z up, each -1..1. Held until changed. */
	UFUNCTION(BlueprintCallable, Category = "Flight")
	void SetTranslation(FVector ShipSpaceInput);

	/** Turns the ship immediately by these angles (applied on the next tick). */
	UFUNCTION(BlueprintCallable, Category = "Flight")
	void AddSteering(float YawDegrees, float PitchDegrees);

	/** -1..1 roll, held until changed. */
	UFUNCTION(BlueprintCallable, Category = "Flight")
	void SetRoll(float Input);

	UFUNCTION(BlueprintCallable, Category = "Flight")
	void SetSurge(bool bSurge);

	/** Drops every input; with no inertia the ship stops where it is. */
	UFUNCTION(BlueprintCallable, Category = "Flight")
	void ReleaseControls();

	UFUNCTION(BlueprintPure, Category = "Flight")
	FVector GetPositionKm() const { return PositionKm; }

	UFUNCTION(BlueprintPure, Category = "Flight")
	FRotator GetSpaceRotation() const { return Rotation.Rotator(); }

	FQuat GetSpaceQuat() const { return Rotation; }

	/** Space-frame velocity, km/s. */
	UFUNCTION(BlueprintPure, Category = "Flight")
	FVector GetVelocityKmPerSecond() const { return VelocityKmPerSecond; }

	UFUNCTION(BlueprintPure, Category = "Flight")
	double GetAltitudeKm() const { return PositionKm.Size() - PlanetRadiusKm; }

	UFUNCTION(BlueprintPure, Category = "Flight")
	double GetSpeedKmPerSecond() const { return VelocityKmPerSecond.Size(); }

	UFUNCTION(BlueprintPure, Category = "Flight")
	float GetSurge() const { return Surge; }

	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

protected:
	virtual void OnRegister() override;

private:
	FVector PositionKm = FVector::ZeroVector;
	FQuat Rotation = FQuat::Identity;
	FVector VelocityKmPerSecond = FVector::ZeroVector;

	FVector TranslationInput = FVector::ZeroVector;
	FVector2D PendingSteering = FVector2D::ZeroVector;
	float RollInput = 0.f;
	bool bSurging = false;
	float Surge = 1.f;
};
