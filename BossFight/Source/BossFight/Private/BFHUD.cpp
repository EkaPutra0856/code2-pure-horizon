#include "BFHUD.h"

#include "BFEnemyBase.h"
#include "BFPlayerCharacter.h"
#include "CanvasItem.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "EngineUtils.h"
#include "Misc/App.h"

namespace
{
	const FLinearColor BarBack(0.02f, 0.02f, 0.02f, 0.75f);
	const FLinearColor HealthRed(0.75f, 0.06f, 0.05f, 1.f);
	const FLinearColor ChipYellow(1.f, 0.78f, 0.25f, 0.9f);
	const FLinearColor RegainGrey(0.85f, 0.78f, 0.72f, 0.55f);
	const FLinearColor DashCyan(0.35f, 0.8f, 1.f, 1.f);
	const FLinearColor OpeningGold(1.f, 0.78f, 0.3f, 1.f);

	UFont* LargeFont()
	{
		return GEngine ? GEngine->GetLargeFont() : nullptr;
	}

}

void ABFHUD::UpdateChip(float Ratio, float& Chip, float& Last, double& HoldUntil, double Now, float Dt)
{
	if (Chip < 0.f || Ratio >= Chip)
	{
		Chip = Ratio;
	}
	else
	{
		if (Ratio < Last - 0.0001f)
		{
			HoldUntil = Now + 0.6; // every new hit restarts the hold
		}
		if (Now >= HoldUntil)
		{
			Chip = FMath::Max(Ratio, Chip - 0.55f * Dt);
		}
	}
	Last = Ratio;
}

void ABFHUD::DrawBar(float X, float Y, float W, float H, float Ratio, const FLinearColor& Fill)
{
	DrawRect(BarBack, X - 2.f, Y - 2.f, W + 4.f, H + 4.f);
	DrawRect(Fill, X, Y, W * FMath::Clamp(Ratio, 0.f, 1.f), H);
}

void ABFHUD::DrawPostureBar(float CenterX, float Y, float HalfW, float H, float Ratio)
{
	Ratio = FMath::Clamp(Ratio, 0.f, 1.f);
	if (Ratio <= 0.01f)
	{
		return;
	}
	// Yellow to orange to red as it fills.
	const FLinearColor Fill = Ratio < 0.6f
		? FMath::Lerp(FLinearColor(1.f, 0.85f, 0.2f), FLinearColor(1.f, 0.45f, 0.05f), Ratio / 0.6f)
		: FMath::Lerp(FLinearColor(1.f, 0.45f, 0.05f), FLinearColor(1.f, 0.08f, 0.02f), (Ratio - 0.6f) / 0.4f);
	DrawRect(BarBack, CenterX - HalfW - 2.f, Y - 2.f, HalfW * 2.f + 4.f, H + 4.f);
	DrawRect(Fill, CenterX - HalfW * Ratio, Y, HalfW * 2.f * Ratio, H);
	// Centre notch.
	DrawRect(FLinearColor(1.f, 1.f, 1.f, 0.6f), CenterX - 1.f, Y - 3.f, 2.f, H + 6.f);
}

void ABFHUD::DrawCircle(const FVector2D& Center, float Radius, const FLinearColor& Color, float Thickness, int32 Segments)
{
	FVector2D Prev = Center + FVector2D(Radius, 0.f);
	for (int32 i = 1; i <= Segments; ++i)
	{
		const float A = UE_TWO_PI * i / Segments;
		const FVector2D Next = Center + FVector2D(FMath::Cos(A), FMath::Sin(A)) * Radius;
		FCanvasLineItem Line(Prev, Next);
		Line.SetColor(Color);
		Line.LineThickness = Thickness;
		Line.BlendMode = SE_BLEND_Translucent;
		Canvas->DrawItem(Line);
		Prev = Next;
	}
}

