#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "BFCombatTypes.h"
#include "BFPlayerCharacter.generated.h"

class UCameraComponent;
class USpringArmComponent;
class UStaticMeshComponent;
class UInputAction;
class UInputMappingContext;
class UAnimSequence;
class UAnimMontage;
class UMaterialInterface;
class UNiagaraSystem;
class USoundBase;
class ABFEnemyBase;
class ACameraActor;
class UBFHitFlashComponent;
class UNiagaraComponent;
class APostProcessVolume;
struct FInputActionValue;

UENUM()
enum class EBFPlayerState : uint8
{
	Free,
	Attacking,
	Dashing,
	/** Guard held: blocks swings; a fresh press is a perfect-parry window. */
	Guarding,
	/** Flinching from a hit or a guard break; no input until it ends. */
	Stunned,
	/** Strength clash after parrying a heavy attack: guard presses push the bar. */
	Clashing,
	/** Jumped a ground wave and dropping onto the boss's head. */
	Stomping,
	/** Heavy in the air: dive straight down, area slam on landing. */
	Plunging,
};

UENUM()
enum class EBFChain : uint8
{
	Light,
	Heavy,
	/** Jump, then light: three hovering swings (the first aerial action of a jump costs a dodge charge). */
	Air,
};

/**
 * Player swordsman: UE4 mannequin with the InsaneAirCombo sword set.
 * Phase 1: movement, camera, jump. Phase 2: light/heavy combos, dash with afterimages,
 * sword sweep hit detection, hitstop, camera shake, hit VFX/SFX.
 * Input actions are created in code so the project needs no input assets.
 */
UCLASS()
class BOSSFIGHT_API ABFPlayerCharacter : public ACharacter
{
	GENERATED_BODY()

public:
	ABFPlayerCharacter();

	/** Hit pause: slows this actor to Dilation for a short real-time duration, easing back out
	 * (a near-freeze only for clash cinematics). */
	void ApplyHitstop(float Duration, float Dilation = BFCombat::HitPauseDilation);

	/** Adds a decaying camera shake (amplitude in cm). With a direction (world space) it is a
	 * kick along that direction that springs back, plus a little roll; FovPunch narrows the view. */
	void AddCameraShake(float Amplitude, float Duration, const FVector& WorldDir = FVector::ZeroVector, float FovPunch = 0.f);

	bool IsInvulnerable() const { return bInvulnerable; }
	/** Rolling through i-frames right now (a grab reaching for us counts as a perfect dodge more generously). */
	bool IsDashDodging() const { return State == EBFPlayerState::Dashing && bInvulnerable; }
	/** A dash started within the grab grace window (a grab reaching us now becomes a clash). */
	bool IsGrabDodging() const;

	/** An enemy swing reached the player: dodge, parry, block, guard break or take the hit. */
	EBFHitResult ResolveEnemyHit(const FBFHitInfo& Hit, ABFEnemyBase* Attacker);

	float GetHealth() const { return Health; }
	float GetMaxHealth() const { return MaxHealth; }
	float GetPosture() const { return Posture; }
	float GetMaxPosture() const { return MaxPosture; }

	void EndHitstop();

	/** Strength clash HUD data. Balance runs -1 (enemy wins) to +1 (player wins). */
	bool IsStruggling() const { return bStruggle; }
	float GetStruggleBalance() const { return StruggleBalance; }
	float GetStruggleTimeLeft01() const;
	float GetStrugglePunch() const { return StrugglePunch; }

	/** Red screen-edge pulse after taking a hit, 1 right after the hit fading to 0. */
	float GetHurtFlash() const;

	// Lock-on
	ABFEnemyBase* GetLockTarget() const { return LockTarget.Get(); }
	/** World point the lock-on camera and reticle aim at. */
	FVector GetLockPoint() const;
	/** 1 right after a target is acquired, fading to 0 (reticle pop). */
	float GetLockPop() const;

