#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "SpacevolutionCharacter.generated.h"

class UCameraComponent;
class UInputAction;
class UInputMappingContext;
struct FInputActionValue;

/** First-person crew member: walks, sprints, jumps and looks around. Input assets are assigned in a Blueprint subclass. */
UCLASS()
class SPACEVOLUTION_API ASpacevolutionCharacter : public ACharacter
{
	GENERATED_BODY()

public:
	ASpacevolutionCharacter();

	UFUNCTION(BlueprintPure, Category = "Camera")
	UCameraComponent* GetFirstPersonCamera() const { return FirstPersonCamera; }

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Movement", meta = (Units = "cm/s"))
	float WalkSpeed = 380.f;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Movement", meta = (Units = "cm/s"))
	float SprintSpeed = 650.f;

protected:
	virtual void BeginPlay() override;
	virtual void NotifyControllerChanged() override;
	virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Input")
	TObjectPtr<UInputMappingContext> DefaultMappingContext;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Input")
	TObjectPtr<UInputAction> MoveAction;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Input")
	TObjectPtr<UInputAction> LookAction;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Input")
	TObjectPtr<UInputAction> JumpAction;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Input")
	TObjectPtr<UInputAction> SprintAction;

private:
	void Move(const FInputActionValue& Value);
	void Look(const FInputActionValue& Value);
	void StartSprint();
	void StopSprint();

	UPROPERTY(VisibleAnywhere, Category = "Camera")
	TObjectPtr<UCameraComponent> FirstPersonCamera;
};
