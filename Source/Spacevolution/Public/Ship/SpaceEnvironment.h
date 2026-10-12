#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "SpaceEnvironment.generated.h"

class ADirectionalLight;
class AShip;
class UMaterialInstanceDynamic;
class UShipFlightComponent;

/**
 * Keeps the universe arranged around a ship that never moves in the level. Each frame it reads the ship's
 * pose in the space frame (planet at the origin, km) and places the planet, sun, clouds and star backdrop
 * so that the view out of the ship matches where it is and which way it faces.
 *
 * Materials on the clouds and backdrop receive SpaceOrigin and SpaceAxisX/Y/Z, which map world km into
 * the space frame (space = SpaceOrigin + SpaceAxisX * x + SpaceAxisY * y + SpaceAxisZ * z).
 *
 * With bPlanetFixed it serves a level built on the planet's surface instead (its top at the world origin, the ship
 * flying through the world): nothing moves, and only the star backdrop is updated, from wherever the camera is,
 * fading out on the way down through the atmosphere.
 */
UCLASS()
class SPACEVOLUTION_API ASpaceEnvironment : public AActor
{
	GENERATED_BODY()

public:
	ASpaceEnvironment();

	/** Ship to follow. If unset, the first ship in the level. */
	UPROPERTY(EditAnywhere, Category = "Space")
	TObjectPtr<AShip> Ship;

	/** Sky atmosphere actor whose transform is the planet's centre. */
	UPROPERTY(EditAnywhere, Category = "Space")
	TObjectPtr<AActor> Planet;

	UPROPERTY(EditAnywhere, Category = "Space")
	TObjectPtr<ADirectionalLight> Sun;

	/** Volumetric cloud actor; its material gets the space-frame mapping so clouds stay put on the planet. */
	UPROPERTY(EditAnywhere, Category = "Space")
	TObjectPtr<AActor> Clouds;

	/** Mesh carrying the star backdrop material. */
	UPROPERTY(EditAnywhere, Category = "Space")
	TObjectPtr<AActor> Backdrop;

	/** Direction from the planet toward the sun, in the space frame. */
	UPROPERTY(EditAnywhere, Category = "Space")
	FVector SunDirection = FVector(-0.3, -0.1, 0.95);

	/** The planet stays put, its top at the world origin; only the backdrop follows the camera. */
	UPROPERTY(EditAnywhere, Category = "Space|Planet Fixed")
	bool bPlanetFixed = false;

	UPROPERTY(EditAnywhere, Category = "Space|Planet Fixed", meta = (EditCondition = "bPlanetFixed"))
	double PlanetRadiusKm = 6360.0;

	/** Camera altitudes over which the stars fade in on the way up out of the atmosphere. */
	UPROPERTY(EditAnywhere, Category = "Space|Planet Fixed", meta = (EditCondition = "bPlanetFixed"))
	FVector2D StarFadeAltitudeKm = FVector2D(25.0, 70.0);

	virtual void Tick(float DeltaSeconds) override;

protected:
	virtual void BeginPlay() override;

private:
	void Apply();
	void ApplyPlanetFixed();

	UPROPERTY(Transient)
	TObjectPtr<UShipFlightComponent> Flight;

	UPROPERTY(Transient)
	TObjectPtr<UMaterialInstanceDynamic> CloudMaterial;

	UPROPERTY(Transient)
	TObjectPtr<UMaterialInstanceDynamic> BackdropMaterial;

	/** The backdrop's brightness parameters as authored, which the planet-fixed fade scales. */
	TMap<FName, float> BackdropBrightness;
};
