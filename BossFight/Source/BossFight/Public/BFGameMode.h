#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "BFGameMode.generated.h"

/** Spawns the player swordsman. Boss and match rules arrive in later phases. */
UCLASS()
class BOSSFIGHT_API ABFGameMode : public AGameModeBase
{
	GENERATED_BODY()

public:
	ABFGameMode();
	virtual void StartPlay() override;

private:
	/** Poster runs on maps with their own auto-possessed pawn (asset demo maps): give the player the swordswoman instead. */
	void EnsurePosterPlayer();
};
