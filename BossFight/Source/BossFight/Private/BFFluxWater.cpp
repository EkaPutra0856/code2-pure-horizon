#include "BFFluxWater.h"

#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Kismet/GameplayStatics.h"
#include "NiagaraComponent.h"
#include "NiagaraFunctionLibrary.h"
#include "NiagaraSystem.h"
#include "Particles/ParticleSystem.h"
#include "Particles/ParticleSystemComponent.h"
#include "TimerManager.h"
#include "UObject/StrongObjectPtr.h"

namespace
{
	// Loaded by path so the game module does not depend on the Fluid Flux content.
	const TCHAR* ContainerPath = TEXT("/Game/FluidFlux/Simulation/Modifiers/BP_FluxModifierContainerActor.BP_FluxModifierContainerActor_C");
	const TCHAR* ForcePath = TEXT("/Game/FluidFlux/Simulation/Modifiers/Components/BP_FluxModifierForceComponent.BP_FluxModifierForceComponent_C");
	const TCHAR* SourcePath = TEXT("/Game/FluidFlux/Simulation/Modifiers/Components/BP_FluxModifierSourceComponent.BP_FluxModifierSourceComponent_C");
	const TCHAR* InteractionPath = TEXT("/Game/FluidFlux/Interaction/Blueprints/BP_FluxInteractionComponent.BP_FluxInteractionComponent_C");
	const TCHAR* SplashSmallPath = TEXT("/Game/DreamscapeSeries/DreamscapeTower/Effects/P_WaterSplash.P_WaterSplash");
	const TCHAR* SplashLargePath = TEXT("/Game/DreamscapeSeries/DreamscapeTower/Effects/P_WaterSplash_Large.P_WaterSplash_Large");

	// Water level of the court channel above its bed (Scripts/45 fills it to z 8 over a bed at z 0).
	constexpr float WaterDepth = 8.f;
	// Impact bursts add no water by default any more (see Impact); -BFFluxVol=300 brings the old waves back.

	template <typename T>
	UClass* LoadFluxClass(const TCHAR* Path)
	{
		UClass* Cls = StaticLoadClass(T::StaticClass(), nullptr, Path, nullptr, LOAD_NoWarn | LOAD_Quiet);
		if (!Cls)
		{
			UE_LOG(LogTemp, Warning, TEXT("BFFLUX missing %s"), Path);
		}
		return Cls;
	}

	/** Sets a Blueprint variable from its text form (the Fluid Flux enums are user-defined: "NewEnumerator0"...). */
	bool SetText(UObject* Object, const TCHAR* Name, const FString& Value)
	{
		FProperty* Prop = Object->GetClass()->FindPropertyByName(Name);
		if (!Prop || !Prop->ImportText_InContainer(*Value, Object, Object, PPF_None))
		{
			UE_LOG(LogTemp, Warning, TEXT("BFFLUX could not set %s=%s on %s"), Name, *Value, *Object->GetName());
			return false;
		}
		return true;
	}

	/** Adds or removes an object in a Blueprint array variable (object references). */
	bool EditObjectArray(UObject* Owner, const TCHAR* Name, UObject* Value, bool bAdd)
	{
		FArrayProperty* Array = Owner ? CastField<FArrayProperty>(Owner->GetClass()->FindPropertyByName(Name)) : nullptr;
		FObjectPropertyBase* Inner = Array ? CastField<FObjectPropertyBase>(Array->Inner) : nullptr;
		if (!Inner)
		{
			UE_LOG(LogTemp, Warning, TEXT("BFFLUX no object array %s on %s"), Name, Owner ? *Owner->GetName() : TEXT("null"));
			return false;
		}
		FScriptArrayHelper Helper(Array, Array->ContainerPtrToValuePtr<void>(Owner));
		for (int32 I = Helper.Num() - 1; I >= 0; --I)
		{
			UObject* Existing = Inner->GetObjectPropertyValue(Helper.GetRawPtr(I));
			if (Existing == Value)
			{
				if (!bAdd)
				{
					Helper.RemoveValues(I, 1);
				}
				return true;
			}
		}
		if (bAdd)
		{
			const int32 Index = Helper.AddValue();
			Inner->SetObjectPropertyValue(Helper.GetRawPtr(Index), Value);
		}
		return true;
	}