	// Dodge charges
	int32 GetDashCharges() const { return DashCharges; }
	bool IsAirAttacking() const { return bAirAttack; }
	/** Progress (0..1) of the reload: full refill DashRefillDelay seconds after the stack first dropped below max. */
	float GetDashRefill01() const;
	/** Pulses: a charge was won back by a perfect dodge / a roll was refused (no charges) / refilled. */
	float GetDashGainFlash() const { return PulseFrom(DashGainTime, 0.6f); }
	float GetDashEmptyFlash() const { return PulseFrom(DashEmptyTime, 0.5f); }
	float GetDashRefillFlash() const { return PulseFrom(DashRefillTime, 0.6f); }
	/** Roll-spam detection for the boss AI: rolls started in the last Window seconds. */
	int32 GetRecentDashCount(float Window) const;

	/** Guard Regain (Lies of P): blocked damage that attacking can win back before it fades. */
	float GetRegainHealth() const { return RegainPool; }

	/** Impact frame: 1 on the frame a big hit lands, fading over a few frames (HUD flash). */
	float GetImpactFrame() const { return PulseFrom(ImpactFrameTime, 0.09f); }
	/** Boss phase mini-cutscene: letterbox amount (0..1) and its title. */
	float GetCinematicAlpha() const;
	/** Phase title card: fades in after the roar, out with the letterbox. */
	float GetCinematicTitleAlpha() const;
	bool IsCinematic() const { return bCinematic; }
	/** Where the boss cutscene's opening shot is filmed from (valid while IsCinematic()). */
	FVector GetCinematicCamLocation() const { return CineCamLoc; }
	/** Mid-air after jumping a ground wave: LMB stomps (HUD prompt). */
	bool CanStomp() const;

	/** Boss phase change: a three-shot cutscene (low push-in on the boss, wide shot of the roar hitting
	 * the player at ImpactAt seconds, slow orbit with the title) for Duration seconds, input locked. */
	void StartBossCinematic(ABFEnemyBase* Boss, float Duration, float ImpactAt = -1.f);
	/** Boss phase-2 roar: braced, then a big standing stagger pushed back (no launch, no knockdown, no damage). */
	void StartRoarKnockback(const FVector& From);

protected:
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void PostInitializeComponents() override;
	/** Off the arena edge: put back on the last solid ground instead of being destroyed. */
	virtual void FellOutOfWorld(const UDamageType& DmgType) override;
	virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Camera")
	TObjectPtr<USpringArmComponent> CameraBoom;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Camera")
	TObjectPtr<UCameraComponent> FollowCamera;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Weapon")
	TObjectPtr<UStaticMeshComponent> Sword;

	/** What the player sees: the anime swordswoman, posed every frame from the hidden mannequin (GetMesh(),
	 * which still runs every animation, root motion and gameplay) through ABP_Swordswoman_Player's runtime
	 * IK retarget. The sword rides in her right hand. Null-safe: without her assets the mannequin stays visible. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Body")
	TObjectPtr<USkeletalMeshComponent> AnimeBody;

	/** The mesh on screen (AnimeBody when it is set up, else the mannequin). */
	USkeletalMeshComponent* GetVisibleBody() const;

	UPROPERTY(VisibleAnywhere, Category = "Impact")
	TObjectPtr<UBFHitFlashComponent> HitFlash;

private:
	// Input
	void BuildInput();
	void Move(const FInputActionValue& Value);
	void Look(const FInputActionValue& Value);
	void OnJumpPressed();
	void OnLightPressed();
	void OnHeavyPressed();
	void OnDashPressed();
	/** LMB: tap = light (on release), hold LightHoldForHeavy = heavy (fires at the threshold). */
	void OnLightDown();
	void OnLightUp();
	void TickLightHold();
	/** Shift held: sprint while free on the ground and moving. */
	void OnSprintPressed();
	void OnSprintReleased();
	void TickSprint(float DeltaSeconds);
	/** Slash arc on swings, speed streaks while dashing / sprinting. */
	void TickSmears();
	/** Boss spell camera: while a boss casts (airborne charge, fire line, circle) pull far out and
	 * frame him in the middle of the screen; ease back to the normal camera when the spell is over. */
	void TickMagicCam(float RealDelta);
	void OnGuardPressed();
	void OnGuardReleased();
	void OnLockPressed();
	void OnLockSwitch(const FInputActionValue& Value);

	// Lock-on
	void SetLockTarget(ABFEnemyBase* Target);
	ABFEnemyBase* FindLockCandidate(float SwitchDir) const;
	void TickLockOn(float RealDelta);
	/** Facing target for actions: the lock target, else the nearest enemy within Range. */
	ABFEnemyBase* GetFacingTarget(float Range) const;

