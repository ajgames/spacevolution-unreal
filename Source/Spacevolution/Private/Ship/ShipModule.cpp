#include "Ship/ShipModule.h"
#include "Ship/ShipFixture.h"
#include "Ship/ShipHardpointComponent.h"
#include "Ship/ShipPartDefinitions.h"
#include "Spacevolution.h"
#include "Components/SceneComponent.h"
#include "Engine/World.h"

AShipModule::AShipModule()
{
	PrimaryActorTick.bCanEverTick = false;

	USceneComponent* Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	Root->SetMobility(EComponentMobility::Static);
	SetRootComponent(Root);
}

void AShipModule::InitModule(UShipModuleDefinition* InDefinition, FIntVector InCell, int32 InQuarterTurns)
{
	Definition = InDefinition;
	Cell = InCell;
	QuarterTurns = InQuarterTurns;
}

TArray<UShipHardpointComponent*> AShipModule::GetHardpoints() const
{
	TArray<UShipHardpointComponent*> Hardpoints;
	GetComponents(Hardpoints);
	return Hardpoints;
}

UShipHardpointComponent* AShipModule::FindHardpoint(FName HardpointName) const
{
	TInlineComponentArray<UShipHardpointComponent*> Hardpoints(this);
	for (UShipHardpointComponent* Hardpoint : Hardpoints)
	{
		if (Hardpoint->GetFName() == HardpointName)
		{
			return Hardpoint;
		}
	}
	return nullptr;
}

AShipFixture* AShipModule::GetFixture(FName HardpointName) const
{
	const TObjectPtr<AShipFixture>* Found = Fixtures.Find(HardpointName);
	return Found ? Found->Get() : nullptr;
}

AShipFixture* AShipModule::MountFixture(FName HardpointName, UShipFixtureDefinition* Fixture)
{
	UShipHardpointComponent* Hardpoint = FindHardpoint(HardpointName);
	if (!Hardpoint)
	{
		UE_LOG(LogShip, Warning, TEXT("%s has no hardpoint named %s"), *GetName(), *HardpointName.ToString());
		return nullptr;
	}

	TObjectPtr<AShipFixture> Previous;
	if (Fixtures.RemoveAndCopyValue(HardpointName, Previous) && Previous)
	{
		Previous->Destroy();
	}

	if (!Fixture)
	{
		return nullptr;
	}
	if (!Fixture->FitsSlot(Hardpoint->SlotType))
	{
		UE_LOG(LogShip, Warning, TEXT("%s doesn't fit %s slot %s on %s"),
			*Fixture->GetName(), *Hardpoint->SlotType.ToString(), *HardpointName.ToString(), *GetName());
		return nullptr;
	}

	UClass* FixtureClass = Fixture->FixtureClass.LoadSynchronous();
	if (!FixtureClass)
	{
		UE_LOG(LogShip, Warning, TEXT("%s has no fixture class"), *Fixture->GetName());
		return nullptr;
	}

	FActorSpawnParameters Params;
	Params.Owner = this;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	const FTransform MountTransform(Hardpoint->GetComponentQuat(), Hardpoint->GetComponentLocation());

	AShipFixture* Spawned = GetWorld()->SpawnActor<AShipFixture>(FixtureClass, MountTransform, Params);
	if (!Spawned)
	{
		return nullptr;
	}
	Spawned->InitFixture(Fixture, HardpointName);
	Spawned->AttachToComponent(Hardpoint, FAttachmentTransformRules::SnapToTargetNotIncludingScale);
#if WITH_EDITOR
	Spawned->SetFolderPath(GetFolderPath());
#endif

	Fixtures.Add(HardpointName, Spawned);
	return Spawned;
}

void AShipModule::MountFixtures(const TMap<FName, TObjectPtr<UShipFixtureDefinition>>& Overrides)
{
	for (UShipHardpointComponent* Hardpoint : GetHardpoints())
	{
		const FName HardpointName = Hardpoint->GetFName();
		const TObjectPtr<UShipFixtureDefinition>* Override = Overrides.Find(HardpointName);
		MountFixture(HardpointName, Override ? Override->Get() : Hardpoint->DefaultFixture.Get());
	}
}

void AShipModule::ClearFixtures()
{
	for (const TPair<FName, TObjectPtr<AShipFixture>>& Pair : Fixtures)
	{
		if (Pair.Value)
		{
			Pair.Value->Destroy();
		}
	}
	Fixtures.Empty();
}

void AShipModule::Destroyed()
{
	ClearFixtures();
	Super::Destroyed();
}
