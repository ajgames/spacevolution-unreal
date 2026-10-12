#include "Ship/ShipFixture.h"
#include "Components/SceneComponent.h"

AShipFixture::AShipFixture()
{
	PrimaryActorTick.bCanEverTick = false;

	USceneComponent* Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	Root->SetMobility(EComponentMobility::Static);
	SetRootComponent(Root);
}

void AShipFixture::InitFixture(UShipFixtureDefinition* InDefinition, FName InHardpointName)
{
	Definition = InDefinition;
	HardpointName = InHardpointName;
}
