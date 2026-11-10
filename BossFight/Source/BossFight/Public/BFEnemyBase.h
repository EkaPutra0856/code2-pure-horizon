#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "BFCombatTypes.h"
#include "BFEnemyBase.generated.h"

class UAnimSequence;
class UAnimMontage;
class UStaticMeshComponent;
class ABFPlayerCharacter;
class UBFHitFlashComponent;
class UNiagaraSystem;
class UNiagaraComponent;
class USoundBase;
class UStaticMesh;
class UMaterialInterface;
class UMaterialInstanceDynamic;
class UPointLightComponent;

/** Minion = humanoid grunt (knocked flying by a lost clash); Boss = holds its ground, only takes damage. */
UENUM()
enum class EBFEnemyRank : uint8
{
	Minion,
	Boss,
};

UENUM()
enum class EBFEnemyState : uint8
{
	Normal,
	Attacking,
	Stagger,
	Down,
	/** Posture broken: kneels, open to an execution. */
	Broken,
	Dead,
	/** Boss phase change (roar / mini-cutscene): untouchable, no attacks. */
	Transition,
};

/**
 * Base for anything the player's sword can hit. Phase 2-3 uses it as a training dummy
 * (mannequin with a sword, regenerates after death, swings at the player so parry can be
 * practised); the Sevarog boss will derive from it later.
 */
UCLASS()
class BOSSFIGHT_API ABFEnemyBase : public ACharacter
{
	GENERATED_BODY()

public:
	ABFEnemyBase();

	/** Applies damage, posture, hit reaction. Returns false if the hit was ignored. */
	virtual bool ReceiveHit(const FBFHitInfo& Hit);

	/** Deathblow on a posture-broken enemy: heavy damage, posture reset, knockdown. */
	virtual void ReceiveExecution(AActor* By);

	/** The player deflected this enemy's swing: recoil and take posture damage. */
	virtual void OnParried(AActor* By);

	/** Hit pause: slows this actor to Dilation for a short real-time duration, easing back out. */
	void ApplyHitstop(float Duration, float Dilation = BFCombat::HitPauseDilation);
	void EndHitstop();

	/** Strength clash after a parried heavy attack: the player won it. */
	virtual void OnClashLost(AActor* By);
	/** Strength clash: the enemy won it; its swing follows through. */
	virtual void OnClashWon(AActor* By);

	bool IsBoss() const { return Rank == EBFEnemyRank::Boss; }
	/** How fast this enemy pushes the clash bar toward its side (bar units per real second). */
	float GetClashPush() const { return ClashPush; }

	float GetHealth() const { return Health; }
	float GetMaxHealth() const { return MaxHealth; }
	float GetPosture() const { return Posture; }
	float GetMaxPosture() const { return MaxPosture; }
	bool IsDead() const { return State == EBFEnemyState::Dead; }
	/** 0 alive .. 1 dead a moment: the cloth sway node drops its shape-keeping so the robe drapes. */
	float GetClothLoose() const { return DeathLoose; }
	/** 0..1 after he lands dead: the cloth node lowers raised arms to the floor. */
	float GetDeathSettle() const { return DeathSettle; }
	/** World Z of the floor under him (bottom of the capsule). */
	float GetFloorZ() const;
	bool IsBroken() const { return State == EBFEnemyState::Broken; }
	bool IsStaggered() const { return State == EBFEnemyState::Stagger; }
	/** Recordings: no new attack for at least this many seconds. */
	void HoldAttacks(float Seconds) { CooldownLeft = FMath::Max(CooldownLeft, Seconds); }
	bool IsAttacking() const { return State == EBFEnemyState::Attacking; }
	EBFEnemyState GetState() const { return State; }
	const FString& GetDisplayName() const { return DisplayName; }

	/** Real seconds until the current swing can connect; negative when not winding up. */
	float GetTimeToHit() const;
	/** Normal swings play the end of their wind-up slowed: speed factor at Pos, and real time left to HitStart. */
	static float WindupRateAt(const struct FBFEnemyAttack& A, float Pos);
	static float WindupTimeLeft(const struct FBFEnemyAttack& A, float Pos);

	/** Number of attacks started so far (tests use it to script responses). */
	int32 GetAttackCount() const { return AttackCount; }
	/** The last ReceiveHit landed on armor (attacking or super armor): damage only, no stagger. */
	bool WasLastHitArmored() const { return bLastHitArmored; }

