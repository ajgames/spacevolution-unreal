#include "Ship/Ship.h"
#include "Ship/ShipFlightComponent.h"
#include "Ship/ShipHardpointComponent.h"
#include "Ship/ShipModule.h"
#include "Ship/ShipPartDefinitions.h"
#include "Ship/ShipSaveGame.h"
#include "Spacevolution.h"
#include "Camera/CameraComponent.h"
#include "Components/SceneComponent.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"

#define LOCTEXT_NAMESPACE "Ship"

namespace
{
	constexpr EShipCellFace AllFaces[] =
	{
		EShipCellFace::Forward, EShipCellFace::Right, EShipCellFace::Back,
		EShipCellFace::Left, EShipCellFace::Up, EShipCellFace::Down
	};
}

AShip::AShip()
{
	PrimaryActorTick.bCanEverTick = false;

	USceneComponent* Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	Root->SetMobility(EComponentMobility::Static);
	SetRootComponent(Root);

	Flight = CreateDefaultSubobject<UShipFlightComponent>(TEXT("Flight"));
}

AShipModule* AShip::FindHelmModule() const
{
	for (AShipModule* Module : ModuleActors)
	{
		if (!IsValid(Module))
		{
			continue;
		}
		TInlineComponentArray<UCameraComponent*> Cameras(Module);
		for (const UCameraComponent* Camera : Cameras)
		{
			if (Camera->GetFName() == TEXT("HelmView"))
			{
				return Module;
			}
		}
	}
	return nullptr;
}

void AShip::BeginPlay()
{
	Super::BeginPlay();

	// A ship built in the editor already has its modules; one spawned at runtime builds itself.
	if (ModuleActors.IsEmpty() && !Layout.Modules.IsEmpty())
	{
		Rebuild();
	}
}

void AShip::Destroyed()
{
	DestroyModules();
	Super::Destroyed();
}

void AShip::Rebuild()
{
	DestroyModules();
	for (const FShipModulePlacement& Placement : Layout.Modules)
	{
		ModuleActors.Add(SpawnModule(Placement));
	}
	OnLayoutChanged.Broadcast();
}

TMap<FIntVector, int32> AShip::BuildOccupancy() const
{
	TMap<FIntVector, int32> Occupancy;
	for (int32 Index = 0; Index < Layout.Modules.Num(); ++Index)
	{
		const FShipModulePlacement& Placement = Layout.Modules[Index];
		if (Placement.Module)
		{
			for (const FIntVector& Cell : Placement.Module->GetPlacedCells(Placement.Cell, Placement.QuarterTurns))
			{
				Occupancy.Add(Cell, Index);
			}
		}
	}
	return Occupancy;
}

int32 AShip::FindPlacementIndex(FIntVector Cell) const
{
	const int32* Index = BuildOccupancy().Find(Cell);
	return Index ? *Index : INDEX_NONE;
}

bool AShip::CanPlaceModule(const UShipModuleDefinition* Module, FIntVector Cell, int32 QuarterTurns, FText& OutReason) const
{
	if (!Module)
	{
		OutReason = LOCTEXT("NoModule", "No module selected.");
		return false;
	}

	const TMap<FIntVector, int32> Occupancy = BuildOccupancy();
	const TArray<FIntVector> NewCells = Module->GetPlacedCells(Cell, QuarterTurns);

	for (const FIntVector& NewCell : NewCells)
	{
		if (const int32* Index = Occupancy.Find(NewCell))
		{
			OutReason = FText::Format(LOCTEXT("Overlap", "Overlaps {0}."), Layout.Modules[*Index].Module->DisplayName);
			return false;
		}
	}

	// A face shared with a neighbour must be open on both sides with the same connector type, or solid on both.
	bool bJoinsShip = false;
	for (const FIntVector& NewCell : NewCells)
	{
		for (const EShipCellFace Face : AllFaces)
		{
			const FIntVector Neighbour = NewCell + ShipGrid::FaceOffset(Face);
			const int32* NeighbourIndex = Occupancy.Find(Neighbour);
			if (!NeighbourIndex)
			{
				continue;
			}

			const FShipModulePlacement& Other = Layout.Modules[*NeighbourIndex];
			const FName Ours = Module->GetConnectorAt(Cell, QuarterTurns, NewCell, Face);
			const FName Theirs = Other.Module->GetConnectorAt(Other.Cell, Other.QuarterTurns, Neighbour, ShipGrid::OppositeFace(Face));
			if (Ours != Theirs)
			{
				OutReason = FText::Format(LOCTEXT("Mismatch", "Doesn't line up with {0}."), Other.Module->DisplayName);
				return false;
			}
			bJoinsShip |= !Ours.IsNone();
		}
	}

	if (!bJoinsShip && !Occupancy.IsEmpty())
	{
		OutReason = LOCTEXT("Detached", "Must connect to the ship.");
		return false;
	}
	return true;
}

