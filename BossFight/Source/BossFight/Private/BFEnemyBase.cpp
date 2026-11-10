#include "BFEnemyBase.h"
#include "BFFluxWater.h"

#include "Animation/AnimInstance.h"
#include "Animation/AnimMontage.h"
#include "Animation/AnimSequence.h"
#include "BFAnimInstance.h"
#include "BFDissolveFX.h"
#include "Materials/MaterialInterface.h"
#include "BFHitFlashComponent.h"
#include "BFPlayerCharacter.h"
#include "BFRingFX.h"
#include "Components/CapsuleComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "EngineUtils.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/App.h"
#include "NiagaraComponent.h"
#include "NiagaraFunctionLibrary.h"
#include "NiagaraSystem.h"
#include "Sound/SoundBase.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	template <typename T>
	T* FindAsset(const TCHAR* Path)
	{
		ConstructorHelpers::FObjectFinder<T> Finder(Path);
		return Finder.Succeeded() ? Finder.Object : nullptr;
	}

	UAnimSequence* FindAnim(const TCHAR* Name)
	{
		const FString Path = FString::Printf(TEXT("/Game/InsaneAirCombo/Animation/%s.%s"), Name, Name);
		return FindAsset<UAnimSequence>(*Path);
	}

	FBFEnemyAttack MakeEnemyAttack(const TCHAR* Anim, float Rate, float Start, float End, float Range, float Damage, float Posture, bool bHeavy = false)
	{
		FBFEnemyAttack A;
		A.AnimPath = Anim;
		A.PlayRate = Rate;
		A.HitStart = Start;
		A.HitEnd = End;
		A.Range = Range;
		A.Damage = Damage;
		A.PostureDamage = Posture;
		A.bHeavy = bHeavy;
		return A;
	}

	/** The telegraph glint shows this long (real seconds) before a swing connects. */
	constexpr float TelegraphLead = 0.4f;
	constexpr float HeavyTelegraphLead = 0.65f;
}

ABFEnemyBase::ABFEnemyBase()
{
	PrimaryActorTick.bCanEverTick = true;

	GetCapsuleComponent()->InitCapsuleSize(42.f, 96.f);
	GetMesh()->SetRelativeLocationAndRotation(FVector(0.f, 0.f, -96.f), FRotator(0.f, -90.f, 0.f));
	// Blocks the player's sword sweeps (Pawn object type) through the capsule; mesh stays visual only.
	GetMesh()->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	// The follow camera passes through enemies: with the boss behind the player, the spring arm
	// used to hit his capsule and slam into the player's back, hiding the boss entirely.
	GetCapsuleComponent()->SetCollisionResponseToChannel(ECC_Camera, ECR_Ignore);

	if (USkeletalMesh* DummyMesh = FindAsset<USkeletalMesh>(TEXT("/Game/InsaneAirCombo/Animation/Skeleton/SK_Mannequin.SK_Mannequin")))
	{
		GetMesh()->SetSkeletalMesh(DummyMesh);
	}
	static ConstructorHelpers::FClassFinder<UAnimInstance> AnimFinder(TEXT("/Game/BossFight/Anim/ABP_Player.ABP_Player_C"));
	if (AnimFinder.Succeeded())
	{
		GetMesh()->SetAnimInstanceClass(AnimFinder.Class);
	}

	// Same sword and hand offset as the player.
	Weapon = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Weapon"));
	Weapon->SetupAttachment(GetMesh(), TEXT("hand_r"));
	Weapon->SetRelativeLocationAndRotation(FVector(0.715f, 8.327f, 0.512f), FRotator(-20.079f, -92.961f, -170.420f));
	Weapon->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	if (UStaticMesh* SwordMesh = FindAsset<UStaticMesh>(TEXT("/Game/InsaneAirCombo/mesh/Sword.Sword")))
	{
		Weapon->SetStaticMesh(SwordMesh);
	}

	HitFlash = CreateDefaultSubobject<UBFHitFlashComponent>(TEXT("HitFlash"));
	SlamVfx = FindAsset<UNiagaraSystem>(TEXT("/Game/SlashHitVFX/NS/NS_Hit_GroundCrack.NS_Hit_GroundCrack"));
	SlamSound = FindAsset<USoundBase>(TEXT("/Game/SlashHitVFX/__GenericSource/SFX/Sfx_Hit_Ground_Hammer_Cue.Sfx_Hit_Ground_Hammer_Cue"));
	EnemySwingSound = FindAsset<USoundBase>(TEXT("/Game/SlashHitVFX/__GenericSource/SFX/Sfx_Weapon_Sword01_Cue.Sfx_Weapon_Sword01_Cue"));
	HeavySwingSound = FindAsset<USoundBase>(TEXT("/Game/SlashHitVFX/__GenericSource/SFX/Sfx_Weapon_BigSword_Cue.Sfx_Weapon_BigSword_Cue"));
	ParryCueSound = FindAsset<USoundBase>(TEXT("/Game/SlashHitVFX/__GenericSource/SFX/Sfx_Hit_Block02_Cue.Sfx_Hit_Block02_Cue"));
	PerilousSound = FindAsset<USoundBase>(TEXT("/Game/SlashHitVFX/__GenericSource/SFX/Sfx_Hit_MagicStaff_Cue.Sfx_Hit_MagicStaff_Cue"));

	HitLeftAnim = FindAnim(TEXT("hit_light_L_body"));
	HitRightAnim = FindAnim(TEXT("hit_light_R_body"));
	HitFrontAnim = FindAnim(TEXT("hit_light_F_head"));
	KnockdownAnim = FindAnim(TEXT("hit_knockdown01"));
	HeavyKnockdownAnim = FindAnim(TEXT("hit_knockdown02"));
	// hit_down_up is a bounce on the floor (ends lying again), not a get-up; rise_1 starts from the
	// knockdown end pose (Scripts/25_rise_probe.py: 3.5 cm mean bone error) and ends standing.
	GetUpAnim = FindAnim(TEXT("rise_1"));
	DownLoopAnim = FindAnim(TEXT("hit_down_idle_up"));
	DeathAnim = FindAnim(TEXT("Dead_Dead1"));
	// Ends kneeling (pelvis ~57 cm down), held while posture is broken.
	BrokenAnim = FindAnim(TEXT("Dead_Dead3"));

	// Slowed so the windup reads; windows from Scripts/11_anim_analyze.py.
	Attacks = {
		MakeEnemyAttack(TEXT("combo01_1"), 0.8f, 0.22f, 0.45f, 260.f, 15.f, 20.f),
		MakeEnemyAttack(TEXT("combo02_2"), 0.8f, 0.25f, 0.68f, 280.f, 20.f, 25.f),
		MakeEnemyAttack(TEXT("Attack_Shockwave"), 1.0f, 0.53f, 0.70f, 300.f, 25.f, 35.f, true),
	};
	for (const FBFEnemyAttack& A : Attacks)
	{
		AttackAnims.Add(FindAnim(A.AnimPath));
		RecoverAnims.Add(A.RecoverPath ? FindAnim(A.RecoverPath) : nullptr);
	}

	GetCharacterMovement()->MaxWalkSpeed = 300.f;
	GetCharacterMovement()->BrakingDecelerationWalking = 1500.f;
	GetCharacterMovement()->GroundFriction = 6.f;
	GetCharacterMovement()->bOrientRotationToMovement = false;
	bUseControllerRotationYaw = false;
	// Default AIController, only so movement input is accepted (the dummy steers itself in Tick).
	AutoPossessAI = EAutoPossessAI::PlacedInWorldOrSpawned;
}

void ABFEnemyBase::BeginPlay()
{
	Super::BeginPlay();
	// Wade through the Fluid Flux river: push the water and leave ripples.
	BFFluxWater::AddInteraction(this, GetCapsuleComponent()->GetScaledCapsuleRadius() * 1.9f);
	MeshBaseLoc = GetMesh()->GetRelativeLocation();
	// Placed instances may carry an older saved collision setup; the camera must pass through.
	GetCapsuleComponent()->SetCollisionResponseToChannel(ECC_Camera, ECR_Ignore);
	// Test switch: -BFBoss makes placed dummies act as a boss (until Sevarog replaces them).
	if (FParse::Param(FCommandLine::Get(), TEXT("BFBoss")))
	{
		Rank = EBFEnemyRank::Boss;
		ClashPush = 0.4f;
		DisplayName = TEXT("Boss (test)");
	}
	Health = MaxHealth;
	Posture = 0.f;
	MoveSpeedBase = GetCharacterMovement()->MaxWalkSpeed;
	Phase1Speed = MoveSpeedBase;
	Phase1Cooldown = AttackCooldown;
	// Automated runs: repeatable attack choices and delays.
	FString Mode;
	if (FParse::Param(FCommandLine::Get(), TEXT("BFAutoTest")) || FParse::Value(FCommandLine::Get(), TEXT("BFAutoTest="), Mode))
	{
		int32 Seed = 1234;
		FParse::Value(FCommandLine::Get(), TEXT("BFSeed="), Seed);
		FMath::RandInit(Seed);
	}
	// Test switch: start in phase 2's threshold (-BFBossHP=0.55 etc.).
	float HpScale = 1.f;
	if (FParse::Value(FCommandLine::Get(), TEXT("BFBossHP="), HpScale) && IsBoss())
	{
		Health = MaxHealth * FMath::Clamp(HpScale, 0.01f, 1.f);
	}
	// Test switch: start with this much stance damage (-BFStance=100).
	if (MaxStance > 0.f && FParse::Value(FCommandLine::Get(), TEXT("BFStance="), Stance))
	{
		Stance = FMath::Clamp(Stance, 0.f, MaxStance - 1.f);
		LastStanceDamageTime = 1.0e9; // no regen until real damage lands
	}
	if (bCircleStrafe)
	{
		if (UBFAnimInstance* Anim = Cast<UBFAnimInstance>(GetMesh()->GetAnimInstance()))
		{
			Anim->bStrafing = true; // directional locomotion while circling / backing off
		}
	}
}

void ABFEnemyBase::SetAttacks(const TArray<FBFEnemyAttack>& InAttacks)
{
	// AnimPath here is a full object path; the attack's clip is loaded once (constructor only).
	Attacks = InAttacks;
	AttackAnims.Reset();
	RecoverAnims.Reset();
	for (const FBFEnemyAttack& A : Attacks)
	{
		ConstructorHelpers::FObjectFinder<UAnimSequence> Finder(A.AnimPath);
		AttackAnims.Add(Finder.Succeeded() ? Finder.Object : nullptr);
		UAnimSequence* Recover = nullptr;
		if (A.RecoverPath)
		{
			ConstructorHelpers::FObjectFinder<UAnimSequence> RecoverFinder(A.RecoverPath);
			Recover = RecoverFinder.Succeeded() ? RecoverFinder.Object : nullptr;
		}
		RecoverAnims.Add(Recover);
	}
}

ABFPlayerCharacter* ABFEnemyBase::GetPlayer() const
{
	return Cast<ABFPlayerCharacter>(UGameplayStatics::GetPlayerPawn(this, 0));
}

UAnimMontage* ABFEnemyBase::PlayAnim(UAnimSequence* Anim, float Rate, float BlendIn, float BlendOut, int32 LoopCount)
{
	UAnimInstance* AnimInstance = GetMesh()->GetAnimInstance();
	if (!Anim || !AnimInstance)
	{
		return nullptr;
	}
	// Inertial blends with a floor on their length: short linear crossfades read as skipped frames.
	const float In = FMath::Max(BlendIn, 0.12f);
	const float Out = BlendOut <= 0.f ? 0.f : FMath::Max(BlendOut, 0.3f);
	CurrentMontage = AnimInstance->PlaySlotAnimationAsDynamicMontage_WithBlendSettings(Anim, TEXT("DefaultSlot"), BFAnimBlend::Inert(In), BFAnimBlend::Inert(Out), Rate, LoopCount);
	bRecovering = false;
	bAttackRecovering = false;
	return CurrentMontage;
}

void ABFEnemyBase::ApplyHitstop(float Duration, float Dilation)
{
	const double Now = GetWorld()->GetRealTimeSeconds();
	if (HitstopEndTime <= Now)
	{
		HitstopStartTime = Now;
		HitstopMinDilation = Dilation;
	}
	HitstopMinDilation = FMath::Min(HitstopMinDilation, Dilation);
	HitstopEndTime = FMath::Max(HitstopEndTime, Now + Duration);
	CustomTimeDilation = HitstopMinDilation;
}

void ABFEnemyBase::EndHitstop()
{
	HitstopEndTime = 0.0;
	CustomTimeDilation = 1.f;
}

namespace BFWindup
{
	// Slowed stretch of a normal swing's wind-up, in seconds of clip time (scaled by the attack's
	// play rate) before HitStart, and the speed it plays at.
	constexpr float From = 0.55f;
	constexpr float To = 0.12f;
	constexpr float Rate = 0.5f;
}

float ABFEnemyBase::WindupRateAt(const FBFEnemyAttack& A, float Pos)
{
	if (A.bHeavy || A.Perilous != EBFPerilous::None || A.bGroundWave)
	{
		return 1.f;
	}
	const float SlowA = A.HitStart - BFWindup::From * A.PlayRate;
	const float SlowB = A.HitStart - BFWindup::To * A.PlayRate;
	return Pos >= SlowA && Pos < SlowB ? BFWindup::Rate : 1.f;
}

float ABFEnemyBase::WindupTimeLeft(const FBFEnemyAttack& A, float Pos)
{
	if (Pos >= A.HitStart)
	{
		return 0.f;
	}
	const float R = A.PlayRate;
	if (A.bHeavy || A.Perilous != EBFPerilous::None || A.bGroundWave)
	{
		return (A.HitStart - Pos) / R;
	}
	const float SlowA = A.HitStart - BFWindup::From * R;
	const float SlowB = A.HitStart - BFWindup::To * R;
	float T = 0.f;
	float P = Pos;
	if (P < SlowA)
	{
		T += (SlowA - P) / R;
		P = SlowA;
	}
	if (P < SlowB)
	{
		T += (SlowB - P) / (R * BFWindup::Rate);
		P = SlowB;
	}
	return T + (A.HitStart - P) / R;
}

float ABFEnemyBase::GetTimeToHit() const
{
	const ABFPlayerCharacter* Player = GetPlayer();
	if (Player && bLineActive && !bLineResolved)
	{
		// Fire line on its way: when its front passes the player (only if they stand on its path).
		const FVector Rel = (Player->GetActorLocation() - LineOrigin) * FVector(1.f, 1.f, 0.f);
		const float Along = FVector::DotProduct(Rel, LineDir);
		const float Lateral = FMath::Abs(FVector::CrossProduct(LineDir, Rel).Z);
		if (Along >= -40.f && Along <= LineLength + 40.f && Lateral < FireLineHalfWidth + 40.f)
		{
			return FMath::Max(0.f, (Along - 40.f - LineFront) / FireLineSpeed);
		}
	}
	if (Player && bCircleActive && FVector::Dist2D(Player->GetActorLocation(), CircleCenter) <= CircleRadius + 60.f)
	{
		return FMath::Max(0.f, CircleTimeLeft);
	}
	if (State == EBFEnemyState::Attacking && IsMagicAttack(CurrentAttack))
	{
		return -1.f; // the cast itself hurts nobody; its effects report above once released
	}
	if (bWaveActive && !bWaveResolved)
	{
		// Ground wave rolling out: when its front reaches the player.
		const float D = Player ? FVector::Dist2D(Player->GetActorLocation(), WaveOrigin) : 0.f;
		return FMath::Max(0.f, (D - 30.f - WaveRadius) / WaveSpeed);
	}
	if (State != EBFEnemyState::Attacking || !Attacks.IsValidIndex(CurrentAttack) || bSwingResolved)
	{
		return -1.f;
	}
	const UAnimInstance* AnimInstance = GetMesh()->GetAnimInstance();
	if (!AnimInstance || !CurrentMontage)
	{
		return -1.f;
	}
	const FBFEnemyAttack& A = Attacks[CurrentAttack];
	const float Pos = AnimInstance->Montage_GetPosition(CurrentMontage);
	// A delayed wind-up adds its (remaining) hold.
	float T = WindupTimeLeft(A, Pos) + (bHolding ? HoldLeft : 0.f) + (bHoldPending ? HoldTime : 0.f);
	if (A.bGroundWave && Player)
	{
		// The plant only starts the wave; it still has to roll out to the player.
		const FVector Plant = GetActorLocation() + GetActorForwardVector() * 100.f;
		T += FMath::Max(0.f, FVector::Dist2D(Player->GetActorLocation(), Plant) - 70.f) / A.WaveSpeed;
	}
	return T;
}