	/** Procedural upper-body flinch away from PushDir plus a white body flash. */
	void PlayImpactFeedback(const FVector& PushDir, float FlinchStrength, float FlashTime);

	/** Tests: stop the AI and play a clip, holding its last frame. Returns the clip length. */
	float DebugPlayAnim(UAnimSequence* Anim, float Rate);
	/** Gallery: run attack Index through the real attack path at half speed, keeping the given facing. Returns its clip time (unscaled). */
	float DebugStartAttack(int32 Index, float Yaw);
	bool bDebugFreezeFacing = false;
	float DebugGetMontagePosition() const;

	bool IsCurrentAttackHeavy() const { return State == EBFEnemyState::Attacking && Attacks.IsValidIndex(CurrentAttack) && Attacks[CurrentAttack].bHeavy; }
	/** Real time the current heavy swing flashed its "parry now" cue; negative before it has. */
	double GetParryCueTime() const { return ParryCueTime; }

	/** Perilous move being telegraphed or swung (or a ground wave still rolling); None otherwise. */
	EBFPerilous GetPerilous() const;
	/** Real seconds since the current perilous telegraph started. */
	float GetPerilousAge() const;
	/** Caught in an opening (attack recovery, whiffed perilous move): hits deal PunishDamageScale. */
	bool IsPunishable() const;
	/** The last ReceiveHit landed during an opening. */
	bool WasLastHitPunish() const { return bLastHitPunish; }
	/** Height above the capsule centre the lock-on camera and reticle aim at. */
	float GetLockHeight() const;
	float GetHalfHeight() const;
	int32 GetPhase() const { return Phase; }
	bool HasPhase2() const { return bHasPhase2; }
	bool IsInTransition() const { return State == EBFEnemyState::Transition; }
	/** Player jumped this enemy's ground wave and landed on its head. */
	void OnStomped(AActor* By, float Damage, float PostureDamage);
	/** Player dodged into this enemy's thrust (mikiri counter). */
	void OnMikiri(AActor* By);
	/** Perilous grab drained the player: heal by Amount. */
	void OnSiphonDrain(float Amount);
	/** Tests: active ground wave (centre, radius); radius < 0 when none. */
	float GetWaveRadius() const { return bWaveActive ? WaveRadius : -1.f; }
	/** Floating out of reach while casting a spell: sword hits pass under him. */
	bool IsMagicAirborne() const { return bMagicAir; }
	/** A spell is being cast or its fire line / eruption is still on its way. */
	bool HasMagicPending() const { return bMagicAir || bLineActive || bCircleActive || bOrbFlying; }
	/** Turning on the spot with a step clip (tests). */
	bool IsTurningInPlace() const { return bTurning; }
	bool IsBackstepping() const { return bBackstepping; }
	float GetStance() const { return Stance; }
	float GetMaxStance() const { return MaxStance; }

	/** Training dummy swings at the player when in range. */
	UPROPERTY(EditAnywhere, Category = "AI")
	bool bAutoAttack = true;

protected:
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	UPROPERTY(EditAnywhere, Category = "Combat")
	float MaxHealth = 300.f;

	UPROPERTY(EditAnywhere, Category = "Combat")
	float MaxPosture = 100.f;

	/** Posture drains at this rate (per second) once no posture damage landed for PostureRegenDelay. */
	UPROPERTY(EditAnywhere, Category = "Combat")
	float PostureRegenRate = 6.f;

	UPROPERTY(EditAnywhere, Category = "Combat")
	float PostureRegenDelay = 2.5f;

	/** How long a posture break keeps the enemy kneeling. */
	UPROPERTY(EditAnywhere, Category = "Combat")
	float BrokenDuration = 3.5f;

	/** Training dummy: refill health this many seconds after dying. Zero disables. */
	UPROPERTY(EditAnywhere, Category = "Combat")
	float RespawnDelay = 3.f;

	/** Starts an attack when the player is within this distance. */
	UPROPERTY(EditAnywhere, Category = "AI")
	float EngageRange = 380.f;

	UPROPERTY(EditAnywhere, Category = "AI")
	float AttackCooldown = 1.8f;

	UPROPERTY(EditAnywhere, Category = "Combat")
	EBFEnemyRank Rank = EBFEnemyRank::Minion;

