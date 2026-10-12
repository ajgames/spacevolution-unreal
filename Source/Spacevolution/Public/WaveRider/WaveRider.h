#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Pawn.h"
#include "WaveRider.generated.h"

class AOcean;
class UBoxComponent;
class UCameraComponent;
class UInputAction;
class UInputMappingContext;
class UMaterialInstanceDynamic;
class UPointLightComponent;
class USpringArmComponent;
class UStaticMesh;
class UStaticMeshComponent;
struct FInputActionValue;

/**
 * Hover jet-ski (the PWC-01): four magnetic lift rings ride a spring-damped cushion over the waves, or over the
 * ground when it leaves the water. Throttle drives it along the surface, steering carves with a little drift,
 * and wave crests throw it into the air. Jump kicks it off the surface; holding jump in the air fires the lift
 * rings to keep it aloft while the burst charge lasts. Boost shares that charge, which refills on the water.
 *
 * Meshes and input assets are assigned in a Blueprint subclass.
 */
UCLASS()
class SPACEVOLUTION_API AWaveRider : public APawn
{
	GENERATED_BODY()

public:
	AWaveRider();

	virtual void Tick(float DeltaSeconds) override;
	virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;
	virtual void OnConstruction(const FTransform& Transform) override;

	UFUNCTION(BlueprintPure, Category = "Rider")
	float GetSpeedKmh() const;

	UFUNCTION(BlueprintPure, Category = "Rider")
	bool IsAirborne() const { return bAirborne; }

	/** Seconds since leaving the surface, while airborne. */
	UFUNCTION(BlueprintPure, Category = "Rider")
	float GetAirTime() const;

	UFUNCTION(BlueprintPure, Category = "Rider")
	float GetLastAirTime() const { return LastAirTime; }

	UFUNCTION(BlueprintPure, Category = "Rider")
	float GetBestAirTime() const { return BestAirTime; }

	/** Burst charge, 0 to 1. */
	UFUNCTION(BlueprintPure, Category = "Rider")
	float GetBurstCharge() const { return BurstCharge; }

	UFUNCTION(BlueprintPure, Category = "Rider")
	bool IsBursting() const { return bBursting; }

	UFUNCTION(BlueprintPure, Category = "Rider")
	bool IsBoosting() const { return bBoosting; }

	/** Height of the hull above whatever is under it, in metres. */
	UFUNCTION(BlueprintPure, Category = "Rider")
	float GetHeightAboveSurface() const { return HeightAboveSurface / 100.f; }

	/** Puts the rider back upright on the surface where it is, at rest. */
	UFUNCTION(BlueprintCallable, Category = "Rider")
	void ResetRider();

	// --- Look ---

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Rider|Look")
	TObjectPtr<UStaticMesh> HullMesh;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Rider|Look")
	TObjectPtr<UStaticMesh> RiderMesh;

	/** Spray sheet thrown off the left of the bow (mirrored for the right). Its material's Spray parameter follows
	 *  speed and water contact. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Rider|Look")
	TObjectPtr<UStaticMesh> SprayMesh;

	/** Rooster tail thrown up behind the hull. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Rider|Look")
	TObjectPtr<UStaticMesh> WakeMesh;

	/** Hull material slots whose EmissiveStrength follows the thrust. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Rider|Look")
	TArray<FName> GlowSlots = {TEXT("LED"), TEXT("ThrusterGlow")};

	/** EmissiveStrength of the glow slots at idle and at full burst. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Rider|Look")
	FVector2D GlowRange = FVector2D(14.f, 90.f);

	/** Brightness (candela) of the glow under the hull at idle and at full burst. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Rider|Look")
	FVector2D LiftLightRange = FVector2D(6.f, 40.f);

	/** How far the hull and rider bank into a full-lock turn at speed. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Rider|Look", meta = (Units = "deg"))
	float LeanAngle = 24.f;

	// --- Hover ---

	/** Lift ring positions in the body's space (cm), on the underside. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Rider|Hover")
	TArray<FVector> Thrusters;

	/** Gap the rings hold between themselves and the surface. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Rider|Hover", meta = (Units = "cm"))
	float HoverHeight = 60.f;

	/** Beyond this gap a ring loses the surface; with all four out the rider is airborne. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Rider|Hover", meta = (Units = "cm"))
	float HoverRange = 190.f;

	/** Bounce frequency of the cushion. Higher holds the water more tightly. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Rider|Hover", meta = (Units = "Hz"))
	float HoverFrequency = 1.7f;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Rider|Hover")
	float HoverDamping = 0.55f;

	/** Most the cushion pulls the hull down toward the surface, as a fraction of gravity. Low lets crests launch it. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Rider|Hover")
	float HoldDown = 0.3f;

	// --- Drive ---

	/** Forward acceleration at full throttle, m/s². */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Rider|Drive")
	float Thrust = 12.f;