EBFPerilous ABFEnemyBase::GetPerilous() const
{
	if (bWaveActive && !bWaveResolved)
	{
		return EBFPerilous::Sweep;
	}
	return State == EBFEnemyState::Attacking && !bSwingResolved ? ActivePerilous : EBFPerilous::None;
}

float ABFEnemyBase::GetPerilousAge() const
{
	return float(GetWorld()->GetRealTimeSeconds() - PerilousStartTime);
}

bool ABFEnemyBase::IsPunishable() const
{
	if (State == EBFEnemyState::Normal && bAttackRecovering)
	{
		return true; // Return2Idle recovery
	}
	if (State != EBFEnemyState::Attacking || !Attacks.IsValidIndex(CurrentAttack))
	{
		return false;
	}
	const FBFEnemyAttack& A = Attacks[CurrentAttack];
	if (A.ChainNext != INDEX_NONE)
	{
		return false;
	}
	if (bWhiffed)
	{
		return true; // dodged / missed perilous move, or the hammer planted for a ground wave
	}
	const UAnimInstance* AnimInstance = GetMesh()->GetAnimInstance();
	const float Pos = AnimInstance && CurrentMontage ? AnimInstance->Montage_GetPosition(CurrentMontage) : 0.f;
	return A.bHeavy && Pos > A.HitEnd + 0.1f; // slam follow-through
}

float ABFEnemyBase::GetHalfHeight() const
{
	return GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
}

float ABFEnemyBase::GetLockHeight() const
{
	return GetHalfHeight() * 0.3f;
}

FVector ABFEnemyBase::GetWeaponTip() const
{
	if (!WeaponTipBone.IsNone())
	{
		return GetMesh()->GetSocketLocation(WeaponTipBone);
	}
	if (Weapon && Weapon->GetStaticMesh())
	{
		const FBox Box = Weapon->GetStaticMesh()->GetBoundingBox();
		const FVector Extent = Box.GetExtent();
		const int32 Axis = Extent.X >= Extent.Y && Extent.X >= Extent.Z ? 0 : (Extent.Y >= Extent.Z ? 1 : 2);
		FVector Tip = Box.GetCenter();
		Tip[Axis] = Box.Max[Axis];
		return Weapon->GetComponentTransform().TransformPosition(Tip);
	}
	return GetMesh()->GetSocketLocation(TEXT("hand_r"));
}

void ABFEnemyBase::AddPosture(float Amount)
{
	if (State == EBFEnemyState::Dead || State == EBFEnemyState::Broken || Amount <= 0.f)
	{
		return;
	}
	Posture = FMath::Min(MaxPosture, Posture + Amount);
	LastPostureDamageTime = GetWorld()->GetRealTimeSeconds();
	if (Posture >= MaxPosture)
	{
		BreakPosture();
	}
}

void ABFEnemyBase::BreakPosture(bool bFromStance)
{
	State = EBFEnemyState::Broken;
	StateTime = 0.f;
	bBrokenLooping = false;
	bStanceBroken = bFromStance;
	bTurning = false;
	bBackstepping = false;
	bHolding = false;
	bHoldPending = false;
	ActivePerilous = EBFPerilous::None;
	PlayAnim(BrokenAnim, 1.2f, 0.08f, 0.f);
	if (CurrentMontage)
	{
		HoldLastFrame();
	}
	UE_LOG(LogTemp, Display, TEXT("BFTEST enemy %s broken"), bFromStance ? TEXT("stance") : TEXT("posture"));
}

void ABFEnemyBase::AddStance(float Amount)
{
	if (MaxStance <= 0.f || Amount <= 0.f || bMagicAir || State == EBFEnemyState::Dead || State == EBFEnemyState::Broken || State == EBFEnemyState::Transition)
	{
		return;
	}
	Stance = FMath::Min(MaxStance, Stance + Amount);
	LastStanceDamageTime = GetWorld()->GetRealTimeSeconds();
	if (Stance < MaxStance)
	{
		return;
	}
	// Stance broken: the heavy blows add up and he buckles to his knees, open to a critical hit.
	// A gold-white burst and a deep crack mark it (separate from the posture bar the player sees).
	const FVector Chest = GetActorLocation() + FVector(0.f, 0.f, GetHalfHeight() * 0.4f);
	ABFRingFX::Spawn(GetWorld(), Chest, FLinearColor(1.f, 0.85f, 0.4f), 60.f, 520.f, 0.5f);
	ABFRingFX::Spawn(GetWorld(), Chest, FLinearColor::White, 30.f, 260.f, 0.3f);
	if (HitFlash)
	{
		HitFlash->Flash(FLinearColor(1.f, 0.85f, 0.45f), 0.4f, 0.8f);
	}
	if (SlamSound)
	{
		UGameplayStatics::PlaySoundAtLocation(this, SlamSound, Chest, 1.2f, 1.4f);
	}
	if (ParryCueSound)
	{
		UGameplayStatics::PlaySoundAtLocation(this, ParryCueSound, Chest, 1.f, 0.6f);
	}
	BreakPosture(true);
}

void ABFEnemyBase::StartAttack(int32 Index)
{
	if (!AttackAnims.IsValidIndex(Index) || !AttackAnims[Index])
	{
		return;
	}
	const FBFEnemyAttack& A = Attacks[Index];
	// A chained swing starts in the previous one's end pose: no snap-turn, short blend.
	const bool bChained = State == EBFEnemyState::Attacking;
	bTurning = false;
	bBackstepping = false;
	if (!bChained && !TurnRightAnim)
	{
		// No step-turn clips (dummy): snap to face. Bosses turn on the spot first (Normal state) and
		// track during the wind-up, so they never pivot in one frame.
		TurnTowardPlayer(1.f, 100000.f);
	}
	if (A.Magic != EBFMagic::None)
	{
		// Spell: rise out of reach, charge, release, float back down (TickMagicCast). With flight clips
		// he gathers power while lifting off; otherwise the cast clip itself is held.
		if (!PlayAnim(HasMagicFlightClips() ? MagicRiseAnim.Get() : AttackAnims[Index].Get(), HasMagicFlightClips() ? 1.f : A.PlayRate, A.BlendIn, A.BlendOut))
		{
			return;
		}
		MagicStartXY = GetActorLocation();
		MagicDriftDir = FVector::ZeroVector;
		if (const ABFPlayerCharacter* Player = GetPlayer())
		{
			MagicDriftDir = (GetActorLocation() - Player->GetActorLocation()).GetSafeNormal2D();
		}
		State = EBFEnemyState::Attacking;
		CurrentAttack = Index;
		++AttackCount;
		bHolding = false;
		bHoldPending = false;
		bSwingResolved = true;
		bTelegraphed = true;
		ActivePerilous = EBFPerilous::None;
		bAttackRecovering = false;
		bMagicAir = true;
		bMagicLocked = false;
		MagicStage = 0;
		MagicT = 0.f;
		MagicBaseZ = GetActorLocation().Z;
		LastMagicTime = GetWorld()->GetRealTimeSeconds();
		GetCharacterMovement()->StopMovementImmediately();
		GetCharacterMovement()->SetMovementMode(MOVE_Flying);
		ABFRingFX::SpawnGround(GetWorld(), GetActorLocation() - FVector(0.f, 0.f, GetHalfHeight() - 4.f), BFCombat::BossMagicColor(), 60.f, 420.f, 0.5f);
		UE_LOG(LogTemp, Display, TEXT("BFTEST boss magic cast kind=%s phase=%d attack=%d"), A.Magic == EBFMagic::FireLine ? TEXT("fireline") : A.Magic == EBFMagic::Orb ? TEXT("orb") : TEXT("circle"), Phase, AttackCount);
		return;
	}
	bAttackRecovering = false;
	if (!PlayAnim(AttackAnims[Index], A.PlayRate, bChained ? 0.08f : A.BlendIn, A.BlendOut))
	{
		return;
	}
	if (A.ChainNext != INDEX_NONE || (RecoverAnims.IsValidIndex(Index) && RecoverAnims[Index]))
	{
		// Something continues from the last frame: do not let it blend back to idle first.
		HoldLastFrame();
	}
	// Delayed wind-up: more likely (and longer) when it was picked against roll spam.
	bHolding = false;
	HoldLeft = 0.f;
	// Automated runs: -BFHoldChance=1 forces every delayed wind-up (0 disables them).
	static const float HoldChanceOverride = []()
	{
		float V = -1.f;
		FParse::Value(FCommandLine::Get(), TEXT("BFHoldChance="), V);
		return V;
	}();
	const float HoldChance = HoldChanceOverride >= 0.f ? HoldChanceOverride
		: (bRollSpamPick && A.bAntiRoll ? FMath::Max(A.HoldChance, 0.85f) : A.HoldChance);
	bHoldPending = A.HoldAt >= 0.f && FMath::FRand() < HoldChance;
	HoldTime = bHoldPending ? FMath::FRandRange(A.HoldMin, A.HoldMax) * (bRollSpamPick ? 1.25f : 1.f) : 0.f;
	bRollSpamPick = false;
	WarpUsed = 0.f;
	bWhiffed = false;
	if (!bChained)
	{
		ActivePerilous = A.Perilous;
		if (A.Perilous != EBFPerilous::None)
		{
			PerilousTelegraph(A.Perilous);
		}
	}
	State = EBFEnemyState::Attacking;
	CurrentAttack = Index;
	bTelegraphed = false;
	bHeavyPulsePending = false;
	ParryCueTime = -100.0;
	bSwingResolved = false;
	bSwingSoundPlayed = false;
	bSlamDone = false;
	++AttackCount;
}

void ABFEnemyBase::TurnTowardPlayer(float DeltaSeconds, float DegPerSec)
{
	if (bDebugFreezeFacing)
	{
		return;
	}
	const ABFPlayerCharacter* Player = GetPlayer();
	if (!Player)
	{
		return;
	}
	const FVector To = (Player->GetActorLocation() - GetActorLocation()).GetSafeNormal2D();
	if (To.IsNearlyZero())
	{
		return;
	}
	const FRotator Target(0.f, To.Rotation().Yaw, 0.f);
	SetActorRotation(FMath::RInterpConstantTo(GetActorRotation(), Target, DeltaSeconds, DegPerSec));
}

void ABFEnemyBase::TickAttack(float DeltaSeconds)
{
	if (IsMagicAttack(CurrentAttack))
	{
		TickMagicCast(DeltaSeconds);
		return;
	}
	UAnimInstance* AnimInstance = GetMesh()->GetAnimInstance();
	if (!AnimInstance || !CurrentMontage || !AnimInstance->Montage_IsPlaying(CurrentMontage))
	{
		FinishAttack();
		return;
	}

	const FBFEnemyAttack& A = Attacks[CurrentAttack];
	const float Pos = AnimInstance->Montage_GetPosition(CurrentMontage);
	if (Pos >= CurrentMontage->GetPlayLength() - 0.02f && (A.ChainNext != INDEX_NONE || (RecoverAnims.IsValidIndex(CurrentAttack) && RecoverAnims[CurrentAttack])))
	{
		// Held on the last frame: hand over to the next swing or the recovery clip.
		FinishAttack();
		return;
	}

	// Delayed wind-up (Elden Ring style): the raised weapon creeps for a random beat while the body
	// keeps tracking, so an early roll is spent before the swing comes.
	if (bHoldPending && Pos >= A.HoldAt)
	{
		bHoldPending = false;
		bHolding = true;
		HoldLeft = HoldTime;
		AnimInstance->Montage_SetPlayRate(CurrentMontage, A.PlayRate * 0.06f);
		UE_LOG(LogTemp, Display, TEXT("BFTEST enemy delayed windup %.2fs attack=%d"), HoldTime, AttackCount);
	}
	if (bHolding)
	{
		HoldLeft -= DeltaSeconds;
		if (HoldLeft <= 0.f)
		{
			bHolding = false;
			AnimInstance->Montage_SetPlayRate(CurrentMontage, A.PlayRate);
		}
	}

	// Normal swings (playtest feedback: their window was too short to read): the last stretch of the
	// wind-up plays slowed, a tense beat with the weapon raised, then the swing comes at full speed.
	if (!bHolding)
	{
		const float Want = A.PlayRate * WindupRateAt(A, Pos);
		if (!FMath::IsNearlyEqual(AnimInstance->Montage_GetPlayRate(CurrentMontage), Want, 0.001f))
		{
			AnimInstance->Montage_SetPlayRate(CurrentMontage, Want);
		}
	}

	// Track the player during the windup (and the hold), then commit to the swing.
	if (Pos < A.HitStart - 0.1f * A.PlayRate || bHolding)
	{
		TurnTowardPlayer(DeltaSeconds, A.Perilous == EBFPerilous::Thrust ? 420.f : 300.f);
	}

	// Motion warp: the clips swing in place, so slide toward the player during the windup and stop
	// just inside reach. Bounded by WarpDist, so backing off early still gets out.
	if (A.WarpDist > 0.f && !bSwingResolved && Pos >= A.WarpFrom && (Pos < A.HitStart || bHolding) && WarpUsed < A.WarpDist)
	{
		if (const ABFPlayerCharacter* Player = GetPlayer())
		{
			const FVector To = (Player->GetActorLocation() - GetActorLocation()) * FVector(1.f, 1.f, 0.f);
			const float Excess = To.Size() - A.WarpStop;
			if (Excess > 1.f)
			{
				const float TimeLeft = FMath::Max((A.HitStart - Pos) / A.PlayRate + (bHolding ? HoldLeft : 0.f), DeltaSeconds);
				const float Step = FMath::Min3(Excess * FMath::Min(1.f, DeltaSeconds / TimeLeft), A.WarpSpeed * DeltaSeconds, A.WarpDist - WarpUsed);
				AddActorWorldOffset(To.GetSafeNormal() * Step, true);
				WarpUsed += Step;
			}
		}
	}

	// Telegraph: small red glint for normal swings; a big burning-orange double pulse, earlier,
	// for heavy attacks (parry or perfect-dodge it to start the strength clash). Perilous moves
	// flash their own colour (their first warning fired when the move started). After any hold.
	// A heavy's first pulse is only "a big one is coming" and fires on schedule even before a hold;
	// its "now" cue (below) waits for the hold.
	const bool bPerilous = A.Perilous != EBFPerilous::None;
	const float Lead = A.bHeavy || bPerilous ? HeavyTelegraphLead : TelegraphLead;
	if (!bTelegraphed && (A.bHeavy || (!bHolding && !bHoldPending)) && Pos >= A.HitStart - Lead * A.PlayRate)
	{
		bTelegraphed = true;
		// Action-game reading (Wuthering Waves / ZZZ style): a flash on the weapon before every swing.
		if (bPerilous)
		{
			ABFRingFX::Spawn(GetWorld(), GetWeaponTip(), BFCombat::PerilousColor(A.Perilous), 20.f, 170.f, 0.4f);
			ABFRingFX::Spawn(GetWorld(), GetWeaponTip(), FLinearColor(1.f, 1.f, 1.f), 10.f, 70.f, 0.25f);
		}
		else if (A.bHeavy)
		{
			ABFRingFX::Spawn(GetWorld(), GetWeaponTip(), FLinearColor(1.f, 0.3f, 0.f), 20.f, 150.f, 0.45f);
			ABFRingFX::Spawn(GetWorld(), GetWeaponTip(), FLinearColor(1.f, 0.75f, 0.2f), 10.f, 80.f, 0.3f);
			bHeavyPulsePending = true;
			UE_LOG(LogTemp, Display, TEXT("BFTEST enemy heavy telegraph attack=%d"), AttackCount);
		}
		else
		{
			// Normal swing (playtest feedback: too easy to miss): a bigger red flash than before, held a
			// little longer, during the slowed end of the wind-up.
			ABFRingFX::Spawn(GetWorld(), GetWeaponTip(), FLinearColor(1.f, 0.05f, 0.02f), 14.f, 115.f, 0.4f);
			ABFRingFX::Spawn(GetWorld(), GetWeaponTip(), FLinearColor(1.f, 0.6f, 0.5f), 6.f, 50.f, 0.25f);
		}
	}
	// "Parry / roll now" cue: a bright white-gold flash and a metallic ring a fixed reaction time
	// before the slam connects (after any delayed hold). Guard (F) or roll (Shift) on it to clash.
	if (bHeavyPulsePending && !bHolding && !bHoldPending && Pos >= A.HitStart - BFCombat::ParryCueLead * A.PlayRate)
	{
		bHeavyPulsePending = false;
		ParryCueTime = GetWorld()->GetRealTimeSeconds();
		const FVector Tip = GetWeaponTip();
		ABFRingFX::Spawn(GetWorld(), Tip, FLinearColor(1.f, 0.95f, 0.75f), 30.f, 230.f, 0.3f);
		ABFRingFX::Spawn(GetWorld(), Tip, FLinearColor(1.f, 0.65f, 0.1f), 12.f, 120.f, 0.22f);
		if (ParryCueSound)
		{
			UGameplayStatics::PlaySoundAtLocation(this, ParryCueSound, Tip, 0.8f, 1.6f);
		}
		UE_LOG(LogTemp, Display, TEXT("BFTEST enemy parry cue attack=%d time_to_hit=%.2f"), AttackCount, GetTimeToHit());
	}

	// Whoosh just before the blade arrives (heavier sound for big attacks).
	if (!bSwingSoundPlayed && !bHolding && !bHoldPending && Pos >= A.HitStart - 0.12f * A.PlayRate)
	{
		bSwingSoundPlayed = true;
		if (USoundBase* Whoosh = (A.bHeavy || bPerilous) && HeavySwingSound ? HeavySwingSound.Get() : EnemySwingSound.Get())
		{
			UGameplayStatics::PlaySoundAtLocation(this, Whoosh, GetWeaponTip(), A.bHeavy ? 1.2f : 0.9f, A.bHeavy ? 0.8f : FMath::FRandRange(0.95f, 1.05f));
		}
	}

	if (!bSwingResolved && !bHolding && Pos >= A.HitStart)
	{
		if (A.bGroundWave)
		{
			// Sweep: the hammer plants and a wave rolls out along the floor (jump it).
			bSwingResolved = true;
			StartGroundWave(A);
		}
		else if (Pos <= A.HitEnd)
		{
			ABFPlayerCharacter* Player = GetPlayer();
			if (Player)
			{
				const FVector To = Player->GetActorLocation() - GetActorLocation();
				const float Dist = To.Size2D();
				const float CosAngle = FVector::DotProduct(To.GetSafeNormal2D(), GetActorForwardVector());
				// A swing answered with a well-timed roll still counts (perfect dodge; heavy / grab -> clash)
				// even though the long slide carries the body out of its narrow reach.
				const bool bDodgeReach = Player->IsDashDodging() || (A.Perilous == EBFPerilous::Grab && Player->IsGrabDodging());
				const float Reach = A.Range + (bDodgeReach ? 260.f : 0.f);
				const float HalfAngle = bDodgeReach ? FMath::Max(A.HalfAngleDeg, 80.f) : A.HalfAngleDeg;
				if (Dist <= Reach && CosAngle >= FMath::Cos(FMath::DegreesToRadians(HalfAngle)))
				{
					bSwingResolved = true;
					FBFHitInfo Hit;
					Hit.Damage = A.Damage;
					Hit.PostureDamage = A.PostureDamage;
					Hit.bHeavy = A.bHeavy;
					Hit.Perilous = A.Perilous;
					Hit.ImpactPoint = Player->GetActorLocation() + FVector(0.f, 0.f, 40.f);
					Hit.Instigator = this;
					const EBFHitResult Result = Player->ResolveEnemyHit(Hit, this);
					if (bPerilous && Result == EBFHitResult::Dodged)
					{
						bWhiffed = true; // the long follow-through of a dodged perilous move is an opening
					}
				}
			}
		}
		else if (bPerilous)
		{
			// Perilous move that reached nobody: the follow-through is an opening too.
			bSwingResolved = true;
			bWhiffed = true;
		}
	}

	// Heavy attacks slam the ground: when the weapon head reaches the floor, or at the end of the window.
	if (A.bHeavy && !bSlamDone && Pos >= A.HitStart)
	{
		const ABFPlayerCharacter* Player = GetPlayer();
		const float FloorZ = GetActorLocation().Z - GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
		if (Player && Player->IsStruggling())
		{
			bSlamDone = true; // the clash cinematic owns the screen; no slam
		}
		else if (GetWeaponTip().Z - FloorZ < 45.f || Pos >= A.HitEnd)
		{
			bSlamDone = true;
			DoSlamImpact();
		}
	}
}

