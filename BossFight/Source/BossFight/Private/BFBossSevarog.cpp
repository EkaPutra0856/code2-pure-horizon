#include "BFBossSevarog.h"

#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"

#include "Sound/SoundBase.h"
#include "BFAnimInstance.h"

#include "Animation/AnimInstance.h"
#include "Animation/AnimSequence.h"
#include "Components/CapsuleComponent.h"
#include "Components/StaticMeshComponent.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "NiagaraSystem.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	const TCHAR* SevarogRoot = TEXT("/Game/ParagonSevarog/Characters/Heroes/Sevarog/");

	FString SevarogAnimPath(const TCHAR* Name)
	{
		return FString::Printf(TEXT("%sAnimations/%s.%s"), SevarogRoot, Name, Name);
	}

	UAnimSequence* FindSevarogAnim(const TCHAR* Name)
	{
		ConstructorHelpers::FObjectFinder<UAnimSequence> Finder(*SevarogAnimPath(Name));
		return Finder.Succeeded() ? Finder.Object : nullptr;
	}

	// AnimPath must outlive the attack table, so the full paths are static strings.
	FBFEnemyAttack MakeBossAttack(const TCHAR* Path, float Rate, float Start, float End, float Range, float Damage, float Posture, bool bHeavy)
	{
		FBFEnemyAttack A;
		A.AnimPath = Path;
		A.PlayRate = Rate;
		A.HitStart = Start;
		A.HitEnd = End;
		A.Range = Range;
		A.HalfAngleDeg = 60.f;
		A.Damage = Damage;
		A.PostureDamage = Posture;
		A.bHeavy = bHeavy;
		return A;
	}
}