	/** Braking and reverse acceleration, m/s². */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Rider|Drive")
	float ReverseThrust = 7.f;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Rider|Drive", meta = (Units = "km/h"))
	float TopSpeed = 120.f;

	/** Forward acceleration while boosting, m/s². */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Rider|Drive")
	float BoostThrust = 20.f;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Rider|Drive", meta = (Units = "km/h"))
	float BoostTopSpeed = 165.f;

	/** Burst charge used per second of boost. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Rider|Drive")
	float BoostDrain = 0.14f;

	/** How quickly sideways slip dies away on the surface (per second). Lower drifts more. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Rider|Drive")
	float Grip = 2.6f;

	/** Turn rate at walking pace and at top speed. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Rider|Drive", meta = (Units = "deg/s"))
	FVector2D TurnRate = FVector2D(100.f, 58.f);

	// --- Air ---

	/** Upward speed a jump adds. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Rider|Air", meta = (Units = "m/s"))
	float JumpSpeed = 7.5f;

	/** Most lift while bursting, as a multiple of gravity: above 1 so a burst can catch a fall. Climbing is capped by BurstClimbSpeed. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Rider|Air")
	float BurstLift = 1.6f;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Rider|Air", meta = (Units = "m/s"))
	float BurstClimbSpeed = 3.f;

	/** Forward push while bursting, m/s². */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Rider|Air")
	float BurstThrust = 5.f;

	/** How long a full charge keeps the rider aloft. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Rider|Air", meta = (Units = "s"))
	float BurstSeconds = 3.f;

	/** Time on the surface to refill an empty charge. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Rider|Air", meta = (Units = "s"))
	float RechargeSeconds = 6.f;

	/** Pitch and yaw rates under the rider's control in the air. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Rider|Air", meta = (Units = "deg/s"))
	FVector2D AirTurnRate = FVector2D(75.f, 60.f);

	/** How firmly the stability assist rights the hull (per second). */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Rider|Air")
	float StabilityAssist = 4.f;

	// --- Camera ---

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Rider|Camera", meta = (Units = "deg"))
	float FieldOfView = 88.f;

	/** Extra field of view at full boost speed. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Rider|Camera", meta = (Units = "deg"))
	float SpeedFieldOfView = 16.f;

	/** Seconds without look input before the camera swings back behind the rider. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Rider|Camera", meta = (Units = "s"))
	float LookRecentreDelay = 1.5f;

	// --- Input ---

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Input")
	TObjectPtr<UInputMappingContext> RiderMappingContext;

	/** Axis1D: forward thrust (+) and brake/reverse (-). */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Input")
	TObjectPtr<UInputAction> ThrottleAction;

	/** Axis1D: right (+) and left (-). */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Input")
	TObjectPtr<UInputAction> SteerAction;

