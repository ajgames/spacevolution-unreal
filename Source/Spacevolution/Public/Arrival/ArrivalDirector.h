#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "ArrivalDirector.generated.h"

class ALandingPad;
class AShip;
class AWaveRider;

UENUM(BlueprintType)
enum class EArrivalStep : uint8
{
	TakeHelm,
	Descend,
	Land,
	Landing,
	LeaveHelm,
	ExitShip,
	BoardRider,
	Ride,
	Done,
};

/**
 * Walks the player through arriving by ship: take the helm, fly down to the spaceport, land, leave the ship and
 * board the wave rider moored there. It reads the step from the state of play every frame (so it can't get out of
 * step with what the player actually did) and offers the HUD an objective, a hint and a target to mark.
 */
UCLASS()
class SPACEVOLUTION_API AArrivalDirector : public AActor
{
	GENERATED_BODY()

public:
	AArrivalDirector();

	/** The ship the player arrives in. If unset, the first ship in the level. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Arrival")
	TObjectPtr<AShip> Ship;

	/** Where to send the player once they're out of the ship: the foot of its boarding ramp, in the ship's space. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Arrival", meta = (Units = "cm"))
	FVector RampFoot = FVector(-560.0, 0.0, -80.0);

	/** How long the riding tips stay up once the player is on the water. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Arrival", meta = (Units = "s"))
	float RideTipSeconds = 25.f;

	UFUNCTION(BlueprintPure, Category = "Arrival")
	EArrivalStep GetStep() const { return Step; }

	/** What to do now; empty once there's nothing left to guide. */
	UFUNCTION(BlueprintPure, Category = "Arrival")
	FText GetObjective() const;

	/** How to do it. */
	UFUNCTION(BlueprintPure, Category = "Arrival")
	FText GetHint() const;

	/** Where the HUD should point, and what to call it. False when there's nothing to point at. */
	UFUNCTION(BlueprintPure, Category = "Arrival")
	bool GetTarget(FVector& OutLocation, FText& OutLabel) const;

	virtual void Tick(float DeltaSeconds) override;

protected:
	virtual void BeginPlay() override;

private:
	EArrivalStep Step = EArrivalStep::TakeHelm;
	TWeakObjectPtr<ALandingPad> Pad;
	TWeakObjectPtr<AWaveRider> Rider;
};
