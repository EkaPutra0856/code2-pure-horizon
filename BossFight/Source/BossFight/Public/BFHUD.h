#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "BFCombatTypes.h"
#include "BFHUD.generated.h"

class ABFEnemyBase;
class ABFPlayerCharacter;

/**
 * Combat HUD drawn with the canvas (final UI comes in phase 8).
 * Bottom-left: player HP (with a delayed chip bar and the Guard Regain segment) and the four dodge
 * charge pips. Bottom-centre: player posture. Top-centre: boss name, HP (chip bar, phase notch) and
 * posture (glows when nearly broken). In the world: lock-on reticle, Sekiro-style perilous warning
 * above the boss, "OPENING" while he can be punished. Letterbox and title during the phase cutscene.
 */
UCLASS()
class BOSSFIGHT_API ABFHUD : public AHUD
{
	GENERATED_BODY()

public:
	virtual void DrawHUD() override;

private:
	void DrawBar(float X, float Y, float W, float H, float Ratio, const FLinearColor& Fill);
	void DrawPostureBar(float CenterX, float Y, float HalfW, float H, float Ratio);
	void DrawStruggle(float W, float H, float S, float Balance, float TimeLeft01, float Punch);
	void DrawPlayer(const ABFPlayerCharacter* Player, float W, float H, float S);
	void DrawDashPips(const ABFPlayerCharacter* Player, float X, float Y, float S);
	void DrawBoss(const ABFEnemyBase* Enemy, float W, float H, float S);
	void DrawLockReticle(const ABFPlayerCharacter* Player, float S);
	void DrawPerilous(const ABFEnemyBase* Enemy, float S);
	void DrawCinematic(const ABFPlayerCharacter* Player, const ABFEnemyBase* Enemy, float W, float H, float S);
	void DrawCircle(const FVector2D& Center, float Radius, const FLinearColor& Color, float Thickness, int32 Segments = 32);
	void DrawDiamond(const FVector2D& Center, float Radius, const FLinearColor& Color);
	void DrawTextCentered(const FString& Text, const FLinearColor& Color, float CX, float Y, float Scale, bool bBacking);
	/** Delayed "chip" bar: holds where the bar was, then drains down to it. */
	static void UpdateChip(float Ratio, float& Chip, float& Last, double& HoldUntil, double Now, float Dt);

	float PlayerChip = -1.f;
	float PlayerLast = -1.f;
	double PlayerChipHold = 0.0;
	float EnemyChip = -1.f;
	float EnemyLast = -1.f;
	double EnemyChipHold = 0.0;
	TWeakObjectPtr<const ABFEnemyBase> ChipEnemy;
};
