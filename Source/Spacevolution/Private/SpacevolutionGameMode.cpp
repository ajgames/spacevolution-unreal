#include "SpacevolutionGameMode.h"
#include "SpacevolutionCharacter.h"
#include "SpacevolutionHUD.h"
#include "SpacevolutionPlayerController.h"

ASpacevolutionGameMode::ASpacevolutionGameMode()
{
	DefaultPawnClass = ASpacevolutionCharacter::StaticClass();
	PlayerControllerClass = ASpacevolutionPlayerController::StaticClass();
	HUDClass = ASpacevolutionHUD::StaticClass();
}
