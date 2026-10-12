#include "Ship/ShipHardpointComponent.h"

UShipHardpointComponent::UShipHardpointComponent()
{
	PrimaryComponentTick.bCanEverTick = false;
	Mobility = EComponentMobility::Static;
#if WITH_EDITORONLY_DATA
	bVisualizeComponent = true;
#endif
}