	// Dodge charges, perilous answers, polish
	void RewardPerfectDodge();
	void PerfectJump(ABFEnemyBase* Attacker);
	void StartStomp();
	void TickStomp(float DeltaSeconds);
	const TArray<FBFAttackDef>& GetChainDefs(EBFChain Chain) const;
	const TArray<TObjectPtr<UAnimSequence>>& GetChainAnims(EBFChain Chain) const;
	/** First aerial action of a jump costs one dodge charge (refused at zero). It never restarts a
	 * running refill countdown; with full charges it starts one (or the charge would come straight back). */
	bool TryPayAirCharge();
	void StartAirAttack(int32 Index);
	void StartPlunge();
	void TickPlunge(float DeltaSeconds);
	void DoMikiri(ABFEnemyBase* Attacker);
	void StartGrabbed(ABFEnemyBase* By, const FBFHitInfo& Hit);
	void TickGrabbed();
	void TickCinematic();
	/** Brief world slow-motion (real seconds), unless a clash cinematic owns time. */
	void WorldSlowMo(float Dilation, float RealSeconds);
	void ImpactFrame();
	bool CanCancelAttack() const;
	/** Ends a ground swing early (recovery, or once it connected) and jumps out of it. */
	void CancelAttackIntoJump();
	void UpdateSwordTrail();
	float PulseFrom(double Start, float Length) const;

	// Combat
	void StartAttack(EBFChain Chain, int32 Index);
	void TickAttack(float DeltaSeconds);
	void SweepBlade(bool bFirstFrame);
	void ApplyWeaponHit(ABFEnemyBase* Target, const FVector& ImpactPoint);
	void StartDash();
	void TickDash(float DeltaSeconds);
	void DoBlink();
	void SpawnAfterImage();
	void EndAction();
	void StartGuard();
	void TurnTowardSoftLock(float DeltaSeconds);
	void TickGuard(float DeltaSeconds);
	void DoParry(ABFEnemyBase* Attacker, const FBFHitInfo& Hit);
	void PerfectDodgeFeedback(ABFEnemyBase* Attacker);
	double PerfectDodgeSlowEnd = 0.0;
	void StartStruggle(ABFEnemyBase* Attacker, const FBFHitInfo& Hit, const FVector& Contact);
	void StrugglePress();
	void TickStruggle(float RealDelta);
	void ResolveStruggle(bool bWon);
	/** Parry clash cinematic: whip-in to a low over-shoulder close-up, frozen beat, whip-out. */
	void StartClashCam(ABFEnemyBase* Attacker, const FVector& Contact, bool bStruggleHold);
	void TickClashCam();
	void EndClashCam();
	void AddPosture(float Amount);
	void StartStun(float Duration, UAnimSequence* Anim, float Rate);
	bool TryExecution();
	ABFEnemyBase* FindBrokenTarget(float Range) const;
	void SpawnVfx(UNiagaraSystem* System, const FVector& Location, const FRotator& Rotation, float SizeScale = 1.f, float Hue = -1.f);
	void FaceForAction();
	ABFEnemyBase* FindSoftLockTarget(float Range) const;
	UAnimMontage* PlayAnim(UAnimSequence* Anim, float Rate, float BlendIn = 0.08f, float BlendOut = 0.25f, int32 LoopCount = 1);
	/** Keeps the current montage on its last frame (sets the instance flag, not only the asset). */
	void HoldLastFrame();
	/** Floors the player with a knockdown clip, lies (looping) and gets up after LieTime. */
	void StartKnockdown(UAnimSequence* Anim, float LieTime);
	void GetBladePoints(TArray<FVector>& OutPoints) const;
	bool HasRecentMoveInput() const;

	// Debug / tests
	void TickAutoTest(float DeltaSeconds);
	void AutoTestShot(const FString& Name);