	bool IsArena(const UWorld* World)
	{
		return World && World->IsGameWorld() && World->GetMapName().Contains(TEXT("L_Arena"));
	}

	AActor* FindDomain(UWorld* World)
	{
		static TWeakObjectPtr<AActor> Cached;
		if (Cached.IsValid() && Cached->GetWorld() == World)
		{
			return Cached.Get();
		}
		for (TActorIterator<AActor> It(World); It; ++It)
		{
			if (It->GetClass()->GetName().Contains(TEXT("FluxSimulationDomain")))
			{
				Cached = *It;
				return *It;
			}
		}
		return nullptr;
	}

	/**
	 * The simulation only reads modifiers from container actors listed in its ModifierActors array (each one hands over
	 * its ModifiderComponents), so runtime modifiers live in a container that is added to that list.
	 */
	AActor* SpawnContainer(UWorld* World, const FVector& At)
	{
		UClass* Cls = LoadFluxClass<AActor>(ContainerPath);
		AActor* Domain = FindDomain(World);
		if (!Cls || !Domain)
		{
			return nullptr;
		}
		FActorSpawnParameters Params;
		Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		AActor* Container = World->SpawnActor<AActor>(Cls, FTransform(At), Params);
		if (Container)
		{
			// Its editor billboard / bounds must not collide: attached to a capsule it would shove the character up.
			Container->SetActorEnableCollision(false);
			EditObjectArray(Domain, TEXT("ModifierActors"), Container, true);
		}
		return Container;
	}

	void DestroyContainer(AActor* Container)
	{
		if (!Container)
		{
			return;
		}
		if (AActor* Domain = FindDomain(Container->GetWorld()))
		{
			EditObjectArray(Domain, TEXT("ModifierActors"), Container, false);
		}
		Container->Destroy();
	}

	/** Creates a modifier component in a container; Setup sets its variables before it registers. */
	USceneComponent* AddModifier(AActor* Container, const TCHAR* Path, const FVector& Scale, TFunctionRef<void(USceneComponent*)> Setup)
	{
		UClass* Cls = LoadFluxClass<USceneComponent>(Path);
		if (!Cls || !Container)
		{
			return nullptr;
		}
		USceneComponent* Comp = NewObject<USceneComponent>(Container, Cls, NAME_None);
		Comp->SetupAttachment(Container->GetRootComponent());
		Comp->SetRelativeScale3D(Scale);
		Setup(Comp);
		Container->AddInstanceComponent(Comp);
		Comp->RegisterComponent();
		EditObjectArray(Container, TEXT("ModifiderComponents"), Comp, true);
		return Comp;
	}

