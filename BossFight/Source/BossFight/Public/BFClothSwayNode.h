// Robe cloth for Paragon-style cloth bones: every strip is a chain of verlet particles (one per bone).
// The top particle is pinned to the animated bone; the others carry inertia, gravity, damping and a
// breeze, get pulled back toward the animated shape (stiff at the root, loose at the tip), stay off
// the legs and torso through capsule colliders, and keep their segment lengths. Motion therefore
// ripples down each strip instead of the strip swinging as one stick.
#pragma once

#include "CoreMinimal.h"
#include "BoneControllers/AnimNode_SkeletalControlBase.h"
#include "BFClothSwayNode.generated.h"

USTRUCT(BlueprintType)
struct BOSSFIGHT_API FBFClothChain
{
	GENERATED_BODY()

	/** Top bone of the strip (pinned to the animation, but it still rotates). */
	UPROPERTY(EditAnywhere, Category = Cloth)
	FName StartBone;

	/** Tip bone of the strip (a descendant of StartBone). */
	UPROPERTY(EditAnywhere, Category = Cloth)
	FName EndBone;

	/** Multiplies the node's stiffness for this strip (sleeves on fast-swinging arms want more). */
	UPROPERTY(EditAnywhere, Category = Cloth)
	float StiffnessScale = 1.f;

	/** Angle limit for this strip; 0 = the node's MaxAngleDeg. */
	UPROPERTY(EditAnywhere, Category = Cloth)
	float MaxAngleDeg = 0.f;

	/** Inertia for this strip; negative = the node's Inertia. */
	UPROPERTY(EditAnywhere, Category = Cloth)
	float Inertia = -1.f;
};

/** Capsule from Bone to EndBone (or a sphere at Bone when EndBone is None) that cloth particles stay out of. */
USTRUCT(BlueprintType)
struct BOSSFIGHT_API FBFClothCollider
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, Category = Cloth)
	FName Bone;

	UPROPERTY(EditAnywhere, Category = Cloth)
	FName EndBone;

	UPROPERTY(EditAnywhere, Category = Cloth)
	float Radius = 10.f;

	/** Shift of the capsule's ends from Bone / EndBone, in component space of the reference pose (cm). The node
	 * turns it into each bone's local frame, so the axis can sit on the flesh instead of on the joints. */
	UPROPERTY(EditAnywhere, Category = Cloth)
	FVector OffsetA = FVector::ZeroVector;

	UPROPERTY(EditAnywhere, Category = Cloth)
	FVector OffsetB = FVector::ZeroVector;
};

