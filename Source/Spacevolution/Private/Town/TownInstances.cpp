#include "Town/TownInstances.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Engine/CollisionProfile.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"

ATownInstances::ATownInstances()
{
	USceneComponent* Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	Root->SetMobility(EComponentMobility::Static);
	SetRootComponent(Root);
}

void ATownInstances::ClearInstances()
{
	TArray<UActorComponent*> Doomed;
	for (UActorComponent* Component : GetInstanceComponents())
	{
		if (Cast<UInstancedStaticMeshComponent>(Component))
		{
			Doomed.Add(Component);
		}
	}
	for (UActorComponent* Component : Doomed)
	{
		RemoveInstanceComponent(Component);
		Component->DestroyComponent();
	}
}

UInstancedStaticMeshComponent* ATownInstances::AddInstances(UStaticMesh* Mesh, const TArray<FTransform>& Transforms,
	const TArray<UMaterialInterface*>& Materials, bool bCollision, bool bCastShadow, float CullDistance)
{
	if (!Mesh || Transforms.IsEmpty())
	{
		return nullptr;
	}
	UInstancedStaticMeshComponent* Component = NewObject<UInstancedStaticMeshComponent>(this, NAME_None, RF_Transactional);
	Component->SetMobility(EComponentMobility::Static);
	Component->SetupAttachment(GetRootComponent());
	Component->SetStaticMesh(Mesh);
	for (int32 Slot = 0; Slot < Materials.Num(); ++Slot)
	{
		if (Materials[Slot])
		{
			Component->SetMaterial(Slot, Materials[Slot]);
		}
	}
	Component->SetCollisionEnabled(bCollision ? ECollisionEnabled::QueryAndPhysics : ECollisionEnabled::NoCollision);
	Component->SetCollisionProfileName(bCollision ? UCollisionProfile::BlockAll_ProfileName : UCollisionProfile::NoCollision_ProfileName);
	Component->SetCastShadow(bCastShadow);
	if (CullDistance > 0.f)
	{
		Component->InstanceEndCullDistance = static_cast<int32>(CullDistance);
		Component->InstanceStartCullDistance = static_cast<int32>(CullDistance * 0.85f);
	}
	AddInstanceComponent(Component);
	Component->RegisterComponent();
	Component->AddInstances(Transforms, /*bShouldReturnIndices*/ false, /*bWorldSpace*/ true);
	return Component;
}

int32 ATownInstances::GetInstanceCount() const
{
	int32 Count = 0;
	for (const UActorComponent* Component : GetInstanceComponents())
	{
		if (const UInstancedStaticMeshComponent* Instanced = Cast<UInstancedStaticMeshComponent>(Component))
		{
			Count += Instanced->GetInstanceCount();
		}
	}
	return Count;
}