	void SpawnSplash(UWorld* World, const FVector& At, float RadiusCm, float Strength)
	{
		// Strong pointers: a plain static UObject* is invisible to the garbage collector, which freed the effect
		// and left a dangling pointer (random crash in SpawnEmitterAtLocation).
		static TStrongObjectPtr<UObject> SmallRef(LoadObject<UObject>(nullptr, SplashSmallPath, nullptr, LOAD_NoWarn | LOAD_Quiet));
		static TStrongObjectPtr<UObject> LargeRef(LoadObject<UObject>(nullptr, SplashLargePath, nullptr, LOAD_NoWarn | LOAD_Quiet));
		UObject* Small = SmallRef.Get();
		UObject* Large = LargeRef.Get();
		UObject* Fx = Strength >= 1.2f && Large ? Large : Small;
		const FVector Scale(FMath::Clamp(RadiusCm / (Fx == Large ? 220.f : 70.f), 0.5f, 4.f));
		UFXSystemComponent* Comp = nullptr;
		if (UNiagaraSystem* Niagara = Cast<UNiagaraSystem>(Fx))
		{
			Comp = UNiagaraFunctionLibrary::SpawnSystemAtLocation(World, Niagara, At, FRotator::ZeroRotator, Scale);
		}
		else if (UParticleSystem* Cascade = Cast<UParticleSystem>(Fx))
		{
			Comp = UGameplayStatics::SpawnEmitterAtLocation(World, Cascade, At, FRotator::ZeroRotator, Scale);
		}
		if (!Comp)
		{
			return;
		}
		// These are the looping splashes of the falls: let them burst briefly, then stop emitting.
		TWeakObjectPtr<UFXSystemComponent> Weak(Comp);
		FTimerHandle Handle;
		World->GetTimerManager().SetTimer(Handle, [Weak]()
		{
			if (Weak.IsValid())
			{
				Weak->Deactivate();
			}
		}, 0.35f, false);
	}
}

void BFFluxWater::AddInteraction(ACharacter* Character, float FootprintCm)
{
	if (!Character || !IsArena(Character->GetWorld()))
	{
		return;
	}
	UCapsuleComponent* Capsule = Character->GetCapsuleComponent();
	// The interaction component finds the body (and its foot_l / foot_r / hand sockets) by this tag.
	Character->GetMesh()->ComponentTags.AddUnique(TEXT("FluxInteractionOwner"));
	// The body pushes the water: a force modifier in a container that rides along with the capsule.
	if (AActor* Container = SpawnContainer(Character->GetWorld(), Character->GetActorLocation()))
	{
		Container->AttachToComponent(Capsule, FAttachmentTransformRules::SnapToTargetNotIncludingScale);
		// Same proportions as the Fluid Flux demo character (40 x 40 x 90 for a 42 cm wide capsule).
		AddModifier(Container, ForcePath, FVector(FootprintCm, FootprintCm, Capsule->GetScaledCapsuleHalfHeight()), [](USceneComponent*) {});
	}
	if (UClass* Cls = LoadFluxClass<UActorComponent>(InteractionPath))
	{
		UActorComponent* Interaction = NewObject<UActorComponent>(Character, Cls, NAME_None);
		if (USceneComponent* Scene = Cast<USceneComponent>(Interaction))
		{
			Scene->SetupAttachment(Capsule);
		}
		// Off by default in Fluid Flux: feet and hands hitting the water spawn splashes (running, jumping, landing).
		SetText(Interaction, TEXT("CanSpawnSplashes"), TEXT("True"));
		Character->AddInstanceComponent(Interaction);
		Interaction->RegisterComponent();
	}
	UBFFluxLandingComponent* Landing = NewObject<UBFFluxLandingComponent>(Character);
	Landing->Footprint = FootprintCm;
	Character->AddInstanceComponent(Landing);
	Landing->RegisterComponent();
	UE_LOG(LogTemp, Display, TEXT("BFFLUX interaction on %s (footprint %.0f cm)"), *Character->GetName(), FootprintCm);
}

bool BFFluxWater::IsInRiver(const UWorld* World, const FVector& L)
{
	if (!IsArena(World) || L.X < -4700.f || L.X > 2545.f)
	{
		return false;
	}
	const float RiverY = 0.37f * L.X + 300.f * FMath::Sin(L.X / 1100.f);
	const float T = FMath::Clamp((FMath::Abs(L.X) - 1500.f) / 600.f, 0.f, 1.f);
	const float Width = FMath::Lerp(1350.f, 760.f, T);
	return FMath::Abs(L.Y - RiverY) < Width * 0.5f;
}