USTRUCT(BlueprintInternalUseOnly)
struct BOSSFIGHT_API FAnimNode_BFClothSway : public FAnimNode_SkeletalControlBase
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, Category = Cloth)
	TArray<FBFClothChain> Chains;

	UPROPERTY(EditAnywhere, Category = Cloth)
	TArray<FBFClothCollider> Colliders;

	/** Velocity lost per 1/60 s step (0 = never settles, 1 = no momentum). */
	UPROPERTY(EditAnywhere, Category = Cloth)
	float Damping = 0.07f;

	/** Pull toward the animated shape per 1/60 s step, at the strip's first moving joint ... */
	UPROPERTY(EditAnywhere, Category = Cloth)
	float StiffnessRoot = 0.16f;

	/** ... and at its tip (lower = floppier tip). */
	UPROPERTY(EditAnywhere, Category = Cloth)
	float StiffnessTip = 0.025f;

	/** World gravity on the particles (cm/s^2). */
	UPROPERTY(EditAnywhere, Category = Cloth)
	FVector Gravity = FVector(0.f, 0.f, -600.f);

	/** Share of the body's world travel the cloth resists (1 = full lag, 0 = moves rigidly with the body). */
	UPROPERTY(EditAnywhere, Category = Cloth)
	float Inertia = 0.75f;

	/** Clamp on each segment's angle away from its animated direction. */
	UPROPERTY(EditAnywhere, Category = Cloth)
	float MaxAngleDeg = 65.f;

	/** Cap on a particle's speed (cm/s). */
	UPROPERTY(EditAnywhere, Category = Cloth)
	float MaxSpeed = 1500.f;

	/** Share of a particle's velocity removed when it hits the angle limit. */
	UPROPERTY(EditAnywhere, Category = Cloth)
	float LimitFriction = 0.7f;

	/** Breeze acceleration (cm/s^2) and its period (s); each strip gets its own phase. */
	UPROPERTY(EditAnywhere, Category = Cloth)
	float WindStrength = 900.f;

	UPROPERTY(EditAnywhere, Category = Cloth)
	float WindPeriod = 2.6f;

	/** Collision radius per particle from the reference pose: a particle that rests closer to a capsule than its
	 * Radius (a skirt hanging against the thigh) keeps that rest gap as its radius instead of skipping the capsule.
	 * Off = the old rule (skip a capsule whenever the animated point is inside it). */
	UPROPERTY(EditAnywhere, Category = Cloth)
	bool bRestRadius = false;

	/** Gap kept beyond the rest distance when bRestRadius (share of it, 0.9 = may come 10 % closer than at rest). */
	UPROPERTY(EditAnywhere, Category = Cloth)
	float RestRadiusScale = 0.9f;

	/** Also test each segment's midpoint and push the segment off a capsule (thin limbs otherwise slip between particles). */
	UPROPERTY(EditAnywhere, Category = Cloth)
	bool bSegmentCollision = false;

	/** Collision passes per substep (more = less sinking where capsules overlap). */
	UPROPERTY(EditAnywhere, Category = Cloth)
	int32 CollisionIterations = 1;

	/** A root jump larger than this in one frame is a teleport: the strip snaps back to the animated pose. */
	UPROPERTY(EditAnywhere, Category = Cloth)
	float TeleportDistance = 250.f;

	/** Dead owner (ABFEnemyBase::GetDeathSettle): these upper arms swing down, rigidly about the shoulder, until
	 * the matching hand rests on the floor. Raised arms of the held death pose sink slowly to the ground. */
	UPROPERTY(EditAnywhere, Category = Cloth)
	TArray<FName> DropArms = { FName(TEXT("upperarm_l")), FName(TEXT("upperarm_r")) };

	UPROPERTY(EditAnywhere, Category = Cloth)
	TArray<FName> DropHands = { FName(TEXT("hand_l")), FName(TEXT("hand_r")) };

	virtual void Initialize_AnyThread(const FAnimationInitializeContext& Context) override;
	virtual void UpdateInternal(const FAnimationUpdateContext& Context) override;
	virtual void EvaluateSkeletalControl_AnyThread(FComponentSpacePoseContext& Output, TArray<FBoneTransform>& OutBoneTransforms) override;
	virtual bool IsValidToEvaluate(const USkeleton* Skeleton, const FBoneContainer& RequiredBones) override;

private:
	virtual void InitializeBoneReferences(const FBoneContainer& RequiredBones) override;

	struct FChainState
	{
		TArray<FCompactPoseBoneIndex> Bones;
		TArray<FVector> X;        // particle positions (world)
		TArray<FVector> XPrev;    // previous step positions (world)
		TArray<FVector> AnimPrev; // animated positions last frame (world)
		float Phase = 0.f;
		bool bInit = false;
		TArray<float> Radius;     // per particle x collider (bRestRadius), particle-major
		TArray<float> MidRadius;  // per segment midpoint x collider (bRestRadius)
	};
	struct FColliderState
	{
		FCompactPoseBoneIndex A = FCompactPoseBoneIndex(INDEX_NONE);
		FCompactPoseBoneIndex B = FCompactPoseBoneIndex(INDEX_NONE);
		float Radius = 0.f;
		FVector LocalA = FVector::ZeroVector; // offsets in the bones' local frames
		FVector LocalB = FVector::ZeroVector;
	};
	TArray<FChainState> State;
	TArray<FColliderState> ColliderState;
	struct FArmDropState
	{
		FCompactPoseBoneIndex Upper = FCompactPoseBoneIndex(INDEX_NONE);
		FCompactPoseBoneIndex Hand = FCompactPoseBoneIndex(INDEX_NONE);
		FCompactPoseBoneIndex Chest = FCompactPoseBoneIndex(INDEX_NONE);
	};
	TArray<FArmDropState> ArmState;
	float Settle = 0.f;
	float FloorZ = 0.f;
	void ApplyArmDrop(FComponentSpacePoseContext& Output, const FTransform& CompT) const;
	float PendingDt = 0.f;
	/** 0 normal .. 1 limp (owner dead): shape keeping off, wide angle limit, so the robe drapes. */
	float Loose = 0.f;
	float Time = 0.f;
	float LastStep = 1.f / 60.f;

	// Diagnostics (BFCLOTH log lines): worst segment angle off the animation, and body yaw rate.
	FQuat DiagPrevCompQ = FQuat::Identity;
	float DiagTimer = 0.f;
	float DiagMaxDev = 0.f;
	float DiagMaxYawRate = 0.f;
	float DiagMaxRelSpeed = 0.f;
	float DiagMaxPen = 0.f; // deepest particle inside a capsule after the solve (cm)
	FName DiagChain;
};