void ABFHUD::DrawDiamond(const FVector2D& Center, float Radius, const FLinearColor& Color)
{
	const FVector2D Top = Center + FVector2D(0.f, -Radius);
	const FVector2D Right = Center + FVector2D(Radius, 0.f);
	const FVector2D Bottom = Center + FVector2D(0.f, Radius);
	const FVector2D Left = Center + FVector2D(-Radius, 0.f);
	for (const auto& Tri : { TArray<FVector2D>{ Top, Right, Bottom }, TArray<FVector2D>{ Top, Bottom, Left } })
	{
		FCanvasTriangleItem Item(Tri[0], Tri[1], Tri[2], GWhiteTexture);
		Item.SetColor(Color);
		Item.BlendMode = SE_BLEND_Translucent;
		Canvas->DrawItem(Item);
	}
}

void ABFHUD::DrawTextCentered(const FString& Text, const FLinearColor& Color, float CX, float Y, float Scale, bool bBacking)
{
	float TW = 0.f, TH = 0.f;
	GetTextSize(Text, TW, TH, LargeFont(), Scale);
	if (bBacking)
	{
		DrawRect(FLinearColor(0.f, 0.f, 0.f, 0.6f * Color.A), CX - TW * 0.5f - 10.f * Scale, Y - 3.f * Scale, TW + 20.f * Scale, TH + 6.f * Scale);
	}
	DrawText(Text, Color, CX - TW * 0.5f, Y, LargeFont(), Scale);
}

void ABFHUD::DrawStruggle(float W, float H, float S, float Balance, float TimeLeft01, float Punch)
{
	// Tug-of-war bar: player power (orange) from the left, enemy power (red) from the right;
	// the white seam is where they meet. The whole widget trembles, harder on each press.
	const float Shake = (2.f + Punch * 7.f) * S;
	const float CX = W * 0.5f + FMath::FRandRange(-Shake, Shake);
	const float Y = H * 0.70f + FMath::FRandRange(-Shake, Shake);
	const float HalfW = 330.f * S;
	const float BarH = 26.f * S;
	const float Seam = CX + HalfW * FMath::Clamp(Balance, -1.f, 1.f);

	DrawRect(FLinearColor(0.f, 0.f, 0.f, 0.8f), CX - HalfW - 4.f * S, Y - 4.f * S, HalfW * 2.f + 8.f * S, BarH + 8.f * S);
	const FLinearColor PlayerCol = FMath::Lerp(FLinearColor(1.f, 0.55f, 0.08f), FLinearColor(1.f, 0.85f, 0.4f), Punch);
	DrawRect(PlayerCol, CX - HalfW, Y, Seam - (CX - HalfW), BarH);
	DrawRect(FLinearColor(0.75f, 0.05f, 0.04f), Seam, Y, CX + HalfW - Seam, BarH);
	DrawRect(FLinearColor::White, Seam - 3.f * S, Y - 8.f * S, 6.f * S, BarH + 16.f * S);
	// Centre notch: the seam must end past it when time runs out.
	DrawRect(FLinearColor(1.f, 1.f, 1.f, 0.35f), CX - 1.f, Y, 2.f, BarH);

	// Time left.
	DrawRect(FLinearColor(0.f, 0.f, 0.f, 0.7f), CX - HalfW, Y + BarH + 10.f * S, HalfW * 2.f, 6.f * S);
	DrawRect(FLinearColor(1.f, 1.f, 1.f, 0.85f), CX - HalfW, Y + BarH + 10.f * S, HalfW * 2.f * TimeLeft01, 6.f * S);

	UFont* Font = LargeFont();
	const float TextScale = (3.f + Punch * 0.5f) * S;
	const FString Prompt = TEXT("MASH  [LMB]");
	float TW = 0.f, TH = 0.f;
	GetTextSize(Prompt, TW, TH, Font, TextScale);
	const float TX = CX - TW * 0.5f;
	const float TY = Y - TH - 18.f * S;
	DrawRect(FLinearColor(0.f, 0.f, 0.f, 0.75f), TX - 14.f * S, TY - 4.f * S, TW + 28.f * S, TH + 8.f * S);
	DrawText(Prompt, FLinearColor(1.f, 0.9f, 0.55f), TX, TY, Font, TextScale);
}