	/** Clash bar push per real second; the player gains a fixed amount per guard press. */
	UPROPERTY(EditAnywhere, Category = "Combat")
	float ClashPush = 0.3f;

	UPROPERTY(EditAnywhere, Category = "AI")
	FString DisplayName = TEXT("Training Dummy");

	UPROPERTY(VisibleAnywhere, Category = "Weapon")
	TObjectPtr<UStaticMeshComponent> Weapon;

	UPROPERTY(VisibleAnywhere, Category = "Impact")
	TObjectPtr<UBFHitFlashComponent> HitFlash;

	/** Heavy attacks crack the ground where the weapon lands (scale of the crack FX). */
	UPROPERTY(EditAnywhere, Category = "Impact")
	float SlamScale = 1.2f;

	/** Bosses barely move from hits; flinch and knockback are scaled by this. */
	UPROPERTY(EditAnywhere, Category = "Impact")
	float ImpactScale = 1.f;

	UPROPERTY()
	TObjectPtr<UNiagaraSystem> SlamVfx;
	UPROPERTY()
	TObjectPtr<USoundBase> SlamSound;
	UPROPERTY()
	TObjectPtr<USoundBase> EnemySwingSound;
	UPROPERTY()
	TObjectPtr<USoundBase> HeavySwingSound;
	/** Metallic ring on a heavy swing's "parry / roll now" cue. */
	UPROPERTY()
	TObjectPtr<USoundBase> ParryCueSound;
	UPROPERTY()
	TObjectPtr<USoundBase> PerilousSound;

	UPROPERTY(VisibleInstanceOnly, Category = "Combat")
	float Health = 0.f;

	UPROPERTY(VisibleInstanceOnly, Category = "Combat")
	float Posture = 0.f;

	UPROPERTY(VisibleInstanceOnly, Category = "Combat")
	EBFEnemyState State = EBFEnemyState::Normal;

	/** Walks toward the player while farther than this. */
	UPROPERTY(EditAnywhere, Category = "AI")
	float ChaseDistance = 230.f;

	/** Bone or socket at the weapon's striking end; None uses the Weapon static mesh bounds. */
	UPROPERTY(EditAnywhere, Category = "Weapon")
	FName WeaponTipBone = NAME_None;

	/** Super armor: only finisher hits make it flinch (bosses). */
	UPROPERTY(EditAnywhere, Category = "Combat")
	bool bSuperArmor = false;

	UPROPERTY(EditAnywhere, Category = "Combat")
	float HitReactRate = 1.f;

	/** Recoil after a plain parry: animation rate and how far it is pushed back. */
	UPROPERTY(EditAnywhere, Category = "Combat")
	float ParryRecoilRate = 0.5f;

	UPROPERTY(EditAnywhere, Category = "Combat")
	float ParryRecoilLaunch = 350.f;

	UAnimMontage* PlayAnim(UAnimSequence* Anim, float Rate = 1.f, float BlendIn = 0.05f, float BlendOut = 0.2f, int32 LoopCount = 1);

	/** Minions are floored by finishers; bosses only stagger (big hit react) and never lie down. */
	UPROPERTY(EditAnywhere, Category = "Combat")
	bool bCanBeKnockedDown = true;
	void SetAttacks(const TArray<FBFEnemyAttack>& InAttacks);

	UPROPERTY()
	TObjectPtr<UAnimSequence> HitLeftAnim;
	UPROPERTY()
	TObjectPtr<UAnimSequence> HitRightAnim;
	UPROPERTY()
	TObjectPtr<UAnimSequence> HitFrontAnim;
	UPROPERTY()
	TObjectPtr<UAnimSequence> KnockdownAnim;
	UPROPERTY()
	TObjectPtr<UAnimSequence> GetUpAnim;
	/** Optional lying-on-the-back loop between the knockdown clip and the get-up. */
	UPROPERTY()
	TObjectPtr<UAnimSequence> DownLoopAnim;
	UPROPERTY()
	TObjectPtr<UAnimSequence> DeathAnim;
	UPROPERTY()
	TObjectPtr<UAnimSequence> BrokenAnim;
	/** Optional: looped after BrokenAnim while posture stays broken, and played on recovery. */
	UPROPERTY()
	TObjectPtr<UAnimSequence> BrokenLoopAnim;
	UPROPERTY()
	TObjectPtr<UAnimSequence> BrokenEndAnim;
	/** Big blow-back (root motion) for heavy finishers and lost clashes; falls back to KnockdownAnim. */
	UPROPERTY()
	TObjectPtr<UAnimSequence> HeavyKnockdownAnim;
	/** Hit from behind (bosses: also the execution reaction). */
	UPROPERTY()
	TObjectPtr<UAnimSequence> HitBackAnim;
	UPROPERTY()
	TArray<TObjectPtr<UAnimSequence>> AttackAnims;
	UPROPERTY()
	TArray<TObjectPtr<UAnimSequence>> RecoverAnims;