void ABFEnemyBase::PerilousTelegraph(EBFPerilous Kind)
{
	// Sekiro-style danger cue, coloured per kind: a burst around the body, the body glowing in that
	// colour, a sharp chime; the HUD shows the matching icon above the boss while GetPerilous() says so.
	PerilousStartTime = GetWorld()->GetRealTimeSeconds();
	const FLinearColor C = BFCombat::PerilousColor(Kind);
	const FVector Chest = GetActorLocation() + FVector(0.f, 0.f, GetHalfHeight() * 0.5f);
	ABFRingFX::Spawn(GetWorld(), Chest, C, 40.f, 360.f, 0.55f);
	ABFRingFX::Spawn(GetWorld(), Chest, FLinearColor::White, 20.f, 150.f, 0.3f);
	if (Kind == EBFPerilous::Sweep)
	{
		// Low threat: a ring on the floor too.
		ABFRingFX::SpawnGround(GetWorld(), GetActorLocation() - FVector(0.f, 0.f, GetHalfHeight() - 4.f), C, 80.f, 520.f, 0.6f);
	}
	if (HitFlash)
	{
		HitFlash->Flash(C, 0.55f, 0.7f);
	}
	if (PerilousSound)
	{
		UGameplayStatics::PlaySoundAtLocation(this, PerilousSound, Chest, 1.3f, 0.7f);
	}
	static const TCHAR* Names[] = { TEXT("none"), TEXT("grab"), TEXT("sweep"), TEXT("thrust") };
	UE_LOG(LogTemp, Display, TEXT("BFTEST enemy perilous %s attack=%d"), Names[int32(Kind)], AttackCount + 1);
}

void ABFEnemyBase::StartGroundWave(const FBFEnemyAttack& A)
{
	const float FloorZ = GetActorLocation().Z - GetHalfHeight();
	FVector Plant = GetWeaponTip();
	Plant.Z = FloorZ + 3.f;
	WaveOrigin = Plant;
	WaveRadius = 40.f;
	WaveMaxRadius = A.WaveRange;
	WaveSpeed = A.WaveSpeed;
	bWaveActive = true;
	bWaveResolved = false;
	bWhiffed = true; // hammer planted in the floor: an opening for whoever cleared the wave
	WaveHit = FBFHitInfo();
	WaveHit.Damage = A.Damage;
	WaveHit.PostureDamage = A.PostureDamage;
	WaveHit.Perilous = EBFPerilous::Sweep;
	WaveHit.Instigator = this;
	DoSlamImpact();
	// The wave front: two flat rings (colour plus a white core) growing at the wave's speed.
	const float Life = (WaveMaxRadius - WaveRadius) / WaveSpeed;
	ABFRingFX::SpawnGround(GetWorld(), WaveOrigin, BFCombat::PerilousColor(EBFPerilous::Sweep), WaveRadius * 2.f, WaveMaxRadius * 2.f, Life);
	ABFRingFX::SpawnGround(GetWorld(), WaveOrigin + FVector(0.f, 0.f, 1.f), FLinearColor(1.f, 0.95f, 0.8f), WaveRadius * 2.f - 30.f, WaveMaxRadius * 2.f - 30.f, Life);
	UE_LOG(LogTemp, Display, TEXT("BFTEST enemy ground wave at %s"), *WaveOrigin.ToCompactString());
}

void ABFEnemyBase::TickGroundWave(float RealDelta)
{
	if (!bWaveActive)
	{
		return;
	}
	// Real time, like its ring: the front on screen is the front that hits.
	WaveRadius += WaveSpeed * RealDelta;
	if (!bWaveResolved)
	{
		if (ABFPlayerCharacter* Player = GetPlayer())
		{
			const float D = FVector::Dist2D(Player->GetActorLocation(), WaveOrigin);
			if (D > WaveMaxRadius + 30.f)
			{
				bWaveResolved = WaveRadius >= WaveMaxRadius;
			}
			else if (WaveRadius >= D - 30.f)
			{
				bWaveResolved = true;
				WaveHit.ImpactPoint = Player->GetActorLocation() - FVector(0.f, 0.f, 60.f);
				const EBFHitResult Result = Player->ResolveEnemyHit(WaveHit, this);
				UE_LOG(LogTemp, Display, TEXT("BFTEST enemy wave reached player dist=%.0f result=%d"), D, int32(Result));
			}
		}
	}
	if (WaveRadius >= WaveMaxRadius)
	{
		bWaveActive = false;
	}
}

void ABFEnemyBase::FinishAttack()
{
	const FBFEnemyAttack* A = Attacks.IsValidIndex(CurrentAttack) ? &Attacks[CurrentAttack] : nullptr;
	bHolding = false;
	bHoldPending = false;
	if (A && Attacks.IsValidIndex(A->ChainNext))
	{
		StartAttack(A->ChainNext);
		return;
	}
	State = EBFEnemyState::Normal;
	CooldownLeft = AttackCooldown;
	ActivePerilous = EBFPerilous::None;
	UAnimSequence* Recover = RecoverAnims.IsValidIndex(CurrentAttack) ? RecoverAnims[CurrentAttack].Get() : nullptr;
	if (A && Recover && PlayAnim(Recover, A->RecoverRate, 0.15f, 0.45f))
	{
		if (UAnimInstance* AnimInstance = GetMesh()->GetAnimInstance())
		{
			AnimInstance->Montage_SetPosition(CurrentMontage, A->RecoverStart);
		}
		bAttackRecovering = true;
	}
}

int32 ABFEnemyBase::PickStarterAttack()
{
	TArray<int32> Starters;
	for (int32 i = 0; i < Attacks.Num(); ++i)
	{
		if (!Attacks[i].bChainOnly)
		{
			Starters.Add(i);
		}
	}
	return Starters.Num() > 0 ? Starters[StarterCount++ % Starters.Num()] : 0;
}

int32 ABFEnemyBase::PickAttack(float Dist)
{
	// Weighted pick over what reaches from here in this phase. Repeats are rare; against a player who
	// keeps rolling, delayed / tracking moves (bAntiRoll) get much likelier.
	const ABFPlayerCharacter* Player = GetPlayer();
	const bool bRollSpam = Player && Player->GetRecentDashCount(2.5f) >= 2;

	// Automated runs: -BFForceAttacks=6,7,8 plays that sequence in order (looping), ignoring MinDist.
	static TArray<int32> Forced;
	static int32 ForcedNext = 0;
	static bool bForcedParsed = false;
	if (!bForcedParsed)
	{
		bForcedParsed = true;
		FString List;
		if (FParse::Value(FCommandLine::Get(), TEXT("BFForceAttacks="), List, false))
		{
			TArray<FString> Parts;
			List.ParseIntoArray(Parts, TEXT(","));
			for (const FString& Part : Parts)
			{
				Forced.Add(FCString::Atoi(*Part));
			}
		}
	}
	if (Forced.Num() > 0)
	{
		const int32 Want = Forced[ForcedNext % Forced.Num()];
		if (!Attacks.IsValidIndex(Want) || !AttackAnims.IsValidIndex(Want) || !AttackAnims[Want])
		{
			++ForcedNext;
			return INDEX_NONE;
		}
		const float MaxDist = Attacks[Want].MaxDist > 0.f ? Attacks[Want].MaxDist : EngageRange;
		if (Dist > MaxDist)
		{
			return INDEX_NONE;
		}
		++ForcedNext;
		LastStarter = Want;
		bRollSpamPick = bRollSpam;
		UE_LOG(LogTemp, Display, TEXT("BFTEST enemy pick attack=%d dist=%.0f phase=%d forced"), Want, Dist, Phase);
		return Want;
	}

	if (!bWeightedAttackPick)
	{
		// Training dummy: its starters in a fixed order, from its engage range.
		return Dist <= EngageRange ? PickStarterAttack() : INDEX_NONE;
	}

	TArray<TPair<int32, float>> Candidates;
	float Total = 0.f;
	for (int32 i = 0; i < Attacks.Num(); ++i)
	{
		const FBFEnemyAttack& A = Attacks[i];
		const float MaxDist = A.MaxDist > 0.f ? A.MaxDist : EngageRange;
		if (A.bChainOnly || !AttackAnims.IsValidIndex(i) || !AttackAnims[i] || Phase < A.MinPhase || Phase > A.MaxPhase || Dist < A.MinDist || Dist > MaxDist)
		{
			continue;
		}
		if (A.Magic != EBFMagic::None && GetWorld()->GetRealTimeSeconds() - LastMagicTime < (Phase >= 2 ? MagicCooldown2 : MagicCooldown1))
		{
			continue; // one spell at a time, with a breather between them
		}
		float W = A.Weight * (Phase >= 2 ? A.Phase2Weight : 1.f);
		if (bPreferRanged && (A.Magic != EBFMagic::None || A.MinDist >= 200.f))
		{
			W *= 4.f; // just hopped back: answer from range
		}
		if (i == LastStarter)
		{
			W *= 0.3f;
		}
		if (bRollSpam && A.bAntiRoll)
		{
			W *= 3.f;
		}
		if (W > 0.f)
		{
			Candidates.Add({ i, W });
			Total += W;
		}
	}
	bPreferRanged = false;
	if (Candidates.Num() == 0)
	{
		return INDEX_NONE;
	}
	float R = FMath::FRand() * Total;
	int32 Pick = Candidates.Last().Key;
	for (const TPair<int32, float>& C : Candidates)
	{
		R -= C.Value;
		if (R <= 0.f)
		{
			Pick = C.Key;
			break;
		}
	}
	LastStarter = Pick;
	bRollSpamPick = bRollSpam;
	UE_LOG(LogTemp, Display, TEXT("BFTEST enemy pick attack=%d dist=%.0f phase=%d rollspam=%d"), Pick, Dist, Phase, bRollSpam ? 1 : 0);
	return Pick;
}

void ABFEnemyBase::OnStomped(AActor* By, float Damage, float PostureDamage)
{
	if (State == EBFEnemyState::Dead || State == EBFEnemyState::Transition || bMagicAir)
	{
		return;
	}
	AddStance(30.f);
	if (State == EBFEnemyState::Broken && bStanceBroken)
	{
		Health = FMath::Max(0.f, Health - Damage * BFCombat::TestDamageToEnemy);
		UE_LOG(LogTemp, Display, TEXT("BFTEST enemy stomped hp=%.0f posture=%.0f state=%d"), Health, Posture, int32(State));
		return;
	}
	const FVector Away = By ? -(By->GetActorLocation() - GetActorLocation()).GetSafeNormal2D() : -GetActorForwardVector();
	Health = FMath::Max(0.f, Health - Damage * BFCombat::TestDamageToEnemy);
	PlayImpactFeedback(Away, BFCombat::GetImpactProfile(EBFHitWeight::Finisher).Flinch, 0.25f);
	bHolding = false;
	bHoldPending = false;
	ActivePerilous = EBFPerilous::None;
	AddPosture(PostureDamage);
	if (Health <= 0.f)
	{
		State = EBFEnemyState::Dead;
		StateTime = 0.f;
		PlayAnim(DeathAnim, 1.f, 0.05f, 0.f);
		HoldLastFrame();
	}
	else if (State != EBFEnemyState::Broken)
	{
		// Even super armor buckles under a stomp on the head.
		State = EBFEnemyState::Stagger;
		StateTime = 0.f;
		PlayAnim(HitFrontAnim, HitReactRate * 0.7f, 0.05f, 0.25f);
		CooldownLeft = AttackCooldown + 0.4f;
	}
	UE_LOG(LogTemp, Display, TEXT("BFTEST enemy stomped hp=%.0f posture=%.0f state=%d"), Health, Posture, int32(State));
}

