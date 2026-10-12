#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "ShipFlightComponent.generated.h"

class ALandingPad;

UENUM(BlueprintType)
enum class EShipLandingState : uint8
{
	Flying,
	/** Autopilot: lining up over the pad. */
	Approaching,
	/** Autopilot: settling onto the pad. */
	Descending,
	Landed,
	/** Autopilot: climbing off the pad before handing back. */
	Lifting,
};

DECLARE_DYNAMIC_MULTICAST_DELEGATE(FShipTouchdownSignature);

/**
 * Inertialess "zero-point" flight. The ship never moves in the level: it keeps a pose in a space frame
 * (kilometres from the planet's centre) and ASpaceEnvironment places the planet, sun and stars around it.
 * Velocity snaps to whatever the pilot commands within a few hundredths of a second, turns are instant,
 * and letting go stops the ship dead. Newton is not consulted.
 *
 * With bFlyInWorld the same drive moves the ship's actor through the level instead, for levels built on the
 * planet's surface (its top at the world origin, as SkyAtmosphere draws it). Then the ship sweeps its collision
 * box through the world, and can land on an ALandingPad under autopilot.
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

	/** Move the ship's actor through the level rather than the universe round the ship. It starts where it's placed. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Flight|World")
	bool bFlyInWorld = false;

	/** From the ship's origin (its deck) down to the feet of its landing gear. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Flight|World", meta = (Units = "cm"))
	float GearHeight = 80.f;

	/** Autopilot speed on the way to a pad. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Flight|World", meta = (Units = "m/s"))
	float ApproachSpeed = 45.f;

	/** Height over the pad the autopilot lines up at before settling. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Flight|World", meta = (Units = "m"))
	float ApproachHeight = 30.f;

	/** Speed the ship settles onto the pad at. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Flight|World", meta = (Units = "m/s"))
	float TouchdownSpeed = 1.5f;

	UPROPERTY(BlueprintAssignable, Category = "Flight|World")
	FShipTouchdownSignature OnLanded;

	/** Fired as the ship starts to climb off a pad. */
	UPROPERTY(BlueprintAssignable, Category = "Flight|World")
	FShipTouchdownSignature OnLiftingOff;

	/** Lands on the pad the ship is over, lifts off if landed, or cancels an approach. False if there's nothing to do. */
	UFUNCTION(BlueprintCallable, Category = "Flight|World")
	bool ToggleLanding();

	/** The nearest pad whose zone the ship is in, or null. */
	UFUNCTION(BlueprintPure, Category = "Flight|World")
	ALandingPad* FindPadInRange() const;

	UFUNCTION(BlueprintPure, Category = "Flight|World")
	EShipLandingState GetLandingState() const { return LandingState; }

	UFUNCTION(BlueprintPure, Category = "Flight|World")
	bool IsLanded() const { return LandingState == EShipLandingState::Landed; }

	UFUNCTION(BlueprintPure, Category = "Flight|World")
	bool IsUnderAutopilot() const { return LandingState != EShipLandingState::Flying && LandingState != EShipLandingState::Landed; }

	/** Box in the ship's own space that it sweeps through the world, and the actors (its own parts) the sweep ignores. */
	void SetCollision(const FBox& LocalBox, const TArray<AActor*>& IgnoredActors);

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
	virtual void BeginPlay() override;

private:
	/** Space frame (km from the planet's centre) to world (cm), and back, for world flight. */
	FVector WorldFromSpace(const FVector& SpaceKm) const;
	FVector SpaceFromWorld(const FVector& WorldCm) const;
	void SyncFromOwner();
	/** Moves the owner to the flown pose, stopping short of anything solid. */
	void MoveOwner();
	void TickAutopilot(float DeltaTime);

	EShipLandingState LandingState = EShipLandingState::Flying;
	TWeakObjectPtr<ALandingPad> Pad;
	FBox CollisionBox = FBox(ForceInit);
	TArray<TWeakObjectPtr<AActor>> CollisionIgnored;

	FVector PositionKm = FVector::ZeroVector;
	FQuat Rotation = FQuat::Identity;
	FVector VelocityKmPerSecond = FVector::ZeroVector;

	FVector TranslationInput = FVector::ZeroVector;
	FVector2D PendingSteering = FVector2D::ZeroVector;
	float RollInput = 0.f;
	bool bSurging = false;
	float Surge = 1.f;
};