	UPROPERTY(Transient)
	TObjectPtr<UInputMappingContext> MappingContext;
	UPROPERTY(Transient)
	TObjectPtr<UInputAction> MoveAction;
	UPROPERTY(Transient)
	TObjectPtr<UInputAction> LookAction;
	UPROPERTY(Transient)
	TObjectPtr<UInputAction> JumpAction;
	UPROPERTY(Transient)
	TObjectPtr<UInputAction> LightAction;
	UPROPERTY(Transient)
	TObjectPtr<UInputAction> HeavyAction;
	UPROPERTY(Transient)
	TObjectPtr<UInputAction> DashAction;
	UPROPERTY(Transient)
	TObjectPtr<UInputAction> SprintAction;
	UPROPERTY(Transient)
	TObjectPtr<UInputAction> GuardAction;
	UPROPERTY(Transient)
	TObjectPtr<UInputAction> LockAction;
	UPROPERTY(Transient)
	TObjectPtr<UInputAction> LockSwitchAction;

	// Assets (hard references so they cook)
	UPROPERTY()
	TArray<TObjectPtr<UAnimSequence>> LightAnims;
	UPROPERTY()
	TArray<TObjectPtr<UAnimSequence>> HeavyAnims;
	UPROPERTY()
	TArray<TObjectPtr<UAnimSequence>> AirAnims;
	/** Boss phase-2 spell hit: launched up, lands on the back. */
	UPROPERTY()
	TObjectPtr<UAnimSequence> KnockUpAnim;
	UPROPERTY()
	TObjectPtr<UAnimSequence> DashAnim;
	/** Lucy slide dashes (root motion): forward, back, left, right. */
	UPROPERTY()
	TArray<TObjectPtr<UAnimSequence>> SlideAnims;
	/** Lucy Avoid F/B/L/R (root motion sidesteps): hit reactions, pushed the way the blow travels. */
	UPROPERTY()
	TArray<TObjectPtr<UAnimSequence>> AvoidAnims;
	UPROPERTY()
	TObjectPtr<UMaterialInterface> SmearMaterial;
	UPROPERTY(Transient)
	TObjectPtr<class UBFSmearTrail> SwordSmear;
	UPROPERTY(Transient)
	TArray<TObjectPtr<class UBFSmearTrail>> SpeedStreaks;
	UPROPERTY()
	TObjectPtr<UMaterialInterface> AfterImageMaterial;
	UPROPERTY()
	TObjectPtr<UNiagaraSystem> HitVfx;
	UPROPERTY()
	TObjectPtr<UNiagaraSystem> BlockVfx;
	UPROPERTY()
	TObjectPtr<UAnimSequence> GuardAnim;
	/** Lucy pack big standing stagger (root motion backward), used for the phase-2 roar. */
	UPROPERTY()
	TObjectPtr<UAnimSequence> RoarHitAnim;
	UPROPERTY()
	TArray<TObjectPtr<UAnimSequence>> HitReactAnims;
	UPROPERTY()
	TObjectPtr<UAnimSequence> ExecutionAnim;
	UPROPERTY()
	TObjectPtr<UAnimSequence> KnockdownAnim;
	UPROPERTY()
	TObjectPtr<UAnimSequence> GetUpAnim;
	/** Lost strength clash: thrown up and back (root motion, ~2 m). */
	UPROPERTY()
	TObjectPtr<UAnimSequence> BlowbackAnim;
	UPROPERTY()
	TObjectPtr<UAnimSequence> DownLoopAnim;
	UPROPERTY()
	TObjectPtr<USoundBase> BlockSound;
	UPROPERTY()
	TObjectPtr<USoundBase> ParrySound;
	UPROPERTY()
	TObjectPtr<USoundBase> HitSound;
	UPROPERTY()
	TObjectPtr<USoundBase> SwingSound;
	/** Mid-air plunge used for the stomp. */
	UPROPERTY()
	TObjectPtr<UAnimSequence> StompAnim;
	/** Held and drained by a perilous grab. */
	UPROPERTY()
	TObjectPtr<UAnimSequence> GrabbedAnim;
	UPROPERTY()
	TObjectPtr<UNiagaraSystem> TrailVfx;
	UPROPERTY(Transient)
	TObjectPtr<UNiagaraComponent> SwordTrail;
	/** Unbound post-process for impact frames (high-contrast monochrome for a few frames). */
	UPROPERTY(Transient)
	TObjectPtr<APostProcessVolume> ImpactVolume;

	UPROPERTY(Transient)
	TObjectPtr<UAnimMontage> CurrentMontage;

	UPROPERTY(Transient)
	TArray<TWeakObjectPtr<AActor>> HitThisWindow;

