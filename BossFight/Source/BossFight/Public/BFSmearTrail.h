// Anime-style smear: a ribbon mesh built in world space from pairs of points sampled every frame
// (sword hilt + tip for a slash arc, a short segment on a bone for speed streaks). Each sample fades
// over Lifetime; gaps between samples are filled with Catmull-Rom points so fast swings stay round.
#pragma once

#include "CoreMinimal.h"
#include "ProceduralMeshComponent.h"
#include "BFSmearTrail.generated.h"

UCLASS(ClassGroup = (BossFight), meta = (BlueprintSpawnableComponent))
class BOSSFIGHT_API UBFSmearTrail : public UProceduralMeshComponent
{
	GENERATED_BODY()

public:
	UBFSmearTrail(const FObjectInitializer& ObjectInitializer);

	/** Material: M_Smear (additive; U = age 0 new..1 old, V = 0 inner..1 outer edge). */
	void Setup(UMaterialInterface* Material, const FLinearColor& Color, float Intensity, float Lifetime);

	/** Adds this frame's pair (A = inner edge, B = outer edge). Call every tick while emitting. */
	void AddSample(const FVector& A, const FVector& B);

	/** Breaks the ribbon: the next sample starts a new strip instead of bridging from the last one. */
	void Cut() { bCut = true; }

	void SetLook(const FLinearColor& Color, float Intensity, float Lifetime);

	/** Any other scalar on the material (M_Smear "Outer": 1 = crescent bright at the outer edge, 0 = centred streak). */
	void SetScalar(FName Name, float Value);

	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

private:
	struct FSample
	{
		FVector A;
		FVector B;
		double Time;
		bool bStripStart;
	};
	TArray<FSample> Samples;
	UPROPERTY()
	TObjectPtr<UMaterialInstanceDynamic> Mid;
	float Lifetime = 0.15f;
	bool bCut = true;
	bool bHasMesh = false;

	void Rebuild(double Now);
};
