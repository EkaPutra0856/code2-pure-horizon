#include "BFGameMode.h"

#include "BFHUD.h"
#include "BFPlayerCharacter.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "Misc/CommandLine.h"
#include "TimerManager.h"

ABFGameMode::ABFGameMode()
{
	DefaultPawnClass = ABFPlayerCharacter::StaticClass();
	HUDClass = ABFHUD::StaticClass();
}

void ABFGameMode::StartPlay()
{
	Super::StartPlay();
	FString Mode;
	if (FParse::Value(FCommandLine::Get(), TEXT("BFAutoTest="), Mode) && Mode == TEXT("poster"))
	{
		FTimerHandle Handle;
		GetWorldTimerManager().SetTimer(Handle, this, &ABFGameMode::EnsurePosterPlayer, 0.5f, false);
	}
}

void ABFGameMode::EnsurePosterPlayer()
{
	APlayerController* PC = GetWorld()->GetFirstPlayerController();
	if (!PC || Cast<ABFPlayerCharacter>(PC->GetPawn()))
	{
		return;
	}
	APawn* Old = PC->GetPawn();
	const FVector At = Old ? Old->GetActorLocation() : FVector::ZeroVector;
	FActorSpawnParameters Params;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	ABFPlayerCharacter* Hero = GetWorld()->SpawnActor<ABFPlayerCharacter>(ABFPlayerCharacter::StaticClass(), At, FRotator::ZeroRotator, Params);
	if (!Hero)
	{
		UE_LOG(LogTemp, Warning, TEXT("BFPOSTER could not spawn the player character"));
		return;
	}
	if (Old)
	{
		PC->UnPossess();
		Old->SetActorHiddenInGame(true);
		Old->SetActorTickEnabled(false);
	}
	PC->Possess(Hero);
	UE_LOG(LogTemp, Display, TEXT("BFPOSTER map pawn %s replaced by the player character"), Old ? *Old->GetName() : TEXT("none"));
}