void BFFluxWater::Impact(UWorld* World, const FVector& Location, float RadiusCm, float Strength, bool bSplash)
{
	if (!IsInRiver(World, Location) || Strength <= 0.f)
	{
		return;
	}
	const FVector Surface(Location.X, Location.Y, WaterDepth);
	if (bSplash)
	{
		SpawnSplash(World, Surface, RadiusCm, Strength);
	}
	Ripple(World, Location, RadiusCm, Strength);
	// Test overrides: -BFFluxVol=<volume per strength> -BFFluxDur=<seconds>.
	// Default 0 (playtest feedback): every landing, slam and spell used to add water, and a busy fight
	// flooded the whole court. The court stays a shallow puddle; hits only splash and ripple it
	// (the splash above plus the characters' Fluid Flux interaction).
	float Vol = 0.f, Dur = 0.15f;
	FParse::Value(FCommandLine::Get(), TEXT("BFFluxVol="), Vol);
	FParse::Value(FCommandLine::Get(), TEXT("BFFluxDur="), Dur);
	if (Vol <= 0.f)
	{
		if (bSplash)
		{
			UE_LOG(LogTemp, Display, TEXT("BFFLUX impact (splash only) at %s r=%.0f strength=%.2f"), *Location.ToCompactString(), RadiusCm, Strength);
		}
		return;
	}
	// A short burst of added water: it spreads out from the hit as a wave and drains away downstream.
	AActor* Container = SpawnContainer(World, Surface);
	if (!Container)
	{
		return;
	}
	AddModifier(Container, SourcePath, FVector(RadiusCm * 2.f, RadiusCm * 2.f, 200.f), [&](USceneComponent* Source)
	{
		SetText(Source, TEXT("Mode"), TEXT("NewEnumerator0"));  // Add
		SetText(Source, TEXT("Shape"), TEXT("NewEnumerator1")); // Circle
		SetText(Source, TEXT("Volume"), FString::SanitizeFloat(Vol * Strength));
		SetText(Source, TEXT("Edge"), TEXT("0.5"));
		SetText(Source, TEXT("Duration"), FString::SanitizeFloat(Dur));
	});
	TWeakObjectPtr<AActor> Weak(Container);
	FTimerHandle Handle;
	World->GetTimerManager().SetTimer(Handle, [Weak]()
	{
		DestroyContainer(Weak.Get());
	}, FMath::Max(0.6f, Dur + 0.4f), false);
	if (bSplash)
	{
		UE_LOG(LogTemp, Display, TEXT("BFFLUX impact at %s r=%.0f strength=%.2f"), *Location.ToCompactString(), RadiusCm, Strength);
	}
}

namespace
{
	/** One short Fluid Flux source burst (Add mode, circle). Negative volume takes water out. */
	void SourceBurst(UWorld* World, const FVector& Surface, float RadiusCm, float Volume, float Duration)
	{
		AActor* Container = SpawnContainer(World, Surface);
		if (!Container)
		{
			return;
		}
		AddModifier(Container, SourcePath, FVector(RadiusCm * 2.f, RadiusCm * 2.f, 200.f), [&](USceneComponent* Source)
		{
			SetText(Source, TEXT("Mode"), TEXT("NewEnumerator0"));  // Add
			SetText(Source, TEXT("Shape"), TEXT("NewEnumerator1")); // Circle
			SetText(Source, TEXT("Volume"), FString::SanitizeFloat(Volume));
			SetText(Source, TEXT("Edge"), TEXT("0.5"));
			SetText(Source, TEXT("Duration"), FString::SanitizeFloat(Duration));
		});
		TWeakObjectPtr<AActor> Weak(Container);
		FTimerHandle Handle;
		World->GetTimerManager().SetTimer(Handle, [Weak]()
		{
			DestroyContainer(Weak.Get());
		}, Duration + 0.4f, false);
	}
}

