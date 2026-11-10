#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "BFFluxWater.generated.h"

class ACharacter;

/** Hooks characters into the Fluid Flux river (L_Arena): they push the simulated water and leave ripples and splashes. */
namespace BFFluxWater
{
	/**
	 * Adds Fluid Flux's force modifier (attached to the capsule, FootprintCm wide), its interaction component
	 * (ripple and splash sources on the mesh's foot and hand sockets, with splashes switched on) and a
	 * UBFFluxLandingComponent (a wave and a splash when the character lands in the river).
	 * Does nothing when Fluid Flux is not in the project.
	 */
	BOSSFIGHT_API void AddInteraction(ACharacter* Character, float FootprintCm);

	/** True when the point lies over L_Arena's river channel (same curve as Scripts/43 and 45). */
	BOSSFIGHT_API bool IsInRiver(const UWorld* World, const FVector& Location);

	/**
	 * A hit on the water: a splash effect plus a brief burst of added water that runs out as a wave.
	 * Strength 1 is a heavy landing; boss spells use 2-4. Does nothing away from the river.
	 */
	BOSSFIGHT_API void Impact(UWorld* World, const FVector& Location, float RadiusCm, float Strength, bool bSplash = true);

	/** Rings spreading on the water surface where something touched it (every Impact and Footstep adds them). */
	BOSSFIGHT_API void Ripple(UWorld* World, const FVector& Location, float RadiusCm, float Strength);

	/** One running footstep in the river: a small spray at the foot and a little wave. Does nothing away from it. */
	BOSSFIGHT_API void Footstep(UWorld* World, const FVector& FootLocation, float FootprintCm, float Speed);
}

/** Watches its character: a BFFluxWater::Impact on a jump or a hard landing, a BFFluxWater::Footstep per stride. */
UCLASS()
class BOSSFIGHT_API UBFFluxLandingComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UBFFluxLandingComponent();
	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

	float Footprint = 40.f;

private:
	bool bWasFalling = false;
	float LowestVelocityZ = 0.f;
	float StepDistance = 0.f;
	bool bLeftFoot = false;
};