void ABFEnemyBase::OnMikiri(AActor* By)
{
	if (State != EBFEnemyState::Attacking)
	{
		return;
	}
	// Stepped on the thrust: thrown off balance, big posture hit.
	State = EBFEnemyState::Stagger;
	StateTime = 0.f;
	bHolding = false;
	bHoldPending = false;
	ActivePerilous = EBFPerilous::None;
	PlayAnim(HitFrontAnim, ParryRecoilRate * 0.8f, 0.04f, 0.25f);
	if (By)
	{
		LaunchCharacter(-(By->GetActorLocation() - GetActorLocation()).GetSafeNormal2D() * ParryRecoilLaunch * 1.5f, true, false);
		PlayImpactFeedback(-(By->GetActorLocation() - GetActorLocation()).GetSafeNormal2D(), 2.f, 0.25f);
	}
	CooldownLeft = AttackCooldown + 0.3f;
	AddPosture(45.f);
	UE_LOG(LogTemp, Display, TEXT("BFTEST enemy mikiri countered posture=%.0f"), Posture);
}

void ABFEnemyBase::OnSiphonDrain(float Amount)
{
	if (State == EBFEnemyState::Dead)
	{
		return;
	}
	Health = FMath::Min(MaxHealth, Health + Amount);
	ABFRingFX::Spawn(GetWorld(), GetActorLocation() + FVector(0.f, 0.f, GetHalfHeight() * 0.5f), BFCombat::BossMagicColor(), 30.f, 200.f, 0.35f);
	if (HitFlash)
	{
		HitFlash->Flash(FLinearColor(0.5f, 1.f, 0.4f), 0.25f, 0.5f);
	}
}

void ABFEnemyBase::StartPhaseTransition()
{
	// Below half health: a short untouchable roar / leap with a shockwave, the player's camera cuts to
	// a low shot of the boss (mini-cutscene), then phase 2: faster, more grabs, new moves.
	Phase = 2;
	State = EBFEnemyState::Transition;
	StateTime = 0.f;
	bTransitionImpactDone = false;
	bHolding = false;
	bHoldPending = false;
	ActivePerilous = EBFPerilous::None;
	EndHitstop();
	Posture = 0.f;
	TransitionLen = 2.f;
	if (TransitionAnim && PlayAnim(TransitionAnim, TransitionRate, 0.35f, 0.4f))
	{
		if (UAnimInstance* AnimInstance = GetMesh()->GetAnimInstance())
		{
			AnimInstance->Montage_SetPosition(CurrentMontage, TransitionStart);
		}
		TransitionLen = (TransitionAnim->GetPlayLength() - TransitionStart) / TransitionRate;
	}
	if (ABFPlayerCharacter* Player = GetPlayer())
	{
		Player->StartBossCinematic(this, TransitionLen + TransitionHold + 0.15f, (TransitionImpact - TransitionStart) / TransitionRate);
	}
	UE_LOG(LogTemp, Display, TEXT("BFTEST boss phase2 transition hp=%.0f len=%.2f"), Health, TransitionLen);
}

void ABFEnemyBase::TickTransition()
{
	// Opening shot of the cutscene: he turns to face the lens and roars straight into it.
	if (!bTransitionImpactDone)
	{
		ABFPlayerCharacter* Player = GetPlayer();
		if (Player && Player->IsCinematic())
		{
			const FVector ToCam = (Player->GetCinematicCamLocation() - GetActorLocation()).GetSafeNormal2D();
			if (!ToCam.IsNearlyZero())
			{
				const FRotator Want(0.f, ToCam.Rotation().Yaw, 0.f);
				SetActorRotation(FMath::RInterpTo(GetActorRotation(), Want, GetWorld()->GetDeltaSeconds(), 9.f));
			}
		}
	}
	if (!bTransitionImpactDone && StateTime >= (TransitionImpact - TransitionStart) / TransitionRate)
	{
		bTransitionImpactDone = true;
		const FVector Feet = GetActorLocation() - FVector(0.f, 0.f, GetHalfHeight() - 3.f);
		if (SlamVfx)
		{
			UNiagaraFunctionLibrary::SpawnSystemAtLocation(GetWorld(), SlamVfx, Feet, FRotator(0.f, GetActorRotation().Yaw, 0.f), FVector(SlamScale * 1.4f));
		}
		if (SlamSound)
		{
			UGameplayStatics::PlaySoundAtLocation(this, SlamSound, Feet, 1.6f, 0.6f);
		}
		const FLinearColor Soul = BFCombat::BossMagicColor();
		ABFRingFX::SpawnGround(GetWorld(), Feet, Soul, 100.f, 1600.f, 0.55f);
		ABFRingFX::SpawnGround(GetWorld(), Feet + FVector(0.f, 0.f, 1.f), BFCombat::BossMagicPale(), 60.f, 1500.f, 0.55f);
		ABFRingFX::Spawn(GetWorld(), GetActorLocation(), Soul, 80.f, 700.f, 0.5f);
		if (HitFlash)
		{
			HitFlash->Flash(Soul, 0.8f, 1.f);
		}
		if (ABFPlayerCharacter* Player = GetPlayer())
		{
			// The roar throws the player back (animation only, no damage).
			Player->StartRoarKnockback(GetActorLocation());
			Player->AddCameraShake(16.f, 0.55f, FVector::UpVector, 6.f);
		}
		UE_LOG(LogTemp, Display, TEXT("BFTEST boss phase2 roar"));
	}
	if (StateTime >= TransitionLen + TransitionHold)
	{
		State = EBFEnemyState::Normal;
		StateTime = 0.f;
		CooldownLeft = 0.6f;
		AttackCooldown = Phase2Cooldown;
		MoveSpeedBase *= Phase2SpeedScale;
		GetCharacterMovement()->MaxWalkSpeed = MoveSpeedBase;
		UE_LOG(LogTemp, Display, TEXT("BFTEST boss phase2 begin cooldown=%.2f speed=%.0f"), AttackCooldown, MoveSpeedBase);
	}
}

void ABFEnemyBase::StartTravel()
{
	bTraveling = true;
	bTravelLooping = false;
	TravelTime = 0.f;
	PlayAnim(TravelStartAnim, 1.3f, 0.25f, 0.2f);
	HoldLastFrame();
	GetCharacterMovement()->MaxWalkSpeed = TravelSpeed;
	ABFRingFX::Spawn(GetWorld(), GetActorLocation(), FLinearColor(0.4f, 1.f, 0.45f), 40.f, 300.f, 0.35f);
	UE_LOG(LogTemp, Display, TEXT("BFTEST boss travel start"));
}

void ABFEnemyBase::TickTravel(float DeltaSeconds)
{
	TravelTime += DeltaSeconds;
	TurnTowardPlayer(DeltaSeconds, 360.f);
	if (!bTravelLooping && (!TravelStartAnim || TravelTime >= TravelStartAnim->GetPlayLength() / 1.3f - 0.15f))
	{
		bTravelLooping = true;
		PlayAnim(TravelLoopAnim, 1.f, 0.2f, 0.25f, 1000);
	}
	const ABFPlayerCharacter* Player = GetPlayer();
	if (!Player)
	{
		EndTravel();
		return;
	}
	const FVector To = (Player->GetActorLocation() - GetActorLocation()).GetSafeNormal2D();
	const float Dist = FVector::Dist2D(Player->GetActorLocation(), GetActorLocation());
	if (TravelTime > 0.3f)
	{
		AddMovementInput(To, 1.f);
	}
	if (Dist <= TravelArriveDist || TravelTime > 4.f)
	{
		EndTravel();
		if (Dist <= 700.f)
		{
			LastStarter = TravelArriveAttack;
			StartAttack(TravelArriveAttack);
		}
		UE_LOG(LogTemp, Display, TEXT("BFTEST boss travel arrive dist=%.0f"), Dist);
	}
}

void ABFEnemyBase::EndTravel()
{
	bTraveling = false;
	GetCharacterMovement()->MaxWalkSpeed = MoveSpeedBase;
}

void ABFEnemyBase::DoSlamImpact()
{
	const float FloorZ = GetActorLocation().Z - GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
	FVector Ground = GetWeaponTip();
	Ground.Z = FloorZ + 2.f;
	if (SlamVfx)
	{
		UNiagaraFunctionLibrary::SpawnSystemAtLocation(GetWorld(), SlamVfx, Ground, FRotator(0.f, GetActorRotation().Yaw, 0.f), FVector(SlamScale));
	}
	if (SlamSound)
	{
		UGameplayStatics::PlaySoundAtLocation(this, SlamSound, Ground, 1.3f, 0.85f);
	}
	ABFRingFX::Spawn(GetWorld(), Ground + FVector(0.f, 0.f, 5.f), FLinearColor(1.f, 0.45f, 0.1f), 30.f, 260.f * SlamScale, 0.35f);
	BFFluxWater::Impact(GetWorld(), Ground, 160.f * SlamScale, 1.5f);
	if (ABFPlayerCharacter* Player = GetPlayer())
	{
		// The ground jolt reaches the player even on a miss, weaker with distance.
		const float Dist = FVector::Dist2D(Player->GetActorLocation(), Ground);
		const float Near = FMath::Clamp(1.f - Dist / 1600.f, 0.3f, 1.f);
		Player->AddCameraShake(13.f * Near * SlamScale / 1.2f, 0.4f, FVector::UpVector, 0.f);
	}
	UE_LOG(LogTemp, Display, TEXT("BFTEST enemy slam impact at %s"), *Ground.ToCompactString());
}

float ABFEnemyBase::DebugStartAttack(int32 Index, float Yaw)
{
	bAutoAttack = false;
	bDebugFreezeFacing = true;
	StartAttack(Index);
	SetActorRotation(FRotator(0.f, Yaw, 0.f));
	CustomTimeDilation = 0.5f;
	if (IsMagicAttack(Index))
	{
		// Rise, charge, throw, glide down (TickMagicCast).
		return MagicRiseTime + Attacks[Index].ChargeTime + 1.6f;
	}
	// Whole attack: chained swings plus the recovery clip.
	float Total = 0.f;
	for (int32 i = Index, Guard = 0; Attacks.IsValidIndex(i) && Guard < 8; i = Attacks[i].ChainNext, ++Guard)
	{
		Total += AttackAnims[i] ? AttackAnims[i]->GetPlayLength() / Attacks[i].PlayRate : 0.f;
		if (Attacks[i].ChainNext == INDEX_NONE && RecoverAnims.IsValidIndex(i) && RecoverAnims[i])
		{
			Total += (RecoverAnims[i]->GetPlayLength() - Attacks[i].RecoverStart) / Attacks[i].RecoverRate;
		}
	}
	return Total;
}

float ABFEnemyBase::DebugPlayAnim(UAnimSequence* Anim, float Rate)
{
	bAutoAttack = false;
	State = EBFEnemyState::Stagger; // keeps its facing while the clip plays
	if (!PlayAnim(Anim, Rate, 0.05f, 0.f) || !CurrentMontage)
	{
		return 0.f;
	}
	HoldLastFrame();
	return Anim->GetPlayLength() / Rate;
}

void ABFEnemyBase::HoldLastFrame()
{
	// The auto-blend-out switch lives on the montage *instance* (copied from the asset when it starts
	// playing), so setting it on the asset afterwards did nothing: the clip blended back to the
	// standing idle at its end - the body "stood up" for a moment before the get-up.
	if (!CurrentMontage)
	{
		return;
	}
	CurrentMontage->bEnableAutoBlendOut = false;
	if (UAnimInstance* AnimInstance = GetMesh()->GetAnimInstance())
	{
		if (FAnimMontageInstance* Instance = AnimInstance->GetActiveInstanceForMontage(CurrentMontage))
		{
			Instance->bEnableAutoBlendOut = false;
		}
	}
}

float ABFEnemyBase::DebugGetMontagePosition() const
{
	const UAnimInstance* AnimInstance = GetMesh()->GetAnimInstance();
	return AnimInstance && CurrentMontage ? AnimInstance->Montage_GetPosition(CurrentMontage) : -1.f;
}

void ABFEnemyBase::PlayImpactFeedback(const FVector& PushDir, float FlinchStrength, float FlashTime)
{
	if (UBFAnimInstance* Anim = Cast<UBFAnimInstance>(GetMesh()->GetAnimInstance()))
	{
		Anim->AddFlinch(PushDir, FlinchStrength * ImpactScale);
	}
	if (HitFlash)
	{
		HitFlash->Flash(FLinearColor(1.f, 0.95f, 0.85f), FlashTime * 0.8f, 0.2f);
	}
}

bool ABFEnemyBase::ReceiveHit(const FBFHitInfo& Hit)
{
	bLastHitArmored = false;
	bLastHitPunish = false;
	if (State == EBFEnemyState::Dead || State == EBFEnemyState::Transition || bMagicAir)
	{
		return false; // floating out of reach while casting: the blade passes under him
	}
	RecentHitTimes.Add(GetWorld()->GetRealTimeSeconds());
	// Struck while standing in the river: the body jolts the water.
	BFFluxWater::Impact(GetWorld(), GetActorLocation() - FVector(0.f, 0.f, GetHalfHeight()), GetCapsuleComponent()->GetScaledCapsuleRadius() * 1.6f, Hit.Weight == EBFHitWeight::Heavy ? 0.9f : 0.45f);

	const FBFImpactProfile& Profile = BFCombat::GetImpactProfile(Hit.Weight);
	FVector ToAttacker = -GetActorForwardVector();
	if (const AActor* Attacker = Hit.Instigator.Get())
	{
		const FVector To = (Attacker->GetActorLocation() - GetActorLocation()).GetSafeNormal2D();
		ToAttacker = To.IsNearlyZero() ? ToAttacker : To;
	}
	const FVector Away = -ToAttacker;

	// Caught in an opening (recovery, whiffed perilous move): extra damage.
	bLastHitPunish = IsPunishable();
	Health = FMath::Max(0.f, Health - Hit.Damage * (bLastHitPunish ? BFCombat::PunishDamageScale : 1.f) * BFCombat::TestDamageToEnemy);
	if (bLastHitPunish)
	{
		UE_LOG(LogTemp, Display, TEXT("BFTEST enemy punished x%.1f hp=%.0f"), BFCombat::PunishDamageScale, Health);
	}
	AddPosture(Hit.PostureDamage);
	{
		// Stance (hidden): light cuts barely dent it; heavy blows, finishers and plunges break it.
		float StanceDmg = Hit.StanceDamage;
		if (StanceDmg < 0.f)
		{
			switch (Hit.Weight)
			{
			case EBFHitWeight::Light: StanceDmg = 4.f; break;
			case EBFHitWeight::Heavy: StanceDmg = 14.f; break;
			case EBFHitWeight::Finisher: StanceDmg = Hit.bHeavy ? 30.f : 18.f; break;
			default: StanceDmg = 0.f; break;
			}
		}
		AddStance(StanceDmg);
	}
	// Every hit reads on the body, even on armor: flinch away from the blow plus a white flash.
	PlayImpactFeedback((Away + Hit.SwingDir.GetSafeNormal2D() * 0.6f).GetSafeNormal2D(), Profile.Flinch, 0.1f + 0.04f * static_cast<float>(Hit.Weight));

	if (State != EBFEnemyState::Broken && State != EBFEnemyState::Down)
	{
		StateTime = 0.f;
	}
	if (Health <= 0.f)
	{
		State = EBFEnemyState::Dead;
		StateTime = 0.f;
		PlayAnim(DeathAnim, 1.f, 0.05f, 0.f);
		if (CurrentMontage)
		{
			// Hold the last frame instead of blending back to idle.
			HoldLastFrame();
		}
		return true;
	}

	// No new reaction while: kneeling broken, lying down (the down timer keeps running), standing
	// back up, or swinging (armor). Light hits never stagger a super-armored boss.
	const bool bArmor = State == EBFEnemyState::Attacking || (bSuperArmor && Hit.Weight == EBFHitWeight::Light);
	if (State == EBFEnemyState::Broken || State == EBFEnemyState::Down || bRecovering || bArmor)
	{
		bLastHitArmored = bArmor;
		if (bArmor && Hit.Weight != EBFHitWeight::Light)
		{
			// Heavy blows still shove an armored body a little.
			LaunchCharacter(Away * Profile.Push * 0.25f * ImpactScale, true, false);
		}
		return true;
	}

	if (Hit.bFinisher && bCanBeKnockedDown)
	{
		// Light-chain finisher: knocked onto the back. Heavy-chain finisher: blown away.
		SetActorRotation(FRotator(0.f, ToAttacker.Rotation().Yaw, 0.f));
		KnockDown(Hit.bHeavy && HeavyKnockdownAnim ? HeavyKnockdownAnim.Get() : KnockdownAnim.Get());
		return true;
	}

	// Stagger. Bosses take finishers as a slower, bigger hit react plus a shove.
	State = EBFEnemyState::Stagger;
	const float RateScale = Hit.bFinisher ? 0.8f : (Hit.Weight == EBFHitWeight::Heavy ? 0.85f : 1.f);
	PlayHitReact(Hit, ToAttacker, RateScale);
	LaunchCharacter(Away * Profile.Push * ImpactScale, true, false);
	return true;
}

