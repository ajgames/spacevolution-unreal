#pragma once

#include "CoreMinimal.h"
#include "GameFramework/PlayerController.h"
#include "SpacevolutionPlayerController.generated.h"

class UCameraComponent;
class UInputAction;
class UInputMappingContext;
class UShipFlightComponent;
struct FInputActionValue;

/** Owns interface input (overlays, the helm, and later menus and build mode) so it works whatever pawn is possessed. */
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

	/** True when there is a ship this player could take the helm of. */
	UFUNCTION(BlueprintPure, Category = "Helm")
	bool CanPilot() const;

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

	/** Extra field of view at full surge, for a sense of the drive opening up. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Helm")
	float SurgeFieldOfViewBoost = 14.f;

private:
	void TogglePerformanceOverlay();
	void ToggleHelm();
	void HelmMove(const FInputActionValue& Value);
	void HelmStop();
	void HelmSteer(const FInputActionValue& Value);
	void HelmRoll(const FInputActionValue& Value);
	void HelmRollStop();
	void HelmSurgeStart();
	void HelmSurgeStop();

	TWeakObjectPtr<UShipFlightComponent> PilotedFlight;
	TWeakObjectPtr<UCameraComponent> HelmCamera;
	float HelmBaseFieldOfView = 80.f;
};
