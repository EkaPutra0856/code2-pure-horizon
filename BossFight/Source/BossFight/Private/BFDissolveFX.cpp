#include "BFDissolveFX.h"

#include "Components/InstancedStaticMeshComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

ABFDissolveFX::ABFDissolveFX()
{
	PrimaryActorTick.bCanEverTick = true;
	Motes = CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("Motes"));
	RootComponent = Motes;
	Motes->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Motes->SetCastShadow(false);
	Motes->SetGenerateOverlapEvents(false);
	Motes->bReceivesDecals = false;
	Motes->SetMobility(EComponentMobility::Movable);
	static ConstructorHelpers::FObjectFinder<UStaticMesh> Sphere(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
	if (Sphere.Succeeded())
	{
		Motes->SetStaticMesh(Sphere.Object);
	}
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Mat(TEXT("/Game/BossFight/FX/M_Mote.M_Mote"));
	if (Mat.Succeeded())
	{
		Motes->SetMaterial(0, Mat.Object);
	}
}

ABFDissolveFX* ABFDissolveFX::Spawn(UWorld* World, USkeletalMeshComponent* Source, float Duration, float Rate, const FLinearColor& Color)
{
	if (!World || !Source)
	{
		return nullptr;
	}
	FActorSpawnParameters Params;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	ABFDissolveFX* FX = World->SpawnActor<ABFDissolveFX>(ABFDissolveFX::StaticClass(), FTransform::Identity, Params);
	if (!FX)
	{
		return nullptr;
	}
	FX->Source = Source;
	FX->Duration = FMath::Max(0.1f, Duration);
	FX->Rate = Rate;
	if (UMaterialInterface* Base = FX->Motes->GetMaterial(0))
	{
		UMaterialInstanceDynamic* MID = UMaterialInstanceDynamic::Create(Base, FX);
		MID->SetVectorParameterValue(TEXT("Color"), Color);
		FX->Motes->SetMaterial(0, MID);
	}
	// Bones the motes come off (segment from each bone's parent to the bone): body, robe and weapon.
	for (int32 I = 0; I < Source->GetNumBones(); ++I)
	{
		const FName Bone = Source->GetBoneName(I);
		const FString Name = Bone.ToString().ToLower();
		const FName Parent = Source->GetParentBone(Bone);
		if (Parent.IsNone() || Name.StartsWith(TEXT("ik_")) || Name == TEXT("root") || Parent == TEXT("root"))
		{
			continue;
		}
		FX->Bones.Add(Bone);
		FX->Parents.Add(Parent);
	}
	FX->Pool.SetNum(MaxMotes);
	FX->Xforms.Init(FTransform(FQuat::Identity, FVector::ZeroVector, FVector::ZeroVector), MaxMotes);
	FX->Motes->AddInstances(FX->Xforms, false, true);
	return FX;
}

void ABFDissolveFX::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	const float Dt = FMath::Min(DeltaSeconds, 0.05f);
	Elapsed += Dt;

	// Emission swells in the middle of the dissolve.
	USkeletalMeshComponent* Mesh = Source.Get();
	if (Mesh && Elapsed < Duration && Bones.Num() > 0)
	{
		const float U = Elapsed / Duration;
		SpawnAcc += (110.f + 520.f * FMath::Sin(UE_PI * U)) * Rate * Dt;
		while (SpawnAcc >= 1.f)
		{
			SpawnAcc -= 1.f;
			const int32 B = FMath::RandRange(0, Bones.Num() - 1);
			const FVector A = Mesh->GetBoneLocation(Parents[B]);
			const FVector C = Mesh->GetBoneLocation(Bones[B]);
			FMote& M = Pool[Next];
			Next = (Next + 1) % MaxMotes;
			M.P = FMath::Lerp(A, C, FMath::FRand()) + FMath::VRand() * FMath::FRandRange(0.f, 12.f);
			M.V = FVector(0.f, 0.f, FMath::FRandRange(40.f, 150.f)) + FMath::VRand() * FMath::FRandRange(10.f, 60.f);
			M.Age = 0.f;
			M.Life = FMath::FRandRange(0.9f, 2.1f);
			M.Size = FMath::FRandRange(0.018f, 0.055f);
			M.Phase = FMath::FRandRange(0.f, UE_TWO_PI);
		}
	}

	bool bAny = false;
	for (int32 I = 0; I < MaxMotes; ++I)
	{
		FMote& M = Pool[I];
		if (M.Life <= 0.f)
		{
			Xforms[I].SetScale3D(FVector::ZeroVector);
			continue;
		}
		M.Age += Dt;
		if (M.Age >= M.Life)
		{
			M.Life = 0.f;
			Xforms[I].SetScale3D(FVector::ZeroVector);
			continue;
		}
		bAny = true;
		// Buoyant drift with a slow swirl, a little drag.
		const float W = M.Phase + M.Age * 2.6f;
		M.V += (FVector(FMath::Cos(W), FMath::Sin(W), 0.f) * 70.f + FVector(0.f, 0.f, 60.f)) * Dt;
		M.V *= 1.f - 0.5f * Dt;
		M.P += M.V * Dt;
		const float K = M.Age / M.Life;
		const float S = M.Size * FMath::Min(1.f, M.Age / 0.12f) * FMath::Pow(1.f - K, 0.7f);
		Xforms[I] = FTransform(FQuat::Identity, M.P, FVector(S));
	}
	Motes->BatchUpdateInstancesTransforms(0, Xforms, true, true, true);

	if (Elapsed >= Duration && !bAny)
	{
		Destroy();
	}
}
