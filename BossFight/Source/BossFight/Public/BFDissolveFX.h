#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "BFDissolveFX.generated.h"

class UInstancedStaticMeshComponent;
class USkeletalMeshComponent;

/**
 * Glowing motes that rise off a skeletal mesh while it dissolves (boss death) or re-forms (respawn).
 * Motes start at random points along the mesh's bones, drift up with a slow swirl and shrink away.
 * Rendered as one instanced sphere mesh with /Game/BossFight/FX/M_Mote (Scripts/38_boss_dissolve.py).
 */
UCLASS()
class BOSSFIGHT_API ABFDissolveFX : public AActor
{
	GENERATED_BODY()

public:
	ABFDissolveFX();

	/** Emits for Duration seconds from Source's bones; Rate scales the mote count; destroys itself when done. */
	static ABFDissolveFX* Spawn(UWorld* World, USkeletalMeshComponent* Source, float Duration, float Rate = 1.f, const FLinearColor& Color = FLinearColor(0.3f, 1.f, 0.5f));

protected:
	virtual void Tick(float DeltaSeconds) override;

private:
	UPROPERTY()
	TObjectPtr<UInstancedStaticMeshComponent> Motes;

	TWeakObjectPtr<USkeletalMeshComponent> Source;

	struct FMote
	{
		FVector P = FVector::ZeroVector;
		FVector V = FVector::ZeroVector;
		float Age = 0.f;
		float Life = 0.f;
		float Size = 0.f;
		float Phase = 0.f;
	};
	TArray<FMote> Pool;
	TArray<FName> Bones;
	TArray<FName> Parents;
	TArray<FTransform> Xforms;
	int32 Next = 0;
	float Duration = 1.f;
	float Rate = 1.f;
	float Elapsed = 0.f;
	float SpawnAcc = 0.f;

	static constexpr int32 MaxMotes = 900;
};
