// Still-poster staging for -BFAutoTest=poster. Reads a scene file (-BFPosterFile=<path>) that places the player
// (the swordswoman), the boss and extra characters in frozen animation poses, adds lights, Niagara effects and props,
// then takes HighResShot stills from one or more cameras and quits. See Scripts/Poster/*.txt for scene files.
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "BFPosterDirector.generated.h"

class ABFPlayerCharacter;
class ACameraActor;
class USkeletalMeshComponent;
class UAnimSequenceBase;

UCLASS()
class BOSSFIGHT_API ABFPosterDirector : public AActor
{
	GENERATED_BODY()

public:
	ABFPosterDirector();
	virtual void Tick(float DeltaSeconds) override;

	/** Loads the scene file and stages everything. Call once right after spawning. */
	void Setup(ABFPlayerCharacter* InPlayer);

private:
	struct FShot
	{
		FVector Loc = FVector::ZeroVector;
		FRotator Rot = FRotator::ZeroRotator;
		float Fov = 40.f;
		FString Name;
	};
	struct FPosed
	{
		TWeakObjectPtr<USkeletalMeshComponent> Mesh;
		TWeakObjectPtr<UAnimSequenceBase> Anim;
		float Time = 0.f;
	};

	void ParseLine(const FString& Line);
	void Pose(USkeletalMeshComponent* Mesh, const FString& AnimPath, float Time);
	void HoldPoses();
	void TickHeadLook();
	USkeletalMeshComponent* HeroBody() const;

	/** Shown in place of the hero's body when the hero line has look= (head tilt); see TickHeadLook. */
	UPROPERTY()
	TObjectPtr<class UPoseableMeshComponent> HeroPose;
	float HeadLook = 0.f;

	UPROPERTY()
	TObjectPtr<ABFPlayerCharacter> Player;
	UPROPERTY()
	TObjectPtr<ACameraActor> Cam;
	UPROPERTY()
	TArray<TObjectPtr<UObject>> Keep;

	/** One-shot effect (burst slashes) that will not hold a frozen age: fired live Lead seconds before every capture. */
	struct FLeadFx
	{
		TWeakObjectPtr<class UNiagaraComponent> Fx;
		float Lead = 0.2f;
		int32 FiredFor = -1;
	};

	TArray<FShot> Shots;
	TArray<FPosed> Posed;
	TArray<FLeadFx> LeadFx;

	/** Ribbon trail (e.g. NS_Trail_Sword) swept from From to To during the Lead seconds before every capture. */
	struct FTrail
	{
		TWeakObjectPtr<class UNiagaraComponent> Fx;
		FVector From = FVector::ZeroVector;
		FVector To = FVector::ZeroVector;
		float Lead = 0.35f;
		float Start = 0.f;
		int32 FiredFor = -1;
	};
	TArray<FTrail> Trails;
	TArray<FString> PostCommands;
	/** Where the hero line put the player; re-applied every tick so nothing turns or moves her. */
	FTransform HeroXform;
	bool bHeroPlaced = false;
	int32 ResX = 1080;
	int32 ResY = 1620;
	float Warm = 4.f;
	float Wait = 0.f;
	float ShotGap = 2.f;
	int32 NextShot = 0;
	float NextShotAt = 0.f;
	bool bStarted = false;
	float Elapsed = 0.f;
};
