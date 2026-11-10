#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "BFAfterImage.generated.h"

class UPoseableMeshComponent;
class UStaticMeshComponent;
class USkeletalMeshComponent;
class UMaterialInstanceDynamic;
class UMaterialInterface;

/** Frozen, fading ghost copy of a character pose (and its weapon), spawned during dashes. */
UCLASS()
class BOSSFIGHT_API ABFAfterImage : public AActor
{
	GENERATED_BODY()

public:
	ABFAfterImage();

	/** Copies Source's current pose and an optional weapon mesh, then fades over Lifetime seconds. */
	void Init(USkeletalMeshComponent* Source, UStaticMeshComponent* Weapon, UMaterialInterface* Material, const FLinearColor& Color, float Lifetime);

protected:
	virtual void Tick(float DeltaSeconds) override;

private:
	UPROPERTY(VisibleAnywhere)
	TObjectPtr<UPoseableMeshComponent> Body;

	UPROPERTY(VisibleAnywhere)
	TObjectPtr<UStaticMeshComponent> WeaponCopy;

	UPROPERTY(Transient)
	TObjectPtr<UMaterialInstanceDynamic> Mid;

	float Life = 0.4f;
	float Age = 0.f;
	float StartOpacity = 0.6f;
};