	TArray<FBFEnemyAttack> Attacks;

	// --- Boss phase 2 (below half health) ---
	UPROPERTY(EditAnywhere, Category = "AI")
	bool bHasPhase2 = false;
	/** Boss AI: weighted pick by distance / phase / roll spam (PickAttack). Off = the training dummy's
	 * predictable round robin of starters. */
	bool bWeightedAttackPick = false;
	/** Roar / transition clip, played from TransitionStart; the shockwave fires at TransitionImpact (anim seconds). */
	UPROPERTY()
	TObjectPtr<UAnimSequence> TransitionAnim;
	float TransitionStart = 0.f;
	float TransitionImpact = 1.f;
	float TransitionRate = 1.f;
	/** Phase-2 tuning applied after the transition. */
	float Phase2Cooldown = 1.1f;
	float Phase2SpeedScale = 1.25f;
	/** Phase-2 gap closer: glide (start clip, then loop) toward a far player, then open with TravelArriveAttack. */
	UPROPERTY()
	TObjectPtr<UAnimSequence> TravelStartAnim;
	UPROPERTY()
	TObjectPtr<UAnimSequence> TravelLoopAnim;
	int32 TravelArriveAttack = INDEX_NONE;
	float TravelSpeed = 900.f;
	float TravelMinDist = 850.f;
	float TravelArriveDist = 380.f;
	/** Between attacks, circle the player sideways (needs a directional locomotion blend space). */
	UPROPERTY(EditAnywhere, Category = "AI")
	bool bCircleStrafe = false;

	// --- Turn on the spot (step clips with no root rotation: the actor yaw is eased over the clip) ---
	UPROPERTY()
	TObjectPtr<UAnimSequence> TurnLeftAnim;
	UPROPERTY()
	TObjectPtr<UAnimSequence> TurnRightAnim;
	UPROPERTY()
	TObjectPtr<UAnimSequence> TurnLeft180Anim;
	UPROPERTY()
	TObjectPtr<UAnimSequence> TurnRight180Anim;
	/** Facing error (degrees) that makes him stop and turn with a step clip instead of sliding round. */
	float TurnInPlaceAngle = 55.f;
	float TurnRate90 = 1.6f;
	float TurnRate180 = 1.5f;

	// --- Backstep (hop back out of a pressing player, then answer from range) ---
	UPROPERTY()
	TObjectPtr<UAnimSequence> BackstepAnim;
	float BackstepDistance = 380.f;
	float BackstepRate = 1.3f;
	float BackstepCooldown = 6.f;

	// --- Body lean: the mesh tips toward where the actor is actually travelling (warp lunges, walking,
	// backsteps), so glides read as lunges instead of a statue on rails. 0 = off. ---
	float MaxLeanPitch = 0.f;  // degrees, forward/back
	float MaxLeanRoll = 0.f;   // degrees, sideways
	float LeanSpeedRef = 650.f; // cm/s that gives the full lean

	// --- Spell flight clips (all three set: gather/rise, hover charge, hover after release; otherwise the
	// cast clip is held while he rises) ---
	UPROPERTY()
	TObjectPtr<UAnimSequence> MagicRiseAnim;
	UPROPERTY()
	TObjectPtr<UAnimSequence> MagicChargeAnim;
	UPROPERTY()
	TObjectPtr<UAnimSequence> MagicHoverAnim;
	float MagicReleaseStart = 0.62f; // cast clip position the release starts from (flight clips only)
	float MagicRiseTime = 0.75f;
	float MagicDrift = 90.f;         // backs off this far from the player while rising
	float MagicBobHeight = 9.f;
	float MagicBobPeriod = 1.7f;
	float MagicAuraScale = 0.28f;   // charge aura; larger swallows the whole body

