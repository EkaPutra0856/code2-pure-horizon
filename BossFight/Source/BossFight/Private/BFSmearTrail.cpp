#include "BFSmearTrail.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

UBFSmearTrail::UBFSmearTrail(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.TickGroup = TG_PostUpdateWork;
	SetUsingAbsoluteLocation(true);
	SetUsingAbsoluteRotation(true);
	SetUsingAbsoluteScale(true);
	SetCollisionEnabled(ECollisionEnabled::NoCollision);
	SetCastShadow(false);
	bUseAsyncCooking = false;
}

void UBFSmearTrail::Setup(UMaterialInterface* Material, const FLinearColor& Color, float Intensity, float InLifetime)
{
	if (Material)
	{
		Mid = UMaterialInstanceDynamic::Create(Material, this);
	}
	SetLook(Color, Intensity, InLifetime);
	SetWorldTransform(FTransform::Identity);
}

void UBFSmearTrail::SetLook(const FLinearColor& Color, float Intensity, float InLifetime)
{
	Lifetime = FMath::Max(0.02f, InLifetime);
	if (Mid)
	{
		Mid->SetVectorParameterValue(TEXT("Color"), Color);
		Mid->SetScalarParameterValue(TEXT("Intensity"), Intensity);
	}
}

void UBFSmearTrail::SetScalar(FName Name, float Value)
{
	if (Mid)
	{
		Mid->SetScalarParameterValue(Name, Value);
	}
}

void UBFSmearTrail::AddSample(const FVector& A, const FVector& B)
{
	// -BFNoDashVFX: no ribbons (footage of the bare animation for the code-breakdown video).
	static const bool bNoVfx = FParse::Param(FCommandLine::Get(), TEXT("BFNoDashVFX"));
	if (bNoVfx)
	{
		return;
	}
	const double Now = GetWorld()->GetTimeSeconds();
	FSample S{ A, B, Now, bCut || Samples.Num() == 0 };
	bCut = false;
	// Fill a big jump between frames with curved in-betweens (Catmull-Rom through the last samples).
	if (!S.bStripStart && Samples.Num() >= 1)
	{
		const FSample& P1 = Samples.Last();
		const FSample& P0 = (Samples.Num() >= 2 && !P1.bStripStart) ? Samples[Samples.Num() - 2] : P1;
		const float Gap = FVector::Dist(P1.B, B);
		const int32 Extra = FMath::Clamp(FMath::FloorToInt(Gap / 10.f), 0, 10);
		for (int32 I = 1; I <= Extra; ++I)
		{
			const float T = float(I) / (Extra + 1);
			auto CR = [T](const FVector& Q0, const FVector& Q1, const FVector& Q2)
			{
				// Catmull-Rom with the next point mirrored (no future sample yet).
				const FVector Q3 = Q2 + (Q2 - Q1);
				const float T2 = T * T, T3 = T2 * T;
				return 0.5f * ((2.f * Q1) + (-Q0 + Q2) * T + (2.f * Q0 - 5.f * Q1 + 4.f * Q2 - Q3) * T2 + (-Q0 + 3.f * Q1 - 3.f * Q2 + Q3) * T3);
			};
			Samples.Add({ CR(P0.A, P1.A, A), CR(P0.B, P1.B, B), FMath::Lerp(P1.Time, Now, double(T)), false });
		}
	}
	Samples.Add(S);
}

void UBFSmearTrail::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
	const double Now = GetWorld()->GetTimeSeconds();
	Samples.RemoveAll([this, Now](const FSample& S) { return Now - S.Time > Lifetime; });
	// A strip whose first sample just expired starts at the next one.
	if (Samples.Num() > 0)
	{
		Samples[0].bStripStart = true;
	}
	Rebuild(Now);
}

void UBFSmearTrail::Rebuild(double Now)
{
	if (Samples.Num() < 2)
	{
		if (bHasMesh)
		{
			ClearMeshSection(0);
			bHasMesh = false;
		}
		return;
	}
	TArray<FVector> Verts;
	TArray<int32> Tris;
	TArray<FVector> Normals;
	TArray<FVector2D> UV0;
	TArray<FLinearColor> Colors;
	TArray<FProcMeshTangent> Tangents;
	Verts.Reserve(Samples.Num() * 2);
	for (int32 I = 0; I < Samples.Num(); ++I)
	{
		const FSample& S = Samples[I];
		const float Age = FMath::Clamp(float((Now - S.Time) / Lifetime), 0.f, 1.f);
		const int32 Base = Verts.Num();
		Verts.Add(S.A);
		Verts.Add(S.B);
		UV0.Add(FVector2D(Age, 0.f));
		UV0.Add(FVector2D(Age, 1.f));
		Colors.Add(FLinearColor::White);
		Colors.Add(FLinearColor::White);
		const FVector N = FVector::CrossProduct(S.B - S.A, I > 0 ? S.A - Samples[I - 1].A : FVector::UpVector).GetSafeNormal();
		Normals.Add(N);
		Normals.Add(N);
		if (I > 0 && !S.bStripStart)
		{
			// Quad between this pair and the previous one (two-sided material).
			Tris.Append({ Base - 2, Base - 1, Base, Base, Base - 1, Base + 1 });
		}
	}
	if (Tris.Num() == 0)
	{
		if (bHasMesh)
		{
			ClearMeshSection(0);
			bHasMesh = false;
		}
		return;
	}
	CreateMeshSection_LinearColor(0, Verts, Tris, Normals, UV0, Colors, Tangents, false);
	if (Mid)
	{
		SetMaterial(0, Mid);
	}
	bHasMesh = true;
}
