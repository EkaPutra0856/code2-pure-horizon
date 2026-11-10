#include "BFAnimInstance.h"

#include "Components/SkeletalMeshComponent.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "KismetAnimationLibrary.h"

void UBFAnimInstance::NativeUpdateAnimation(float DeltaSeconds)
{
	Super::NativeUpdateAnimation(DeltaSeconds);

	const ACharacter* Character = Cast<ACharacter>(TryGetPawnOwner());
	if (!Character)
	{
		return;
	}

	const FVector Velocity = Character->GetVelocity();
	Speed = FVector(Velocity.X, Velocity.Y, 0.f).Size();
	Direction = bStrafing && Speed > 1.f ? UKismetAnimationLibrary::CalculateDirection(Velocity, Character->GetActorRotation()) : 0.f;

	if (const UCharacterMovementComponent* Movement = Character->GetCharacterMovement())
	{
		bIsInAir = Movement->IsFalling();
	}

	// Look-at: eased so the head leads a turn instead of snapping.
	{
		float WantYaw = 0.f;
		float WantPitch = 0.f;
		const AActor* Target = LookTarget.Get();
		if (Target)
		{
			const FVector Eye = Character->GetActorLocation() + FVector(0.f, 0.f, 70.f);
			const FVector To = Target->GetActorLocation() + FVector(0.f, 0.f, 40.f) - Eye;
			WantYaw = FMath::Clamp(FRotator::NormalizeAxis(To.Rotation().Yaw - Character->GetActorRotation().Yaw), -90.f, 90.f);
			WantPitch = FMath::Clamp(To.Rotation().Pitch, -35.f, 35.f);
		}
		const float Dt = FMath::Min(DeltaSeconds, 0.05f);
		AimYaw = FMath::FInterpTo(AimYaw, WantYaw, Dt, 6.f);
		AimPitch = FMath::FInterpTo(AimPitch, WantPitch, Dt, 5.f);
		AimAlpha = FMath::FInterpTo(AimAlpha, bLookEnabled && Target ? 1.f : 0.f, Dt, 5.f);
	}

	// Flinch spring: stiff and slightly underdamped, so the body snaps back with a small overshoot.
	constexpr float Stiffness = 170.f;
	constexpr float Damping = 11.f;
	const float Dt = FMath::Min(DeltaSeconds, 0.05f);
	if (!FlinchVec.IsNearlyZero(0.01f) || !FlinchVel.IsNearlyZero(0.01f))
	{
		FlinchVel += (-Stiffness * FlinchVec - Damping * FlinchVel) * Dt;
		FlinchVec += FlinchVel * Dt;
		const float Deg = FlinchVec.Size();
		const USkeletalMeshComponent* Mesh = GetSkelMeshComponent();
		if (Deg > 0.01f && Mesh)
		{
			const FVector AxisCS = Mesh->GetComponentTransform().InverseTransformVectorNoScale(FlinchVec / Deg);
			FlinchRot = FQuat(AxisCS, FMath::DegreesToRadians(Deg)).Rotator();
		}
		else
		{
			FlinchRot = FRotator::ZeroRotator;
		}
	}
	else
	{
		FlinchVec = FlinchVel = FVector::ZeroVector;
		FlinchRot = FRotator::ZeroRotator;
	}
}

void UBFAnimInstance::AddFlinch(const FVector& PushDir, float Strength)
{
	const FVector D = PushDir.GetSafeNormal2D();
	if (D.IsNearlyZero() || Strength <= 0.f)
	{
		return;
	}
	// Rotating about Up x D tips the chest toward D (away from the attacker).
	const FVector Axis = FVector::CrossProduct(FVector::UpVector, D);
	// Instant snap (visible during the hitstop freeze) plus a velocity kick that carries on after it.
	FlinchVec += Axis * 7.f * Strength;
	FlinchVel += Axis * 140.f * Strength;
	FlinchVec = FlinchVec.GetClampedToMaxSize(28.f);
}