void BFFluxWater::Ripple(UWorld* World, const FVector& Location, float RadiusCm, float Strength)
{
	if (!World || !IsInRiver(World, Location))
	{
		return;
	}
	// Real Fluid Flux waves (playtest: the painted rings looked fake). A small bump of water is added,
	// then the same amount is taken back at the same spot: the bump and the dip spread out as rings
	// on the simulated surface, and the court never gains water (no flooding).
	// Test override: -BFFluxRipVol=<volume per strength>.
	float PerStrength = 120.f;
	FParse::Value(FCommandLine::Get(), TEXT("BFFluxRipVol="), PerStrength);
	const float K = FMath::Clamp(Strength, 0.05f, 3.f);
	const float R = FMath::Max(RadiusCm, 25.f);
	const float Vol = PerStrength * K;
	const float Dur = 0.12f;
	const FVector Surface(Location.X, Location.Y, WaterDepth);
	SourceBurst(World, Surface, R, Vol, Dur);
	TWeakObjectPtr<UWorld> WeakWorld(World);
	FTimerHandle Handle;
	World->GetTimerManager().SetTimer(Handle, [WeakWorld, Surface, R, Vol, Dur]()
	{
		if (WeakWorld.IsValid())
		{
			SourceBurst(WeakWorld.Get(), Surface, R, -Vol, Dur);
		}
	}, Dur + 0.05f, false);
}

void BFFluxWater::Footstep(UWorld* World, const FVector& Foot, float FootprintCm, float Speed)
{
	if (!IsInRiver(World, Foot))
	{
		return;
	}
	const float Run = FMath::Clamp(Speed / 600.f, 0.3f, 1.4f);
	SpawnSplash(World, FVector(Foot.X, Foot.Y, WaterDepth), FootprintCm * 0.9f * Run, 0.f);
	Impact(World, Foot, FootprintCm * 1.4f, 0.08f * Run, false);
}

UBFFluxLandingComponent::UBFFluxLandingComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
}

void UBFFluxLandingComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
	const ACharacter* Character = Cast<ACharacter>(GetOwner());
	const UCharacterMovementComponent* Move = Character ? Character->GetCharacterMovement() : nullptr;
	if (!Move)
	{
		return;
	}
	const bool bFalling = Move->IsFalling();
	const float Vz = Move->Velocity.Z;
	const FVector Feet = Character->GetActorLocation() - FVector(0.f, 0.f, Character->GetCapsuleComponent()->GetScaledCapsuleHalfHeight());
	if (bFalling && !bWasFalling)
	{
		LowestVelocityZ = 0.f;
		if (Vz > 250.f)
		{
			// Push-off of a jump.
			BFFluxWater::Impact(GetWorld(), Feet, Footprint * 1.5f, 0.3f);
		}
	}
	if (bFalling)
	{
		LowestVelocityZ = FMath::Min(LowestVelocityZ, Vz);
	}
	else if (bWasFalling && LowestVelocityZ < -300.f)
	{
		BFFluxWater::Impact(GetWorld(), Feet, Footprint * 2.5f, FMath::Clamp(-LowestVelocityZ / 900.f, 0.4f, 1.6f));
	}
	else
	{
		// Running or walking: a spray at each footfall, one stride apart (longer strides for bigger bodies).
		const float Speed = Move->Velocity.Size2D();
		StepDistance = Speed > 40.f ? StepDistance + Speed * DeltaTime : 0.f;
		const float Stride = FMath::Max(70.f, Footprint * 2.2f);
		if (StepDistance >= Stride)
		{
			StepDistance -= Stride;
			bLeftFoot = !bLeftFoot;
			FVector Foot = Feet;
			const USkeletalMeshComponent* Mesh = Character->GetMesh();
			const FName Socket = bLeftFoot ? TEXT("foot_l") : TEXT("foot_r");
			if (Mesh && Mesh->DoesSocketExist(Socket))
			{
				Foot = Mesh->GetSocketLocation(Socket);
			}
			BFFluxWater::Footstep(GetWorld(), Foot, Footprint, Speed);
		}
	}
	bWasFalling = bFalling;
}
