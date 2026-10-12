#pragma once

#include "CoreMinimal.h"
#include "GameFramework/PlayerController.h"
#include "SpacevolutionPlayerController.generated.h"

class AShip;
class AWaveRider;
class UCameraComponent;
class UInputAction;
class UInputMappingContext;
class UShipFlightComponent;
struct FInputActionValue;

/**
 * Owns interface input (overlays, the helm, and later menus and build mode) so it works whatever pawn is possessed.
 * The use key (F) is contextual: it boards a moored wave rider within reach, otherwise takes or leaves the helm.
 */
UCLASS()
class SPACEVOLUTION_API ASpacevolutionPlayerController : public APlayerController
{
	GENERATED_BODY()

public:
	ASpacevolutionPlayerController();

	/** Take or leave the helm. Piloting glides the view to the ship's helm viewpoint and routes input to the flight drive. */
	UFUNCTION(BlueprintCallable, Category = "Helm")
	void SetPiloting(bool bPilot);

	UFUNCTION(BlueprintPure, Category = "Helm")
	bool IsPiloting() const { return PilotedFlight.IsValid(); }

	/** Flight drive being piloted, or null. */
	UFUNCTION(BlueprintPure, Category = "Helm")
	UShipFlightComponent* GetPilotedFlight() const { return PilotedFlight.Get(); }

	/** True when the player is aboard a ship and could take its helm. */
	UFUNCTION(BlueprintPure, Category = "Helm")
	bool CanPilot() const;

	/** The ship in the level, if any. */
	UFUNCTION(BlueprintPure, Category = "Helm")
	AShip* GetShip() const;

	/** An unridden wave rider within reach of the player on foot, or null. */
	UFUNCTION(BlueprintPure, Category = "Interact")
	AWaveRider* FindRideableNearby() const;

	/** Hands the player over to a wave rider; the crew member stays behind out of sight. */
	UFUNCTION(BlueprintCallable, Category = "Interact")
	bool BoardRider(AWaveRider* Rider);

	/** A short notice for the HUD (e.g. why the pad won't take you yet), empty once it has been up a while. */
	UFUNCTION(BlueprintPure, Category = "HUD")
	FText GetNotice() const;

	UFUNCTION(BlueprintCallable, Category = "HUD")
	void ShowNotice(const FText& Notice);

	virtual void PlayerTick(float DeltaTime) override;

protected:
	virtual void BeginPlay() override;
	virtual void SetupInputComponent() override;

	/** Added above the pawn's context so interface keys always win. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Input")
	TObjectPtr<UInputMappingContext> InterfaceMappingContext;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Input")
	TObjectPtr<UInputAction> TogglePerformanceOverlayAction;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Input|Helm")
	TObjectPtr<UInputAction> ToggleHelmAction;

	/** Added on top of everything while piloting; its keys shadow the crew's walking controls. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Input|Helm")
	TObjectPtr<UInputMappingContext> HelmMappingContext;

	/** Axis3D in ship space: X forward, Y right, Z up. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Input|Helm")
	TObjectPtr<UInputAction> HelmMoveAction;

	/** Axis2D in degrees: X yaw, Y pitch. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Input|Helm")
	TObjectPtr<UInputAction> HelmSteerAction;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Input|Helm")
	TObjectPtr<UInputAction> HelmRollAction;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Input|Helm")
	TObjectPtr<UInputAction> HelmSurgeAction;

	/** Calls the landing autopilot over a pad, or lifts off from one. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Input|Helm")
	TObjectPtr<UInputAction> HelmLandAction;

	/** How close the player has to walk to a wave rider to board it. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Interact", meta = (Units = "cm"))
	float RideReach = 450.f;

	/** Extra field of view at full surge, for a sense of the drive opening up. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Helm")
	float SurgeFieldOfViewBoost = 14.f;

private:
	void TogglePerformanceOverlay();
	void Interact();
	void ToggleHelm();
	void HelmLand();
	void HelmMove(const FInputActionValue& Value);
	void HelmStop();
	void HelmSteer(const FInputActionValue& Value);
	void HelmRoll(const FInputActionValue& Value);
	void HelmRollStop();
	void HelmSurgeStart();
	void HelmSurgeStop();

	TWeakObjectPtr<UShipFlightComponent> PilotedFlight;
	FText Notice;
	double NoticeTime = -100.0;
	TWeakObjectPtr<UCameraComponent> HelmCamera;
	float HelmBaseFieldOfView = 80.f;
};
