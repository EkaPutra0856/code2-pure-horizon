#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "BFCookManifest.generated.h"

/**
 * Packaging only: hard-references every asset the C++ loads by path at runtime (LoadObject / LoadClass /
 * FindAsset in PostInitializeComponents, BeginPlay and later). The package cooks only L_Arena and what it
 * references, so those assets would otherwise be left out. The asset /Game/BossFight/Cook/DA_CookManifest
 * lives in a DirectoriesToAlwaysCook folder (Config/DefaultGame.ini); the cooker follows these hard
 * references, so exactly these assets (and their dependencies) are added. Filled by Scripts/60_cook_label.py.
 * Never loaded by the game itself.
 */
UCLASS(BlueprintType)
class BOSSFIGHT_API UBFCookManifest : public UDataAsset
{
	GENERATED_BODY()

public:
	UPROPERTY(EditAnywhere, Category = "Cook")
	TArray<TObjectPtr<UObject>> Assets;
};
