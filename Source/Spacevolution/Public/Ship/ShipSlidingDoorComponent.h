#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "ShipSlidingDoorComponent.generated.h"

class APawn;
class UAudioComponent;
class UMaterialInterface;
class UPrimitiveComponent;
class USceneComponent;
class UShapeComponent;
class USoundAttenuation;
class USoundBase;

/** One moving part of a door: a scene component on the same actor, and how far it travels and turns to open. */
USTRUCT(BlueprintType)
struct FShipDoorLeaf
{
	GENERATED_BODY()

	/** Name of the component to move. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Door")
	FName Component;

	/** Offset from its closed position when fully open, in its parent's space. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Door")
	FVector OpenOffset = FVector::ZeroVector;

	/** Turn about the leaf's own pivot when fully open, e.g. a hatch hinged at its foot swinging down into a ramp. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Door")
	FRotator OpenRotation = FRotator::ZeroRotator;
};

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FShipDoorStateSignature, bool, bOpen);

/**
 * Slides (or swings) an actor's door leaves open while a pawn is inside a trigger volume, and closes them once it
 * leaves. Without a trigger the door only moves when told to. Leaves and trigger are found by component name, so any
 * module Blueprint can be given a door. Leaves must be Movable.
 */
UCLASS(ClassGroup = (Ship), meta = (BlueprintSpawnableComponent))
class SPACEVOLUTION_API UShipSlidingDoorComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UShipSlidingDoorComponent();

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Door")
	TArray<FShipDoorLeaf> Leaves;

	/** Shape component whose pawn overlaps open the door. None leaves it to Open/Close calls. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Door")
	FName Trigger;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Door", meta = (ClampMin = 0.05, Units = "s"))
	float OpenSeconds = 0.7f;

	/** How long the door waits after the last pawn leaves before closing. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Door", meta = (ClampMin = 0, Units = "s"))
	float CloseDelay = 0.8f;

	/** A locked door ignores the trigger and Open(). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Door")
	bool bLocked = false;

	/** Optional mesh component whose first material slot shows whether the door is open. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Door|Status Lamp")
	FName StatusLamp;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Door|Status Lamp")
	TObjectPtr<UMaterialInterface> OpenLampMaterial;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Door|Status Lamp")
	TObjectPtr<UMaterialInterface> ClosedLampMaterial;

	/** Played from the doorway (the trigger, else the first leaf) as the door starts to open. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Door|Sound")
	TObjectPtr<USoundBase> OpenSound;

	/** Played as the door starts to close. A door that reverses mid-travel fades out the sound it was making. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Door|Sound")
	TObjectPtr<USoundBase> CloseSound;

	/** How the door's sounds fall off with distance. None plays them at full volume everywhere. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Door|Sound")
	TObjectPtr<USoundAttenuation> SoundAttenuation;

	UPROPERTY(BlueprintAssignable, Category = "Door")
	FShipDoorStateSignature OnDoorStateChanged;

	UFUNCTION(BlueprintCallable, Category = "Door")
	void Open();

	UFUNCTION(BlueprintCallable, Category = "Door")
	void Close();

	/** True while the door is opening or open. */
	UFUNCTION(BlueprintPure, Category = "Door")
	bool IsOpen() const { return bWantsOpen; }

	/** 0 closed .. 1 fully open. */
	UFUNCTION(BlueprintPure, Category = "Door")
	float GetOpenAlpha() const { return Alpha; }

	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

protected:
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

private:
	UFUNCTION()
	void HandleTriggerBegin(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor, UPrimitiveComponent* OtherComp,
		int32 OtherBodyIndex, bool bFromSweep, const FHitResult& SweepResult);

	UFUNCTION()
	void HandleTriggerEnd(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor, UPrimitiveComponent* OtherComp,
		int32 OtherBodyIndex);

	void SetWantsOpen(bool bOpen);
	void PlayDoorSound(bool bOpen);
	void ApplyAlpha();
	USceneComponent* FindOwnedComponent(FName Name) const;

	TArray<TWeakObjectPtr<USceneComponent>> LeafComponents;
	TArray<FVector> ClosedLocations;
	TArray<FQuat> ClosedRotations;
	TWeakObjectPtr<UShapeComponent> TriggerComponent;
	TSet<TWeakObjectPtr<APawn>> PawnsInside;
	FTimerHandle CloseTimer;
	TWeakObjectPtr<UAudioComponent> ActiveSound;
	float Alpha = 0.f;
	bool bWantsOpen = false;
	/** False while BeginPlay sets the starting state, so a door that starts open doesn't announce it. */
	bool bPlaySounds = false;
};
