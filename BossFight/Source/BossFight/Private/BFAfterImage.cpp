#include "BFAfterImage.h"

#include "Components/PoseableMeshComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

ABFAfterImage::ABFAfterImage()
{
	PrimaryActorTick.bCanEverTick = true;

	Body = CreateDefaultSubobject<UPoseableMeshComponent>(TEXT("Body"));
	RootComponent = Body;
	Body->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Body->SetCastShadow(false);

	WeaponCopy = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("WeaponCopy"));
	WeaponCopy->SetupAttachment(Body);
	WeaponCopy->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	WeaponCopy->SetCastShadow(false);
}

void ABFAfterImage::Init(USkeletalMeshComponent* Source, UStaticMeshComponent* Weapon, UMaterialInterface* Material, const FLinearColor& Color, float Lifetime)
{
	Life = FMath::Max(0.05f, Lifetime);
	if (!Source)
	{
		return;
	}
	// -BFNoDashVFX: no ghost (footage of the bare animation for the code-breakdown video).
	static const bool bNoVfx = FParse::Param(FCommandLine::Get(), TEXT("BFNoDashVFX"));
	if (bNoVfx)
	{
		Destroy();
		return;
	}

	Body->SetSkinnedAssetAndUpdate(Source->GetSkinnedAsset());
	Body->SetWorldTransform(Source->GetComponentTransform());
	Body->CopyPoseFromSkeletalComponent(Source);

	if (Material)
	{
		Mid = UMaterialInstanceDynamic::Create(Material, this);
		Mid->SetVectorParameterValue(TEXT("Color"), Color);
		Mid->SetScalarParameterValue(TEXT("Opacity"), StartOpacity);
		for (int32 i = 0; i < Body->GetNumMaterials(); ++i)
		{
			Body->SetMaterial(i, Mid);
		}
	}

	if (Weapon && Weapon->GetStaticMesh())
	{
		WeaponCopy->SetStaticMesh(Weapon->GetStaticMesh());
		WeaponCopy->SetWorldTransform(Weapon->GetComponentTransform());
		if (Mid)
		{
			for (int32 i = 0; i < WeaponCopy->GetNumMaterials(); ++i)
			{
				WeaponCopy->SetMaterial(i, Mid);
			}
		}
	}
	else
	{
		WeaponCopy->SetVisibility(false);
	}
}

void ABFAfterImage::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	Age += DeltaSeconds;
	const float Alpha = FMath::Clamp(1.f - Age / Life, 0.f, 1.f);
	if (Mid)
	{
		Mid->SetScalarParameterValue(TEXT("Opacity"), StartOpacity * Alpha * Alpha);
	}
	if (Age >= Life)
	{
		Destroy();
	}
}