void ABFEnemyBase::PlayHitReact(const FBFHitInfo& Hit, const FVector& ToAttacker, float RateScale)
{
	// Side from the blade's travel: a blade moving toward our right came in from our left.
	// Falls back to where it struck; a hit from behind uses the back react when there is one.
	const FVector Fwd = GetActorForwardVector();
	const FVector Right = GetActorRightVector();
	UAnimSequence* React = HitFrontAnim;
	if (HitBackAnim && FVector::DotProduct(ToAttacker, Fwd) < -0.5f)
	{
		React = HitBackAnim;
	}
	else
	{
		const FVector Swing = Hit.SwingDir.GetSafeNormal2D();
		const float Side = !Swing.IsNearlyZero() ? FVector::DotProduct(Swing, Right)
			: -FVector::DotProduct((Hit.ImpactPoint - GetActorLocation()).GetSafeNormal2D(), Right);
		if (Side > 0.35f)
		{
			React = HitLeftAnim;
		}
		else if (Side < -0.35f)
		{
			React = HitRightAnim;
		}
	}
	PlayAnim(React ? React : HitFrontAnim.Get(), HitReactRate * RateScale, 0.06f, 0.4f);
}

void ABFEnemyBase::KnockDown(UAnimSequence* Anim)
{
	// The knockdown clips carry root motion (the body slides back on its own), so no launch here:
	// a launch would fight the root motion and pop the body.
	State = EBFEnemyState::Down;
	StateTime = 0.f;
	PlayAnim(Anim, 1.f, 0.05f, 0.f);
	HoldLastFrame();
	DownClipLen = Anim ? Anim->GetPlayLength() : 1.2f;
	DownHold = DownClipLen + 0.9f;
	bDownLooping = false;
}

void ABFEnemyBase::OnParried(AActor* By)
{
	if (State != EBFEnemyState::Attacking)
	{
		return;
	}
	// Recoil: knocked back off the blade, swing cancelled.
	State = EBFEnemyState::Stagger;
	StateTime = 0.f;
	PlayAnim(HitFrontAnim, ParryRecoilRate, 0.03f, 0.25f);
	if (By)
	{
		LaunchCharacter(-(By->GetActorLocation() - GetActorLocation()).GetSafeNormal2D() * ParryRecoilLaunch, true, false);
	}
	AddPosture(34.f);
	CooldownLeft = AttackCooldown;
}

void ABFEnemyBase::OnClashLost(AActor* By)
{
	if (State == EBFEnemyState::Dead)
	{
		return;
	}
	const FVector Away = By ? -(By->GetActorLocation() - GetActorLocation()).GetSafeNormal2D() : -GetActorForwardVector();
	StateTime = 0.f;
	CooldownLeft = AttackCooldown;
	if (IsBoss())
	{
		// Boss: overpowered and hurt, but keeps its footing.
		Health = FMath::Max(0.f, Health - MaxHealth * 0.1f * FMath::Min(BFCombat::TestDamageToEnemy, 1.f));
		State = EBFEnemyState::Stagger;
		PlayAnim(HitFrontAnim, HitReactRate * 0.8f, 0.05f, 0.25f);
		LaunchCharacter(Away * 220.f, true, false);
		AddPosture(30.f);
	}
	else
	{
		// Minion: blown off its feet (root-motion blow-back clip carries it ~2 m).
		Health = FMath::Max(0.f, Health - MaxHealth * 0.2f * FMath::Min(BFCombat::TestDamageToEnemy, 1.f));
		SetActorRotation(FRotator(0.f, (-Away).Rotation().Yaw, 0.f));
		KnockDown(HeavyKnockdownAnim ? HeavyKnockdownAnim.Get() : KnockdownAnim.Get());
	}
	if (Health <= 0.f)
	{
		State = EBFEnemyState::Dead;
		PlayAnim(DeathAnim, 1.f, 0.05f, 0.f);
		if (CurrentMontage)
		{
			HoldLastFrame();
		}
	}
	UE_LOG(LogTemp, Display, TEXT("BFTEST clash lost by enemy rank=%s hp=%.0f posture=%.0f state=%d"), IsBoss() ? TEXT("boss") : TEXT("minion"), Health, Posture, int32(State));
}

void ABFEnemyBase::OnClashWon(AActor* By)
{
	// The swing was already resolved; un-freezing lets it follow through over the player.
	CooldownLeft = AttackCooldown;
	UE_LOG(LogTemp, Display, TEXT("BFTEST clash won by enemy"));
}

void ABFEnemyBase::ReceiveExecution(AActor* By)
{
	if (State != EBFEnemyState::Broken)
	{
		return;
	}
	Health = FMath::Max(0.f, Health - MaxHealth * (bStanceBroken ? 0.2f : 0.3f) * FMath::Min(BFCombat::TestDamageToEnemy, 1.f));
	UE_LOG(LogTemp, Display, TEXT("BFTEST enemy critical after %s break"), bStanceBroken ? TEXT("stance") : TEXT("posture"));
	Posture = 0.f;
	Stance = 0.f;
	bStanceBroken = false;
	if (By)
	{
		PlayImpactFeedback(-(By->GetActorLocation() - GetActorLocation()).GetSafeNormal2D(), BFCombat::GetImpactProfile(EBFHitWeight::Execution).Flinch, 0.3f);
	}
	StateTime = 0.f;
	if (Health <= 0.f)
	{
		State = EBFEnemyState::Dead;
		PlayAnim(DeathAnim, 1.f, 0.05f, 0.f);
		HoldLastFrame();
	}
	else if (bCanBeKnockedDown)
	{
		KnockDown(KnockdownAnim);
	}
	else
	{
		// Boss: doubles over from the deathblow, then fights on.
		State = EBFEnemyState::Stagger;
		PlayAnim(HitBackAnim ? HitBackAnim.Get() : HitFrontAnim.Get(), 1.f, 0.06f, 0.3f);
	}
	if (CurrentMontage && State != EBFEnemyState::Stagger)
	{
		HoldLastFrame();
	}
	UE_LOG(LogTemp, Display, TEXT("BFTEST enemy executed hp=%.0f"), Health);
}

void ABFEnemyBase::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	TickLean(DeltaSeconds);

	// Re-forming after a respawn: the dissolve runs backwards.
	if (Reform > 0.f)
	{
		Reform = FMath::Max(0.f, Reform - DeltaSeconds / 1.2f);
		GetMesh()->SetScalarParameterValueOnMaterials(TEXT("BFDissolve"), FMath::SmoothStep(0.f, 1.f, Reform));
	}

	// Head and upper body follow the player while idling, walking or turning (the aim offset sits under
	// the montage slot, so attacks and reactions still own the whole body).
	if (UBFAnimInstance* Anim = Cast<UBFAnimInstance>(GetMesh()->GetAnimInstance()))
	{
		Anim->LookTarget = GetPlayer();
		Anim->bLookEnabled = State == EBFEnemyState::Normal && !IsDead() && !bBackstepping;
	}

	const double Now = GetWorld()->GetRealTimeSeconds();
	if (HitstopEndTime > 0.0 && Now >= HitstopEndTime)
	{
		HitstopEndTime = 0.0;
		CustomTimeDilation = 1.f;
	}
	else if (HitstopEndTime > 0.0)
	{
		// Hit pause is slow motion that eases back to full speed over its second half (not a hard freeze).
		const float T = float((Now - HitstopStartTime) / FMath::Max(HitstopEndTime - HitstopStartTime, 0.001));
		CustomTimeDilation = FMath::Lerp(HitstopMinDilation, 1.f, FMath::SmoothStep(0.5f, 1.f, T));
	}

	// Posture drains once the enemy has not been pressured for a while.
	if (State != EBFEnemyState::Broken && Posture > 0.f && Now - LastPostureDamageTime > PostureRegenDelay)
	{
		Posture = FMath::Max(0.f, Posture - PostureRegenRate * DeltaSeconds);
	}

	// Stance recovers once no heavy blow landed for a while.
	if (State != EBFEnemyState::Broken && Stance > 0.f && Now - LastStanceDamageTime > StanceRegenDelay)
	{
		Stance = FMath::Max(0.f, Stance - StanceRegenRate * DeltaSeconds);
	}

	StateTime += DeltaSeconds;
	UAnimInstance* AnimInstance = GetMesh()->GetAnimInstance();
	TickMagicFX(FApp::GetDeltaTime());
	TickRuneCircle(FApp::GetDeltaTime());
	if (bMagicAir && State != EBFEnemyState::Attacking)
	{
		LandFromMagic(); // cast cut short: drop back to the floor
	}
	if (State != EBFEnemyState::Normal)
	{
		bTurning = false;
		bBackstepping = false;
	}

	// Diagnostic heartbeat (real time) so automated runs can see what the enemy is doing.
	if (Now - LastDebugLogTime >= 2.0)
	{
		LastDebugLogTime = Now;
		const ABFPlayerCharacter* P = GetPlayer();
		UE_LOG(LogTemp, Display, TEXT("BFENEMY %s state=%d loc=%s dist=%.0f cooldown=%.2f montage=%d hp=%.0f"), *GetName(), int32(State),
			*GetActorLocation().ToCompactString(), P ? FVector::Dist2D(P->GetActorLocation(), GetActorLocation()) : -1.f, CooldownLeft,
			AnimInstance && CurrentMontage && AnimInstance->Montage_IsPlaying(CurrentMontage) ? 1 : 0, Health);
	}
	bool bMontagePlaying = AnimInstance && CurrentMontage && AnimInstance->Montage_IsPlaying(CurrentMontage);

	TickGroundWave(FApp::GetDeltaTime());
	if (bTraveling && State != EBFEnemyState::Normal)
	{
		EndTravel();
	}
	// Half health: phase 2 (waits out a strength clash, a posture break or a stagger).
	if (bHasPhase2 && Phase == 1 && Health > 0.f && Health <= MaxHealth * 0.5f && !bMagicAir && (State == EBFEnemyState::Normal || State == EBFEnemyState::Attacking))
	{
		const ABFPlayerCharacter* P = GetPlayer();
		if (!P || !P->IsStruggling())
		{
			StartPhaseTransition();
		}
	}
	// Opening cue: a soft gold ring the moment the boss becomes punishable.
	const bool bOpen = IsPunishable();
	if (bOpen && !bWasPunishable)
	{
		ABFRingFX::Spawn(GetWorld(), GetActorLocation() + FVector(0.f, 0.f, GetLockHeight()), FLinearColor(1.f, 0.82f, 0.35f), 40.f, 200.f, 0.4f);
		UE_LOG(LogTemp, Display, TEXT("BFTEST enemy opening"));
	}
	bWasPunishable = bOpen;

	switch (State)
	{
	case EBFEnemyState::Normal:
	{
		CooldownLeft -= DeltaSeconds;
		if (bAttackRecovering)
		{
			// The recovery clip carries the swing's end pose back to idle; stand still meanwhile.
			if (bMontagePlaying)
			{
				break;
			}
			bAttackRecovering = false;
		}
		if (bTraveling)
		{
			TickTravel(DeltaSeconds);
			break;
		}
		if (bBackstepping)
		{
			TickBackstep(DeltaSeconds);
			break;
		}
		if (bTurning)
		{
			TickTurnInPlace(DeltaSeconds);
			break;
		}
		const ABFPlayerCharacter* Player = GetPlayer();
		if (!Player)
		{
			break;
		}
		const FVector ToPlayer = (Player->GetActorLocation() - GetActorLocation()).GetSafeNormal2D();
		const float Dist = FVector::Dist2D(Player->GetActorLocation(), GetActorLocation());
		// Backstep: hop out of a player who keeps landing hits (3 in 2 s) or hugs him.
		static const bool bBackstepAllowed = !FParse::Param(FCommandLine::Get(), TEXT("BFNoBackstep"))
			&& (!FCString::Strifind(FCommandLine::Get(), TEXT("-BFForceAttacks=")) || FParse::Param(FCommandLine::Get(), TEXT("BFBackstep")));
		if (BackstepAnim && bBackstepAllowed && !Player->IsCinematic() && Now - LastBackstepTime > BackstepCooldown)
		{
			RecentHitTimes.RemoveAll([Now](double T) { return Now - T > 2.0; });
			HugStartTime = Dist < 170.f ? (HugStartTime < 0.0 ? Now : HugStartTime) : -1.0;
			if (RecentHitTimes.Num() >= 3)
			{
				StartBackstep(TEXT("pressure"));
				break;
			}
			if (HugStartTime >= 0.0 && Now - HugStartTime > 1.2)
			{
				StartBackstep(TEXT("close"));
				break;
			}
		}
		// Big facing error: stop and turn on the spot with a stepping clip. Small errors are trimmed
		// slowly while walking, so the body never spins in place without moving its feet.
		const float YawErr = YawToPlayer();
		if (TurnRightAnim && !Player->IsCinematic() && FMath::Abs(YawErr) > TurnInPlaceAngle && StartTurnInPlace(YawErr))
		{
			break;
		}
		TurnTowardPlayer(DeltaSeconds, TurnRightAnim ? 90.f : 240.f);
		if (!bAutoAttack)
		{
			break; // tests / training: no attacks, no chasing
		}
		if (CooldownLeft <= 0.f && !Player->IsCinematic())
		{
			// Phase 2 at range: either a spell from where he stands, or glide in and open with a leaping strike.
			if (Phase >= 2 && TravelLoopAnim && Attacks.IsValidIndex(TravelArriveAttack) && Dist > TravelMinDist)
			{
				const int32 Spell = FMath::FRand() < 0.5f ? PickAttack(Dist) : INDEX_NONE;
				if (IsMagicAttack(Spell))
				{
					StartAttack(Spell);
					break;
				}
				StartTravel();
				break;
			}
			// Now and then, instead of swinging at a player standing on top of him: hop back first.
			if (BackstepAnim && bBackstepAllowed && Dist < 230.f && Now - LastBackstepTime > BackstepCooldown && FMath::FRand() < 0.2f)
			{
				StartBackstep(TEXT("spacing"));
				break;
			}
			const int32 Pick = PickAttack(Dist);
			if (Pick != INDEX_NONE)
			{
				StartAttack(Pick);
				break;
			}
		}
		if (Dist > ChaseDistance)
		{
			// Close the distance at walking pace when the player backs off.
			AddMovementInput(ToPlayer, 1.f);
		}
		else if (bCircleStrafe && Dist > 150.f)
		{
			// Between attacks: circle the player, switching sides now and then.
			CircleSwitchLeft -= DeltaSeconds;
			if (CircleSwitchLeft <= 0.f)
			{
				CircleDir = FMath::RandBool() ? 1.f : -1.f;
				CircleSwitchLeft = FMath::FRandRange(1.5f, 3.f);
			}
			AddMovementInput(FVector::CrossProduct(FVector::UpVector, ToPlayer) * CircleDir, 0.45f);
		}
		break;
	}
	case EBFEnemyState::Attacking:
		TickAttack(DeltaSeconds);
		break;
	case EBFEnemyState::Stagger:
		// A get-up holds its last frame (no auto blend-out): the montage counts as stopped as soon
		// as a blend-out starts, which sent the enemy back to Normal half-crouched, hittable into a
		// standing flinch. Finish the whole clip, then blend into idle.
		if (bRecovering && bMontagePlaying && CurrentMontage
			&& AnimInstance->Montage_GetPosition(CurrentMontage) >= CurrentMontage->GetPlayLength() - 0.04f)
		{
			AnimInstance->Montage_StopWithBlendSettings(BFAnimBlend::Inert(0.30f), CurrentMontage);
			bMontagePlaying = false;
		}
		if (!bMontagePlaying)
		{
			State = EBFEnemyState::Normal;
			bRecovering = false;
		}
		break;
	case EBFEnemyState::Broken:
		// Stun intro, then its loop (when the enemy has one) until recovery.
		if (BrokenLoopAnim && !bBrokenLooping && BrokenAnim && StateTime > BrokenAnim->GetPlayLength() / 1.2f - 0.1f)
		{
			bBrokenLooping = true;
			PlayAnim(BrokenLoopAnim, 1.f, 0.15f, 0.f, 1000);
		}
		if (StateTime > (bStanceBroken ? StanceBreakDuration : BrokenDuration))
		{
			// Recovered without being executed: stand back up, posture (or stance) reset.
			if (bStanceBroken)
			{
				Stance = 0.f;
				bStanceBroken = false;
			}
			else
			{
				Posture = 0.f;
			}
			State = EBFEnemyState::Stagger;
			if (BrokenEndAnim)
			{
				PlayAnim(BrokenEndAnim, 1.f, 0.4f, 0.45f); // Stun_Loop ends 37 cm from Stun_End's first pose: wider blend
				HoldLastFrame();
			}
			else if (AnimInstance && CurrentMontage)
			{
				AnimInstance->Montage_StopWithBlendSettings(BFAnimBlend::Inert(0.45f), CurrentMontage);
			}
			bRecovering = true;
			CooldownLeft = AttackCooldown;
		}
		break;
	case EBFEnemyState::Down:
		// Knockdown holds its last frame; after lying for a moment, stand up (no new reactions
		// while rising, so a hit cannot snap the body from the floor into a standing flinch).
		// Landed: settle into the lying loop (breathing) instead of a frozen last frame.
		if (DownLoopAnim && !bDownLooping && StateTime > DownClipLen - 0.05f)
		{
			bDownLooping = true;
			PlayAnim(DownLoopAnim, 1.f, 0.25f, 0.f, 1000);
		}
		if (StateTime > DownHold)
		{
			State = EBFEnemyState::Stagger;
			PlayAnim(GetUpAnim, 1.f, 0.3f, 0.45f);
			HoldLastFrame();
			bRecovering = true;
			CooldownLeft = AttackCooldown;
		}
		break;
	case EBFEnemyState::Transition:
		TickTransition();
		break;
	case EBFEnemyState::Dead:
		TickDeathFall(GetWorld()->GetDeltaSeconds());
		// A boss respawns only once he has fully dissolved (and a beat after).
		if (RespawnDelay > 0.f && StateTime > RespawnDelay && (!IsBoss() || DeathAfterLand > DissolveStart + DissolveLen + 1.2f))
		{
			ResetDeathFall();
			Health = MaxHealth;
			Posture = 0.f;
			Stance = 0.f;
			if (Phase != 1)
			{
				Phase = 1;
				AttackCooldown = Phase1Cooldown;
				MoveSpeedBase = Phase1Speed;
				GetCharacterMovement()->MaxWalkSpeed = MoveSpeedBase;
			}
			State = EBFEnemyState::Stagger;
			StateTime = 0.f;
			PlayAnim(GetUpAnim, 1.f, 0.3f, 0.45f);
			HoldLastFrame();
			bRecovering = true;
			CooldownLeft = AttackCooldown;
		}
		break;
	default:
		break;
	}
}