	TArray<FBFAttackDef> LightChain;
	TArray<FBFAttackDef> HeavyChain;
	TArray<FBFAttackDef> AirChain;
	// Air combo / plunge
	bool bAirAttack = false;
	bool bAirChargePaid = false;
	bool bAirComboUsed = false;
	float AirHoverZ = 0.f;
	FVector PlungeFrom = FVector::ZeroVector;
	FVector PlungeTo = FVector::ZeroVector;
	float PlungeT = 0.f;
	bool bPlungeLanded = false;
	double PlungeLandTime = 0.0;

	EBFPlayerState State = EBFPlayerState::Free;
	EBFChain CurrentChain = EBFChain::Light;
	int32 ComboIndex = 0;
	int32 ActiveWindow = INDEX_NONE;
	TArray<FVector> PrevBladePoints;

	// Buffered input: what was pressed and when (real seconds).
	enum class EBuffered : uint8 { None, Light, Heavy, Dash, Jump };
	EBuffered Buffered = EBuffered::None;
	double BufferedTime = 0.0;

	FVector LastMoveInput = FVector::ZeroVector;
	double LastMoveInputTime = -100.0;

	// Health, posture, guard
	float MaxHealth = 100.f;
	float Health = 100.f;
	float MaxPosture = 100.f;
	float Posture = 0.f;
	double LastPostureDamageTime = -100.0;
	bool bGuardHeld = false;
	double ParryPressTime = -100.0;
	double StunEndTime = 0.0;
	bool bExecuting = false;

	// Dash
	bool bInvulnerable = false;
	float AfterImageTimer = 0.f;
	bool bLightHeld = false;
	bool bLightHeavyFired = false;
	double LightDownTime = 0.0;
	bool bSprintHeld = false;
	bool bSprinting = false;
	bool bSwordSmearOn = false;
	float StreakStrength = 0.f;
	float MagicCamAlpha = 0.f;
	float BaseArmLength = 420.f;
	TWeakObjectPtr<ABFEnemyBase> MagicCamBoss;
	/** Spell camera framing: sideways shift of the boom pivot (cm) that keeps pillars out of the shot, and arm length. */
	float MagicCamSide = 0.f;
	float MagicCamArm = 1300.f;
	float MagicCamCheckTimer = 0.f;
	double DashReadyTime = 0.0;
	int32 DashCharges = BFCombat::MaxDashCharges;
	/** Time the running dash reload started (stack dropped below max); not restarted by later rolls. */
	double DashReloadStartTime = -100.0;
	/** Real time the last ground dash started (grab grace window). */
	double DashPressRealTime = -100.0;
	double DashGainTime = -100.0;
	double DashEmptyTime = -100.0;
	double DashRefillTime = -100.0;
	bool bDashRewarded = false;
	FVector DashDir = FVector::ForwardVector;
	FVector DashStartLoc = FVector::ZeroVector;
	/** Dash out of a swing = blink: slide at the enemy, teleport through to his far side, turn to face him. */
	TWeakObjectPtr<ABFEnemyBase> BlinkTarget;
	bool bBlinkPending = false;
	/** Gap-close blink (dash at a near enemy, not from a swing): lands in front of him instead of behind. */
	bool bBlinkFront = false;
	bool bBlinked = false;
	TArray<double> DashHistory;

	// Lock-on
	TWeakObjectPtr<ABFEnemyBase> LockTarget;
	bool bLockedOn = false;
	double LockTime = -100.0;
	double LockSwitchTime = -100.0;
	float BaseWalkSpeed = 488.f;
	FVector BoomBaseSocket = FVector::ZeroVector;

	// Guard Regain
	float RegainPool = 0.f;
	double RegainFadeStart = 0.0;

	// Perilous answers
	bool bStompReady = false;
	double StompReadyUntil = 0.0;
	TWeakObjectPtr<ABFEnemyBase> StompTarget;
	FVector StompFrom = FVector::ZeroVector;
	float StompT = 0.f;
	bool bGrabbed = false;
	double GrabStart = 0.0;
	FVector GrabFrom = FVector::ZeroVector;
	TWeakObjectPtr<ABFEnemyBase> GrabBy;
	float GrabDamage = 0.f;
	int32 GrabTicks = 0;

