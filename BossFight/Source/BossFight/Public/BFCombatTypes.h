#pragma once

#include "CoreMinimal.h"
#include "Animation/AnimMontage.h"

/** Montage blends go through the Inertialization node after DefaultSlot (ABP_Player / ABP_Sevarog):
 * the new pose takes over at once and the old pose's motion decays smoothly into it, instead of a
 * linear crossfade that pops when a clip starts or stops mid-motion. */
namespace BFAnimBlend
{
	inline FMontageBlendSettings Inert(float Time)
	{
		FMontageBlendSettings Settings(Time);
		Settings.BlendMode = EMontageBlendMode::Inertialization;
		return Settings;
	}
}

class UAnimSequence;

/** One swing window in animation time (seconds). Each window can hit a target once. */
struct FBFHitWindow
{
	float Start = 0.f;
	float End = 0.f;
};

/** One attack in a combo chain. Timings are animation seconds, measured from hand_r speed peaks. */
struct FBFAttackDef
{
	const TCHAR* AnimPath = nullptr;
	TArray<FBFHitWindow> Windows;
	/** From this time a buffered input chains into the next attack. */
	float CancelTime = 0.f;
	float Damage = 10.f;
	float PostureDamage = 10.f;
	float PlayRate = 1.f;
	/** Last hit of a chain: longer hitstop, bigger shake, knocks the target down. */
	bool bFinisher = false;
};

/** How hard a hit lands; picks the impact profile (hitstop, shake, push, flinch). */
enum class EBFHitWeight : uint8
{
	Light,
	Heavy,
	Finisher,
	Execution,
};

/** Feel of one hit weight. Times are real seconds, distances cm, angles degrees. */
struct FBFImpactProfile
{
	/** Hitstop on the one who swung, and (longer) on the one who got hit. */
	float AttackerStop = 0.f;
	float VictimStop = 0.f;
	/** Directional camera kick (cm) and its length. */
	float Shake = 0.f;
	float ShakeTime = 0.f;
	/** Camera FOV punch in degrees (narrows, then springs back). */
	float FovPunch = 0.f;
	/** Knockback on an unarmored victim. */
	float Push = 0.f;
	/** Procedural upper-body flinch strength (1 = light jab). */
	float Flinch = 0.f;
	float VfxScale = 1.f;
};

/** Sekiro-style perilous attack: guard does not stop it; each kind has its own answer. */
enum class EBFPerilous : uint8
{
	None,
	/** Grab: only a dodge (i-frames) escapes it. Guard and parry do nothing. */
	Grab,
	/** Ground wave: jump over it (then stomp the boss in mid-air). Guard does nothing. */
	Sweep,
	/** Thrust: dodge INTO it for a counter, or parry it. Blocking does not stop it. */
	Thrust,
};

/** What a weapon hit carries to the target. */
struct FBFHitInfo
{
	float Damage = 0.f;
	float PostureDamage = 0.f;
	bool bFinisher = false;
	EBFHitWeight Weight = EBFHitWeight::Light;
	/** Big enemy attack: a parry on it starts a strength clash (mash guard). */
	bool bHeavy = false;
	FVector ImpactPoint = FVector::ZeroVector;
	/** Direction the blade was travelling at contact (world, may be zero). Picks the hit-react side. */
	FVector SwingDir = FVector::ZeroVector;
	TWeakObjectPtr<AActor> Instigator;
	EBFPerilous Perilous = EBFPerilous::None;
	/** Boss magic: cannot be guarded or parried; a roll's i-frames slip it, but it is no perfect dodge. */
	bool bMagic = false;
	/** Launches the player into the air (knock-up), then floors them. */
	bool bKnockUp = false;
	/** Hidden stance damage (Elden Ring style); negative = derived from Weight. */
	float StanceDamage = -1.f;
};

/** Boss spell cast from the air (the caster rises out of reach while charging). */
enum class EBFMagic : uint8
{
	None,
	/** A line of fire runs along the floor from the caster toward the player's last position, to the arena edge. */
	FireLine,
	/** A circle erupts under the player's last position after a short warning. */
	Circle,
	/** A green energy orb grows in his claw while he charges, flies at the player's spot and bursts over an area. */
	Orb,
};

/** One enemy attack: clip, speed, the swing window that can connect, and its reach. */
struct FBFEnemyAttack
{
	const TCHAR* AnimPath = nullptr;
	float PlayRate = 1.f;
	/** Swing window in animation seconds; the first frame the player is in reach resolves the hit. */
	float HitStart = 0.f;
	float HitEnd = 0.f;
	float Range = 260.f;
	float HalfAngleDeg = 70.f;
	float Damage = 15.f;
	float PostureDamage = 20.f;
	/** Big attack: parrying it starts a strength clash instead of a plain deflect. */
	bool bHeavy = false;
	/** Blend from whatever was playing into the swing, and (with no chain / recovery) back to idle. */
	float BlendIn = 0.15f;
	float BlendOut = 0.3f;
	/** Combo: when this swing's clip ends, continue straight into this attack (its clip starts in this one's end pose). */
	int32 ChainNext = INDEX_NONE;
	/** Only reachable through a chain, never picked on its own. */
	bool bChainOnly = false;
	/** Clip that carries the end pose of the swing back to idle (instead of a blend), from RecoverStart seconds. */
	const TCHAR* RecoverPath = nullptr;
	float RecoverStart = 0.f;
	float RecoverRate = 1.f;

