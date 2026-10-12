#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Ocean.generated.h"

class UMaterialInstanceDynamic;
class UMaterialInterface;
class UStaticMeshComponent;

/** One Gerstner wave train. Its speed follows from the wavelength (deep-water dispersion). */
USTRUCT(BlueprintType)
struct FOceanWave
{
	GENERATED_BODY()

	/** Direction of travel, degrees from world +X toward +Y. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Wave")
	float DirectionDegrees = 0.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Wave", meta = (Units = "m", ClampMin = "0.5"))
	float Wavelength = 40.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Wave", meta = (Units = "m", ClampMin = "0"))
	float Amplitude = 0.5f;
};

/** Sheltered water round an island: full waves beyond OuterRadius, the ocean's CalmFloor of them inside InnerRadius. */
USTRUCT(BlueprintType)
struct FOceanCalmZone
{
	GENERATED_BODY()

	/** Centre in world metres. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Calm")
	FVector2D Centre = FVector2D::ZeroVector;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Calm", meta = (Units = "m"))
	float InnerRadius = 100.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Calm", meta = (Units = "m"))
	float OuterRadius = 400.f;
};

/**
 * An endless ocean of Gerstner waves at the actor's height.
 *
 * The surface mesh follows the view, and its material displaces it with the same waves this actor evaluates
 * on the CPU, so anything that floats or rides on the water (SampleSurface) sits exactly on what is drawn.
 * Two things are left to the material alone, as they only matter far from the view: waves fade out where the
 * mesh grows too coarse for them, and the sea curves away with the planet. Seen from high up, the mesh grows with
 * altitude so the sea still reaches the horizon.
 * Wave and calm-zone parameters are pushed to the material each frame as Wave0..7 (dir X, dir Y, wavelength,
 * amplitude) and Calm0..15 (centre X, centre Y, inner, outer radius), all in metres.
 */
UCLASS()
class SPACEVOLUTION_API AOcean : public AActor
{
	GENERATED_BODY()

public:
	static constexpr int32 MaxWaves = 8;
	static constexpr int32 MaxCalmZones = 16;

	AOcean();

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Ocean")
	TArray<FOceanWave> Waves;

	/** How sharp the crests are, 0 (sine swell) to 1 (crests about to fold). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Ocean", meta = (ClampMin = "0", ClampMax = "1"))
	float Steepness = 0.6f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Ocean", meta = (ClampMin = "0"))
	float TimeScale = 1.f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Ocean|Calm")
	TArray<FOceanCalmZone> CalmZones;

	/** Fraction of the waves left inside a calm zone. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Ocean|Calm", meta = (ClampMin = "0", ClampMax = "1"))
	float CalmFloor = 0.15f;

	/** Material for the surface mesh; it reads the parameters above. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Ocean|Surface")
	TObjectPtr<UMaterialInterface> OceanMaterial;

	/**
	 * The surface mesh's vertices spread out away from its centre, so each wave fades out of the geometry from
	 * this many wavelengths from the centre (the material keeps it in the shading normals).
	 */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Ocean|Surface", meta = (ClampMin = "1"))
	float FadeWavelengths = 7.f;

	/** The surface mesh jumps in steps this size as it follows the view, so its dense core never swims. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Ocean|Surface", meta = (Units = "cm", ClampMin = "1"))
	float SnapSize = 1600.f;

	/** Above this height the surface mesh grows in proportion, so the sea reaches the horizon even from orbit. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Ocean|Surface", meta = (Units = "m", ClampMin = "1"))
	float GrowAboveHeight = 500.f;

	/** The sea curves away from the view as a planet this size would. 0 keeps it flat. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Ocean|Surface", meta = (Units = "km"))
	float PlanetRadiusKm = 6360.f;

	/** Water surface under (or over) a world location: its height in world cm, normal, and how fast it is rising (cm/s). */
	UFUNCTION(BlueprintCallable, Category = "Ocean")
	void SampleSurface(const FVector& WorldLocation, float& OutHeight, FVector& OutNormal, float& OutRiseSpeed) const;

	/** Water surface height in world cm under a world location. */
	UFUNCTION(BlueprintPure, Category = "Ocean")
	float GetWaterHeight(const FVector& WorldLocation) const;

	UFUNCTION(BlueprintPure, Category = "Ocean")
	float GetOceanTime() const { return static_cast<float>(OceanTime); }

	/** First ocean in the world, or null. */
	UFUNCTION(BlueprintPure, Category = "Ocean", meta = (WorldContext = "WorldContextObject"))
	static AOcean* FindOcean(const UObject* WorldContextObject);

	virtual void Tick(float DeltaSeconds) override;
	virtual bool ShouldTickIfViewportsOnly() const override { return true; }
	virtual void OnConstruction(const FTransform& Transform) override;

protected:
	virtual void BeginPlay() override;

private:
	/** Displacement (m) of the surface point that starts at P0 (world metres), its normal, and its vertical speed (m/s). */
	FVector Displace(const FVector2D& P0, FVector* OutNormal, float* OutRiseSpeed) const;
	float CalmFactor(const FVector2D& P0) const;
	int32 ActiveWaveCount() const;
	void EnsureMaterial();
	void PushParameters();
	void FollowView();

	UPROPERTY(VisibleAnywhere, Category = "Ocean|Surface")
	TObjectPtr<UStaticMeshComponent> Surface;

	UPROPERTY(Transient)
	TObjectPtr<UMaterialInstanceDynamic> SurfaceMaterial;

	double OceanTime = 0.0;
	/** How much the surface mesh is grown for the view's height. */
	float SurfaceScale = 1.f;
};