	// Slow-mo, impact frame, cinematic
	double SlowMoEnd = 0.0;
	double ImpactFrameTime = -100.0;
	bool bCinematic = false;
	/** The follow camera got squeezed into the body (backed into a wall), so the mesh is hidden. */
	bool bCamHidBody = false;
	/** Last spot stood on (on the ground, free to act); a fall off the arena returns here. */
	FVector LastSafeGround = FVector::ZeroVector;
	void RecoverFromFall();
	double CineStart = 0.0;
	float CineDuration = 0.f;
	TWeakObjectPtr<ABFEnemyBase> CineBoss;
	FVector CineCamLoc = FVector::ZeroVector;
	FRotator CineCamRot = FRotator::ZeroRotator;
	/** Cutscene beats: roar impact time (s from start), whether the brace / impact already played. */
	float CineImpactAt = 1.3f;
	bool bCineBraced = false;
	bool bCineImpact = false;
	/** Shot 2 (wide on the player) and shot 3 (orbit around the boss), smoothed every frame. */
	FVector CineWideLoc = FVector::ZeroVector;
	FVector CineWideLook = FVector::ZeroVector;
	bool bCineWideInit = false;
	float CineOrbitYaw = 0.f;
	float CineOrbitDist = 600.f;
	float CineOrbitSign = 1.f;
	FVector CineCamLook = FVector::ZeroVector;
	/** Real time the current hit pause started (eases back to full speed over its second half). */
	double HitstopStartTime = 0.0;
	float HitstopMinDilation = BFCombat::HitPauseDilation;
	int32 PerilousCount = 0;

	// Hitstop and camera shake
	double HitstopEndTime = 0.0;
	float ShakeAmplitude = 0.f;
	float ShakeDuration = 0.f;
	float ShakeTime = 0.f;
	FVector CameraBaseOffset = FVector::ZeroVector;
	float CameraBaseFov = 80.f;
	/** Kick direction in the camera's own space (zero = random shake), roll sign and FOV punch. */
	FVector ShakeDirLocal = FVector::ZeroVector;
	float ShakeRoll = 0.f;
	float ShakeFovPunch = 0.f;
	double HurtTime = -100.0;
	/** Heavy hit floored the player: get up when the stun ends (i-frames while rising). */
	bool bKnockedDown = false;
	bool bGettingUp = false;
	/** Real time the knockdown clip lands (switch to the lying loop then). */
	double DownLoopAt = 0.0;

	// Parry clash camera (real-time seconds)
	bool bClashCam = false;
	double ClashStartTime = 0.0;
	FVector ClashCamLoc = FVector::ZeroVector;
	FRotator ClashCamRot = FRotator::ZeroRotator;
	FVector ClashPushDir = FVector::ZeroVector;
	/** Hold length of the close-up; open-ended while a strength clash runs. */
	float ClashHoldDuration = 0.5f;
	bool bClashStruggleMode = false;

	// Strength clash
	bool bStruggle = false;
	double StruggleStart = 0.0;
	float StruggleBalance = 0.f;
	float StrugglePunch = 0.f;
	float StruggleEnemyPush = 0.3f;
	FVector StruggleContact = FVector::ZeroVector;
	TWeakObjectPtr<ABFEnemyBase> StruggleEnemy;
	FBFHitInfo StruggleHit;
	int32 StruggleCount = 0;
	int32 StrugglePressCount = 0;
	float AutoTestMashTimer = 0.f;
	double InkPrewarmEnd = 0.0;
	UPROPERTY()
	TObjectPtr<UMaterialInterface> InkMaterial;

	// Blade segment in sword-mesh space, from the mesh bounds.
	FVector BladeLocalA = FVector::ZeroVector;
	FVector BladeLocalB = FVector::ZeroVector;

	float DebugLogTimer = 0.f;

	// -BFAutoTest (movement) / -BFAutoTest=combat scripted runs.
	FString AutoTestMode;
	float AutoTestTime = 0.f;
	TSet<FString> AutoTestDone;
	FString PendingShotName;
	float PendingShotTime = 0.f;
	/** Extra timed screenshots (test time, name), e.g. a burst through the clash cinematic. */
	TArray<TPair<float, FString>> PendingBurst;
	float AutoTestMaxDrift = 0.f;
	int32 AutoTestHandledAttack = 0;
	double AutoTestGuardRelease = 0.0;
	bool bAutoTestExecuted = false;
	float AutoTestExecTime = 0.f;
	float AutoTestLogTimer = 0.f;
	double AutoTestJumpRelease = 0.0;
	float AutoTestMarkTime = 0.f;
	int32 AutoTestStage = 0;