AShipModule* AShip::AddModule(UShipModuleDefinition* Module, FIntVector Cell, int32 QuarterTurns)
{
	FText Reason;
	if (!CanPlaceModule(Module, Cell, QuarterTurns, Reason))
	{
		UE_LOG(LogShip, Log, TEXT("Can't place module at %s: %s"), *Cell.ToString(), *Reason.ToString());
		return nullptr;
	}

	// Keep ModuleActors index-aligned with Layout.Modules even if it went stale.
	ModuleActors.SetNum(Layout.Modules.Num());

	FShipModulePlacement& Placement = Layout.Modules.AddDefaulted_GetRef();
	Placement.Module = Module;
	Placement.Cell = Cell;
	Placement.QuarterTurns = QuarterTurns;

	AShipModule* Spawned = SpawnModule(Placement);
	ModuleActors.Add(Spawned);
	OnLayoutChanged.Broadcast();
	return Spawned;
}

bool AShip::RemoveModuleAt(FIntVector Cell)
{
	const int32 Index = FindPlacementIndex(Cell);
	if (Index == INDEX_NONE)
	{
		return false;
	}

	if (ModuleActors.IsValidIndex(Index))
	{
		if (AShipModule* Module = ModuleActors[Index])
		{
			Module->Destroy();
		}
		ModuleActors.RemoveAt(Index);
	}
	Layout.Modules.RemoveAt(Index);
	OnLayoutChanged.Broadcast();
	return true;
}

bool AShip::SetFixture(FIntVector Cell, FName Hardpoint, UShipFixtureDefinition* Fixture)
{
	const int32 Index = FindPlacementIndex(Cell);
	if (Index == INDEX_NONE)
	{
		return false;
	}

	AShipModule* Module = ModuleActors.IsValidIndex(Index) ? ModuleActors[Index].Get() : nullptr;
	if (Module)
	{
		const UShipHardpointComponent* HardpointComponent = Module->FindHardpoint(Hardpoint);
		if (!HardpointComponent || (Fixture && !Fixture->FitsSlot(HardpointComponent->SlotType)))
		{
			return false;
		}
		Module->MountFixture(Hardpoint, Fixture);
	}

	Layout.Modules[Index].FixtureOverrides.Add(Hardpoint, Fixture);
	OnLayoutChanged.Broadcast();
	return true;
}

AShipModule* AShip::GetModuleAt(FIntVector Cell) const
{
	const int32 Index = FindPlacementIndex(Cell);
	return ModuleActors.IsValidIndex(Index) ? ModuleActors[Index].Get() : nullptr;
}

FTransform AShip::GetCellTransform(FIntVector Cell, int32 QuarterTurns) const
{
	const FTransform Local(FRotator(0.0, 90.0 * QuarterTurns, 0.0), FVector(Cell) * CellSize);
	return Local * GetActorTransform();
}

FIntVector AShip::WorldToCell(FVector WorldLocation) const
{
	const FVector Local = GetActorTransform().InverseTransformPosition(WorldLocation) / CellSize;
	return FIntVector(FMath::RoundToInt(Local.X), FMath::RoundToInt(Local.Y), FMath::FloorToInt(Local.Z));
}

bool AShip::SaveLayout(const FString& SlotName, int32 UserIndex) const
{
	UShipSaveGame* Save = Cast<UShipSaveGame>(UGameplayStatics::CreateSaveGameObject(UShipSaveGame::StaticClass()));
	Save->Layout = Layout;
	return UGameplayStatics::SaveGameToSlot(Save, SlotName, UserIndex);
}

bool AShip::LoadLayout(const FString& SlotName, int32 UserIndex)
{
	const UShipSaveGame* Save = Cast<UShipSaveGame>(UGameplayStatics::LoadGameFromSlot(SlotName, UserIndex));
	if (!Save)
	{
		return false;
	}
	Layout = Save->Layout;
	Rebuild();
	return true;
}

AShipModule* AShip::SpawnModule(const FShipModulePlacement& Placement)
{
	if (!Placement.Module)
	{
		return nullptr;
	}

	UClass* ModuleClass = Placement.Module->ModuleClass.LoadSynchronous();
	if (!ModuleClass)
	{
		UE_LOG(LogShip, Warning, TEXT("%s has no module class"), *Placement.Module->GetName());
		return nullptr;
	}

	FActorSpawnParameters Params;
	Params.Owner = this;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;

	AShipModule* Module = GetWorld()->SpawnActor<AShipModule>(
		ModuleClass, GetCellTransform(Placement.Cell, Placement.QuarterTurns), Params);
	if (!Module)
	{
		return nullptr;
	}

	Module->InitModule(Placement.Module, Placement.Cell, Placement.QuarterTurns);
	Module->AttachToActor(this, FAttachmentTransformRules::KeepWorldTransform);
#if WITH_EDITOR
	Module->SetActorLabel(FString::Printf(TEXT("%s_%d_%d_%d"),
		*Placement.Module->GetName(), Placement.Cell.X, Placement.Cell.Y, Placement.Cell.Z));
	Module->SetFolderPath(GetFolderPath());
#endif
	Module->MountFixtures(Placement.FixtureOverrides);
	return Module;
}

void AShip::DestroyModules()
{
	// Also sweep attached modules the array lost track of (e.g. after an undo).
	TArray<AActor*> Attached;
	GetAttachedActors(Attached);
	for (AActor* Actor : Attached)
	{
		if (AShipModule* Module = Cast<AShipModule>(Actor))
		{
			Module->Destroy();
		}
	}
	for (AShipModule* Module : ModuleActors)
	{
		if (IsValid(Module))
		{
			Module->Destroy();
		}
	}
	ModuleActors.Reset();
}

#undef LOCTEXT_NAMESPACE
