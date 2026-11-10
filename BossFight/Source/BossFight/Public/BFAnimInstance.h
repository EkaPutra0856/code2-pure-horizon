#pragma once

#include "CoreMinimal.h"
#include "Animation/AnimInstance.h"
#include "BFAnimInstance.generated.h"

/**
 * Native parent of the generated player Anim Blueprint.
 * Feeds the locomotion blend space (Direction x Speed) and the air branch.
 */
UCLASS()
class BOSSFIGHT_API UBFAnimInstance : public UAnimInstance
{
	GENERATED_BODY()

public:
	/** Ground speed in cm/s. Blend space Y axis. */
	UPROPERTY(BlueprintReadOnly, Category = "Locomotion")
	float Speed = 0.f;

	/** Movement direction relative to actor facing, -180..180. Blend space X axis. */
	UPROPERTY(BlueprintReadOnly, Category = "Locomotion")
	float Direction = 0.f;

	/** Lock-on strafing (phase 6). When false the body faces its movement, so Direction stays 0. */
	UPROPERTY(BlueprintReadWrite, Category = "Locomotion")
	bool bStrafing = false;

	/** True while falling or jumping. Picks the air pose. */
	UPROPERTY(BlueprintReadOnly, Category = "Locomotion")
	bool bIsInAir = false;

	/** Additive component-space rotation for the spine (ModifyBone in the generated graph). */
	UPROPERTY(BlueprintReadOnly, Category = "Impact")
	FRotator FlinchRot = FRotator::ZeroRotator;

	/** Constant additive component-space rotation on the head bone chain (ABP_Sevarog only):
	 * lifts a head that the source clips hold hunched low. Set by the owning character. */
	UPROPERTY(BlueprintReadOnly, Category = "Pose")
	FRotator HeadLift = FRotator::ZeroRotator;

	/** Aim offset (ABP_Sevarog): head and upper body turn toward LookTarget. Yaw -90..90 (+ = right),
	 * pitch -35..35, Alpha fades the whole offset in and out (off while montages own the body). */
	UPROPERTY(BlueprintReadOnly, Category = "Look")
	float AimYaw = 0.f;
	UPROPERTY(BlueprintReadOnly, Category = "Look")
	float AimPitch = 0.f;
	UPROPERTY(BlueprintReadOnly, Category = "Look")
	float AimAlpha = 0.f;

	/** Set by the owner each frame. */
	TWeakObjectPtr<const AActor> LookTarget;
	bool bLookEnabled = false;

	/** Kicks the upper body away from a hit. PushDir = world direction the blow travels. */
	void AddFlinch(const FVector& PushDir, float Strength);

protected:
	virtual void NativeUpdateAnimation(float DeltaSeconds) override;

private:
	/** Damped spring on a world-space rotation vector (axis * degrees). Uses dilated time,
	 * so it holds still while the owner is in hitstop. */
	FVector FlinchVec = FVector::ZeroVector;
	FVector FlinchVel = FVector::ZeroVector;
};