void ABFEnemyBase::TickDeathFall(float DeltaSeconds)
{
	DeathLoose = FMath::Min(1.f, DeathLoose + DeltaSeconds / 0.6f);
	if (bDeathLanded)
	{
		TickDeathAfterLand(DeltaSeconds);
		return;
	}
	UAnimInstance* AnimInstance = GetMesh()->GetAnimInstance();
	const bool bClipDone = !CurrentMontage || !AnimInstance || !AnimInstance->Montage_IsPlaying(CurrentMontage)
		|| AnimInstance->Montage_GetPosition(CurrentMontage) >= CurrentMontage->GetPlayLength() - 0.04f;
	if (!bClipDone)
	{
		return;
	}
	if (DeathDropTarget < 0.f)
	{
		// How far the held pose hangs above the floor: the lowest bone of body and robe (the robe is thick:
		// body bones alone sank him into the floor). Weapon, IK and root bones do not count.
		const float FloorZ = GetActorLocation().Z - GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
		float Lowest = BIG_NUMBER;
		FName LowestBone;
		for (int32 I = 0; I < GetMesh()->GetNumBones(); ++I)
		{
			const FName Bone = GetMesh()->GetBoneName(I);
			const FString Name = Bone.ToString().ToLower();
			if (Name.Contains(TEXT("weapon")) || Name.StartsWith(TEXT("ik_")) || Name == TEXT("root"))
			{
				continue;
			}
			const float Z = GetMesh()->GetBoneLocation(Bone).Z;
			if (Z < Lowest)
			{
				Lowest = Z;
				LowestBone = Bone;
			}
		}
		DeathDropTarget = Lowest < BIG_NUMBER ? FMath::Max(0.f, Lowest - FloorZ - 6.f) : 0.f;
		UE_LOG(LogTemp, Display, TEXT("BFTEST death lowest bone %s at %.0f above floor"), *LowestBone.ToString(), Lowest - FloorZ);
		DeathDropVel = 250.f; // the clip ends falling
		UE_LOG(LogTemp, Display, TEXT("BFTEST death fall drop=%.0f"), DeathDropTarget);
	}
	DeathDropVel += 2400.f * DeltaSeconds;
	DeathDrop = FMath::Min(DeathDropTarget, DeathDrop + DeathDropVel * DeltaSeconds);
	GetMesh()->SetRelativeLocation(MeshBaseLoc - FVector(0.f, 0.f, DeathDrop));
	if (DeathDrop >= DeathDropTarget)
	{
		bDeathLanded = true;
		const FVector Feet = GetActorLocation() - FVector(0.f, 0.f, GetCapsuleComponent()->GetScaledCapsuleHalfHeight() - 3.f);
		if (DeathDropTarget > 10.f)
		{
			ABFRingFX::SpawnGround(GetWorld(), Feet, FLinearColor(0.7f, 0.66f, 0.58f), 60.f, 420.f, 0.5f);
			if (ABFPlayerCharacter* Player = GetPlayer())
			{
				Player->AddCameraShake(IsBoss() ? 7.f : 3.f, 0.25f, FVector::UpVector, 3.f);
			}
		}
		UE_LOG(LogTemp, Display, TEXT("BFTEST death landed drop=%.0f"), DeathDrop);
	}
}

float ABFEnemyBase::GetFloorZ() const
{
	return GetActorLocation().Z - GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
}

void ABFEnemyBase::TickDeathAfterLand(float DeltaSeconds)
{
	DeathAfterLand += DeltaSeconds;
	// Slow ease: the raised arm sinks to the floor.
	DeathSettle = FMath::SmoothStep(0.15f, IsBoss() ? 2.4f : 1.2f, DeathAfterLand);
	if (!IsBoss() || DeathAfterLand < DissolveStart)
	{
		return;
	}
	if (!bDissolveStarted)
	{
		bDissolveStarted = true;
		ABFDissolveFX::Spawn(GetWorld(), GetMesh(), DissolveLen);
		UE_LOG(LogTemp, Display, TEXT("BFTEST death dissolve start"));
	}
	const float Prev = DeathDissolve;
	DeathDissolve = FMath::Min(1.f, (DeathAfterLand - DissolveStart) / DissolveLen);
	if (DeathDissolve != Prev)
	{
		GetMesh()->SetScalarParameterValueOnMaterials(TEXT("BFDissolve"), DeathDissolve);
	}
	if (DeathDissolve > 0.5f && Prev <= 0.5f)
	{
		for (int32 I = 0; I < GetMesh()->GetNumMaterials(); ++I)
		{
			UMaterialInterface* M = GetMesh()->GetMaterial(I);
			float V = -1.f;
			const bool bHas = M && M->GetScalarParameterValue(FHashedMaterialParameterInfo(TEXT("BFDissolve")), V);
			UE_LOG(LogTemp, Display, TEXT("BFTEST dissolve mat %d %s blend=%d has=%d v=%.2f"), I, M ? *M->GetPathName() : TEXT("none"), M ? int32(M->GetBlendMode()) : -1, bHas ? 1 : 0, V);
		}
	}
	if (DeathDissolve >= 1.f && GetMesh()->IsVisible())
	{
		GetMesh()->SetVisibility(false, true);
		ABFRingFX::SpawnGround(GetWorld(), FVector(GetActorLocation().X, GetActorLocation().Y, GetFloorZ() + 3.f), FLinearColor(0.3f, 1.f, 0.5f), 80.f, 520.f, 0.9f);
		UE_LOG(LogTemp, Display, TEXT("BFTEST death dissolved"));
	}
}

void ABFEnemyBase::ResetDeathFall()
{
	if (bDissolveStarted)
	{
		GetMesh()->SetVisibility(true, true);
		Reform = 1.f;
		GetMesh()->SetScalarParameterValueOnMaterials(TEXT("BFDissolve"), 1.f);
		ABFDissolveFX::Spawn(GetWorld(), GetMesh(), 1.2f, 0.6f);
	}
	DeathAfterLand = 0.f;
	DeathSettle = 0.f;
	DeathDissolve = 0.f;
	bDissolveStarted = false;
	DeathLoose = 0.f;
	DeathDrop = 0.f;
	DeathDropVel = 0.f;
	DeathDropTarget = -1.f;
	bDeathLanded = false;
	GetMesh()->SetRelativeLocation(MeshBaseLoc);
}

// ---------------------------------------------------------------------------------------------
// Turn on the spot, backstep

float ABFEnemyBase::YawToPlayer() const
{
	const ABFPlayerCharacter* Player = GetPlayer();
	if (!Player)
	{
		return 0.f;
	}
	const FVector To = (Player->GetActorLocation() - GetActorLocation()).GetSafeNormal2D();
	return To.IsNearlyZero() ? 0.f : FRotator::NormalizeAxis(To.Rotation().Yaw - GetActorRotation().Yaw);
}

bool ABFEnemyBase::StartTurnInPlace(float Delta)
{
	// The Paragon turn clips step the feet round but keep the root facing forward: the actor yaw is
	// eased across the clip so the body ends up facing the player as the last step lands.
	const bool b180 = FMath::Abs(Delta) >= 125.f;
	UAnimSequence* Clip = Delta > 0.f ? (b180 ? TurnRight180Anim : TurnRightAnim) : (b180 ? TurnLeft180Anim : TurnLeftAnim);
	if (!Clip)
	{
		return false;
	}
	const float Rate = b180 ? TurnRate180 : TurnRate90;
	if (!PlayAnim(Clip, Rate, 0.2f, 0.25f))
	{
		return false;
	}
	bTurning = true;
	TurnFromYaw = GetActorRotation().Yaw;
	TurnDelta = Delta;
	TurnDur = Clip->GetPlayLength() / Rate;
	TurnT = 0.f;
	UE_LOG(LogTemp, Display, TEXT("BFTEST boss turn in place delta=%.0f clip=%s dur=%.2f"), Delta, *Clip->GetName(), TurnDur);
	return true;
}

void ABFEnemyBase::TickTurnInPlace(float DeltaSeconds)
{
	TurnT += DeltaSeconds;
	// Rotate over the stepping part of the clip (the slow walk turn trims what is left afterwards).
	const float Want = TurnDelta;
	const float A = FMath::Clamp(TurnT / (TurnDur * 0.8f), 0.f, 1.f);
	SetActorRotation(FRotator(0.f, TurnFromYaw + Want * FMath::SmoothStep(0.f, 1.f, A), 0.f));
	if (TurnT >= TurnDur * 0.88f)
	{
		bTurning = false;
		if (UAnimInstance* AnimInstance = GetMesh()->GetAnimInstance())
		{
			AnimInstance->Montage_StopWithBlendSettings(BFAnimBlend::Inert(0.30f), CurrentMontage);
		}
	}
}

bool ABFEnemyBase::FindFloorZ(const FVector& At, float& OutZ) const
{
	FHitResult Hit;
	FCollisionQueryParams Params(SCENE_QUERY_STAT(BFFloor), false, this);
	if (const ABFPlayerCharacter* Player = GetPlayer())
	{
		Params.AddIgnoredActor(Player);
	}
	const FVector From(At.X, At.Y, At.Z + 150.f);
	const FVector To(At.X, At.Y, At.Z - 450.f);
	if (!GetWorld()->LineTraceSingleByChannel(Hit, From, To, ECC_Visibility, Params))
	{
		return false;
	}
	OutZ = Hit.ImpactPoint.Z;
	return true;
}

void ABFEnemyBase::StartBackstep(const TCHAR* Reason)
{
	bBackstepping = true;
	BackstepT = 0.f;
	BackstepMoved = 0.f;
	LastBackstepTime = GetWorld()->GetRealTimeSeconds();
	RecentHitTimes.Reset();
	HugStartTime = -1.0;
	PlayAnim(BackstepAnim, BackstepRate, 0.12f, 0.3f);
	ABFRingFX::SpawnGround(GetWorld(), GetActorLocation() - FVector(0.f, 0.f, GetHalfHeight() - 4.f), FLinearColor(0.4f, 1.f, 0.45f), 60.f, 300.f, 0.35f);
	UE_LOG(LogTemp, Display, TEXT("BFTEST boss backstep reason=%s"), Reason);
}

void ABFEnemyBase::TickBackstep(float DeltaSeconds)
{
	BackstepT += DeltaSeconds;
	const float MoveTime = 0.55f;
	const float A = FMath::Clamp(BackstepT / MoveTime, 0.f, 1.f);
	const float Target = BackstepDistance * (1.f - (1.f - A) * (1.f - A));
	const float Step = Target - BackstepMoved;
	FVector Away = -GetActorForwardVector();
	if (const ABFPlayerCharacter* Player = GetPlayer())
	{
		const FVector From = (GetActorLocation() - Player->GetActorLocation()).GetSafeNormal2D();
		Away = From.IsNearlyZero() ? Away : From;
	}
	if (Step > 0.f)
	{
		// Never hop off the arena: stop where the floor ends or drops away.
		const FVector Next = GetActorLocation() + Away * (Step + 60.f);
		const float FeetZ = GetActorLocation().Z - GetHalfHeight();
		float FloorZ = 0.f;
		if (FindFloorZ(Next, FloorZ) && FMath::Abs(FloorZ - FeetZ) < 60.f)
		{
			AddActorWorldOffset(Away * Step, true);
			BackstepMoved = Target;
		}
		else
		{
			BackstepMoved = BackstepDistance;
		}
	}
	TurnTowardPlayer(DeltaSeconds, 120.f);
	const float Len = BackstepAnim ? BackstepAnim->GetPlayLength() / BackstepRate : 0.9f;
	if (BackstepT >= Len * 0.78f)
	{
		bBackstepping = false;
		bPreferRanged = true;
		CooldownLeft = FMath::Min(CooldownLeft, 0.2f);
		if (UAnimInstance* AnimInstance = GetMesh()->GetAnimInstance())
		{
			AnimInstance->Montage_StopWithBlendSettings(BFAnimBlend::Inert(0.30f), CurrentMontage);
		}
		UE_LOG(LogTemp, Display, TEXT("BFTEST boss backstep end moved=%.0f"), BackstepMoved);
	}
}