void ABFHUD::DrawDashPips(const ABFPlayerCharacter* Player, float X, float Y, float S)
{
	// Four slanted pips; a perfect dodge flashes them white, an empty roll flashes red and shakes.
	const int32 Charges = Player->GetDashCharges();
	const float Gain = Player->GetDashGainFlash();
	const float Empty = Player->GetDashEmptyFlash();
	const float Refill = Player->GetDashRefillFlash();
	const float PipW = 40.f * S;
	const float PipH = 11.f * S;
	const float Gap = 7.f * S;
	const float Slant = 5.f * S;
	const float ShakeX = Empty > 0.f ? FMath::Sin(Empty * 40.f) * 4.f * S * Empty : 0.f;
	for (int32 i = 0; i < BFCombat::MaxDashCharges; ++i)
	{
		const float PX = X + ShakeX + i * (PipW + Gap);
		const bool bFull = i < Charges;
		FLinearColor C = bFull ? DashCyan : FLinearColor(0.08f, 0.1f, 0.12f, 0.85f);
		if (bFull)
		{
			C = FMath::Lerp(C, FLinearColor::White, FMath::Max(Gain, Refill) * 0.8f);
		}
		else if (Empty > 0.f)
		{
			C = FMath::Lerp(C, FLinearColor(0.9f, 0.1f, 0.05f, 0.95f), Empty);
		}
		// Back plate, then the slanted fill (parallelogram as two triangles).
		const FVector2D A(PX + Slant, Y), B(PX + PipW + Slant, Y), Cc(PX + PipW, Y + PipH), D(PX, Y + PipH);
		const FVector2D Pad(2.f * S, 0.f);
		for (const auto& Tri : { TArray<FVector2D>{ A - Pad, B + Pad, Cc + Pad }, TArray<FVector2D>{ A - Pad, Cc + Pad, D - Pad } })
		{
			FCanvasTriangleItem Back(Tri[0] - FVector2D(0.f, 2.f * S), Tri[1] - FVector2D(0.f, 2.f * S), Tri[2] + FVector2D(0.f, 2.f * S), GWhiteTexture);
			Back.SetColor(BarBack);
			Back.BlendMode = SE_BLEND_Translucent;
			Canvas->DrawItem(Back);
		}
		for (const auto& Tri : { TArray<FVector2D>{ A, B, Cc }, TArray<FVector2D>{ A, Cc, D } })
		{
			FCanvasTriangleItem Item(Tri[0], Tri[1], Tri[2], GWhiteTexture);
			Item.SetColor(C);
			Item.BlendMode = SE_BLEND_Translucent;
			Canvas->DrawItem(Item);
		}
	}
	// Refill timer: a thin line under the pips while any charge is spent.
	if (Charges < BFCombat::MaxDashCharges)
	{
		const float TotalW = BFCombat::MaxDashCharges * (PipW + Gap) - Gap + Slant;
		DrawRect(FLinearColor(0.f, 0.f, 0.f, 0.6f), X, Y + PipH + 5.f * S, TotalW, 3.f * S);
		DrawRect(FLinearColor(0.6f, 0.85f, 1.f, 0.85f), X, Y + PipH + 5.f * S, TotalW * Player->GetDashRefill01(), 3.f * S);
	}
}

