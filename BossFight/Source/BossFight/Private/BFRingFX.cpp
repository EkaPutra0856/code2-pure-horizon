#include "BFRingFX.h"

#include "BFFluxWater.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/StaticMeshComponent.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Misc/App.h"
#include "UObject/ConstructorHelpers.h"

ABFRingFX::ABFRingFX()
{
	PrimaryActorTick.bCanEverTick = true;
	// Real-time feel: the ring keeps expanding through hitstop.
	PrimaryActorTick.TickGroup = TG_PostUpdateWork;

	Plane = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Plane"));
	RootComponent = Plane;
	Plane->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Plane->SetCastShadow(false);

	static ConstructorHelpers::FObjectFinder<UStaticMesh> PlaneMesh(TEXT("/Engine/BasicShapes/Plane.Plane"));
	if (PlaneMesh.Succeeded())
	{
		Plane->SetStaticMesh(PlaneMesh.Object);
	}
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Mat(TEXT("/Game/BossFight/FX/M_Ring.M_Ring"));
	if (Mat.Succeeded())
	{
		RingMaterial = Mat.Object;
	}
}

ABFRingFX* ABFRingFX::Spawn(UWorld* World, const FVector& Location, const FLinearColor& Color, float InStartSize, float InEndSize, float InLife)
{
	if (!World)
	{
		return nullptr;
	}
	FActorSpawnParameters Params;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	ABFRingFX* Ring = World->SpawnActor<ABFRingFX>(ABFRingFX::StaticClass(), Location, FRotator::ZeroRotator, Params);
	if (!Ring)
	{
		return nullptr;
	}
	Ring->StartSize = InStartSize;
	Ring->EndSize = InEndSize;
	Ring->Life = FMath::Max(0.05f, InLife);
	if (Ring->RingMaterial)
	{
		Ring->Mid = UMaterialInstanceDynamic::Create(Ring->RingMaterial, Ring);
		Ring->Mid->SetVectorParameterValue(TEXT("Color"), Color);
		Ring->Mid->SetScalarParameterValue(TEXT("Opacity"), 1.f);
		Ring->Plane->SetMaterial(0, Ring->Mid);
	}
	Ring->FaceCamera();
	// Plane mesh is 100 cm across.
	Ring->SetActorScale3D(FVector(InStartSize / 100.f));
	return Ring;
}

ABFRingFX* ABFRingFX::SpawnGround(UWorld* World, const FVector& Location, const FLinearColor& Color, float InStartSize, float InEndSize, float InLife)
{
	// In the river the floor marks sat under the Fluid Flux surface (z 8) and were washed out: lift them just
	// above it (keeping their few-cm stacking order) and let them draw after the water.
	FVector At = Location;
	const bool bInWater = BFFluxWater::IsInRiver(World, Location) && Location.Z < 12.f;
	if (bInWater)
	{
		At.Z += 8.f;
	}
	// Floor warnings glow a little hotter than air flashes so they read on wet stone and water alike.
	FLinearColor Glow = Color * 1.8f;
	Glow.A = Color.A;
	ABFRingFX* Ring = Spawn(World, At, Glow, InStartSize, InEndSize, InLife);
	if (Ring)
	{
		Ring->bGround = true;
		Ring->SetActorRotation(FRotator::ZeroRotator); // plane normal up
		Ring->Plane->SetTranslucentSortPriority(10);
	}
	return Ring;
}

void ABFRingFX::FaceCamera()
{
	if (bGround)
	{
		return;
	}
	if (const APlayerCameraManager* Cam = UGameplayStatics::GetPlayerCameraManager(this, 0))
	{
		// The plane's normal is +Z; point it at the camera.
		const FVector ToCam = (Cam->GetCameraLocation() - GetActorLocation()).GetSafeNormal();
		SetActorRotation(FRotationMatrix::MakeFromZ(ToCam).Rotator());
	}
}

void ABFRingFX::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	// Undilated time so global slow-mo or hitstop does not stall the flash.
	Age += FApp::GetDeltaTime();
	const float T = FMath::Clamp(Age / Life, 0.f, 1.f);
	// Ground waves grow linearly so the ring is the exact wave front; flashes ease out.
	const float Ease = bGround ? T : 1.f - FMath::Square(1.f - T);
	SetActorScale3D(FVector(FMath::Lerp(StartSize, EndSize, Ease) / 100.f));
	FaceCamera();
	if (Mid)
	{
		Mid->SetScalarParameterValue(TEXT("Opacity"), bGround ? FMath::Min(1.f, (1.f - T) * 2.5f) : 1.f - T);
	}
	if (Age >= Life)
	{
		Destroy();
	}
}
