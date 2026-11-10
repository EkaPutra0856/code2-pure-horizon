#pragma once

#include "CoreMinimal.h"
#include "BFEnemyBase.h"
#include "BFBossSevarog.generated.h"

/**
 * Sevarog boss (Paragon model): hammer swings, a heavy overhead slam that starts a strength
 * clash when parried, super armor (only finishers make him flinch), larger posture pool.
 * All combat logic lives in ABFEnemyBase; this class swaps mesh, animations and tuning.
 */
UCLASS()
class BOSSFIGHT_API ABFBossSevarog : public ABFEnemyBase
{
	GENERATED_BODY()

public:
	ABFBossSevarog();

	/** Optional additive component-space rotation on neck_01 (roll = nod forward/back). Zero by default:
	 * the "bent head" came from the wrong anim class, not the clips. Test override: -BFHeadLift=<roll>. */
	UPROPERTY(EditAnywhere, Category = "Pose")
	FRotator HeadLift = FRotator::ZeroRotator;

	virtual void Tick(float DeltaSeconds) override;

protected:
	virtual void BeginPlay() override;
	virtual void PostInitializeComponents() override;

	/** ABP_Sevarog. Kept apart from the mesh's AnimClass: the boss placed in L_Arena had saved an
	 * override to ABP_Player, so his own locomotion graph never ran. */
	UPROPERTY()
	TSubclassOf<UAnimInstance> SevarogAnimClass;

	/** Soul aura: a slightly inflated copy of the body (follows its pose) with M_BossAura, shown while
	 * his posture holds and faded out while he is broken or dead. */
	UPROPERTY(VisibleAnywhere, Category = "FX")
	TObjectPtr<USkeletalMeshComponent> AuraShell;
	UPROPERTY()
	TObjectPtr<UMaterialInterface> AuraMaterial;
	UPROPERTY(Transient)
	TObjectPtr<UMaterialInstanceDynamic> AuraMid;
	float AuraFade = 1.f;
	float AuraLogTimer = 0.f;
};