	// Showcase recordings (BFPlayerShowcase.cpp): -BFAutoTest=showcase (gameplay) / trailer (cinematic).
	void TickShowcase(float Dt);
	void TickShowcaseBot(ABFEnemyBase* Enemy, float Dt);
	void TickShowcaseCapture(float Dt);
	void TickTrailerCamera(ABFEnemyBase* Enemy, float Dt);
	/** Cutscene film (-BFAutoTest=cutscene): she stands at two spots, then walks; the camera cuts between angles. */
	void TickCutscene(float T, float Dt);
	/** Cutscene face: VRoid blend shapes on the anime body (blinks + a mood timeline). */
	void TickCutsceneFace(float T, float Dt);
	/** Cutscene idle clips at the two spots (dynamic montages on the driving mannequin). */
	void TickCutsceneIdle(float T);
	/** True when nothing blocks the lens's view of her head and body. */
	bool CutViewClear(const FVector& Loc, const FVector& Head, const FVector& Feet) const;
	/** -BFAutoTest=tutorial -BFTut=<scene>: scripted footage for the dash tutorial video (one move per scene). */
	void TickTutorialBot(ABFEnemyBase* Enemy, float Dt);
	/** -BFBuildUp scenery timelapse: hide the map's pieces, then bring them back group by group. */
	void SetupBuildUp(const TArray<AActor*>& Keep);
	void TickBuildUp(float T);
	bool IsShowGameplay() const { return AutoTestMode == TEXT("showcase") || AutoTestMode == TEXT("tutorial"); }
	FString TutScene;
	int32 TutStep = 0;
	float TutNextAt = 0.f;
	FVector TutFwd = FVector::ForwardVector;
	bool bTutNoBlink = false;
	void BotMove(const FVector& Dir, float Scale = 1.f);
	void BotDash(const FVector& Dir);
	void BotJump();

	UPROPERTY(Transient)
	TObjectPtr<ACameraActor> ShowCam;
	UPROPERTY(Transient)
	TObjectPtr<class UAudioComponent> ShowMusic;
	UPROPERTY(Transient)
	TObjectPtr<class UAudioComponent> ShowMusic2;
	/** Recordings: soft key light from the camera side so she reads against the night arena. */
	UPROPERTY(Transient)
	TObjectPtr<class UPointLightComponent> ShowKeyLight;
	float ShowT = -1.f;            // scene time (s) since the recording started; <0 = waiting for compilation
	float ShowWaitT = 0.f;
	bool bShowCapture = false;
	int32 ShowFrame = 0;
	float ShowLen = 90.f;
	FString ShowName;
	bool bShowAudio = false;
	bool bShowEnded = false;
	float ShowEndT = -1.f;
	// Bot brain
	double BotGuardRelease = 0.0;
	double BotJumpRelease = 0.0;
	double BotLastReact = -10.0;
	int32 BotReactN = -1;
	int32 BotDefense = 0;
	float BotMash = 0.f;
	double BotStompAt = -1.0;
	int32 BotRoutine = -1;
	int32 BotStep = 0;
	double BotStepAt = 0.0;
	int32 BotRoutineCount = 0;
	double BotRestUntil = 0.0;
	float BotStrafe = 1.f;
	double BotStrafeFlip = 0.0;
	bool bBotSprint = false;
	// Trailer camera
	int32 TrailerShot = -1;
	int32 CutShot = -1;
	int32 CutPhase = -1;
	int32 CutWaypoint = 0;
	FVector CutFwd = FVector::ForwardVector;
	float CutYaw = 0.f;
	FVector CutCamLoc = FVector::ForwardVector; // cutscene: her facing when the current shot began
	float CutIdleNext = 0.f;
	float CutBlocked = 0.f;
	int32 CutIdleStep = -1;
	TMap<FName, float> CutFace;
	float TrailerShotStart = 0.f;
	FVector TrailerA = FVector::ZeroVector;
	FVector TrailerB = FVector::ZeroVector;
	float TrailerSlowUntil = -1.f;
	bool bTrailerBossShown = false;
};
