#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "TownInstances.generated.h"

class UInstancedStaticMeshComponent;
class UMaterialInterface;
class UStaticMesh;

/**
 * Holds instanced meshes placed by an editor script: one instanced component per mesh, saved with the level.
 * The town generator fills one of these per layer (buildings, trees, ...) and clears it before rebuilding.
 */
UCLASS()
class SPACEVOLUTION_API ATownInstances : public AActor
{
	GENERATED_BODY()

public:
	ATownInstances();

	/** Removes every instanced component this actor holds. */
	UFUNCTION(BlueprintCallable, Category = "Town")
	void ClearInstances();

	/**
	 * Adds a component drawing Mesh at each world transform. Materials override the mesh's slots in order (null keeps
	 * the mesh's own). CullDistance (cm) hides instances beyond it; 0 never culls. Returns the new component.
	 */
	UFUNCTION(BlueprintCallable, Category = "Town")
	UInstancedStaticMeshComponent* AddInstances(UStaticMesh* Mesh, const TArray<FTransform>& Transforms,
		const TArray<UMaterialInterface*>& Materials, bool bCollision = true, bool bCastShadow = true, float CullDistance = 0.f);

	UFUNCTION(BlueprintPure, Category = "Town")
	int32 GetInstanceCount() const;
};