// ---------------------------------------------------------------------------------------------
// Magic: fire line and eruption circle, cast from the air

float ABFEnemyBase::MagicHeightAt(float T, float RiseHeight) const
{
	// Lift-off with a slight overshoot (ease-out-back), then a slow breathing bob while he hangs there.
	const float RiseA = FMath::Clamp(T / MagicRiseTime, 0.f, 1.f);
	float Rise;
	if (HasMagicFlightClips())
	{
		const float C1 = 1.2f;
		const float C3 = C1 + 1.f;
		const float X = RiseA - 1.f;
		Rise = 1.f + C3 * X * X * X + C1 * X * X;
	}
	else
	{
		Rise = FMath::SmoothStep(0.f, 1.f, RiseA);
	}
	float Bob = 0.f;
	if (HasMagicFlightClips() && T > MagicRiseTime)
	{
		const float H = T - MagicRiseTime;
		Bob = FMath::Sin(H * UE_TWO_PI / MagicBobPeriod) * MagicBobHeight * FMath::Clamp(H / 0.4f, 0.f, 1.f);
	}
	return RiseHeight * Rise + Bob;
}

void ABFEnemyBase::TickMagicCast(float DeltaSeconds)
{
	const FBFEnemyAttack& A = Attacks[CurrentAttack];
	UAnimInstance* AnimInstance = GetMesh()->GetAnimInstance();
	const bool bPlaying = AnimInstance && CurrentMontage && AnimInstance->Montage_IsPlaying(CurrentMontage);
	const float Pos = bPlaying ? AnimInstance->Montage_GetPosition(CurrentMontage) : 100.f;
	const bool bFlight = HasMagicFlightClips();
	MagicT += DeltaSeconds;

	if (MagicStage <= 3)
	{
		// Rise out of sword reach (backing off from the player a little), then hang there.
		FVector L = GetActorLocation();
		L.Z = MagicBaseZ + MagicHeightAt(MagicT, A.RiseHeight);
		if (bFlight && !MagicDriftDir.IsNearlyZero())
		{
			const FVector XY = MagicStartXY + MagicDriftDir * MagicDrift * FMath::InterpEaseOut(0.f, 1.f, FMath::Clamp(MagicT / MagicRiseTime, 0.f, 1.f), 2.f);
			L.X = XY.X;
			L.Y = XY.Y;
		}
		SetActorLocation(L, true);
	}
	switch (MagicStage)
	{
	case 0: // gathering power while lifting off
		TurnTowardPlayer(DeltaSeconds, 200.f);
		if (bFlight ? MagicT >= MagicRiseTime * 0.85f : Pos >= 0.5f)
		{
			MagicStage = 1;
			MagicChargeLeft = A.ChargeTime * (Phase >= 2 ? 0.7f : 1.f);
			if (bFlight)
			{
				PlayAnim(MagicChargeAnim, 1.f, 0.3f, 0.2f); // hovering charge pose, claw raised, cape flared
			}
			else if (AnimInstance && CurrentMontage)
			{
				AnimInstance->Montage_SetPlayRate(CurrentMontage, A.PlayRate * 0.04f);
			}
			if (CastAuraVfx)
			{
				// Under his feet: a levitation vortex he hangs over (around the body it hides the pose).
				CastAura = UNiagaraFunctionLibrary::SpawnSystemAttached(CastAuraVfx, GetRootComponent(), NAME_None, FVector(0.f, 0.f, bFlight ? -GetHalfHeight() - 70.f : -GetHalfHeight() * 0.3f),
					FRotator::ZeroRotator, FVector(MagicAuraScale), EAttachLocation::KeepRelativeOffset, true, ENCPoolMethod::None);
			}
			if (CastChargeSound)
			{
				UGameplayStatics::PlaySoundAtLocation(this, CastChargeSound, GetActorLocation(), 1.2f, 0.9f);
			}
			if (A.Magic == EBFMagic::Orb)
			{
				OrbChargeTotal = FMath::Max(MagicChargeLeft, 0.1f);
				SpawnOrb();
			}
			if (HitFlash)
			{
				HitFlash->Flash(BFCombat::BossMagicColor(), MagicChargeLeft, 0.5f);
			}
			UE_LOG(LogTemp, Display, TEXT("BFTEST boss magic charge %.2fs height=%.0f"), MagicChargeLeft, GetActorLocation().Z - MagicBaseZ);
		}
		break;
	case 1: // charging, still tracking the player
		TurnTowardPlayer(DeltaSeconds, 240.f);
		MagicChargeLeft -= DeltaSeconds;
		if (MagicChargeLeft <= 0.f)
		{
			MagicStage = 2;
			const float Rate = A.PlayRate * 1.15f;
			float StartPos = Pos;
			if (bFlight)
			{
				// Slow build-up, fast release: jump into the cast clip just before its throw.
				if (UAnimMontage* M = PlayAnim(AttackAnims[CurrentAttack], Rate, 0.12f, 0.3f))
				{
					GetMesh()->GetAnimInstance()->Montage_SetPosition(M, MagicReleaseStart);
				}
				StartPos = MagicReleaseStart;
			}
			else if (AnimInstance && CurrentMontage)
			{
				AnimInstance->Montage_SetPlayRate(CurrentMontage, Rate);
			}
			if (const ABFPlayerCharacter* Player = GetPlayer())
			{
				MagicTarget = Player->GetActorLocation();
			}
			bMagicLocked = true;
			if (A.Magic == EBFMagic::FireLine)
			{
				// Aim locked at the player's position now; the floor is marked along the whole path.
				const float FeetZ = MagicBaseZ - GetHalfHeight();
				LineDir = (MagicTarget - GetActorLocation()).GetSafeNormal2D();
				if (LineDir.IsNearlyZero())
				{
					LineDir = GetActorForwardVector().GetSafeNormal2D();
				}
				SetActorRotation(FRotator(0.f, LineDir.Rotation().Yaw, 0.f));
				LineOrigin = FVector(GetActorLocation().X, GetActorLocation().Y, FeetZ + 3.f) + LineDir * 60.f;
				LineLength = 0.f;
				for (float D = 100.f; D <= FireLineMaxLength; D += 100.f)
				{
					float Z = 0.f;
					if (!FindFloorZ(LineOrigin + LineDir * D + FVector(0.f, 0.f, 20.f), Z) || FMath::Abs(Z - FeetZ) > 120.f)
					{
						break; // arena edge
					}
					LineLength = D;
				}
				const float Lead = FMath::Max(0.05f, (0.8f - StartPos) / Rate);
				for (float D = 0.f; D <= LineLength; D += 140.f)
				{
					ABFRingFX::SpawnGround(GetWorld(), LineOrigin + LineDir * D, BFCombat::BossMagicColor(), 150.f, 175.f, Lead + D / FireLineSpeed + 0.1f);
				}
				UE_LOG(LogTemp, Display, TEXT("BFTEST boss magic fireline locked len=%.0f"), LineLength);
			}
		}
		break;
	case 2: // release
		if (Pos >= 0.8f)
		{
			MagicStage = 3;
			ReleaseMagic(A);
		}
		break;
	case 3: // follow-through, then float down
		if (Pos >= (bFlight ? 1.05f : CurrentMontage->GetPlayLength() - 0.05f) || !bPlaying)
		{
			MagicStage = 4;
			MagicT = 0.f;
			MagicLandFromZ = GetActorLocation().Z;
			if (bFlight)
			{
				PlayAnim(MagicHoverAnim, 1.f, 0.35f, 0.35f); // robe hanging, drifting back down
			}
			if (CastAura)
			{
				CastAura->Deactivate();
				CastAura = nullptr;
			}
		}
		break;
	default:
	{
		// Flight clips: a short hang, then an eased glide down; otherwise a quick drop.
		const float Hang = bFlight ? 0.15f : 0.f;
		const float Dur = bFlight ? 0.6f : 0.45f;
		const float LandA = FMath::Clamp((MagicT - Hang) / Dur, 0.f, 1.f);
		FVector L = GetActorLocation();
		L.Z = FMath::Lerp(MagicLandFromZ, MagicBaseZ, FMath::InterpEaseInOut(0.f, 1.f, LandA, 2.2f));
		SetActorLocation(L, true);
		if (LandA >= 1.f)
		{
			if (bFlight)
			{
				if (AnimInstance && CurrentMontage)
				{
					AnimInstance->Montage_StopWithBlendSettings(BFAnimBlend::Inert(0.35f), CurrentMontage);
				}
				ABFRingFX::SpawnGround(GetWorld(), GetActorLocation() - FVector(0.f, 0.f, GetHalfHeight() - 4.f), BFCombat::BossMagicColor(), 40.f, 300.f, 0.35f);
			}
			LandFromMagic();
			UE_LOG(LogTemp, Display, TEXT("BFTEST boss magic landed"));
			FinishAttack();
			CooldownLeft = AttackCooldown + 0.4f;
		}
		break;
	}
	}
}

void ABFEnemyBase::ReleaseMagic(const FBFEnemyAttack& A)
{
	FBFHitInfo Hit;
	Hit.Damage = A.Damage;
	Hit.PostureDamage = A.PostureDamage;
	Hit.bMagic = true;
	Hit.bKnockUp = Phase >= 2; // phase 2: spells launch the player
	Hit.Instigator = this;
	if (A.Magic == EBFMagic::FireLine)
	{
		LineHit = Hit;
		LineFront = 0.f;
		LineNextFx = 0.f;
		bLineActive = LineLength > 0.f;
		bLineResolved = false;
		if (FireLineSound)
		{
			UGameplayStatics::PlaySoundAtLocation(this, FireLineSound, LineOrigin, 1.4f, 0.9f);
		}
		UE_LOG(LogTemp, Display, TEXT("BFTEST boss magic fireline release dir=%s knockup=%d"), *LineDir.ToCompactString(), Hit.bKnockUp ? 1 : 0);
	}
	else if (A.Magic == EBFMagic::Orb)
	{
		// Throw the orb at the spot the player stood on when the charge ended; the floor there is marked
		// with the burst radius for the whole flight, so a roll or a sprint out of the ring avoids it.
		if (!OrbCore)
		{
			SpawnOrb();
		}
		FVector To = MagicTarget;
		float Z = 0.f;
		To.Z = FindFloorZ(To + FVector(0.f, 0.f, 60.f), Z) ? Z : MagicBaseZ - GetHalfHeight();
		OrbFrom = OrbCore ? OrbCore->GetComponentLocation() : OrbHoldLocation();
		OrbTo = To;
		const float Dist = FVector::Dist(OrbFrom, OrbTo);
		OrbDur = FMath::Max(0.6f, Dist / OrbSpeed);
		OrbArc = FMath::Clamp(Dist * 0.22f, 120.f, 420.f);
		OrbT = 0.f;
		OrbHit = Hit;
		bOrbFlying = true;
		ABFRingFX::SpawnGround(GetWorld(), OrbTo + FVector(0.f, 0.f, 3.f), BFCombat::BossMagicColor(), OrbRadius * 2.f, OrbRadius * 2.f + 24.f, OrbDur);
		ABFRingFX::SpawnGround(GetWorld(), OrbTo + FVector(0.f, 0.f, 4.f), BFCombat::BossMagicPale(), 40.f, OrbRadius * 2.f, OrbDur);
		if (OrbThrowSound)
		{
			UGameplayStatics::PlaySoundAtLocation(this, OrbThrowSound, OrbFrom, 1.4f, 1.f);
		}
		UE_LOG(LogTemp, Display, TEXT("BFTEST boss magic orb thrown to %s dist=%.0f flight=%.2fs knockup=%d"), *OrbTo.ToCompactString(), Dist, OrbDur, Hit.bKnockUp ? 1 : 0);
	}
	else
	{
		// Eruption under the player after a warning; the ring chases them on a leash first (TickMagicFX).
		const ABFPlayerCharacter* Player = GetPlayer();
		FVector C = Player ? Player->GetActorLocation() : MagicTarget;
		float Z = 0.f;
		C.Z = FindFloorZ(C, Z) ? Z + 3.f : MagicBaseZ - GetHalfHeight() + 3.f;
		CircleCenter = C;
		CircleOrigin = C;
		bCircleLocked = false;
		CircleTimeLeft = CircleWarnTime;
		CircleHit = Hit;
		bCircleActive = true;
		const FLinearColor Purple = BFCombat::BossMagicColor(); // soul green (was purple)
		CircleRings.Reset();
		CircleRings.Add(ABFRingFX::SpawnGround(GetWorld(), C, Purple, CircleRadius * 2.f, CircleRadius * 2.f + 20.f, CircleWarnTime));
		CircleRings.Add(ABFRingFX::SpawnGround(GetWorld(), C + FVector(0.f, 0.f, 1.f), BFCombat::BossMagicPale(), 30.f, CircleRadius * 2.f, CircleWarnTime));
		if (CastChargeSound)
		{
			UGameplayStatics::PlaySoundAtLocation(this, CastChargeSound, C, 1.f, 1.3f);
		}
		UE_LOG(LogTemp, Display, TEXT("BFTEST boss magic circle release at %s knockup=%d"), *C.ToCompactString(), Hit.bKnockUp ? 1 : 0);
	}
}