	/** Axis1D: nose down (+) and up (-), in the air. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Input")
	TObjectPtr<UInputAction> PitchAction;

	/** Axis2D: camera orbit. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Input")
	TObjectPtr<UInputAction> LookAction;

	/** Tap to jump off the surface; hold in the air to burst. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Input")
	TObjectPtr<UInputAction> JumpAction;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Input")
	TObjectPtr<UInputAction> BoostAction;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Input")
	TObjectPtr<UInputAction> ResetAction;

protected:
	virtual void BeginPlay() override;
	virtual void NotifyControllerChanged() override;

	/** Physics body: a box round the hull. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Rider")
	TObjectPtr<UBoxComponent> Body;

	/** Pivot the visible hull banks around, so leaning is cosmetic and never fights the physics. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Rider")
	TObjectPtr<USceneComponent> Lean;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Rider")
	TObjectPtr<UStaticMeshComponent> Hull;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Rider")
	TObjectPtr<UStaticMeshComponent> RiderFigure;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Rider")
	TObjectPtr<UStaticMeshComponent> SprayLeft;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Rider")
	TObjectPtr<UStaticMeshComponent> SprayRight;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Rider")
	TObjectPtr<UStaticMeshComponent> Wake;

	/** Glow the lift rings throw on the water. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Rider")
	TObjectPtr<UPointLightComponent> LiftGlow;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Rider")
	TObjectPtr<USpringArmComponent> Boom;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Rider")
	TObjectPtr<UCameraComponent> Camera;

private:
	struct FSurfaceHit
	{
		float Height = -UE_BIG_NUMBER;
		FVector Normal = FVector::UpVector;
		float RiseSpeed = 0.f;
		bool bWater = false;
	};

	FSurfaceHit FindSurface(const FVector& Point) const;
	void Hover(float DeltaSeconds, int32& OutInRange, FVector& OutSurfaceNormal, bool& OutOnWater);
	void Drive(float DeltaSeconds, float Grounded, const FVector& SurfaceNormal);
	void Attitude(float DeltaSeconds, float Grounded, const FVector& SurfaceNormal);
	void UpdateBurst(float DeltaSeconds, bool bOnSurface);
	void UpdateLook(float DeltaSeconds);
	void UpdateFeedback(float DeltaSeconds);
	void UpdateSpray(float DeltaSeconds);
	void CheckUpset(float DeltaSeconds);

	void OnThrottle(const FInputActionValue& Value);
	void OnThrottleEnd() { ThrottleInput = 0.f; }
	void OnSteer(const FInputActionValue& Value);
	void OnSteerEnd() { SteerInput = 0.f; }
	void OnPitch(const FInputActionValue& Value);
	void OnPitchEnd() { PitchInput = 0.f; }
	void OnLook(const FInputActionValue& Value);
	void OnJumpStart();
	void OnJumpEnd() { bJumpHeld = false; }
	void OnBoostStart() { bBoostHeld = true; }
	void OnBoostEnd() { bBoostHeld = false; }

	TWeakObjectPtr<AOcean> Ocean;

	UPROPERTY(Transient)
	TArray<TObjectPtr<UMaterialInstanceDynamic>> GlowMaterials;

	UPROPERTY(Transient)
	TArray<TObjectPtr<UMaterialInstanceDynamic>> SprayMaterials;

	float ThrottleInput = 0.f;
	float SteerInput = 0.f;
	float PitchInput = 0.f;
	bool bJumpHeld = false;
	bool bBoostHeld = false;
	bool bJumpQueued = false;

	FVector2D LookOffset = FVector2D::ZeroVector;
	float LookIdle = 0.f;

	bool bAirborne = false;
	bool bBursting = false;
	bool bBoosting = false;
	float BurstCharge = 1.f;
	float AirStartTime = 0.f;
	float LastAirTime = 0.f;
	float BestAirTime = 0.f;
	float LastJumpTime = -10.f;
	float HeightAboveSurface = 0.f;
	float UpsetTime = 0.f;
	float Glow = 0.f;
	/** Share of the lift rings skimming the water, 0 to 1. */
	float WaterContact = 0.f;
	float Spray = 0.f;
	/** Extra spray from a landing, dying away. */
	float SprayKick = 0.f;
	float LeanRoll = 0.f;
	float LeanPitch = 0.f;
};