	// --- Stance (hidden, Elden Ring style): heavy blows and plunges fill it; full = kneel, critical hit ---
	/** Zero disables stance. */
	float MaxStance = 0.f;
	float StanceRegenDelay = 4.f;
	float StanceRegenRate = 15.f;
	float StanceBreakDuration = 2.6f;

	// --- Magic ---
	UPROPERTY()
	TObjectPtr<UNiagaraSystem> FireLineVfx;
	UPROPERTY()
	TObjectPtr<UNiagaraSystem> CircleVfx;
	UPROPERTY()
	TObjectPtr<UNiagaraSystem> CastAuraVfx;
	UPROPERTY()
	TObjectPtr<USoundBase> CastChargeSound;
	UPROPERTY()
	TObjectPtr<USoundBase> FireLineSound;
	UPROPERTY()
	TObjectPtr<USoundBase> CircleSound;
	float FireLineSpeed = 1450.f;
	/** Half width of the fire line that hurts (cm from its centre line). */
	float FireLineHalfWidth = 95.f;
	float FireLineMaxLength = 2800.f;
	float CircleRadius = 290.f;
	float CircleWarnTime = 2.0f;
	// The circle crawls after the player for CircleChaseTime (slower than a walk), never further than
	// CircleLeash from where it appeared, then locks for the rest of the warning: stepping aside is not
	// enough, the player has to keep running (or roll the eruption).
	float CircleChaseTime = 1.5f;
	float CircleChaseSpeed = 300.f;
	float CircleLeash = 700.f;
	// Energy orb (EBFMagic::Orb): a glowing core sphere wrapped in flames, grown in his claw during the charge.
	UPROPERTY()
	TObjectPtr<UStaticMesh> OrbMesh;
	UPROPERTY()
	TObjectPtr<UMaterialInterface> OrbMaterial;
	UPROPERTY()
	TObjectPtr<UNiagaraSystem> OrbFlameVfx;
	UPROPERTY()
	TObjectPtr<UNiagaraSystem> OrbBurstVfx;
	UPROPERTY()
	TObjectPtr<USoundBase> OrbThrowSound;
	UPROPERTY()
	TObjectPtr<USoundBase> OrbBurstSound;
	float OrbSize = 140.f;     // core diameter when fully charged (cm)
	float OrbRadius = 430.f;   // burst radius that hurts
	float OrbSpeed = 1400.f;   // flight speed toward the marked spot
	FName OrbHandSocket = TEXT("hand_r");
	/** No second spell within this many seconds (phase 1 / phase 2). */
	float MagicCooldown1 = 7.f;
	float MagicCooldown2 = 4.f;

	int32 Phase = 1;
	/** Phase-1 values, restored when a dead boss respawns. */
	float Phase1Cooldown = 0.f;
	float Phase1Speed = 0.f;

private:
	void AddPosture(float Amount);
	void BreakPosture(bool bFromStance = false);
	void AddStance(float Amount);
	/** Signed yaw (degrees) from our facing to the player; 0 without a player. */
	float YawToPlayer() const;
	bool StartTurnInPlace(float Delta);
	void TickTurnInPlace(float DeltaSeconds);
	void StartBackstep(const TCHAR* Reason);
	void TickBackstep(float DeltaSeconds);
	/** Floor height under a point (Z), or false when there is no floor within reach (arena edge). */
	bool FindFloorZ(const FVector& At, float& OutZ) const;
	void TickMagicCast(float DeltaSeconds);
	void ReleaseMagic(const FBFEnemyAttack& A);
	void TickMagicFX(float RealDelta);
	void LandFromMagic();
	bool IsMagicAttack(int32 Index) const { return Attacks.IsValidIndex(Index) && Attacks[Index].Magic != EBFMagic::None; }
	void StartAttack(int32 Index);
	void TickAttack(float DeltaSeconds);
	void TurnTowardPlayer(float DeltaSeconds, float DegPerSec);
	FVector GetWeaponTip() const;
	/** Ground crack, boom and a distance-scaled camera jolt where a heavy attack lands. */
	void DoSlamImpact();
	/** Floors the enemy with a knockdown clip; stands up after the clip plus DownHold seconds. */
	void KnockDown(UAnimSequence* Anim);
	/** Directional hit react from the side the blade came from. */
	void PlayHitReact(const FBFHitInfo& Hit, const FVector& ToAttacker, float RateScale);
	ABFPlayerCharacter* GetPlayer() const;

	UPROPERTY(Transient)
	TObjectPtr<UAnimMontage> CurrentMontage;