void ABFEnemyBase::TickMagicFX(float RealDelta)
{
	ABFPlayerCharacter* Player = GetPlayer();
	if (OrbCore && !bOrbFlying)
	{
		// Growing in his claw while he charges (full size once the throw starts).
		const float Grow = MagicStage >= 2 ? 1.f : FMath::Clamp(1.f - MagicChargeLeft / OrbChargeTotal, 0.f, 1.f);
		SetOrbTransform(OrbHoldLocation(), OrbSize * FMath::Lerp(0.2f, 1.f, FMath::InterpEaseOut(0.f, 1.f, Grow, 2.f)));
	}
	else if (bOrbFlying)
	{
		OrbT += RealDelta;
		const float A = FMath::Clamp(OrbT / OrbDur, 0.f, 1.f);
		const float Ease = FMath::InterpEaseIn(0.f, 1.f, A, 1.6f); // leaves slowly, slams in
		const FVector P = FMath::Lerp(OrbFrom, OrbTo + FVector(0.f, 0.f, OrbSize * 0.4f), Ease) + FVector(0.f, 0.f, OrbArc * FMath::Sin(PI * Ease));
		SetOrbTransform(P, OrbSize * (1.f + 0.08f * FMath::Sin(OrbT * 30.f)));
		if (A >= 1.f)
		{
			BurstOrb();
		}
	}
	if (bLineActive)
	{
		// The front runs along the floor in real time (like its flames); pillars of fire every 110 cm.
		LineFront = FMath::Min(LineLength, LineFront + FireLineSpeed * RealDelta);
		while (LineNextFx <= LineFront)
		{
			if (FireLineVfx)
			{
				UNiagaraFunctionLibrary::SpawnSystemAtLocation(GetWorld(), FireLineVfx, LineOrigin + LineDir * LineNextFx, FRotator(0.f, LineDir.Rotation().Yaw, 0.f), FVector(0.8f));
			}
			BFFluxWater::Impact(GetWorld(), LineOrigin + LineDir * LineNextFx, 90.f, 0.35f);
			LineNextFx += 110.f;
		}
		if (!bLineResolved && Player)
		{
			const FVector Rel = (Player->GetActorLocation() - LineOrigin) * FVector(1.f, 1.f, 0.f);
			const float Along = FVector::DotProduct(Rel, LineDir);
			const float Lateral = FMath::Abs(FVector::CrossProduct(LineDir, Rel).Z);
			if (Along < -60.f || Along > LineLength + 60.f)
			{
				bLineResolved = LineFront >= LineLength; // not on the path
			}
			else if (LineFront >= Along - 40.f)
			{
				bLineResolved = true;
				const float Height = Player->GetActorLocation().Z - LineOrigin.Z;
				if (Lateral < FireLineHalfWidth && Height < 300.f)
				{
					LineHit.ImpactPoint = Player->GetActorLocation() - FVector(0.f, 0.f, 40.f);
					const EBFHitResult Result = Player->ResolveEnemyHit(LineHit, this);
					UE_LOG(LogTemp, Display, TEXT("BFTEST boss magic fireline reached player lateral=%.0f result=%d"), Lateral, int32(Result));
				}
				else
				{
					UE_LOG(LogTemp, Display, TEXT("BFTEST boss magic fireline missed lateral=%.0f"), Lateral);
				}
			}
		}
		if (LineFront >= LineLength)
		{
			bLineActive = false;
		}
	}
	if (bCircleActive)
	{
		CircleTimeLeft -= RealDelta;
		const float Elapsed = CircleWarnTime - CircleTimeLeft;
		if (!bCircleLocked && Elapsed < CircleChaseTime && Player)
		{
			// Crawl toward the player, leashed to the spot it appeared on; the warning rings ride along.
			FVector Goal = Player->GetActorLocation();
			FVector Off = Goal - CircleOrigin;
			Off.Z = 0.f;
			if (Off.Size() > CircleLeash)
			{
				Goal = CircleOrigin + Off.GetSafeNormal() * CircleLeash;
			}
			FVector Step = Goal - CircleCenter;
			Step.Z = 0.f;
			const float MaxStep = CircleChaseSpeed * RealDelta;
			if (Step.Size() > MaxStep)
			{
				Step = Step.GetSafeNormal() * MaxStep;
			}
			const FVector Prev = CircleCenter;
			CircleCenter += Step;
			float Z = 0.f;
			if (FindFloorZ(CircleCenter + FVector(0.f, 0.f, 60.f), Z))
			{
				CircleCenter.Z = Z + 3.f;
			}
			for (const TWeakObjectPtr<AActor>& Ring : CircleRings)
			{
				if (Ring.IsValid())
				{
					Ring->SetActorLocation(Ring->GetActorLocation() + (CircleCenter - Prev));
				}
			}
		}
		else if (!bCircleLocked)
		{
			// Locked: a bright flash says "it stops here", then the eruption.
			bCircleLocked = true;
			ABFRingFX::SpawnGround(GetWorld(), CircleCenter + FVector(0.f, 0.f, 2.f), BFCombat::BossMagicPale(), CircleRadius * 2.2f, CircleRadius * 2.f, FMath::Max(0.1f, CircleTimeLeft));
			UE_LOG(LogTemp, Display, TEXT("BFTEST boss magic circle locked moved=%.0f"), FVector::Dist2D(CircleCenter, CircleOrigin));
		}
		if (CircleTimeLeft <= 0.f)
		{
			bCircleActive = false;
			if (CircleVfx)
			{
				UNiagaraFunctionLibrary::SpawnSystemAtLocation(GetWorld(), CircleVfx, CircleCenter, FRotator::ZeroRotator, FVector(CircleRadius / 400.f));
			}
			ABFRingFX::SpawnGround(GetWorld(), CircleCenter + FVector(0.f, 0.f, 2.f), BFCombat::BossMagicHot(), CircleRadius * 1.6f, CircleRadius * 2.4f, 0.35f);
			BFFluxWater::Impact(GetWorld(), CircleCenter, CircleRadius * 0.8f, 2.5f);
			if (CircleSound)
			{
				UGameplayStatics::PlaySoundAtLocation(this, CircleSound, CircleCenter, 1.5f, 0.85f);
			}
			if (Player)
			{
				const float D = FVector::Dist2D(Player->GetActorLocation(), CircleCenter);
				Player->AddCameraShake(8.f, 0.3f, FVector::UpVector, 2.f);
				if (D <= CircleRadius + 20.f && Player->GetActorLocation().Z - CircleCenter.Z < 350.f)
				{
					CircleHit.ImpactPoint = Player->GetActorLocation() - FVector(0.f, 0.f, 40.f);
					const EBFHitResult Result = Player->ResolveEnemyHit(CircleHit, this);
					UE_LOG(LogTemp, Display, TEXT("BFTEST boss magic circle erupt dist=%.0f result=%d"), D, int32(Result));
				}
				else
				{
					UE_LOG(LogTemp, Display, TEXT("BFTEST boss magic circle erupt dist=%.0f missed"), D);
				}
			}
		}
	}
}

void ABFEnemyBase::TickLean(float DeltaSeconds)
{
	if (MaxLeanPitch <= 0.f && MaxLeanRoll <= 0.f)
	{
		return;
	}
	const FVector Loc = GetActorLocation();
	if (!bLeanInit)
	{
		bLeanInit = true;
		LeanPrevLoc = Loc;
		MeshBaseRot = GetMesh()->GetRelativeRotation();
		return;
	}
	const float Dt = FMath::Max(DeltaSeconds, 1e-3f);
	FVector V = (Loc - LeanPrevLoc) / Dt;
	LeanPrevLoc = Loc;
	V.Z = 0.f;
	if (V.Size() > 3000.f || IsDead() || State == EBFEnemyState::Broken)
	{
		V = FVector::ZeroVector; // teleports and collapses: no lean
	}
	const float Fwd = FVector::DotProduct(V, GetActorForwardVector()) / LeanSpeedRef;
	const float Side = FVector::DotProduct(V, GetActorRightVector()) / LeanSpeedRef;
	const float WantPitch = FMath::Clamp(Fwd, -0.6f, 1.f) * MaxLeanPitch;
	const float WantRoll = FMath::Clamp(Side, -1.f, 1.f) * MaxLeanRoll;
	// Quick to lean in, slower to settle back upright.
	LeanPitch = FMath::FInterpTo(LeanPitch, WantPitch, DeltaSeconds, FMath::Abs(WantPitch) > FMath::Abs(LeanPitch) ? 9.f : 4.f);
	LeanRoll = FMath::FInterpTo(LeanRoll, WantRoll, DeltaSeconds, FMath::Abs(WantRoll) > FMath::Abs(LeanRoll) ? 9.f : 4.f);
	// Actor-space tilt (top toward +X for forward, toward +Y for right) about the feet, then the mesh's own offset.
	const FQuat Tilt = FQuat(FVector::RightVector, FMath::DegreesToRadians(LeanPitch)) * FQuat(FVector::ForwardVector, FMath::DegreesToRadians(-LeanRoll));
	GetMesh()->SetRelativeRotation(Tilt * MeshBaseRot.Quaternion());
}

void ABFEnemyBase::LandFromMagic()
{
	if (!bOrbFlying)
	{
		DestroyOrb(); // cast cut short while the orb was still in his claw
	}
	bMagicAir = false;
	MagicStage = 0;
	{
		const FVector Feet = GetActorLocation() - FVector(0.f, 0.f, GetCapsuleComponent()->GetScaledCapsuleHalfHeight());
		BFFluxWater::Impact(GetWorld(), Feet, 220.f, 1.5f);
	}
	if (CastAura)
	{
		CastAura->Deactivate();
		CastAura = nullptr;
	}
	GetCharacterMovement()->SetMovementMode(MOVE_Walking);
}

FVector ABFEnemyBase::OrbHoldLocation() const
{
	// Above the raised claw; without that socket, in front of his chest.
	const float Lift = OrbSize * 0.55f;
	if (GetMesh()->DoesSocketExist(OrbHandSocket))
	{
		return GetMesh()->GetSocketLocation(OrbHandSocket) + FVector(0.f, 0.f, Lift) + GetActorForwardVector() * 25.f;
	}
	return GetActorLocation() + GetActorForwardVector() * 110.f + FVector(0.f, 0.f, GetHalfHeight() * 0.6f + Lift);
}

void ABFEnemyBase::SpawnOrb()
{
	DestroyOrb();
	const FVector At = OrbHoldLocation();
	if (OrbMesh)
	{
		OrbCore = NewObject<UStaticMeshComponent>(this);
		OrbCore->SetUsingAbsoluteLocation(true);
		OrbCore->SetUsingAbsoluteRotation(true);
		OrbCore->SetUsingAbsoluteScale(true);
		OrbCore->SetStaticMesh(OrbMesh);
		OrbCore->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		OrbCore->SetCastShadow(false);
		OrbCore->SetupAttachment(GetRootComponent());
		OrbCore->RegisterComponent();
		if (OrbMaterial)
		{
			OrbMid = UMaterialInstanceDynamic::Create(OrbMaterial, this);
			OrbCore->SetMaterial(0, OrbMid);
		}
	}
	if (OrbFlameVfx)
	{
		OrbFlames = UNiagaraFunctionLibrary::SpawnSystemAtLocation(GetWorld(), OrbFlameVfx, At, FRotator::ZeroRotator, FVector(0.4f), false, true, ENCPoolMethod::None);
	}
	OrbLight = NewObject<UPointLightComponent>(this);
	OrbLight->SetUsingAbsoluteLocation(true);
	OrbLight->SetupAttachment(GetRootComponent());
	OrbLight->SetLightColor(BFCombat::BossMagicColor());
	OrbLight->SetIntensityUnits(ELightUnits::Candelas);
	OrbLight->SetIntensity(0.f);
	OrbLight->SetAttenuationRadius(1100.f);
	OrbLight->SetCastShadows(false);
	OrbLight->RegisterComponent();
	SetOrbTransform(At, OrbSize * 0.2f);
	UE_LOG(LogTemp, Display, TEXT("BFTEST boss magic orb charging socket=%d"), GetMesh()->DoesSocketExist(OrbHandSocket) ? 1 : 0);
}

void ABFEnemyBase::SetOrbTransform(const FVector& At, float Size)
{
	const float K = Size / FMath::Max(OrbSize, 1.f);
	if (OrbCore)
	{
		OrbCore->SetWorldLocation(At);
		OrbCore->SetWorldScale3D(FVector(Size / 100.f)); // engine sphere is 100 cm across
	}
	if (OrbFlames)
	{
		OrbFlames->SetWorldLocation(At);
		OrbFlames->SetWorldScale3D(FVector(1.3f * K));
	}
	if (OrbLight)
	{
		OrbLight->SetWorldLocation(At);
		OrbLight->SetIntensity(140.f * K);
	}
}

void ABFEnemyBase::DestroyOrb()
{
	bOrbFlying = false;
	if (OrbCore)
	{
		OrbCore->DestroyComponent();
		OrbCore = nullptr;
	}
	if (OrbLight)
	{
		OrbLight->DestroyComponent();
		OrbLight = nullptr;
	}
	if (OrbFlames)
	{
		OrbFlames->Deactivate();
		OrbFlames->SetAutoDestroy(true);
		OrbFlames = nullptr;
	}
	OrbMid = nullptr;
}

void ABFEnemyBase::BurstOrb()
{
	const FVector C = OrbTo;
	DestroyOrb();
	if (OrbBurstVfx)
	{
		UNiagaraFunctionLibrary::SpawnSystemAtLocation(GetWorld(), OrbBurstVfx, C, FRotator::ZeroRotator, FVector(OrbRadius / 260.f));
	}
	if (CircleVfx)
	{
		UNiagaraFunctionLibrary::SpawnSystemAtLocation(GetWorld(), CircleVfx, C, FRotator::ZeroRotator, FVector(OrbRadius / 420.f));
	}
	ABFRingFX::SpawnGround(GetWorld(), C + FVector(0.f, 0.f, 3.f), BFCombat::BossMagicHot(), OrbRadius * 0.6f, OrbRadius * 2.8f, 0.45f);
	BFFluxWater::Impact(GetWorld(), C, OrbRadius * 0.7f, 3.f);
	ABFRingFX::SpawnGround(GetWorld(), C + FVector(0.f, 0.f, 4.f), BFCombat::BossMagicPale(), OrbRadius * 1.6f, OrbRadius * 2.2f, 0.3f);
	if (OrbBurstSound)
	{
		UGameplayStatics::PlaySoundAtLocation(this, OrbBurstSound, C, 1.7f, 0.8f);
	}
	ABFPlayerCharacter* Player = GetPlayer();
	if (!Player)
	{
		return;
	}
	const float D = FVector::Dist2D(Player->GetActorLocation(), C);
	Player->AddCameraShake(D < OrbRadius * 2.f ? 13.f : 6.f, 0.4f, FVector::UpVector, 3.f);
	if (D <= OrbRadius + 20.f && Player->GetActorLocation().Z - C.Z < 350.f)
	{
		OrbHit.ImpactPoint = Player->GetActorLocation() - FVector(0.f, 0.f, 40.f);
		const EBFHitResult Result = Player->ResolveEnemyHit(OrbHit, this);
		UE_LOG(LogTemp, Display, TEXT("BFTEST boss magic orb burst dist=%.0f result=%d"), D, int32(Result));
	}
	else
	{
		UE_LOG(LogTemp, Display, TEXT("BFTEST boss magic orb burst dist=%.0f missed"), D);
	}
}

void ABFEnemyBase::TickRuneCircle(float RealDelta)
{
	if (!IsBoss())
	{
		return;
	}
	if (!bRuneInit)
	{
		bRuneInit = true;
		for (TActorIterator<AActor> It(GetWorld()); It; ++It)
		{
			if (It->ActorHasTag(TEXT("BFRuneCircle")))
			{
				RuneActors.Add(*It);
				It->SetActorEnableCollision(false); // it slides around under the boss: it must never push anyone
				TArray<UStaticMeshComponent*> Meshes;
				It->GetComponents(Meshes);
				for (UStaticMeshComponent* M : Meshes)
				{
					if (UMaterialInstanceDynamic* Mid = M->CreateAndSetMaterialInstanceDynamic(0))
					{
						RuneMids.Add(Mid);
					}
				}
			}
			else if (It->ActorHasTag(TEXT("BFRuneLight")))
			{
				TArray<ULightComponent*> Lights;
				It->GetComponents(Lights);
				for (ULightComponent* L : Lights)
				{
					RuneLights.Add({L, L->Intensity});
				}
			}
		}
		UE_LOG(LogTemp, Display, TEXT("BFTEST rune circle found=%d lights=%d"), RuneActors.Num(), RuneLights.Num());
	}
	if (RuneActors.Num() == 0 && RuneLights.Num() == 0)
	{
		return;
	}
	const bool bShow = bMagicAir || bLineActive || bCircleActive || bOrbFlying;
	// Flares up fast, fades out slowly.
	RuneReveal = FMath::FInterpConstantTo(RuneReveal, bShow ? 1.f : 0.f, RealDelta, bShow ? 2.5f : 0.8f);
	const float Glow = FMath::SmoothStep(0.f, 1.f, RuneReveal);
	// The circle follows the boss on the floor: only X and Y track him (the user asked for that), its height stays
	// where the level put it. It glides after him while lit and jumps straight under him while hidden.
	{
		const FVector Me = GetActorLocation();
		const FVector Now = RuneActors.Num() > 0 && RuneActors[0].IsValid() ? RuneActors[0]->GetActorLocation() : FVector(Me.X, Me.Y, 0.f);
		const FVector Target(Me.X, Me.Y, Now.Z);
		const FVector At = Glow <= 0.001f ? Target : FMath::VInterpTo(Now, Target, RealDelta, 10.f);
		const FVector Delta(At.X - Now.X, At.Y - Now.Y, 0.f);
		for (const TWeakObjectPtr<AActor>& A : RuneActors)
		{
			if (A.IsValid())
			{
				A->SetActorLocation(A->GetActorLocation() + Delta);
			}
		}
		for (const TPair<TWeakObjectPtr<ULightComponent>, float>& L : RuneLights)
		{
			if (L.Key.IsValid() && L.Key->GetOwner())
			{
				L.Key->GetOwner()->SetActorLocation(L.Key->GetOwner()->GetActorLocation() + Delta);
			}
		}
	}
	for (UMaterialInstanceDynamic* Mid : RuneMids)
	{
		if (Mid)
		{
			Mid->SetScalarParameterValue(TEXT("Reveal"), Glow * RuneMaxGlow);
		}
	}
	for (const TPair<TWeakObjectPtr<ULightComponent>, float>& L : RuneLights)
	{
		if (L.Key.IsValid())
		{
			L.Key->SetIntensity(L.Value * Glow * RuneMaxGlow);
			L.Key->SetVisibility(Glow > 0.001f);
		}
	}
	for (const TWeakObjectPtr<AActor>& A : RuneActors)
	{
		if (A.IsValid())
		{
			A->SetActorHiddenInGame(Glow <= 0.001f);
		}
	}
}
