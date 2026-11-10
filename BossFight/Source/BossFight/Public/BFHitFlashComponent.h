#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "BFHitFlashComponent.generated.h"

class UMaterialInstanceDynamic;
class UMeshComponent;

/**
 * Hit flash: puts an additive overlay material (M_HitFlash) on the owner's skeletal mesh and
 * fades it out in real time, so the flash also reads during the hitstop freeze.
 */
UCLASS()
class BOSSFIGHT_API UBFHitFlashComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UBFHitFlashComponent();

	void Flash(const FLinearColor& Color, float Duration, float Intensity = 1.f);

	/** Mesh that gets the overlay (default: the owning character's mesh). */
	void SetTarget(UMeshComponent* Mesh) { Target = Mesh; }

protected:
	virtual void BeginPlay() override;
	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

private:
	UPROPERTY(Transient)
	TObjectPtr<UMaterialInstanceDynamic> FlashMID;

	TWeakObjectPtr<UMeshComponent> Target;
	double FlashStart = 0.0;
	float FlashDuration = 0.f;
	float FlashIntensity = 1.f;
	bool bActive = false;
};
