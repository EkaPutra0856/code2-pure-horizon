#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "BFRingFX.generated.h"

class UStaticMeshComponent;
class UMaterialInterface;
class UMaterialInstanceDynamic;

/**
 * Camera-facing expanding ring that fades out. Used for the orange parry flash
 * and the red attack telegraph glint. Material: /Game/BossFight/FX/M_Ring (Color, Opacity).
 */
UCLASS()
class BOSSFIGHT_API ABFRingFX : public AActor
{
	GENERATED_BODY()

public:
	ABFRingFX();

	/** Spawns a ring that grows from StartSize to EndSize (cm) over Life seconds while fading. */
	static ABFRingFX* Spawn(UWorld* World, const FVector& Location, const FLinearColor& Color, float StartSize, float EndSize, float Life);
	/** Ring lying flat on the ground, growing at a constant rate (a shockwave front). */
	static ABFRingFX* SpawnGround(UWorld* World, const FVector& Location, const FLinearColor& Color, float StartSize, float EndSize, float Life);

protected:
	virtual void Tick(float DeltaSeconds) override;

private:
	void FaceCamera();

	UPROPERTY(VisibleAnywhere)
	TObjectPtr<UStaticMeshComponent> Plane;

	UPROPERTY()
	TObjectPtr<UMaterialInterface> RingMaterial;

	UPROPERTY(Transient)
	TObjectPtr<UMaterialInstanceDynamic> Mid;

	float StartSize = 30.f;
	float EndSize = 200.f;
	float Life = 0.25f;
	float Age = 0.f;
	bool bGround = false;
};