void ABFHUD::DrawPlayer(const ABFPlayerCharacter* Player, float W, float H, float S)
{
	// Hurt pulse: red bands closing in from the screen edges, fading over ~0.6 s.
	if (const float Hurt = Player->GetHurtFlash(); Hurt > 0.f)
	{
		constexpr int32 NumLayers = 16;
		const float Depth = FMath::Min(W, H) * 0.16f;
		for (int32 i = 0; i < NumLayers; ++i)
		{
			const float D = Depth * (i + 1) / NumLayers;
			const float A = Hurt * 0.035f;
			const FLinearColor C(0.75f, 0.f, 0.f, A);
			for (const FVector4f& R : { FVector4f(0, 0, W, D), FVector4f(0, H - D, W, D), FVector4f(0, 0, D, H), FVector4f(W - D, 0, D, H) })
			{
				FCanvasTileItem Tile(FVector2D(R.X, R.Y), FVector2D(R.Z, R.W), C);
				Tile.BlendMode = SE_BLEND_Translucent;
				Canvas->DrawItem(Tile);
			}
		}
	}

	// HP: chip (delayed yellow), Guard Regain (pale, can be won back by attacking), current.
	const double Now = GetWorld()->GetRealTimeSeconds();
	const float Dt = FApp::GetDeltaTime();
	const float Max = FMath::Max(Player->GetMaxHealth(), 1.f);
	const float Ratio = FMath::Clamp(Player->GetHealth() / Max, 0.f, 1.f);
	UpdateChip(Ratio, PlayerChip, PlayerLast, PlayerChipHold, Now, Dt);
	const float BX = 48.f * S;
	const float BY = H - 86.f * S;
	const float BW = 420.f * S;
	const float BH = 14.f * S;
	DrawRect(BarBack, BX - 2.f, BY - 2.f, BW + 4.f, BH + 4.f);
	DrawRect(ChipYellow, BX, BY, BW * PlayerChip, BH);
	const float Regain = FMath::Clamp(Player->GetRegainHealth() / Max, 0.f, 1.f - Ratio);
	if (Regain > 0.f)
	{
		const float Pulse = 0.75f + 0.25f * FMath::Sin(float(Now) * 9.f);
		DrawRect(RegainGrey * FLinearColor(1.f, 1.f, 1.f, Pulse), BX + BW * Ratio, BY, BW * Regain, BH);
	}
	DrawRect(HealthRed, BX, BY, BW * Ratio, BH);
	DrawDashPips(Player, BX, BY + BH + 12.f * S, S);

	DrawPostureBar(W * 0.5f, H - 120.f * S, 230.f * S, 10.f * S, Player->GetPosture() / Player->GetMaxPosture());
	if (Player->IsStruggling())
	{
		DrawStruggle(W, H, S, Player->GetStruggleBalance(), Player->GetStruggleTimeLeft01(), Player->GetStrugglePunch());
	}
	// No "[LMB] STOMP" prompt either (playtest feedback: let players discover it).
}

