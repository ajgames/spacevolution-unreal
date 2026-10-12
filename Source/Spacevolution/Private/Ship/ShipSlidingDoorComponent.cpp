#include "Ship/ShipSlidingDoorComponent.h"
#include "Spacevolution.h"
#include "Components/MeshComponent.h"
#include "Components/ShapeComponent.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "TimerManager.h"

UShipSlidingDoorComponent::UShipSlidingDoorComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.bStartWithTickEnabled = false;
}

USceneComponent* UShipSlidingDoorComponent::FindOwnedComponent(FName Name) const
{
	TInlineComponentArray<USceneComponent*> Components(GetOwner());
	for (USceneComponent* Component : Components)
	{
		if (Component->GetFName() == Name)
		{
			return Component;
		}
	}
	return nullptr;
}

void UShipSlidingDoorComponent::BeginPlay()
{
	Super::BeginPlay();

	for (const FShipDoorLeaf& Leaf : Leaves)
	{
		USceneComponent* Component = FindOwnedComponent(Leaf.Component);
		if (!Component)
		{
			UE_LOG(LogShip, Warning, TEXT("%s: door leaf %s not found"), *GetOwner()->GetName(), *Leaf.Component.ToString());
		}
		else if (Component->Mobility != EComponentMobility::Movable)
		{
			UE_LOG(LogShip, Warning, TEXT("%s: door leaf %s must be Movable"), *GetOwner()->GetName(), *Leaf.Component.ToString());
		}
		LeafComponents.Add(Component);
		ClosedLocations.Add(Component ? Component->GetRelativeLocation() : FVector::ZeroVector);
	}

	if (!Trigger.IsNone())
	{
		TriggerComponent = Cast<UShapeComponent>(FindOwnedComponent(Trigger));
		if (UShapeComponent* Shape = TriggerComponent.Get())
		{
			Shape->OnComponentBeginOverlap.AddDynamic(this, &UShipSlidingDoorComponent::HandleTriggerBegin);
			Shape->OnComponentEndOverlap.AddDynamic(this, &UShipSlidingDoorComponent::HandleTriggerEnd);

			// Someone may already be standing in the doorway when play starts.
			TArray<AActor*> Overlapping;
			Shape->GetOverlappingActors(Overlapping, APawn::StaticClass());
			for (AActor* Actor : Overlapping)
			{
				PawnsInside.Add(Cast<APawn>(Actor));
			}
		}
		else
		{
			UE_LOG(LogShip, Warning, TEXT("%s: door trigger %s not found"), *GetOwner()->GetName(), *Trigger.ToString());
		}
	}

	SetWantsOpen(!PawnsInside.IsEmpty() && !bLocked);
	Alpha = bWantsOpen ? 1.f : 0.f;
	ApplyAlpha();
}

void UShipSlidingDoorComponent::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (const UWorld* World = GetWorld())
	{
		World->GetTimerManager().ClearTimer(CloseTimer);
	}
	Super::EndPlay(EndPlayReason);
}

void UShipSlidingDoorComponent::HandleTriggerBegin(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor,
	UPrimitiveComponent* OtherComp, int32 OtherBodyIndex, bool bFromSweep, const FHitResult& SweepResult)
{
	if (APawn* Pawn = Cast<APawn>(OtherActor))
	{
		PawnsInside.Add(Pawn);
		GetWorld()->GetTimerManager().ClearTimer(CloseTimer);
		Open();
	}
}

void UShipSlidingDoorComponent::HandleTriggerEnd(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor,
	UPrimitiveComponent* OtherComp, int32 OtherBodyIndex)
{
	APawn* Pawn = Cast<APawn>(OtherActor);
	// A pawn can overlap with several components; it has only left once none of them overlap.
	if (!Pawn || (OverlappedComponent && OverlappedComponent->IsOverlappingActor(Pawn)))
	{
		return;
	}
	PawnsInside.Remove(Pawn);
	if (PawnsInside.IsEmpty())
	{
		GetWorld()->GetTimerManager().SetTimer(CloseTimer, this, &UShipSlidingDoorComponent::Close, FMath::Max(CloseDelay, 0.01f));
	}
}

void UShipSlidingDoorComponent::Open()
{
	if (!bLocked)
	{
		SetWantsOpen(true);
	}
}

void UShipSlidingDoorComponent::Close()
{
	SetWantsOpen(false);
}

void UShipSlidingDoorComponent::SetWantsOpen(bool bOpen)
{
	const bool bChanged = bOpen != bWantsOpen;
	bWantsOpen = bOpen;

	if (UMeshComponent* Lamp = Cast<UMeshComponent>(StatusLamp.IsNone() ? nullptr : FindOwnedComponent(StatusLamp)))
	{
		if (UMaterialInterface* LampMaterial = bOpen ? OpenLampMaterial : ClosedLampMaterial)
		{
			Lamp->SetMaterial(0, LampMaterial);
		}
	}

	if (bChanged)
	{
		SetComponentTickEnabled(true);
		OnDoorStateChanged.Broadcast(bWantsOpen);
	}
}

void UShipSlidingDoorComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);

	const float Target = bWantsOpen ? 1.f : 0.f;
	Alpha = FMath::FInterpConstantTo(Alpha, Target, DeltaTime, 1.f / OpenSeconds);
	ApplyAlpha();
	if (Alpha == Target)
	{
		SetComponentTickEnabled(false);
	}
}

void UShipSlidingDoorComponent::ApplyAlpha()
{
	const float Eased = FMath::InterpEaseInOut(0.f, 1.f, Alpha, 2.f);
	for (int32 Index = 0; Index < LeafComponents.Num(); ++Index)
	{
		if (USceneComponent* Leaf = LeafComponents[Index].Get())
		{
			Leaf->SetRelativeLocation(ClosedLocations[Index] + Leaves[Index].OpenOffset * Eased);
		}
	}
}