ABFBossSevarog::ABFBossSevarog()
{
	// Paragon Sevarog stands ~2.9 m; the hammer is part of the skeletal mesh.
	GetCapsuleComponent()->InitCapsuleSize(62.f, 145.f);
	GetMesh()->SetRelativeLocationAndRotation(FVector(0.f, 0.f, -145.f), FRotator(0.f, -90.f, 0.f));

	static ConstructorHelpers::FObjectFinder<USkeletalMesh> MeshFinder(TEXT("/Game/ParagonSevarog/Characters/Heroes/Sevarog/Meshes/Sevarog.Sevarog"));
	if (MeshFinder.Succeeded())
	{
		GetMesh()->SetSkeletalMesh(MeshFinder.Object);
	}
	// Locomotion + DefaultSlot (ABP_Sevarog, built by BFEditorTools::BuildSevarogAnimBlueprint) is loaded in
	// PostInitializeComponents: loading it here, during module startup, ran before the BossFightAnimGraph
	// module registered the cloth sway graph node, and the ABP came up broken (frozen pose).
	Weapon->SetStaticMesh(nullptr);
	Weapon->SetVisibility(false);
	WeaponTipBone = TEXT("root_weapon_end_r");

	HitFrontAnim = FindSevarogAnim(TEXT("Hitreact_Front"));
	HitLeftAnim = FindSevarogAnim(TEXT("Hitreact_Left"));
	HitRightAnim = FindSevarogAnim(TEXT("Hitreact_Right"));
	KnockdownAnim = FindSevarogAnim(TEXT("Knock_back"));
	GetUpAnim = FindSevarogAnim(TEXT("Stun_End"));
	DeathAnim = FindSevarogAnim(TEXT("Death_front"));
	BrokenAnim = FindSevarogAnim(TEXT("Stun_Start"));
	BrokenLoopAnim = FindSevarogAnim(TEXT("Stun_Loop"));
	BrokenEndAnim = FindSevarogAnim(TEXT("Stun_End"));
	HitBackAnim = FindSevarogAnim(TEXT("Hitreact_Back"));
	// Knock_back is a sideways flailing loop meant for ability knockbacks, not a fall: the boss
	// never goes down. Finishers stagger him, deathblows double him over (Hitreact_Back).
	bCanBeKnockedDown = false;
	HeavyKnockdownAnim = nullptr;
	DownLoopAnim = nullptr;

	// Hit windows from the hammer head's speed (Scripts/19_sevarog_probe.py, root_weapon_end_r).
	// The Paragon swings are one spinning combo: Swing1 ends where Swing2 starts and Swing2 ends where
	// Swing3 starts (pose gaps 7 / 4 cm, Scripts/27_sevarog_join_probe.py), and each starts from a
	// wound-up pose turned ~100 deg away from Idle. Played alone and blended straight back to idle,
	// the body spun 100-170 deg in a fraction of a second. Now: slower blend into the wind-up, combo
	// swings chain end-to-start, and every exit runs the matching Return2Idle clip from the frame that
	// continues the swing's end pose (Swing1 -> Swing1_Return2Idle_120fps @0.21 s, 1.8 cm;
	// Swing3 -> Swing3_Return2Idle @0.52 s, 2.2 cm).
	static const FString Swing1 = SevarogAnimPath(TEXT("Swing1_Slow"));
	static const FString Swing2 = SevarogAnimPath(TEXT("Swing2_Slow"));
	static const FString Swing3 = SevarogAnimPath(TEXT("Swing3_Slow"));
	static const FString Slam = SevarogAnimPath(TEXT("Ultimate_Swing_120fps"));
	static const FString Swing1Back = SevarogAnimPath(TEXT("Swing1_Return2Idle_120fps"));
	static const FString Swing3Back = SevarogAnimPath(TEXT("Swing3_Return2Idle"));
	auto Recover = [](FBFEnemyAttack A, const FString& Path, float Start, float Rate)
	{
		A.RecoverPath = *Path;
		A.RecoverStart = Start;
		A.RecoverRate = Rate;
		return A;
	};
	auto Chain = [](FBFEnemyAttack A, int32 Next, bool bOnly)
	{
		A.ChainNext = Next;
		A.bChainOnly = bOnly;
		return A;
	};
	FBFEnemyAttack S1 = MakeBossAttack(*Swing1, 1.0f, 0.33f, 0.56f, 340.f, 20.f, 25.f, false);
	FBFEnemyAttack S2 = MakeBossAttack(*Swing2, 1.0f, 0.37f, 0.60f, 340.f, 22.f, 28.f, false);
	FBFEnemyAttack S3 = MakeBossAttack(*Swing3, 1.0f, 0.43f, 0.60f, 340.f, 25.f, 30.f, false);
	// Big overhead slam: parrying it locks blades into a strength clash. Starts and ends near Idle.
	FBFEnemyAttack Big = MakeBossAttack(*Slam, 0.9f, 0.63f, 1.00f, 400.f, 35.f, 45.f, true);
	S1.BlendIn = S3.BlendIn = Big.BlendIn = 0.3f;
	Big.BlendOut = 0.35f;

	// The clips swing in place: motion warp slides him in during the wind-up (bounded), so a swing
	// started at the edge of reach still connects unless the player keeps backing off.
	auto Warp = [](FBFEnemyAttack A, float Dist, float Stop, float Speed, float From = 0.f)
	{
		A.WarpDist = Dist;
		A.WarpStop = Stop;
		A.WarpSpeed = Speed;
		A.WarpFrom = From;
		return A;
	};
	// Delayed wind-up: freeze on the raised weapon for a random beat (~0.22 s of swing left after it).
	// Heavy slams hold earlier (0.5 s left) so their "parry / roll now" cue still comes after the
	// hold with a human reaction time to spare.
	auto Delay = [](FBFEnemyAttack A, float Chance, float Min, float Max)
	{
		A.HoldAt = FMath::Max(0.02f, A.HitStart - (A.bHeavy ? 0.5f : 0.22f) * A.PlayRate);
		A.HoldChance = Chance;
		A.HoldMin = Min;
		A.HoldMax = Max;
		A.bAntiRoll = true;
		return A;
	};
	auto Pick = [](FBFEnemyAttack A, float MinDist, float MaxDist, float Weight, float Phase2Weight = 1.f, int32 MinPhase = 1)
	{
		A.MinDist = MinDist;
		A.MaxDist = MaxDist;
		A.Weight = Weight;
		A.Phase2Weight = Phase2Weight;
		A.MinPhase = MinPhase;
		return A;
	};

	// Perilous moves (Sekiro): coloured warning, guard does not stop them.
	static const FString Siphon = SevarogAnimPath(TEXT("Soul_Siphon"));
	static const FString Subjugate = SevarogAnimPath(TEXT("Subjugation"));
	static const FString Burst = SevarogAnimPath(TEXT("Speedburst"));
	static const FString AirSwing = SevarogAnimPath(TEXT("Swing_In_Air_120fps"));
	// Grab: Soul_Siphon reaches out at 0.10-0.30 s, then pulls back and drains (to 1.07 s). Its wind-up
	// is a fixed 0.75-0.95 s creep on the reaching claw while he glides in. Only a roll escapes.
	FBFEnemyAttack Grab = MakeBossAttack(*Siphon, 0.9f, 0.08f, 0.30f, 330.f, 30.f, 0.f, false);
	Grab.Perilous = EBFPerilous::Grab;
	Grab.HalfAngleDeg = 45.f;
	Grab.HoldAt = 0.02f;
	Grab.HoldChance = 1.f;
	Grab.HoldMin = 0.75f;
	Grab.HoldMax = 0.95f;
	Grab.BlendIn = 0.3f;
	Grab.BlendOut = 0.35f;
	// Sweep: Subjugation plants the hammer at 0.93 s; a ground wave rolls out from it (jump it). The
	// hammer stays planted until ~1.9 s: a long opening for whoever cleared the wave.
	FBFEnemyAttack Sweep = MakeBossAttack(*Subjugate, 1.f, 0.93f, 1.0f, 900.f, 24.f, 30.f, false);
	Sweep.Perilous = EBFPerilous::Sweep;
	Sweep.bGroundWave = true;
	Sweep.WaveSpeed = 950.f;
	Sweep.WaveRange = 900.f;
	Sweep.BlendIn = 0.3f;
	// Thrust: Speedburst is a forward lean with the hammer's spike leading; gathered for a beat, then a
	// fast lunge (warp from 0.2 s) that ends on the player. Dodge INTO it (mikiri) or parry it.
	FBFEnemyAttack Thrust = MakeBossAttack(*Burst, 0.7f, 0.42f, 0.85f, 260.f, 26.f, 30.f, false);
	Thrust.Perilous = EBFPerilous::Thrust;
	Thrust.HalfAngleDeg = 35.f;
	Thrust.HoldAt = 0.15f;
	Thrust.HoldChance = 1.f;
	Thrust.HoldMin = 0.25f;
	Thrust.HoldMax = 0.4f;
	Thrust.BlendIn = 0.25f;
	Thrust.BlendOut = 0.4f;
	// Phase 2: leaping overhead strike (also opens every glide-in).
	FBFEnemyAttack Air = MakeBossAttack(*AirSwing, 1.f, 0.20f, 0.47f, 360.f, 28.f, 32.f, false);
	Air.BlendIn = 0.2f;
	// Spells (Cast: arms rise 0.19-0.56 s, thrown forward 0.75-0.93 s). He floats up out of reach,
	// holds the charge pose, releases at 0.8 s and drifts back down. Picked at range; phase 2 casts
	// more often and its hits knock the player up.
	static const FString CastClip = SevarogAnimPath(TEXT("Cast"));
	FBFEnemyAttack FireLine = MakeBossAttack(*CastClip, 0.85f, 0.f, 0.f, 0.f, 22.f, 0.f, false);
	FireLine.Magic = EBFMagic::FireLine;
	FireLine.ChargeTime = 0.8f;
	FireLine.RiseHeight = 330.f;
	FireLine.BlendIn = 0.25f;
	FireLine.BlendOut = 0.35f;
	FBFEnemyAttack Circle = FireLine;
	Circle.Magic = EBFMagic::Circle;
	Circle.Damage = 26.f;
	Circle.ChargeTime = 0.6f;
	// Green energy orb: grows in his claw over a longer charge, thrown at the player's spot, bursts over an area.
	FBFEnemyAttack Orb = FireLine;
	Orb.Magic = EBFMagic::Orb;
	Orb.Damage = 30.f;
	Orb.ChargeTime = 1.1f;
	Orb.RiseHeight = 360.f;

	SetAttacks({
		/* 0 */ Pick(Delay(Warp(Recover(S1, Swing1Back, 0.21f, 1.2f), 220.f, 200.f, 650.f), 0.25f, 0.3f, 0.6f), 0.f, 470.f, 1.f),
		/* 1 */ Pick(Warp(Chain(S1, 4, false), 220.f, 200.f, 650.f), 0.f, 450.f, 1.2f, 1.3f), // three-hit combo opener
		/* 2 */ Pick(Delay(Warp(Big, 300.f, 230.f, 700.f), 0.35f, 0.3f, 0.7f), 0.f, 560.f, 0.8f),
		/* 3 */ Pick(Delay(Warp(Recover(S3, Swing3Back, 0.52f, 1.f), 220.f, 200.f, 650.f), 0.3f, 0.3f, 0.6f), 0.f, 450.f, 0.8f),
		/* 4 */ Chain(S2, 5, true),
		/* 5 */ Chain(Recover(S3, Swing3Back, 0.52f, 1.f), INDEX_NONE, true),
		/* 6 */ Pick(Warp(Grab, 260.f, 170.f, 650.f), 0.f, 450.f, 0.55f, 2.f),
		/* 7 */ Pick(Sweep, 0.f, 650.f, 0.6f, 1.2f),
		/* 8 */ Pick(Warp(Thrust, 520.f, 110.f, 1600.f, 0.2f), 250.f, 760.f, 0.7f, 1.2f),
		/* 9 */ Pick(Delay(Warp(Air, 450.f, 190.f, 1100.f), 0.4f, 0.25f, 0.5f), 200.f, 700.f, 1.f, 1.f, 2),
		/* 10 */ Pick(FireLine, 450.f, 1700.f, 0.9f, 1.7f),
		/* 11 */ Pick(Circle, 450.f, 1700.f, 0.8f, 1.7f),
		/* 12 */ Pick(Orb, 450.f, 1900.f, 0.9f, 1.8f),
	});

	// Turn on the spot (stepping clips, actor yaw eased in code) and the backstep glide.
	TurnLeftAnim = FindSevarogAnim(TEXT("Turn_Lt_90"));
	TurnRightAnim = FindSevarogAnim(TEXT("Turn_Rt_90"));
	TurnLeft180Anim = FindSevarogAnim(TEXT("Turn_Lt_180"));
	TurnRight180Anim = FindSevarogAnim(TEXT("Turn_Rt_180"));
	BackstepAnim = FindSevarogAnim(TEXT("Travel_Mode_Bwd_Start"));
	// Spell flight: gathers power while lifting off, hovers in the charge pose (claw raised, cape flared),
	// throws with the Cast clip, then hangs in travel-mode hover while gliding back down.
	MagicRiseAnim = FindSevarogAnim(TEXT("Ultimate_Targeting"));
	MagicChargeAnim = FindSevarogAnim(TEXT("Ultimate_Targeting_Loop"));
	MagicHoverAnim = FindSevarogAnim(TEXT("Travel_Mode_Idle"));
	MaxStance = 120.f;
	// He floats: lean into glides and lunges like a flying body, not a statue on rails.
	MaxLeanPitch = 11.f;
	MaxLeanRoll = 6.f;

	// Purple night-flame spells (MagicKit); sounds are the pack's raw waves (its cues point at a missing pack).
	static ConstructorHelpers::FObjectFinder<UNiagaraSystem> LineFx(TEXT("/Game/MagicKit/Particles/NightFlame/NS_NightFlame_Impact_02.NS_NightFlame_Impact_02"));
	static ConstructorHelpers::FObjectFinder<UNiagaraSystem> CircleFx(TEXT("/Game/MagicKit/Particles/NightFlame/NS_NightFlame_Special_01.NS_NightFlame_Special_01"));
	static ConstructorHelpers::FObjectFinder<UNiagaraSystem> AuraFx(TEXT("/Game/MagicKit/Particles/NightFlame/NS_NightFlame_Defense_01.NS_NightFlame_Defense_01"));
	static ConstructorHelpers::FObjectFinder<USoundBase> ChargeSfx(TEXT("/Game/Casting___Loops/wav/Field_2_Start.Field_2_Start"));
	static ConstructorHelpers::FObjectFinder<USoundBase> LineSfx(TEXT("/Game/Elements___School/Fire/wav/Fire_Spell_10.Fire_Spell_10"));
	static ConstructorHelpers::FObjectFinder<USoundBase> CircleSfx(TEXT("/Game/Elements___School/Fire/wav/Fire_Spell_3.Fire_Spell_3"));
	FireLineVfx = LineFx.Succeeded() ? LineFx.Object : nullptr;
	CircleVfx = CircleFx.Succeeded() ? CircleFx.Object : nullptr;
	CastAuraVfx = AuraFx.Succeeded() ? AuraFx.Object : nullptr;
	CastChargeSound = ChargeSfx.Succeeded() ? ChargeSfx.Object : nullptr;
	FireLineSound = LineSfx.Succeeded() ? LineSfx.Object : nullptr;
	CircleSound = CircleSfx.Succeeded() ? CircleSfx.Object : nullptr;
	static ConstructorHelpers::FObjectFinder<UStaticMesh> OrbSphere(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> OrbMat(TEXT("/Game/BossFight/FX/M_BossOrb.M_BossOrb"));
	static ConstructorHelpers::FObjectFinder<UNiagaraSystem> OrbFlameFx(TEXT("/Game/MagicKit/Particles/NightFlame/NS_NightFlame_Attack_LVL_02.NS_NightFlame_Attack_LVL_02"));
	static ConstructorHelpers::FObjectFinder<UNiagaraSystem> OrbBurstFx(TEXT("/Game/MagicKit/Particles/NightFlame/NS_NightFlame_Impact_03.NS_NightFlame_Impact_03"));
	static ConstructorHelpers::FObjectFinder<USoundBase> OrbThrowSfx(TEXT("/Game/Elements___School/Arcane/wav/Arcane_Spell_11.Arcane_Spell_11"));
	static ConstructorHelpers::FObjectFinder<USoundBase> OrbBurstSfx(TEXT("/Game/Elements___School/Fire/wav/Fire_Spell_15.Fire_Spell_15"));
	OrbMesh = OrbSphere.Succeeded() ? OrbSphere.Object : nullptr;
	OrbMaterial = OrbMat.Succeeded() ? OrbMat.Object : nullptr;
	OrbFlameVfx = OrbFlameFx.Succeeded() ? OrbFlameFx.Object : nullptr;
	OrbBurstVfx = OrbBurstFx.Succeeded() ? OrbBurstFx.Object : nullptr;
	OrbThrowSound = OrbThrowSfx.Succeeded() ? OrbThrowSfx.Object : nullptr;
	OrbBurstSound = OrbBurstSfx.Succeeded() ? OrbBurstSfx.Object : nullptr;

	// Phase 2 below half health: leap-and-land roar (LevelStart from the hammer pick-up: rises, leaps,
	// lands at ~3.65 s with a shockwave), then faster, grabs twice as often, Swing_In_Air, and
	// Travel_Mode glides in from afar into that leaping strike.
	bHasPhase2 = true;
	bWeightedAttackPick = true;
	TransitionAnim = FindSevarogAnim(TEXT("LevelStart"));
	TransitionStart = 2.3f;
	TransitionImpact = 3.65f;
	TransitionRate = 1.f;
	Phase2Cooldown = 1.1f;
	Phase2SpeedScale = 1.25f;
	TravelStartAnim = FindSevarogAnim(TEXT("Travel_Mode_Start"));
	TravelLoopAnim = FindSevarogAnim(TEXT("Travel_Mode_Idle"));
	TravelArriveAttack = 9;
	TravelSpeed = 950.f;
	TravelMinDist = 850.f;
	TravelArriveDist = 420.f;
	bCircleStrafe = true;

	Rank = EBFEnemyRank::Boss;
	ClashPush = 0.4f;
	DisplayName = TEXT("Sevarog");
	MaxHealth = 900.f;
	MaxPosture = 150.f;
	PostureRegenRate = 8.f;
	BrokenDuration = 4.f;
	RespawnDelay = 5.f;
	EngageRange = 430.f;
	ChaseDistance = 300.f;
	AttackCooldown = 1.6f;
	bSuperArmor = true;
	HitReactRate = 1.6f;
	ParryRecoilRate = 1.3f;
	ParryRecoilLaunch = 160.f;
	// Huge body: small flinch and shove; the slam cracks a wide patch of ground.
	ImpactScale = 0.6f;
	SlamScale = 2.f;
	static ConstructorHelpers::FObjectFinder<USoundBase> HammerWhoosh(TEXT("/Game/SlashHitVFX/__GenericSource/SFX/Sfx_Weapon_Hammer_Cue.Sfx_Weapon_Hammer_Cue"));
	static ConstructorHelpers::FObjectFinder<USoundBase> HammerWhoosh2(TEXT("/Game/SlashHitVFX/__GenericSource/SFX/Sfx_Weapon_Hammer2Cue.Sfx_Weapon_Hammer2Cue"));
	if (HammerWhoosh.Succeeded())
	{
		EnemySwingSound = HammerWhoosh.Object;
	}
	if (HammerWhoosh2.Succeeded())
	{
		HeavySwingSound = HammerWhoosh2.Object;
	}

	GetCharacterMovement()->MaxWalkSpeed = 260.f;

	AuraShell = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("AuraShell"));
	AuraShell->SetupAttachment(GetMesh());
	AuraShell->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	AuraShell->SetCastShadow(false);
	AuraShell->SetGenerateOverlapEvents(false);
	AuraShell->bReceivesDecals = false;
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> AuraFinder(TEXT("/Game/BossFight/FX/M_BossAura.M_BossAura")); // Scripts/36_build_smear_aura.py
	if (AuraFinder.Succeeded())
	{
		AuraMaterial = AuraFinder.Object;
	}
	PrimaryActorTick.bCanEverTick = true;
}