void ABFHUD::DrawBoss(const ABFEnemyBase* Enemy, float W, float H, float S)
{
	if (ChipEnemy.Get() != Enemy)
	{
		ChipEnemy = Enemy;
		EnemyChip = EnemyLast = -1.f;
	}
	const double Now = GetWorld()->GetRealTimeSeconds();
	const float Ratio = FMath::Clamp(Enemy->GetHealth() / FMath::Max(Enemy->GetMaxHealth(), 1.f), 0.f, 1.f);
	UpdateChip(Ratio, EnemyChip, EnemyLast, EnemyChipHold, Now, FApp::GetDeltaTime());

	const float BarW = 640.f * S;
	const float X = (W - BarW) * 0.5f;
	const float Y = 70.f * S;
	const float BarH = 12.f * S;

	// Posture: glows and pulses once it is close to breaking.
	const float PostureRatio = Enemy->GetPosture() / Enemy->GetMaxPosture();
	if (PostureRatio >= 0.75f && !Enemy->IsBroken())
	{
		const float Glow = 0.35f + 0.3f * FMath::Sin(float(Now) * 10.f);
		const float HalfW = 260.f * S;
		for (int32 i = 1; i <= 3; ++i)
		{
			const float P = i * 3.f * S;
			DrawRect(FLinearColor(1.f, 0.25f, 0.05f, Glow / (i * 1.6f)), W * 0.5f - HalfW - P, Y - 26.f * S - P, HalfW * 2.f + P * 2.f, 10.f * S + P * 2.f);
		}
	}
	DrawPostureBar(W * 0.5f, Y - 26.f * S, 260.f * S, 10.f * S, PostureRatio);

	DrawRect(BarBack, X - 2.f, Y - 2.f, BarW + 4.f, BarH + 4.f);
	DrawRect(ChipYellow, X, Y, BarW * EnemyChip, BarH);
	DrawRect(HealthRed, X, Y, BarW * Ratio, BarH);
	if (Enemy->HasPhase2() && Enemy->GetPhase() == 1)
	{
		// Phase threshold notch at half health.
		DrawRect(FLinearColor(1.f, 1.f, 1.f, 0.7f), X + BarW * 0.5f - 1.f, Y - 4.f * S, 2.f, BarH + 8.f * S);
	}
	FString Name = Enemy->GetDisplayName();
	if (Enemy->GetPhase() >= 2)
	{
		Name += TEXT("  II");
	}
	DrawText(Name, FLinearColor(0.95f, 0.92f, 0.85f), X, Y + 18.f * S, LargeFont(), 1.1f * S);
	if (Enemy->IsPunishable())
	{
		// Opening (Return2Idle / dodged perilous follow-through): hits deal more damage.
		const float A = 0.7f + 0.3f * FMath::Sin(float(Now) * 12.f);
		const FString Tag = FString::Printf(TEXT("OPENING  x%.1f"), BFCombat::PunishDamageScale);
		float TW = 0.f, TH = 0.f;
		GetTextSize(Tag, TW, TH, LargeFont(), 1.1f * S);
		DrawText(Tag, OpeningGold * FLinearColor(1.f, 1.f, 1.f, A), X + BarW - TW, Y + 18.f * S, LargeFont(), 1.1f * S);
	}
	if (Enemy->IsBroken())
	{
		DrawText(TEXT("POSTURE BROKEN - ATTACK TO EXECUTE"), FLinearColor(1.f, 0.25f, 0.1f), W * 0.5f - 300.f * S, Y + 56.f * S, LargeFont(), 1.3f * S);
	}
}

void ABFHUD::DrawLockReticle(const ABFPlayerCharacter* Player, float S)
{
	const ABFEnemyBase* Target = Player->GetLockTarget();
	if (!Target || Player->IsCinematic())
	{
		return;
	}
	const FVector P = Project(Player->GetLockPoint());
	if (P.Z <= 0.f)
	{
		return;
	}
	// Small ring and dot; it pops in when acquired and turns gold while the target is open.
	const float Pop = Player->GetLockPop();
	const FVector2D C(P.X, P.Y);
	const FLinearColor Col = Target->IsPunishable() ? OpeningGold : FLinearColor(1.f, 1.f, 1.f, 0.9f);
	DrawCircle(C, (11.f + 26.f * Pop * Pop) * S, Col * FLinearColor(1.f, 1.f, 1.f, 0.85f), 2.f * S, 28);
	DrawCircle(C, 3.f * S, Col, 3.f * S, 10);
}

void ABFHUD::DrawPerilous(const ABFEnemyBase* Enemy, float S)
{
	const EBFPerilous Kind = Enemy->GetPerilous();
	if (Kind == EBFPerilous::None)
	{
		return;
	}
	const FVector P = Project(Enemy->GetActorLocation() + FVector(0.f, 0.f, Enemy->GetHalfHeight() + 70.f));
	if (P.Z <= 0.f)
	{
		return;
	}
	// Sekiro-style warning: coloured diamond that slams in, then the answer underneath.
	const float Age = Enemy->GetPerilousAge();
	const float In = FMath::Clamp(Age / 0.12f, 0.f, 1.f);
	const float Scale = FMath::Lerp(2.2f, 1.f, FMath::InterpEaseOut(0.f, 1.f, In, 3.f));
	const float Flicker = Age < 0.4f ? 0.75f + 0.25f * FMath::Sin(Age * 60.f) : 1.f;
	const FLinearColor Col = BFCombat::PerilousColor(Kind);
	const FVector2D C(P.X, P.Y);
	DrawDiamond(C, 34.f * S * Scale, FLinearColor(0.f, 0.f, 0.f, 0.7f * In));
	DrawDiamond(C, 29.f * S * Scale, Col * FLinearColor(1.f, 1.f, 1.f, In * Flicker));
	DrawDiamond(C, 12.f * S * Scale, FLinearColor(1.f, 1.f, 1.f, 0.9f * In));
	// No answer text under the diamond (playtest feedback): players work out jump / dodge themselves.
}