	// --- AI chooser ---
	/** Picked only while the player is this far away (cm). MaxDist < 0 = the enemy's EngageRange. */
	float MinDist = 0.f;
	float MaxDist = -1.f;
	float Weight = 1.f;
	/** Boss phases this attack belongs to (1 = from the start, 2 = after the half-health transition). */
	int32 MinPhase = 1;
	int32 MaxPhase = 2;
	/** Weight multiplier in phase 2. */
	float Phase2Weight = 1.f;
	/** Favoured when the player spams rolls (delayed or tracking attacks). */
	bool bAntiRoll = false;
	/** Delayed wind-up (Elden Ring style): at HoldAt (anim seconds) the clip may freeze for a random time. */
	float HoldAt = -1.f;
	float HoldChance = 0.f;
	float HoldMin = 0.25f;
	float HoldMax = 0.6f;

	// --- Motion warp (the swings are in-place clips) ---
	/** Up to WarpDist cm of travel toward the player before the hit, stopping WarpStop cm from them. */
	float WarpDist = 0.f;
	float WarpStop = 190.f;
	float WarpSpeed = 700.f;
	/** Warp starts at this anim time. */
	float WarpFrom = 0.f;

	// --- Perilous ---
	EBFPerilous Perilous = EBFPerilous::None;
	/** Sweep: at HitStart the weapon plants and a ground wave rolls outward instead of a swing check. */
	bool bGroundWave = false;
	float WaveSpeed = 1000.f;
	float WaveRange = 900.f;

	// --- Magic (rises, charges, releases; untouchable while airborne) ---
	EBFMagic Magic = EBFMagic::None;
	/** Seconds the charge pose is held before release (phase 2 shortens it). */
	float ChargeTime = 0.8f;
	/** How high the caster floats (cm). */
	float RiseHeight = 320.f;
};

/** How the player answered an enemy swing. */
enum class EBFHitResult : uint8
{
	Hit,
	Blocked,
	Parried,
	Dodged,
	GuardBroken,
	/** Perilous grab connected: the player is held and drained. */
	Grabbed,
	/** Perilous answer landed: jumped the wave, or dodged into the thrust. */
	Countered,
};

namespace BFCombat
{
	/** Showcase / trailer recordings: damage multipliers (enemy pacing, keep the player alive). */
	inline float TestDamageToEnemy = 1.f;
	inline float TestDamageToPlayer = 1.f;

	/** Hitstop lengths in real seconds. */
	constexpr float HitstopLight = 0.07f;
	constexpr float HitstopFinisher = 0.14f;
	/** Time dilation while frozen; slightly above zero so animation still creeps. */
	constexpr float HitstopDilation = 0.02f;
	constexpr float HitstopParry = 0.14f;
	constexpr float HitstopExecution = 0.28f;
	/** Perfect parry: guard pressed at most this long (real seconds) before the swing connects. */
	constexpr float ParryWindow = 0.2f;
	/** Heavy (clash) attacks are rarer and telegraphed by a "now" cue: a little more forgiving. */
	constexpr float HeavyParryWindow = 0.3f;
	/** A heavy swing flashes its "parry / roll now" cue this long (real seconds) before it connects. */
	constexpr float ParryCueLead = 0.35f;
	/** Weapon hits slow the fighters to this instead of freezing them (clash cinematics still freeze). */
	constexpr float HitPauseDilation = 0.1f;
	/** Damage multiplier on an enemy caught in an opening (attack recovery / whiffed perilous move). */
	constexpr float PunishDamageScale = 1.3f;
	/** Dodge charges: spent per roll; all refill this many seconds after the stack first drops below max
	 *  (rolls during the reload do not restart it). */
	constexpr int32 MaxDashCharges = 4;
	constexpr float DashRefillDelay = 8.f;
	/** A grab still counts as perfectly dodged (-> clash) when a dash started this long before it reaches
	 * (his windup can be held, so a dash on the first cue lands early). */
	constexpr float GrabDodgeGrace = 0.8f;

	/** Sevarog's soul magic: same green as his aura (M_BossAura "Color"), with lighter / brighter variants. */
	inline FLinearColor BossMagicColor() { return FLinearColor(0.2f, 0.9f, 0.5f); }
	inline FLinearColor BossMagicPale() { return FLinearColor(0.65f, 1.f, 0.8f); }
	inline FLinearColor BossMagicHot() { return FLinearColor(0.35f, 1.f, 0.6f); }

	inline FLinearColor PerilousColor(EBFPerilous P)
	{
		switch (P)
		{
		case EBFPerilous::Grab: return FLinearColor(0.62f, 0.12f, 1.f);
		case EBFPerilous::Sweep: return FLinearColor(1.f, 0.72f, 0.05f);
		case EBFPerilous::Thrust: return FLinearColor(1.f, 0.05f, 0.2f);
		default: return FLinearColor::White;
		}
	}

	/** Impact profile per hit weight. The victim always freezes longer than the attacker. */
	inline const FBFImpactProfile& GetImpactProfile(EBFHitWeight Weight)
	{
		//                                         atkStop victimStop shake  time  fov  push  flinch vfx
		static const FBFImpactProfile Light     { 0.06f,  0.09f,     3.5f,  0.14f, 0.f, 150.f, 1.0f, 1.0f };
		static const FBFImpactProfile Heavy     { 0.09f,  0.13f,     6.f,   0.20f, 3.f, 380.f, 1.6f, 1.5f };
		static const FBFImpactProfile Finisher  { 0.14f,  0.20f,     10.f,  0.32f, 6.f, 650.f, 2.2f, 2.2f };
		static const FBFImpactProfile Execution { 0.28f,  0.28f,     13.f,  0.45f, 9.f, 0.f,   2.5f, 3.0f };
		switch (Weight)
		{
		case EBFHitWeight::Heavy: return Heavy;
		case EBFHitWeight::Finisher: return Finisher;
		case EBFHitWeight::Execution: return Execution;
		default: return Light;
		}
	}
}
