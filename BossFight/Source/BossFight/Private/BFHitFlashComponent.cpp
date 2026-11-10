#include "BFHitFlashComponent.h"

#include "Components/SkeletalMeshComponent.h"
#include "GameFramework/Character.h"
#include "Materials/MaterialInstanceDynamic.h"

UBFHitFlashComponent::UBFHitFlashComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.bStartWithTickEnabled = false;
}

void UBFHitFlashComponent::BeginPlay()
{
	Super::BeginPlay();
	// Loaded at runtime (not in the constructor) so the class does not depend on asset build order.
	if (UMaterialInterface* Base = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/BossFight/FX/M_HitFlash.M_HitFlash")))
	{
		FlashMID = UMaterialInstanceDynamic::Create(Base, this);
	}
	if (const ACharacter* Character = Cast<ACharacter>(GetOwner()))
	{
		Target = Character->GetMesh();
	}
}

void UBFHitFlashComponent::Flash(const FLinearColor& Color, float Duration, float Intensity)
{
	UMeshComponent* Mesh = Target.Get();
	if (!FlashMID || !Mesh)
	{
		return;
	}
	FlashMID->SetVectorParameterValue(TEXT("Color"), Color);
	FlashMID->SetScalarParameterValue(TEXT("Opacity"), Intensity);
	Mesh->SetOverlayMaterial(FlashMID);
	FlashStart = GetWorld()->GetRealTimeSeconds();
	FlashDuration = FMath::Max(Duration, 0.01f);
	FlashIntensity = Intensity;
	bActive = true;
	SetComponentTickEnabled(true);
}

void UBFHitFlashComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
	if (!bActive)
	{
		SetComponentTickEnabled(false);
		return;
	}
	const float T = static_cast<float>(GetWorld()->GetRealTimeSeconds() - FlashStart) / FlashDuration;
	if (T >= 1.f)
	{
		bActive = false;
		if (UMeshComponent* Mesh = Target.Get())
		{
			Mesh->SetOverlayMaterial(nullptr);
		}
		SetComponentTickEnabled(false);
		return;
	}
	// Hold full for the first fifth, then ease out.
	const float A = T < 0.2f ? 1.f : FMath::Square(1.f - (T - 0.2f) / 0.8f);
	FlashMID->SetScalarParameterValue(TEXT("Opacity"), FlashIntensity * A);
}