void ABFHUD::DrawCinematic(const ABFPlayerCharacter* Player, const ABFEnemyBase* Enemy, float W, float H, float S)
{
	const float A = Player->GetCinematicAlpha();
	if (A <= 0.f)
	{
		return;
	}
	const float Bar = H * 0.12f * A;
	DrawRect(FLinearColor::Black, 0.f, 0.f, W, Bar);
	DrawRect(FLinearColor::Black, 0.f, H - Bar, W, Bar);
	if (Enemy)
	{
		const float TA = Player->GetCinematicTitleAlpha();
		if (TA > 0.f)
		{
			const FString Title = FString::Printf(TEXT("%s  -  PHASE II"), *Enemy->GetDisplayName().ToUpper());
			const float Y = H - Bar + Bar * 0.22f + (1.f - TA) * 14.f * S;
			DrawTextCentered(Title, FLinearColor(0.95f, 0.85f, 0.75f, TA), W * 0.5f, Y, 3.4f * S, false);
			const float LineW = W * 0.22f * TA;
			DrawRect(FLinearColor(0.35f, 1.f, 0.6f, 0.8f * TA), W * 0.5f - LineW, Y - 8.f * S, LineW * 2.f, 2.f * S);
		}
	}
}

void ABFHUD::DrawHUD()
{
	Super::DrawHUD();
	if (!Canvas)
	{
		return;
	}
	const float W = Canvas->ClipX;
	const float H = Canvas->ClipY;
	const float S = H / 1080.f; // scale with resolution

	const ABFPlayerCharacter* Player = Cast<ABFPlayerCharacter>(GetOwningPawn());

	// Boss shown: the locked target, else the nearest living enemy.
	const ABFEnemyBase* Enemy = Player ? Player->GetLockTarget() : nullptr;
	if (!Enemy)
	{
		float BestDistSq = TNumericLimits<float>::Max();
		const FVector From = GetOwningPawn() ? GetOwningPawn()->GetActorLocation() : FVector::ZeroVector;
		for (TActorIterator<ABFEnemyBase> It(GetWorld()); It; ++It)
		{
			const float DistSq = FVector::DistSquared(It->GetActorLocation(), From);
			if (DistSq < BestDistSq)
			{
				BestDistSq = DistSq;
				Enemy = *It;
			}
		}
	}

	const bool bCine = Player && Player->IsCinematic();
	if (Enemy && !bCine)
	{
		DrawPerilous(Enemy, S);
	}
	if (Player)
	{
		DrawLockReticle(Player, S);
		if (!bCine)
		{
			DrawPlayer(Player, W, H, S);
		}
	}
	if (Enemy && !bCine && !Enemy->IsHidden())
	{
		DrawBoss(Enemy, W, H, S);
	}
	if (Player)
	{
		DrawCinematic(Player, Enemy, W, H, S);
		// Impact frame: a white flash on top of the monochrome post-process for a frame or two.
		if (const float Impact = Player->GetImpactFrame(); Impact > 0.f)
		{
			FCanvasTileItem Tile(FVector2D::ZeroVector, FVector2D(W, H), FLinearColor(1.f, 1.f, 1.f, 0.22f * Impact));
			Tile.BlendMode = SE_BLEND_Translucent;
			Canvas->DrawItem(Tile);
		}
	}
}