void ABFBossSevarog::PostInitializeComponents()
{
	Super::PostInitializeComponents();
	if (!SevarogAnimClass)
	{
		SevarogAnimClass = LoadClass<UAnimInstance>(nullptr, TEXT("/Game/BossFight/Anim/ABP_Sevarog.ABP_Sevarog_C"));
	}
	if (SevarogAnimClass && GetMesh()->GetAnimClass() != SevarogAnimClass)
	{
		UE_LOG(LogTemp, Display, TEXT("BFTEST sevarog anim class override %s -> %s"), GetMesh()->GetAnimClass() ? *GetMesh()->GetAnimClass()->GetName() : TEXT("none"), *SevarogAnimClass->GetName());
		GetMesh()->SetAnimInstanceClass(SevarogAnimClass);
	}
}

void ABFBossSevarog::BeginPlay()
{
	Super::BeginPlay();
	if (UBFAnimInstance* Anim = Cast<UBFAnimInstance>(GetMesh()->GetAnimInstance()))
	{
		float Roll = HeadLift.Roll;
		FParse::Value(FCommandLine::Get(), TEXT("BFHeadLift="), Roll); // test override
		Anim->HeadLift = FRotator(HeadLift.Pitch, HeadLift.Yaw, Roll);
	}

	if (AuraShell)
	{
		if (AuraMaterial && GetMesh()->GetSkeletalMeshAsset())
		{
			AuraShell->SetSkeletalMesh(GetMesh()->GetSkeletalMeshAsset());
			AuraShell->SetLeaderPoseComponent(GetMesh());
			AuraMid = UMaterialInstanceDynamic::Create(AuraMaterial, this);
			for (int32 I = 0; I < AuraShell->GetNumMaterials(); ++I)
			{
				AuraShell->SetMaterial(I, AuraMid);
			}
		}
		else
		{
			AuraShell->SetVisibility(false);
		}
	}
}

void ABFBossSevarog::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (!AuraMid)
	{
		return;
	}
	// Fades out fast when his posture breaks (or he dies), back in slowly once he recovers.
	const bool bOn = !IsBroken() && !IsDead();
	const float Prev = AuraFade;
	AuraFade = FMath::FInterpConstantTo(AuraFade, bOn ? 1.f : 0.f, DeltaSeconds, bOn ? 1.2f : 4.f);
	if (AuraFade != Prev)
	{
		AuraMid->SetScalarParameterValue(TEXT("Fade"), AuraFade);
	}
	AuraShell->SetVisibility(AuraFade > 0.01f);
	AuraLogTimer += DeltaSeconds;
	if (AuraLogTimer >= 0.5f)
	{
		AuraLogTimer = 0.f;
		UE_LOG(LogTemp, Display, TEXT("BFAURA fade=%.2f broken=%d dead=%d"), AuraFade, IsBroken() ? 1 : 0, IsDead() ? 1 : 0);
	}
}