	int32 CurrentAttack = 0;
	int32 AttackCount = 0;
	/** Rotation over the attacks that may start on their own (chain-only ones are skipped). */
	int32 StarterCount = 0;
	/** Playing an attack's recovery clip: idle-like (hittable), but no moving, turning or new attack until it ends. */
	bool bAttackRecovering = false;
	void FinishAttack();
	int32 PickStarterAttack();
	/** Weighted pick over the attacks usable at this distance and phase (INDEX_NONE if none). */
	int32 PickAttack(float Dist);
	void StartPhaseTransition();
	void TickTransition();
	void StartTravel();
	void TickTravel(float DeltaSeconds);
	void EndTravel();
	void StartGroundWave(const FBFEnemyAttack& A);
	void TickGroundWave(float DeltaSeconds);
	/** Perilous telegraph: coloured flash at the weapon plus the HUD icon (via GetPerilous). */
	void PerilousTelegraph(EBFPerilous Kind);
	float MoveSpeedBase = 0.f;
	int32 LastStarter = INDEX_NONE;
	bool bRollSpamPick = false;
	// Delayed wind-up
	bool bHoldPending = false;
	bool bHolding = false;
	float HoldTime = 0.f;
	float HoldLeft = 0.f;
	// Motion warp
	float WarpUsed = 0.f;
	// Openings
	bool bWasPunishable = false;
	bool bLastHitPunish = false;
	bool bWhiffed = false;
	// Perilous
	EBFPerilous ActivePerilous = EBFPerilous::None;
	double PerilousStartTime = -100.0;
	// Ground wave
	bool bWaveActive = false;
	bool bWaveResolved = false;
	FVector WaveOrigin = FVector::ZeroVector;
	float WaveRadius = 0.f;
	float WaveMaxRadius = 0.f;
	float WaveSpeed = 1000.f;
	FBFHitInfo WaveHit;
	// Phase transition / travel / circling
	bool bTransitionImpactDone = false;
	float TransitionLen = 0.f;
	/** Seconds he holds after the roar clip while the cutscene plays its closing orbit shot. */
	float TransitionHold = 1.6f;
	bool bTraveling = false;
	bool bTravelLooping = false;
	float TravelTime = 0.f;
	float CircleDir = 1.f;
	float CircleSwitchLeft = 2.f;
	bool bTelegraphed = false;
	bool bHeavyPulsePending = false;
	double ParryCueTime = -100.0;
	bool bSwingResolved = false;
	bool bSwingSoundPlayed = false;
	bool bSlamDone = false;
	bool bLastHitArmored = false;
	/** Standing up from a knockdown / stun: hits deal damage but do not restart reactions. */
	bool bRecovering = false;
	/** Death: the Paragon death clip ends mid-fall (made for a ragdoll), so the held pose floats. After it
	 * the mesh drops under gravity until the lowest body bone rests on the floor. */
	void TickDeathFall(float DeltaSeconds);
	void ResetDeathFall();
	FVector MeshBaseLoc = FVector::ZeroVector;
	float DeathLoose = 0.f;
	float DeathDrop = 0.f;
	float DeathDropVel = 0.f;
	float DeathDropTarget = -1.f;
	bool bDeathLanded = false;
	/** After landing: the raised arms lower (DeathSettle), then the boss dissolves into motes (material param
	 * BFDissolve from Scripts/38_boss_dissolve.py) and the mesh hides. On respawn he re-forms (Reform 1 -> 0). */
	void TickDeathAfterLand(float DeltaSeconds);
	float DeathAfterLand = 0.f;
	float DeathSettle = 0.f;
	float DeathDissolve = 0.f;
	bool bDissolveStarted = false;
	float Reform = 0.f;
	static constexpr float DissolveStart = 2.6f;
	static constexpr float DissolveLen = 3.f;
	bool bBrokenLooping = false;
	// Turn in place
	bool bTurning = false;
	float TurnFromYaw = 0.f;
	float TurnDelta = 0.f;
	float TurnDur = 1.f;
	float TurnT = 0.f;
	// Backstep
	bool bBackstepping = false;
	float BackstepT = 0.f;
	float BackstepMoved = 0.f;
	double LastBackstepTime = -100.0;
	double HugStartTime = -1.0;
	TArray<double> RecentHitTimes;
	/** Next pick right after a backstep: spells (and other ranged answers) much likelier. */
	bool bPreferRanged = false;
	// Stance
	float Stance = 0.f;
	double LastStanceDamageTime = -100.0;
	bool bStanceBroken = false;
	// Magic cast (airborne) and its effects (they outlive the cast)
	bool bMagicAir = false;
	int32 MagicStage = 0;
	float MagicT = 0.f;
	float MagicChargeLeft = 0.f;
	float MagicBaseZ = 0.f;
	float MagicLandFromZ = 0.f;
	FVector MagicStartXY = FVector::ZeroVector;
	// Body lean state
	FVector LeanPrevLoc = FVector::ZeroVector;
	FRotator MeshBaseRot = FRotator::ZeroRotator;
	float LeanPitch = 0.f;
	float LeanRoll = 0.f;
	bool bLeanInit = false;
	void TickLean(float DeltaSeconds);
	FVector MagicDriftDir = FVector::ZeroVector;
	bool HasMagicFlightClips() const { return MagicRiseAnim && MagicChargeAnim && MagicHoverAnim; }
	float MagicHeightAt(float T, float RiseHeight) const;
	double LastMagicTime = -100.0;
	bool bMagicLocked = false;
	FVector MagicTarget = FVector::ZeroVector;
	UPROPERTY(Transient)
	TObjectPtr<UNiagaraComponent> CastAura;
	bool bLineActive = false;
	bool bLineResolved = false;
	FVector LineOrigin = FVector::ZeroVector;
	FVector LineDir = FVector::ForwardVector;
	float LineLength = 0.f;
	float LineFront = 0.f;
	float LineNextFx = 0.f;
	FBFHitInfo LineHit;
	bool bCircleActive = false;
	FVector CircleCenter = FVector::ZeroVector;
	FVector CircleOrigin = FVector::ZeroVector;
	bool bCircleLocked = false;
	TArray<TWeakObjectPtr<AActor>> CircleRings;
	float CircleTimeLeft = 0.f;
	FBFHitInfo CircleHit;
	// Energy orb: held while charging (OrbCore exists, bOrbFlying false), then in flight to OrbTo.
	void SpawnOrb();
	void DestroyOrb();
	void SetOrbTransform(const FVector& At, float Size);
	FVector OrbHoldLocation() const;
	void BurstOrb();
	UPROPERTY(Transient)
	TObjectPtr<UStaticMeshComponent> OrbCore;
	UPROPERTY(Transient)
	TObjectPtr<UNiagaraComponent> OrbFlames;
	UPROPERTY(Transient)
	TObjectPtr<UPointLightComponent> OrbLight;
	UPROPERTY(Transient)
	TObjectPtr<UMaterialInstanceDynamic> OrbMid;
	bool bOrbFlying = false;
	float OrbChargeTotal = 1.f;
	float OrbT = 0.f;
	float OrbDur = 1.f;
	float OrbArc = 200.f;
	FVector OrbFrom = FVector::ZeroVector;
	FVector OrbTo = FVector::ZeroVector;
	FBFHitInfo OrbHit;
	// Arena rune circle (actors tagged BFRuneCircle, lights tagged BFRuneLight): it glows under the boss only while
	// he casts or his spells are live (the user asked for no circle at his entrance).
	void TickRuneCircle(float RealDelta);
	bool bRuneInit = false;
	float RuneReveal = 0.f;
	/** Peak strength of the rune circle's glow and light while the boss casts (user found full strength too bright). */
	UPROPERTY(EditAnywhere, Category = "Magic")
	float RuneMaxGlow = 0.15f;
	TArray<TWeakObjectPtr<AActor>> RuneActors;
	UPROPERTY(Transient)
	TArray<TObjectPtr<UMaterialInstanceDynamic>> RuneMids;
	TArray<TPair<TWeakObjectPtr<class ULightComponent>, float>> RuneLights;
	float DownHold = 1.8f;
	float DownClipLen = 1.2f;
	bool bDownLooping = false;
	/** Keeps the current montage on its last frame instead of blending back to locomotion. */
	void HoldLastFrame();
	float CooldownLeft = 1.5f;

	double HitstopEndTime = 0.0;
	double HitstopStartTime = 0.0;
	float HitstopMinDilation = BFCombat::HitPauseDilation;
	double LastPostureDamageTime = -100.0;
	double LastDebugLogTime = 0.0;
	float StateTime = 0.f;
};
