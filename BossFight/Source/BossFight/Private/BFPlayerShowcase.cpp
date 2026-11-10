// Showcase recordings: a bot that plays the boss fight like a person (gameplay video) and a cinematic
// camera director (trailer). Run with:
//   -BFAutoTest=showcase|trailer -BFCapture -UseFixedTimeStep -FPS=30 -deterministicaudio
// -BFCapture writes one HighResShot per frame (Screenshots/WindowsEditor/Cap_<name>_NNNNN.png) and records
// the game's audio output in sync (non-realtime mixer) to Saved/BouncedWavFiles/<name>.wav.
// Flags: -BFShowLen=<s> -BFShowName= -BFCapRes=1080x1920 -BFShowFov= -BFShowArm= -BFMusic=<sound path>
//        -BFMusicVol= -BFMusic2= -BFMusic2At=<s> -BFShowPlayerDmg=

#include "BFPlayerCharacter.h"
#include "BFEnemyBase.h"
#include "BFCombatTypes.h"
#include "AudioMixerBlueprintLibrary.h"
#include "AssetCompilingManager.h"
#include "ShaderCompiler.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "Components/AudioComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/LightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "Camera/PlayerCameraManager.h"
#include "EngineUtils.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/HUD.h"
#include "GameFramework/SpringArmComponent.h"
#include "Animation/AnimInstance.h"
#include "Animation/AnimMontage.h"
#include "Animation/AnimSequence.h"
#include "Animation/MorphTarget.h"
#include "Components/SkeletalMeshComponent.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/App.h"
#include "Sound/SoundBase.h"

namespace
{
	float ShowFlag(const TCHAR* Name, float Default)
	{
		float V = Default;
		FParse::Value(FCommandLine::Get(), Name, V);
		return V;
	}

	FString ShowFlagStr(const TCHAR* Name, const FString& Default)
	{
		FString V = Default;
		FParse::Value(FCommandLine::Get(), Name, V, false);
		return V;
	}

	float Ease01(float X)
	{
		X = FMath::Clamp(X, 0.f, 1.f);
		return X * X * (3.f - 2.f * X);
	}

	/** Boss health (0..1) the recording should be at, so the fight hits its beats on time. */
	float PaceTarget(bool bTrailer, float T)
	{
		if (bTrailer)
		{
			if (T < 21.f) return 1.f;
			if (T < 46.f) return FMath::Lerp(1.f, 0.48f, (T - 21.f) / 25.f);
			return FMath::Lerp(0.48f, 0.3f, FMath::Clamp((T - 46.f) / 14.f, 0.f, 1.f));
		}
		if (T < 4.f) return 1.f;
		if (T < 37.f) return FMath::Lerp(1.f, 0.48f, (T - 4.f) / 33.f);
		if (T < 45.f) return 0.48f;
		return FMath::Lerp(0.48f, 0.f, FMath::Clamp((T - 45.f) / 35.f, 0.f, 1.f));
	}

	struct FBotStep
	{
		float Delay;
		TCHAR Act; // L light, H heavy, J jump, D dash at him (blink), S side dash, B back dash
	};

	const TArray<TArray<FBotStep>>& BotRoutines()
	{
		static const TArray<TArray<FBotStep>> R = {
			{ { 0.f, 'L' }, { 0.36f, 'L' }, { 0.4f, 'L' } },
			{ { 0.f, 'J' }, { 0.24f, 'L' }, { 0.34f, 'L' }, { 0.36f, 'L' }, { 0.36f, 'H' } },
			{ { 0.f, 'L' }, { 0.34f, 'D' }, { 0.5f, 'L' }, { 0.4f, 'L' } },
			{ { 0.f, 'L' }, { 0.36f, 'L' }, { 0.45f, 'H' } },
			{ { 0.f, 'L' }, { 0.32f, 'J' }, { 0.22f, 'L' }, { 0.36f, 'H' } },
			{ { 0.f, 'H' }, { 0.8f, 'H' } },
			{ { 0.f, 'L' }, { 0.36f, 'L' }, { 0.4f, 'L' }, { 0.5f, 'B' } },
			{ { 0.f, 'S' }, { 0.45f, 'L' }, { 0.36f, 'L' } },
		};
		return R;
	}
}

void ABFPlayerCharacter::BotMove(const FVector& Dir, float Scale)
{
	const FVector D = Dir.GetSafeNormal2D();
	if (D.IsNearlyZero())
	{
		return;
	}
	LastMoveInput = D;
	LastMoveInputTime = GetWorld()->GetRealTimeSeconds();
	if (State == EBFPlayerState::Free && !bCinematic && !bGrabbed)
	{
		AddMovementInput(D, Scale);
	}
}

void ABFPlayerCharacter::BotDash(const FVector& Dir)
{
	LastMoveInput = Dir.GetSafeNormal2D();
	LastMoveInputTime = GetWorld()->GetRealTimeSeconds();
	OnDashPressed();
}

void ABFPlayerCharacter::BotJump()
{
	OnJumpPressed();
	BotJumpRelease = GetWorld()->GetRealTimeSeconds() + 0.15;
}

namespace
{
	/** Scenery film (no fighters): six slow 10 s shots around the arena centre C. F = start facing (player -> boss). */
	void TickSceneryCamera(UWorld* World, ACameraActor* Cam, const FVector& C, const FVector& F, float T)
	{
		// 10 s slots: close tour (0-4), then the far views (6-8), the crane into the sky (5) closes. 60 s films end after slot 5.
		static const int32 Order[9] = { 0, 1, 2, 3, 4, 6, 7, 8, 5 };
		const int32 Slots = FMath::Max(1, int32((ShowFlag(TEXT("BFShowLen="), 60.f) + ShowFlag(TEXT("BFSceneryOffset="), 0.f)) / 10.f + 0.5f));
		const int32 Slot = FMath::Clamp(int32(T / 10.f), 0, FMath::Min(Slots, 9) - 1);
		const int32 Shot = Slots >= 9 ? Order[Slot] : FMath::Min(Slot, 5);
		const float U = T - Slot * 10.f;
		const float A = Ease01(U / 10.f);
		const float L = U / 10.f; // linear: steady drift, no stop at the end of a shot
		const FVector Up(0.f, 0.f, 1.f);
		auto Dir = [&F](float Yaw) { return F.RotateAngleAxis(Yaw, FVector::UpVector).GetSafeNormal2D(); };
		FVector Loc;
		FVector Look;
		float Fov = 58.f;
		switch (Shot)
		{
		case 0: // establishing: high over the temple, sinking in
			Loc = C + Dir(200.f + L * 20.f) * FMath::Lerp(1300.f, 850.f, A) + Up * FMath::Lerp(900.f, 330.f, A);
			Look = C - Dir(200.f) * 700.f + Up * FMath::Lerp(150.f, 230.f, A);
			Fov = FMath::Lerp(62.f, 56.f, A);
			break;
		case 1: // low glide over the water toward the centre
			Loc = C + Dir(130.f) * FMath::Lerp(1350.f, 450.f, L) + Up * 70.f;
			Look = C + Dir(130.f) * FMath::Lerp(900.f, -300.f, L) + Up * 130.f;
			break;
		case 2: // slow orbit, mid height
			Loc = C + Dir(40.f + L * 50.f) * 1200.f + Up * 380.f;
			Look = C + Up * 100.f;
			break;
		case 3: // from the middle, tilting up from the ruins to the sky
			Loc = C + Dir(-30.f) * 450.f + Up * 45.f;
			Look = Loc + Dir(-30.f + L * 25.f) * 1200.f + Up * FMath::Lerp(60.f, 1000.f, A);
			Fov = 60.f;
			break;
		case 4: // lateral track past the edge, looking in
		{
			const FVector D = Dir(250.f);
			const FVector Side = FVector::CrossProduct(Up, D);
			Loc = C + D * 950.f + Side * FMath::Lerp(-450.f, 450.f, L) + Up * 170.f;
			Look = C + Side * FMath::Lerp(-150.f, 150.f, L) + Up * 120.f;
			break;
		}
		case 6: // far: wide orbit from across the valley
			Loc = C + Dir(165.f + L * 20.f) * 2300.f + Up * 1900.f;
			Look = C - Dir(165.f + L * 20.f) * 1800.f + Up * 150.f;
			Fov = 60.f;
			break;
		case 7: // far: down the river, looking upstream at the falls, drifting in
			Loc = FVector(FMath::Lerp(-2900.f, -2300.f, L), FMath::Lerp(-1050.f, -880.f, L), FMath::Lerp(1450.f, 1250.f, L));
			Look = FVector(2700.f, 1150.f, 120.f);
			Fov = 52.f;
			break;
		case 8: // far: very high crane over the whole temple
			Loc = C + Dir(250.f - L * 25.f) * 2100.f + Up * FMath::Lerp(2400.f, 2900.f, A);
			Look = C - Dir(250.f - L * 25.f) * 3000.f + Up * 100.f;
			Fov = 62.f;
			break;
		default: // finale: crane up and away into the sky
			Loc = C + Dir(160.f) * FMath::Lerp(800.f, 1700.f, A) + Up * FMath::Lerp(220.f, 1600.f, A);
			Look = C + Up * FMath::Lerp(100.f, 1300.f, A);
			Fov = 56.f;
			break;
		}
		// Keep the lens out of walls and props between it and the centre.
		FHitResult Hit;
		if (Shot < 6 && World->SweepSingleByChannel(Hit, C + Up * 150.f, Loc, FQuat::Identity, ECC_Camera, FCollisionShape::MakeSphere(25.f),
			FCollisionQueryParams(SCENE_QUERY_STAT(BFSceneryCam), false)))
		{
			Loc = Hit.Location;
		}
		Cam->SetActorLocationAndRotation(Loc, (Look - Loc).Rotation());
		Cam->GetCameraComponent()->SetFieldOfView(Fov);
		static int32 LastShot = -1;
		if (Shot != LastShot)
		{
			LastShot = Shot;
			UE_LOG(LogTemp, Display, TEXT("BFTEST scenery shot %d t=%.2f"), Shot, T);
		}
	}

	// -BFBuildUp (scenery mode): a "the map being built" timelapse. Everything but the ground and the sky starts hidden,
	// then comes back group by group (structures, water, props, foliage, lights, VFX), nearest to the centre first.
	struct FBuildItem
	{
		TWeakObjectPtr<USceneComponent> Comp;
		int32 Group = 0;
		float Dist = 0.f;
		bool bShown = false;
	};
	TArray<FBuildItem> GBuildItems;
	// Share of the build-up length at which each group starts and ends.
	const float GBuildWindow[6][2] = { { 0.f, 0.38f }, { 0.34f, 0.44f }, { 0.42f, 0.64f }, { 0.58f, 0.82f }, { 0.8f, 0.9f }, { 0.88f, 0.96f } };

	int32 BuildGroupOf(const AActor* Owner, const USceneComponent* C)
	{
		const FString Cls = Owner->GetClass()->GetName();
		const FString Name = Owner->GetActorNameOrLabel();
		if (Cls.Contains(TEXT("Flux")) || Name.Contains(TEXT("Flux")) || Name.Contains(TEXT("Water")) || Name.Contains(TEXT("River")))
		{
			return 1;
		}
		if (C->IsA<ULightComponent>())
		{
			return 4;
		}
		const FString CCls = C->GetClass()->GetName();
		if (CCls.Contains(TEXT("Niagara")) || CCls.Contains(TEXT("Particle")))
		{
			return 5;
		}
		FString MeshPath;
		if (const UStaticMeshComponent* SM = Cast<UStaticMeshComponent>(C))
		{
			MeshPath = SM->GetStaticMesh() ? SM->GetStaticMesh()->GetPathName() : FString();
		}
		static const TCHAR* Green[] = { TEXT("Tree"), TEXT("Grass"), TEXT("Bush"), TEXT("Plant"), TEXT("Foliage"), TEXT("Flower"), TEXT("Fern"), TEXT("Leaf"), TEXT("Ivy"), TEXT("Moss") };
		for (const TCHAR* G : Green)
		{
			if (Cls.Contains(G) || Name.Contains(G) || MeshPath.Contains(G))
			{
				return 3;
			}
		}
		if (Cls.Contains(TEXT("InstancedFoliage")))
		{
			return 3;
		}
		const UPrimitiveComponent* P = Cast<UPrimitiveComponent>(C);
		return P && P->Bounds.SphereRadius > 400.f ? 0 : 2;
	}
}

void ABFPlayerCharacter::SetupBuildUp(const TArray<AActor*>& Keep)
{
	int32 Counts[6] = { 0 };
	for (TActorIterator<AActor> It(GetWorld()); It; ++It)
	{
		AActor* A = *It;
		if (A->IsHidden() || Keep.Contains(A) || A->IsA<APawn>() || A->IsA<ACameraActor>())
		{
			continue;
		}
		const FString Cls = A->GetClass()->GetName();
		static const TCHAR* Skip[] = { TEXT("Landscape"), TEXT("Sky"), TEXT("Atmosphere"), TEXT("Cloud"), TEXT("Fog"), TEXT("PostProcess"), TEXT("WorldSettings"), TEXT("Brush"), TEXT("Volume") };
		bool bSkip = false;
		for (const TCHAR* S : Skip)
		{
			bSkip |= Cls.Contains(S);
		}
		if (bSkip)
		{
			continue;
		}
		TArray<USceneComponent*> Comps;
		A->GetComponents(Comps);
		for (USceneComponent* C : Comps)
		{
			const bool bLight = C->IsA<ULightComponent>();
			if (!(bLight || C->IsA<UPrimitiveComponent>()) || C->bHiddenInGame || !C->IsVisible())
			{
				continue;
			}
			if (const ULightComponent* L = Cast<ULightComponent>(C); L && (Cls.Contains(TEXT("Directional")) || Cls.Contains(TEXT("SkyLight"))))
			{
				continue;
			}
			FBuildItem Item;
			Item.Comp = C;
			Item.Group = BuildGroupOf(A, C);
			const FVector Pos = C->IsA<UPrimitiveComponent>() ? Cast<UPrimitiveComponent>(C)->Bounds.Origin : C->GetComponentLocation();
			Item.Dist = FVector::Dist2D(Pos, TrailerB);
			C->SetHiddenInGame(true);
			GBuildItems.Add(Item);
			++Counts[Item.Group];
		}
	}
	// Hidden pieces must not leave cached shadows behind.
	if (APlayerController* PC = Cast<APlayerController>(GetController()))
	{
		PC->ConsoleCommand(TEXT("r.Shadow.Virtual.Cache 0"));
	}
	GBuildItems.Sort([](const FBuildItem& X, const FBuildItem& Y) { return X.Group != Y.Group ? X.Group < Y.Group : X.Dist < Y.Dist; });
	UE_LOG(LogTemp, Display, TEXT("BFTEST buildup items=%d struct=%d water=%d props=%d green=%d lights=%d vfx=%d"), GBuildItems.Num(),
		Counts[0], Counts[1], Counts[2], Counts[3], Counts[4], Counts[5]);
}

void ABFPlayerCharacter::TickBuildUp(float T)
{
	static const float Start = ShowFlag(TEXT("BFBuildStart="), 1.5f);
	static const float Len = ShowFlag(TEXT("BFBuildLen="), 16.f);
	const float U = (T - Start) / FMath::Max(1.f, Len);
	int32 GroupNum[6] = { 0 };
	for (const FBuildItem& I : GBuildItems)
	{
		++GroupNum[I.Group];
	}
	int32 GroupIdx[6] = { 0 };
	for (FBuildItem& I : GBuildItems)
	{
		const int32 K = GroupIdx[I.Group]++;
		const float W0 = GBuildWindow[I.Group][0];
		const float W1 = GBuildWindow[I.Group][1];
		const float At = W0 + (W1 - W0) * (GroupNum[I.Group] > 1 ? float(K) / (GroupNum[I.Group] - 1) : 0.f);
		if (!I.bShown && U >= At && I.Comp.IsValid())
		{
			I.bShown = true;
			I.Comp->SetHiddenInGame(false);
		}
	}
	static int32 LastStage = -1;
	const int32 Stage = FMath::Clamp(int32(U * 10.f), -1, 10);
	if (Stage != LastStage)
	{
		LastStage = Stage;
		UE_LOG(LogTemp, Display, TEXT("BFTEST buildup stage=%d t=%.2f"), Stage, T);
	}
	// Camera: one slow high orbit over the centre.
	if (ShowCam)
	{
		static const float Yaw0 = ShowFlag(TEXT("BFBuildYaw="), 200.f);
		static const float Radius = ShowFlag(TEXT("BFBuildDist="), 1250.f);
		static const float Height = ShowFlag(TEXT("BFBuildHeight="), 450.f);
		const float L = T / FMath::Max(1.f, ShowLen);
		const FVector Dir = TrailerA.RotateAngleAxis(Yaw0 + L * ShowFlag(TEXT("BFBuildOrbit="), 70.f), FVector::UpVector).GetSafeNormal2D();
		const FVector Loc = TrailerB + Dir * FMath::Lerp(Radius, Radius * 0.85f, L) + FVector(0.f, 0.f, FMath::Lerp(Height, Height * 0.8f, L));
		static const float LookZ = ShowFlag(TEXT("BFBuildLookZ="), 120.f);
		const FVector Look = TrailerB + FVector(0.f, 0.f, LookZ);
		ShowCam->SetActorLocationAndRotation(Loc, (Look - Loc).Rotation());
		ShowCam->GetCameraComponent()->SetFieldOfView(ShowFlag(TEXT("BFBuildFov="), 58.f));
	}
}

void ABFPlayerCharacter::TickShowcase(float Dt)
{
	const bool bTrailer = AutoTestMode == TEXT("trailer");
	const bool bScenery = AutoTestMode == TEXT("scenery");
	const bool bCutscene = AutoTestMode == TEXT("cutscene");
	const bool bFilm = bTrailer || bScenery || bCutscene; // own camera, no HUD
	APlayerController* PC = Cast<APlayerController>(GetController());
	ABFEnemyBase* Enemy = nullptr;
	for (TActorIterator<ABFEnemyBase> It(GetWorld()); It; ++It)
	{
		Enemy = *It;
		break;
	}

	if (ShowT < 0.f)
	{
		if (ShowWaitT == 0.f)
		{
			ShowLen = ShowFlag(TEXT("BFShowLen="), bFilm ? 60.f : 90.f);
			ShowName = ShowFlagStr(TEXT("BFShowName="), AutoTestMode);
			bShowCapture = FParse::Param(FCommandLine::Get(), TEXT("BFCapture"));
			CameraBaseFov = ShowFlag(TEXT("BFShowFov="), 64.f);
			FollowCamera->SetFieldOfView(CameraBaseFov);
			BaseArmLength = ShowFlag(TEXT("BFShowArm="), 470.f);
			CameraBoom->TargetArmLength = BaseArmLength;
			if (!bTrailer)
			{
				// Gameplay record: the camera looks straight at the player's pivot, so she sits mid-frame.
				BoomBaseSocket = FVector::ZeroVector;
				CameraBoom->SocketOffset = BoomBaseSocket;
			}
			BFCombat::TestDamageToPlayer = ShowFlag(TEXT("BFShowPlayerDmg="), 0.3f);
			if (Enemy)
			{
				// Frozen out of the way until the recording starts (the trailer reveals him later).
				Enemy->SetActorTickEnabled(false);
				if (bFilm)
				{
					Enemy->SetActorHiddenInGame(true);
					Enemy->SetActorEnableCollision(false);
				}
			}
			if (PC && PC->GetHUD() && bFilm)
			{
				PC->GetHUD()->bShowHUD = false;
			}
			if (bScenery || bCutscene)
			{
				// Scenery film: nobody in it. Cutscene: only her. Either way no boss, nothing he carries, no magic circle.
				TrailerB = Enemy ? (GetActorLocation() + Enemy->GetActorLocation()) * 0.5f : GetActorLocation();
				TrailerB.Z = GetActorLocation().Z - GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
				TrailerA = Enemy ? (Enemy->GetActorLocation() - GetActorLocation()).GetSafeNormal2D() : GetActorForwardVector().GetSafeNormal2D();
				TArray<AActor*> Carried;
				if (bScenery)
				{
					SetActorHiddenInGame(true);
					SetActorEnableCollision(false);
					GetCharacterMovement()->DisableMovement();
					GetAttachedActors(Carried, true, true);
				}
				// No blur on her: motion blur and depth of field off for the films.
				if (PC)
				{
					PC->ConsoleCommand(TEXT("r.MotionBlurQuality 0"));
					PC->ConsoleCommand(TEXT("r.DepthOfFieldQuality 0"));
				}
				if (Enemy)
				{
					Enemy->GetAttachedActors(Carried, false, true);
				}
				for (AActor* Each : Carried)
				{
					Each->SetActorHiddenInGame(true);
				}
				// No magic circle either: the arena's rune circle (M_RuneCircle plane) and its glow light.
				int32 Hidden = 0;
				for (TActorIterator<AActor> It(GetWorld()); It; ++It)
				{
					bool bRune = It->GetActorNameOrLabel().Contains(TEXT("RuneCircle")) || It->GetActorNameOrLabel().Contains(TEXT("RuneLight"));
					TArray<UStaticMeshComponent*> Meshes;
					It->GetComponents(Meshes);
					for (UStaticMeshComponent* M : Meshes)
					{
						for (int32 I = 0; I < M->GetNumMaterials() && !bRune; ++I)
						{
							bRune = M->GetMaterial(I) && M->GetMaterial(I)->GetPathName().Contains(TEXT("M_RuneCircle"));
						}
					}
					if (bRune)
					{
						It->SetActorHiddenInGame(true);
						TArray<ULightComponent*> Lights;
						It->GetComponents(Lights);
						for (ULightComponent* Light : Lights)
						{
							Light->SetVisibility(false);
						}
						UE_LOG(LogTemp, Display, TEXT("BFTEST scenery hide %s"), *It->GetActorNameOrLabel());
						++Hidden;
					}
				}
				UE_LOG(LogTemp, Display, TEXT("BFTEST scenery centre=%s facing=%s hidden=%d rune=%d"), *TrailerB.ToString(), *TrailerA.ToString(), Carried.Num(), Hidden);
				if (bScenery && FParse::Param(FCommandLine::Get(), TEXT("BFBuildUp")))
				{
					TArray<AActor*> Keep = Carried;
					Keep.Add(this);
					if (Enemy)
					{
						Keep.Add(Enemy);
					}
					SetupBuildUp(Keep);
				}
			}
			if (bFilm)
			{
				FActorSpawnParameters Params;
				Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
				ShowCam = GetWorld()->SpawnActor<ACameraActor>(ACameraActor::StaticClass(), FTransform(GetActorLocation() + FVector(0.f, 0.f, 500.f)), Params);
				if (ShowCam)
				{
					ShowCam->GetCameraComponent()->bConstrainAspectRatio = false;
					ShowCam->GetCameraComponent()->SetFieldOfView(50.f);
					if (PC)
					{
						PC->SetViewTarget(ShowCam);
					}
				}
			}
			UE_LOG(LogTemp, Display, TEXT("BFTEST showcase setup mode=%s len=%.0f capture=%d"), *AutoTestMode, ShowLen, bShowCapture ? 1 : 0);
		}
		ShowWaitT += Dt;
		bool bBusy = false;
#if WITH_EDITOR
		bBusy = (GShaderCompilingManager && GShaderCompilingManager->GetNumRemainingJobs() > 0)
			|| FAssetCompilingManager::Get().GetNumRemainingAssets() > 0;
#endif
		// -BFWarmup=<s>: let the world run (Fluid Flux water settles and flows) before the recording starts.
		static const float Warmup = ShowFlag(TEXT("BFWarmup="), 0.f);
		if (ShowWaitT > FMath::Max(3.f, Warmup) && (!bBusy || ShowWaitT > 200.f + Warmup))
		{
			ShowT = 0.f;
			UE_LOG(LogTemp, Display, TEXT("BFTEST showcase start after %.1f s"), ShowWaitT);
			if (Enemy && !bFilm) // trailer reveals him later; the scenery film never wakes him (no spells, no battle VFX)
			{
				Enemy->SetActorTickEnabled(true);
			}
			if (bShowCapture)
			{
				UAudioMixerBlueprintLibrary::StartRecordingOutput(this, ShowLen + 10.f);
				bShowAudio = true;
			}
			const FString MusicPath = ShowFlagStr(TEXT("BFMusic="), TEXT(""));
			if (!MusicPath.IsEmpty())
			{
				if (USoundBase* Music = LoadObject<USoundBase>(nullptr, *MusicPath))
				{
					ShowMusic = UGameplayStatics::SpawnSound2D(this, Music, ShowFlag(TEXT("BFMusicVol="), 0.6f), 1.f, 0.f, nullptr, false, false);
				}
			}
			if (bCutscene && ShowCam)
			{
				TickCutscene(0.f, 0.f);
			}
			if (bScenery && ShowCam)
			{
				if (GBuildItems.Num() > 0)
				{
					TickBuildUp(0.f);
				}
				else
				{
					TickSceneryCamera(GetWorld(), ShowCam, TrailerB, TrailerA, 0.f);
				}
			}
			if (bTrailer && ShowCam)
			{
				TrailerShot = -1;
				TickTrailerCamera(Enemy, 0.f);
			}
		}
		return;
	}

	ShowT += Dt;
	const float T = ShowT;

	// Music: keep the loop going, second layer from -BFMusic2At.
	if (ShowMusic && !ShowMusic->IsPlaying() && T < ShowLen - 1.f)
	{
		ShowMusic->Play();
	}
	static const float Music2At = ShowFlag(TEXT("BFMusic2At="), -1.f);
	if (Music2At >= 0.f && !ShowMusic2 && T >= Music2At)
	{
		const FString Path = ShowFlagStr(TEXT("BFMusic2="), TEXT(""));
		if (USoundBase* Music = Path.IsEmpty() ? nullptr : LoadObject<USoundBase>(nullptr, *Path))
		{
			ShowMusic2 = UGameplayStatics::SpawnSound2D(this, Music, ShowFlag(TEXT("BFMusic2Vol="), 0.5f), 1.f, 0.f, nullptr, false, false);
		}
	}

	// Pace the boss's health so phase 2 and his death land on time (scales the player's damage).
	if (AutoTestMode == TEXT("tutorial"))
	{
		BFCombat::TestDamageToEnemy = 0.05f; // tutorial footage: the boss never drops into phase 2 or dies
	}
	else if (Enemy && Enemy->GetMaxHealth() > 0.f)
	{
		const float Hp01 = Enemy->GetHealth() / Enemy->GetMaxHealth();
		BFCombat::TestDamageToEnemy = FMath::Clamp(1.f + (Hp01 - PaceTarget(bTrailer, T)) * 18.f, 0.1f, 3.f);
		if (FMath::FloorToInt(T / 2.f) != FMath::FloorToInt((T - Dt) / 2.f))
		{
			UE_LOG(LogTemp, Display, TEXT("BFTEST pace t=%.1f hp=%.2f target=%.2f scale=%.2f max=%.0f phase=%d"), T, Hp01, PaceTarget(bTrailer, T),
				BFCombat::TestDamageToEnemy, Enemy->GetMaxHealth(), Enemy->GetPhase());
		}
	}

	if (bCutscene)
	{
		TickCutscene(T, Dt);
	}
	else if (bScenery)
	{
		if (ShowCam)
		{
			// -BFSceneryOffset=<s>: start the shot list later (quick checks of the late shots).
			static const float SceneryOffset = ShowFlag(TEXT("BFSceneryOffset="), 0.f);
			if (GBuildItems.Num() > 0)
			{
				TickBuildUp(T);
			}
			else
			{
				TickSceneryCamera(GetWorld(), ShowCam, TrailerB, TrailerA, T + SceneryOffset);
			}
		}
	}
	else if (bTrailer && T < 17.5f)
	{
		// Intro: she walks across the temple alone, stops and looks at her sword.
		if (T > 5.5f && T < 14.5f && Enemy)
		{
			BotMove(Enemy->GetActorLocation() - GetActorLocation(), 0.22f);
		}
	}
	else
	{
		if (bTrailer && Enemy && !bTrailerBossShown)
		{
			bTrailerBossShown = true;
			Enemy->SetActorHiddenInGame(false);
			Enemy->SetActorEnableCollision(true);
			Enemy->SetActorTickEnabled(true);
			UE_LOG(LogTemp, Display, TEXT("BFTEST trailer boss reveal"));
		}
		if (bTrailer && Enemy && T < 23.f)
		{
			// The reveal shots belong to him standing there: the fight starts with the montage.
			Enemy->HoldAttacks(23.f - T);
		}
		if (AutoTestMode == TEXT("tutorial"))
		{
			TickTutorialBot(Enemy, Dt);
		}
		else if (!bTrailer || T > 22.5f)
		{
			TickShowcaseBot(Enemy, Dt);
		}
	}

	if (bTrailer)
	{
		TickTrailerCamera(Enemy, Dt);
	}

	// Key light: hangs between the lens and her chest, a little above, so her face and outfit read.
	if (!ShowKeyLight && !bScenery)
	{
		ShowKeyLight = NewObject<UPointLightComponent>(this, TEXT("ShowKeyLight"));
		ShowKeyLight->SetIntensityUnits(ELightUnits::Candelas);
		ShowKeyLight->SetIntensity(ShowFlag(TEXT("BFKeyLight="), 45.f));
		ShowKeyLight->SetAttenuationRadius(520.f);
		ShowKeyLight->SetLightColor(FLinearColor(1.f, 0.9f, 0.82f));
		ShowKeyLight->SetCastShadows(false);
		ShowKeyLight->RegisterComponent();
	}
	if (APlayerController* KeyPC = Cast<APlayerController>(GetController()); ShowKeyLight && KeyPC && KeyPC->PlayerCameraManager)
	{
		const FVector KeyChest = GetActorLocation() + FVector(0.f, 0.f, 40.f);
		const FVector ToLens = (KeyPC->PlayerCameraManager->GetCameraLocation() - KeyChest).GetSafeNormal();
		ShowKeyLight->SetWorldLocation(KeyChest + ToLens * 170.f + FVector(0.f, 0.f, 90.f));
	}

	TickShowcaseCapture(Dt);

	// Gameplay: end on the victory, before he re-forms.
	if (!bTrailer && Enemy && Enemy->IsDead() && ShowEndT < 0.f)
	{
		ShowEndT = T + 8.5f;
		UE_LOG(LogTemp, Display, TEXT("BFTEST showcase boss dead t=%.1f"), T);
	}
	if (ShowEndT > 0.f && T >= ShowEndT)
	{
		ShowLen = FMath::Min(ShowLen, T);
	}
	if (T >= ShowLen && !bShowEnded)
	{
		bShowEnded = true;
		if (bShowAudio)
		{
			UAudioMixerBlueprintLibrary::StopRecordingOutput(this, EAudioRecordingExportType::WavFile, ShowName, TEXT(""));
		}
		UE_LOG(LogTemp, Display, TEXT("BFTEST showcase end frames=%d boss_hp=%.0f player_hp=%.0f"), ShowFrame, Enemy ? Enemy->GetHealth() : -1.f, Health);
		UE_LOG(LogTemp, Display, TEXT("BFTEST done"));
		FPlatformMisc::RequestExit(false);
	}
}

namespace
{
	// --- Cutscene face (VRoid "Fcl_*" blend shapes on sw_ue). A mood is a small set of weights; the face eases between moods.
	struct FCutMorph
	{
		const TCHAR* Name;
		float W;
	};
	struct FCutMood
	{
		FCutMorph M[5];
	};
	static const FCutMood CutMoods[] = {
		/* 0 calm      */ { { { TEXT("Fcl_BRW_Fun"), 0.25f }, { TEXT("Fcl_MTH_Fun"), 0.18f } } },
		/* 1 smile     */ { { { TEXT("Fcl_BRW_Fun"), 0.55f }, { TEXT("Fcl_MTH_Fun"), 0.4f }, { TEXT("Fcl_MTH_Joy"), 0.22f }, { TEXT("Fcl_EYE_Joy"), 0.45f } } },
		/* 2 wistful   */ { { { TEXT("Fcl_BRW_Sorrow"), 0.5f }, { TEXT("Fcl_EYE_Sorrow"), 0.25f }, { TEXT("Fcl_MTH_Sorrow"), 0.2f } } },
		/* 3 surprised */ { { { TEXT("Fcl_BRW_Surprised"), 0.7f }, { TEXT("Fcl_EYE_Surprised"), 0.35f }, { TEXT("Fcl_MTH_O"), 0.3f } } },
		/* 4 resolve   */ { { { TEXT("Fcl_BRW_Angry"), 0.35f }, { TEXT("Fcl_EYE_Angry"), 0.2f }, { TEXT("Fcl_MTH_Close"), 0.3f } } },
		/* 5 happy     */ { { { TEXT("Fcl_BRW_Joy"), 0.35f }, { TEXT("Fcl_MTH_Fun"), 0.45f } } },
		/* 6 soft smile*/ { { { TEXT("Fcl_BRW_Fun"), 0.4f }, { TEXT("Fcl_MTH_Fun"), 0.4f }, { TEXT("Fcl_EYE_Joy"), 0.18f } } },
	};
	static const TCHAR* CutMoodNames[] = { TEXT("calm"), TEXT("smile"), TEXT("wistful"), TEXT("surprised"), TEXT("resolve"), TEXT("happy"), TEXT("softsmile") };
	// When each mood starts (seconds into the film).
	static const FVector2f CutMoodTimeline[] = { { 0.f, 0 }, { 4.f, 4 }, { 8.5f, 0 }, { 11.f, 1 }, { 14.2f, 0 }, { 15.f, 2 }, { 20.5f, 3 },
		{ 22.6f, 0 }, { 25.5f, 6 }, { 30.f, 5 }, { 40.f, 0 }, { 46.f, 4 }, { 52.f, 1 } };

	// Blink weight at time T: a blink every 2.4-4.6 s (fixed pseudo-random spacing), every fifth one doubled.
	float CutBlink(float T)
	{
		float B = 0.9f;
		for (int32 I = 0; I < 40 && B < T + 1.f; ++I)
		{
			const float Hash = FMath::Frac(FMath::Sin(I * 12.9898f + 1.7f) * 43758.547f);
			auto One = [T](float Start)
			{
				const float X = T - Start;
				if (X < 0.f || X > 0.22f)
				{
					return 0.f;
				}
				if (X < 0.07f)
				{
					return X / 0.07f; // close
				}
				if (X < 0.11f)
				{
					return 1.f; // shut
				}
				return 1.f - (X - 0.11f) / 0.11f; // open
			};
			float W = One(B);
			if (I % 5 == 3)
			{
				W = FMath::Max(W, One(B + 0.3f));
			}
			if (W > 0.f)
			{
				return W;
			}
			B += 2.4f + Hash * 2.2f;
		}
		return 0.f;
	}

	// --- Idle clips at the spots (played as dynamic montages on the mannequin that drives her body).
	struct FCutClip
	{
		float At; // < 0: right after the previous clip
		const TCHAR* Path;
		int32 Loops;
		float BlendIn;
	};
	static const FCutClip CutClips[] = {
		// Spot A, before the gate.
		{ 0.f, TEXT("/Game/Lucy/Animations/Battle/Lucy_Idle.Lucy_Idle"), 100, 0.3f },
		{ 6.f, TEXT("/Game/Lucy/Animations/Battle/Inplace/Lucy_Idle2Rest_Inplace.Lucy_Idle2Rest_Inplace"), 1, 0.45f },
		{ -1.f, TEXT("/Game/Lucy/Animations/Battle/Lucy_Rest.Lucy_Rest"), 100, 0.35f },
		// Spot B, on the river bank: relaxed, a hand to her chest when something in the water surprises her.
		{ 15.f, TEXT("/Game/Lucy/DEMO/Mannequin/Animations/ThirdPersonIdle.ThirdPersonIdle"), 100, 0.3f },
		{ 20.5f, TEXT("/Game/MageAnimationSet/Animations/InPlace/Mage_ExitCombat_IP.Mage_ExitCombat_IP"), 1, 0.4f },
		{ -1.f, TEXT("/Game/Lucy/DEMO/Mannequin/Animations/ThirdPersonIdle.ThirdPersonIdle"), 100, 0.5f },
	};
	// -BFCutGallery: every candidate idle for 6 s each (3 s full body, 3 s face), with a mood each.
	static const TCHAR* CutGallery[] = {
		TEXT("/Game/Lucy/Animations/Battle/Lucy_Idle.Lucy_Idle"),
		TEXT("/Game/Lucy/Animations/Battle/Lucy_Rest.Lucy_Rest"),
		TEXT("/Game/Lucy/Animations/Battle/Inplace/Lucy_Idle2Rest_Inplace.Lucy_Idle2Rest_Inplace"),
		TEXT("/Game/Lucy/DEMO/Mannequin/Animations/ThirdPersonIdle.ThirdPersonIdle"),
		TEXT("/Game/MageAnimationSet/Animations/InPlace/Mage_Idle_IP.Mage_Idle_IP"),
		TEXT("/Game/InsaneAirCombo/Animation/Idle.Idle"),
		TEXT("/Game/Lucy/Animations/Battle/Lucy_Idle_Pose.Lucy_Idle_Pose"),
		TEXT("/Game/MageAnimationSet/Animations/InPlace/Mage_ExitCombat_IP.Mage_ExitCombat_IP"),
	};
}

bool ABFPlayerCharacter::CutViewClear(const FVector& Loc, const FVector& Head, const FVector& Feet) const
{
	FCollisionQueryParams Params(SCENE_QUERY_STAT(BFCutView), true, this);
	TArray<AActor*> Attached;
	GetAttachedActors(Attached, true, true);
	Params.AddIgnoredActors(Attached);
	// The lens itself must not sit inside a mesh (a trace that starts inside one does not see it).
	if (GetWorld()->OverlapAnyTestByChannel(Loc, FQuat::Identity, ECC_Visibility, FCollisionShape::MakeSphere(22.f), Params)
		|| GetWorld()->OverlapAnyTestByChannel(Loc, FQuat::Identity, ECC_Camera, FCollisionShape::MakeSphere(22.f), Params))
	{
		return false;
	}
	const FVector Points[] = { Head + FVector(0.f, 0.f, 6.f), FMath::Lerp(Feet, Head, 0.55f), Feet + FVector(0.f, 0.f, 35.f) };
	for (const FVector& P : Points)
	{
		FHitResult Hit;
		if (GetWorld()->LineTraceSingleByChannel(Hit, Loc, P, ECC_Visibility, Params)
			|| GetWorld()->LineTraceSingleByChannel(Hit, Loc, P, ECC_Camera, Params))
		{
			return false;
		}
	}
	return true;
}

void ABFPlayerCharacter::TickCutsceneFace(float T, float Dt)
{
	if (!AnimeBody || !AnimeBody->GetSkeletalMeshAsset())
	{
		return;
	}
	static const bool bGallery = FParse::Param(FCommandLine::Get(), TEXT("BFCutGallery"));
	int32 Mood = 0;
	if (bGallery)
	{
		Mood = int32(T / 6.f) % UE_ARRAY_COUNT(CutMoods);
	}
	else
	{
		for (const FVector2f& Key : CutMoodTimeline)
		{
			if (T >= Key.X)
			{
				Mood = int32(Key.Y);
			}
		}
	}
	// Targets: every morph any mood uses, at zero unless the current mood sets it.
	TMap<FName, float> Target;
	for (const FCutMood& M : CutMoods)
	{
		for (const FCutMorph& X : M.M)
		{
			if (X.Name)
			{
				Target.FindOrAdd(FName(X.Name)) = 0.f;
			}
		}
	}
	for (const FCutMorph& X : CutMoods[Mood].M)
	{
		if (X.Name)
		{
			Target.FindOrAdd(FName(X.Name)) = X.W;
		}
	}
	// Ease: ~0.35 s to settle (instant on the first frame).
	const float Alpha = Dt <= 0.f ? 1.f : 1.f - FMath::Exp(-Dt * 6.f);
	for (const TPair<FName, float>& Pair : Target)
	{
		float& W = CutFace.FindOrAdd(Pair.Key);
		W = FMath::Lerp(W, Pair.Value, Alpha);
	}
	// Blink on top: the lids shut fully and the other eye shapes give way while they do.
	const float Blink = CutBlink(T);
	for (const TPair<FName, float>& Pair : CutFace)
	{
		const bool bEye = Pair.Key.ToString().StartsWith(TEXT("Fcl_EYE_"));
		AnimeBody->SetMorphTarget(Pair.Key, bEye ? Pair.Value * (1.f - Blink) : Pair.Value, false);
	}
	AnimeBody->SetMorphTarget(TEXT("Fcl_EYE_Close"), Blink, false);
	static const bool bFaceTest = FParse::Param(FCommandLine::Get(), TEXT("BFCutFaceTest"));
	if (bFaceTest)
	{
		AnimeBody->SetMorphTarget(TEXT("Fcl_ALL_Joy"), 1.f, false);
	}
	if (FMath::FloorToInt(T) != FMath::FloorToInt(T - Dt))
	{
		USkeletalMesh* SkM = AnimeBody->GetSkeletalMeshAsset();
		if (UMorphTarget* MT = SkM ? SkM->FindMorphTarget(TEXT("Fcl_ALL_Joy")) : nullptr)
		{
			const int32* Idx = AnimeBody->ActiveMorphTargets.Find(MT);
			float MaxD = 0.f;
			int32 NumV = 0;
			if (MT->GetMorphLODModels().Num() > 0)
			{
				for (const FMorphTargetDelta& D : MT->GetMorphLODModels()[0].Vertices)
				{
					MaxD = FMath::Max(MaxD, FVector3f(D.PositionDelta).Size());
				}
				NumV = MT->GetMorphLODModels()[0].Vertices.Num();
			}
			UE_LOG(LogTemp, Display, TEXT("BFTEST face joy idx=%d w=%.2f lodmodels=%d verts=%d maxdelta=%.4f"), Idx ? *Idx : -1,
				Idx && AnimeBody->MorphTargetWeights.IsValidIndex(*Idx) ? AnimeBody->MorphTargetWeights[*Idx] : -1.f, MT->GetMorphLODModels().Num(), NumV, MaxD);
		}
		UE_LOG(LogTemp, Display, TEXT("BFTEST face t=%.1f active=%d overrides=%d joy=%.2f found=%d lod=%d disable=%d weights=%d"), T,
			AnimeBody->ActiveMorphTargets.Num(), AnimeBody->GetMorphTargetCurves().Num(), AnimeBody->GetMorphTarget(TEXT("Fcl_MTH_Joy")),
			SkM && SkM->FindMorphTarget(TEXT("Fcl_MTH_Joy")) ? 1 : 0, AnimeBody->GetPredictedLODLevel(), AnimeBody->bDisableMorphTarget ? 1 : 0,
			AnimeBody->MorphTargetWeights.Num());
	}
	static int32 LastMood = -1;
	if (Mood != LastMood)
	{
		LastMood = Mood;
		UE_LOG(LogTemp, Display, TEXT("BFTEST cutscene mood %s t=%.2f"), CutMoodNames[Mood], T);
	}
}

void ABFPlayerCharacter::TickCutsceneIdle(float T)
{
	static const bool bGallery = FParse::Param(FCommandLine::Get(), TEXT("BFCutGallery"));
	auto Play = [this, T](const TCHAR* Path, int32 Loops, float BlendIn) -> float
	{
		UAnimSequence* Seq = LoadObject<UAnimSequence>(nullptr, Path);
		UAnimMontage* M = Seq ? PlayAnim(Seq, 1.f, BlendIn, 0.35f, Loops) : nullptr;
		UE_LOG(LogTemp, Display, TEXT("BFTEST cutscene idle %s t=%.2f len=%.2f ok=%d"), Path, T, Seq ? Seq->GetPlayLength() : 0.f, M ? 1 : 0);
		return Seq ? Seq->GetPlayLength() : 0.f;
	};
	if (bGallery)
	{
		const int32 Step = int32(T / 6.f) % UE_ARRAY_COUNT(CutGallery);
		if (Step != CutIdleStep)
		{
			CutIdleStep = Step;
			Play(CutGallery[Step], 100, 0.3f);
		}
		return;
	}
	if (T >= 30.f)
	{
		// The walk: back to her own locomotion.
		if (CutIdleStep != 1000)
		{
			CutIdleStep = 1000;
			if (UAnimInstance* AI = GetMesh()->GetAnimInstance())
			{
				AI->Montage_Stop(0.3f);
			}
		}
		return;
	}
	const int32 Next = CutIdleStep + 1;
	if (Next < int32(UE_ARRAY_COUNT(CutClips)))
	{
		const FCutClip& C = CutClips[Next];
		const float Start = C.At >= 0.f ? C.At : CutIdleNext;
		if (T >= Start)
		{
			CutIdleStep = Next;
			const float Len = Play(C.Path, C.Loops, C.BlendIn);
			CutIdleNext = T + FMath::Max(0.5f, Len * C.Loops - 0.3f);
		}
	}
}

void ABFPlayerCharacter::TickCutscene(float T, float Dt)
{
	APlayerController* PC = Cast<APlayerController>(GetController());
	if (!ShowCam || !PC)
	{
		return;
	}
	if (PC->GetViewTarget() != ShowCam)
	{
		PC->SetViewTarget(ShowCam);
	}
	static const bool bGallery = FParse::Param(FCommandLine::Get(), TEXT("BFCutGallery"));
	// Spots on the dry court (the river runs through the middle): before the temple gate, then on the south bank.
	const FVector Gate(1930.f, -1508.f, 0.f);
	const FVector SpotA(1350.f, -1050.f, 0.f);
	const FVector SpotB(-900.f, -1500.f, 0.f);
	// The route passes north of the ruined pillar at (1202, -1202): straight through, she walked into it and stopped.
	static const FVector Route[] = { FVector(-1300.f, -1550.f, 0.f), FVector(-300.f, -1150.f, 0.f), FVector(700.f, -930.f, 0.f),
		FVector(1200.f, -930.f, 0.f), FVector(1650.f, -1250.f, 0.f), FVector(1930.f, -1508.f, 0.f), FVector(2350.f, -1800.f, 0.f) };
	constexpr int32 RouteN = UE_ARRAY_COUNT(Route);
	static const float WalkScale = ShowFlag(TEXT("BFWalkScale="), 0.25f);

	// Phases: 0 = spot A (0-15 s), 1 = spot B (15-30 s), 2 = walk (30-60 s). The gallery stays at spot A.
	const int32 Phase = bGallery ? 0 : (T < 15.f ? 0 : (T < 30.f ? 1 : 2));
	if (Phase != CutPhase)
	{
		CutPhase = Phase;
		const float HalfH = GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
		FVector At;
		FVector Face;
		if (Phase == 0)
		{
			At = SpotA;
			Face = (Gate - SpotA).GetSafeNormal2D();
		}
		else if (Phase == 1)
		{
			At = SpotB;
			Face = FVector(0.15f, 1.f, 0.f).GetSafeNormal2D(); // looking over the river
		}
		else
		{
			At = Route[0];
			Face = (Route[1] - Route[0]).GetSafeNormal2D();
			CutWaypoint = 1;
		}
		// Drop onto the ground under the spot.
		FHitResult Ground;
		FCollisionQueryParams Q(SCENE_QUERY_STAT(BFCutGround), false, this);
		float Z = At.Z;
		if (GetWorld()->LineTraceSingleByChannel(Ground, At + FVector(0.f, 0.f, 600.f), At - FVector(0.f, 0.f, 600.f), ECC_Visibility, Q))
		{
			Z = Ground.ImpactPoint.Z;
		}
		GetCharacterMovement()->StopMovementImmediately();
		SetActorLocationAndRotation(FVector(At.X, At.Y, Z + HalfH + 2.f), Face.Rotation(), false, nullptr, ETeleportType::ResetPhysics);
		PC->SetControlRotation(Face.Rotation());
		CutFwd = Face;
		UE_LOG(LogTemp, Display, TEXT("BFTEST cutscene phase %d t=%.2f at=%s"), Phase, T, *GetActorLocation().ToString());
	}
	TickCutsceneIdle(T);
	TickCutsceneFace(T, Dt);

	// Walk: steer along the route toward the gate and through it.
	if (Phase == 2 && CutWaypoint < RouteN)
	{
		const FVector To = Route[CutWaypoint] - GetActorLocation();
		if (To.Size2D() < 140.f)
		{
			++CutWaypoint;
		}
		if (CutWaypoint < RouteN)
		{
			BotMove(Route[CutWaypoint] - GetActorLocation(), WalkScale);
		}
	}
	const FVector Vel = GetVelocity().GetSafeNormal2D();
	if (Phase == 2 && !Vel.IsNearlyZero())
	{
		CutFwd = FMath::VInterpNormalRotationTo(CutFwd, Vel, Dt, 90.f).GetSafeNormal2D();
	}

	// Shots: 5 s each, six at the spots (three per spot), six on the walk. Gallery: 3 s full body, 3 s face.
	const int32 Shot = bGallery ? (FMath::Frac(T / 6.f) < 0.5f ? 13 : 2) : FMath::Clamp(int32(T / 5.f), 0, 11);
	const float U = bGallery ? 0.f : T - Shot * 5.f;
	const float A = Ease01(U / 5.f);
	bool bCut = Shot != CutShot;
	const FVector Up(0.f, 0.f, 1.f);
	const FVector Feet = GetActorLocation() - Up * GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
	// Her face: the anime body's head bone (the mannequin's sits higher than her face).
	static const FName AnimeHead(TEXT("J_Bip_C_Head"));
	const bool bAnimeHead = AnimeBody && AnimeBody->GetSkeletalMeshAsset() && AnimeBody->GetBoneIndex(AnimeHead) != INDEX_NONE;
	const FVector Head = bAnimeHead ? AnimeBody->GetBoneLocation(AnimeHead) + Up * 7.f : GetMesh()->GetBoneLocation(TEXT("head"));
	const FVector Chest = FMath::Lerp(Feet, Head, 0.7f);
	if (bCut)
	{
		CutShot = Shot;
		CutCamLoc = CutFwd; // her facing when the shot began (the closing shot keeps its lens on it)
		UE_LOG(LogTemp, Display, TEXT("BFTEST cutscene shot %d t=%.2f at=%s head=%s mannequin_head=%s"), Shot, T, *GetActorLocation().ToString(),
			*(Head - Feet).ToString(), *(GetMesh()->GetBoneLocation(TEXT("head")) - Feet).ToString());
	}

	// The rig of a shot, built on her facing F (rotated by Yaw when the plain angle is blocked).
	auto Rig = [&](float Yaw, float Ax, FVector& Loc, FVector& Look, float& Fov)
	{
		const FVector F = CutFwd.RotateAngleAxis(Yaw, Up);
		const FVector R = FVector::CrossProduct(Up, F);
		Fov = 45.f;
		switch (Shot)
		{
		// --- Spot A, before the temple gate.
		case 0: // wide from behind: she faces the gate, slow push in
			Loc = Feet - F * FMath::Lerp(620.f, 480.f, Ax) - R * 150.f + Up * 200.f;
			Look = Chest + F * 120.f + Up * 20.f;
			Fov = 50.f;
			break;
		case 1: // three-quarter front, medium, gentle slide
			Loc = Feet + R * 230.f + F * FMath::Lerp(130.f, 70.f, Ax) + Up * 135.f;
			Look = Chest + Up * 10.f;
			Fov = 40.f;
			break;
		case 2: // face close-up
			Loc = Head + F * FMath::Lerp(125.f, 100.f, Ax) + R * 22.f + Up * 2.f;
			Look = Head - Up * 3.f;
			Fov = 30.f;
			break;
		// --- Spot B, on the river bank.
		case 3: // wide from behind: she watches the water run
			Loc = Feet - F * 480.f + R * FMath::Lerp(150.f, 90.f, Ax) + Up * 190.f;
			Look = Chest + F * 200.f;
			Fov = 52.f;
			break;
		case 4: // medium-close three-quarter front, a little low
			Loc = Head + F * 170.f - R * 90.f - Up * 25.f;
			Look = Head - Up * 12.f;
			Fov = 38.f;
			break;
		case 5: // three-quarter close-up, the river beside her
			Loc = Head + F * FMath::Lerp(90.f, 60.f, Ax) - R * 115.f;
			Look = Head;
			Fov = 32.f;
			break;
		// --- Walk.
		case 6: // wide from behind and above: she sets off along the court (the side lens hit the ruined pillar)
			Loc = Feet - F * 420.f + R * 40.f + Up * 270.f;
			Look = Chest + F * 220.f;
			Fov = 50.f;
			break;
		case 7: // ahead of her, she walks toward the lens
			Loc = Feet + F * 420.f + R * 40.f + Up * 140.f;
			Look = Chest + Up * 15.f;
			Fov = 38.f;
			break;
		case 8: // low three-quarter front, tracking
			Loc = Feet + F * 300.f - R * 110.f + Up * 45.f;
			Look = Chest + Up * 35.f;
			Fov = 46.f;
			break;
		case 9: // following behind her, a little high: where she is going (centred, portrait frame)
			Loc = Feet - F * 300.f + R * 30.f + Up * 185.f;
			Look = Head + F * 220.f - Up * 45.f;
			Fov = 50.f;
			break;
		// A fixed lens on the court (the walk is deterministic): one riding on her facing swung through her
		// when she turned at a waypoint.
		case 10: // she walks toward the lens, turns and passes it (210 cm off her path)
			Loc = FVector(1450.f, -850.f, Feet.Z + 165.f);
			Look = Chest;
			Fov = 36.f;
			break;
		case 11: // closing: in front of her face as she walks, smiling. The lens keeps the facing she had when
		{        // the shot began: she turns at a waypoint here, and a lens riding on her facing swung away.
			const FVector F0 = CutCamLoc.GetSafeNormal2D().RotateAngleAxis(Yaw, Up);
			Loc = Head + F0 * 210.f + FVector::CrossProduct(Up, F0) * 35.f - Up * 6.f;
			Look = Head - Up * 12.f;
			Fov = 34.f;
			break;
		}
		default: // gallery full body, from the front
			Loc = Feet + F * 330.f + R * 40.f + Up * 105.f;
			Look = Chest - Up * 15.f;
			Fov = 40.f;
			break;
		}
	};

	// On a cut, pick the first angle (plain, then swung around her) with nothing in the way at both ends of the move.
	// While she walks, a lens that stays blocked for a moment re-picks its angle (a fresh cut).
	FVector Loc;
	FVector Look;
	float Fov;
	Rig(CutYaw, A, Loc, Look, Fov);
	if (!bCut && Phase == 2 && !bGallery)
	{
		// Re-pick only after it stays blocked for a while (a lamp post passing by is fine).
		CutBlocked = CutViewClear(Loc, Head, Feet) ? FMath::Min(CutBlocked, 0.f) : CutBlocked + Dt;
		if (CutBlocked > 0.6f)
		{
			bCut = true;
			UE_LOG(LogTemp, Display, TEXT("BFTEST cutscene reangle shot %d t=%.2f"), Shot, T);
		}
	}
	if (bCut)
	{
		CutBlocked = -1.2f; // a fresh angle holds at least ~1.8 s
		static const float Yaws[] = { 0.f, 25.f, -25.f, 50.f, -50.f, 80.f, -80.f, 115.f, -115.f, 150.f, -150.f };
		CutYaw = 0.f;
		bool bFound = false;
		for (float Yaw : Yaws)
		{
			FVector L0, L1, K;
			float Fv;
			Rig(Yaw, 0.f, L0, K, Fv);
			Rig(Yaw, 1.f, L1, K, Fv);
			if (CutViewClear(L0, Head, Feet) && CutViewClear(L1, Head, Feet))
			{
				CutYaw = Yaw;
				bFound = true;
				break;
			}
		}
		UE_LOG(LogTemp, Display, TEXT("BFTEST cutscene angle shot %d yaw=%.0f clear=%d"), Shot, CutYaw, bFound ? 1 : 0);
		Rig(CutYaw, A, Loc, Look, Fov);
	}
	// Last resort: keep the lens out of walls between it and her. Her attached sword is ignored, and the lens is never
	// pulled closer than 110 cm: a hit right at her put the lens inside her body (the frame showed the scene through her).
	{
		FCollisionQueryParams Params(SCENE_QUERY_STAT(BFCutCam), false, this);
		TArray<AActor*> Attached;
		GetAttachedActors(Attached, true, true);
		Params.AddIgnoredActors(Attached);
		FHitResult Hit;
		if (GetWorld()->SweepSingleByChannel(Hit, Chest, Loc, FQuat::Identity, ECC_Camera, FCollisionShape::MakeSphere(20.f), Params)
			&& FVector::Dist(Hit.Location, Chest) > 110.f)
		{
			Loc = Hit.Location;
		}
	}
	// Spots: locked rig. Walk: the rig follows her smoothly (no jitter from her steps).
	FVector NewLoc = Loc;
	if (!bCut && Phase == 2)
	{
		NewLoc = FMath::VInterpTo(ShowCam->GetActorLocation(), Loc, Dt, 7.f);
	}
	ShowCam->SetActorLocationAndRotation(NewLoc, (Look - NewLoc).Rotation());
	ShowCam->GetCameraComponent()->SetFieldOfView(Fov);
	if (bCut && PC->PlayerCameraManager)
	{
		// Fresh temporal history on a cut: no smear from the previous angle.
		PC->PlayerCameraManager->SetGameCameraCutThisFrame();
	}
}

void ABFPlayerCharacter::TickShowcaseCapture(float Dt)
{
	if (!bShowCapture || bShowEnded)
	{
		return;
	}
	if (APlayerController* PC = Cast<APlayerController>(GetController()))
	{
		// -BFCapEvery=<n>: keep one frame in n (quick framing checks).
		static const int32 CapEvery = FMath::Max(1, int32(ShowFlag(TEXT("BFCapEvery="), 1.f)));
		static int32 CapTick = 0;
		if (CapTick++ % CapEvery != 0)
		{
			return;
		}
		static const FString Res = ShowFlagStr(TEXT("BFCapRes="), TEXT("1080x1920"));
		PC->ConsoleCommand(FString::Printf(TEXT("HighResShot %s filename=Cap_%s_%05d"), *Res, *ShowName, ShowFrame));
		++ShowFrame;
	}
}

void ABFPlayerCharacter::TickShowcaseBot(ABFEnemyBase* Enemy, float Dt)
{
	const double Now = GetWorld()->GetRealTimeSeconds();
	if (BotGuardRelease > 0.0 && Now >= BotGuardRelease)
	{
		OnGuardReleased();
		BotGuardRelease = 0.0;
	}
	if (BotJumpRelease > 0.0 && Now >= BotJumpRelease)
	{
		StopJumping();
		BotJumpRelease = 0.0;
	}
	auto SetSprint = [this](bool bOn)
	{
		if (bOn != bBotSprint)
		{
			bBotSprint = bOn;
			bOn ? OnSprintPressed() : OnSprintReleased();
		}
	};

	// Strength clashes (parried heavy, perfect-dodged grab): mash.
	if (bStruggle || State == EBFPlayerState::Clashing)
	{
		SetSprint(false);
		BotMash += Dt;
		if (BotMash >= 0.085f)
		{
			BotMash = 0.f;
			OnGuardPressed();
			OnGuardReleased();
			OnLightDown();
			OnLightUp();
		}
		BotRoutine = -1;
		return;
	}
	if (!Enemy || Enemy->IsDead())
	{
		SetSprint(false);
		BotRoutine = -1;
		return;
	}
	if (bGrabbed || bCinematic || Enemy->IsInTransition() || bKnockedDown)
	{
		SetSprint(false);
		BotRoutine = -1;
		return;
	}
	if (!bLockedOn)
	{
		SetLockTarget(Enemy);
	}

	const FVector ToB = Enemy->GetActorLocation() - GetActorLocation();
	const float Dist = ToB.Size2D();
	const FVector Dir = ToB.GetSafeNormal2D();
	const FVector Right = FVector::CrossProduct(FVector::UpVector, Dir);

	// Jumped a ground wave: drop onto him.
	if (CanStomp())
	{
		if (BotStompAt < 0.0)
		{
			BotStompAt = Now + 0.12;
		}
		else if (Now >= BotStompAt)
		{
			OnLightPressed();
			BotStompAt = -1.0;
		}
		return;
	}
	BotStompAt = -1.0;

	// Defence: read the swing and answer it the way it asks to be answered.
	const float TTH = Enemy->GetTimeToHit();
	const EBFPerilous Kind = Enemy->GetPerilous();
	const bool bMagic = Enemy->HasMagicPending() || Enemy->IsMagicAirborne();
	if (TTH >= 0.f && Now - BotLastReact > 0.38)
	{
		bool bReact = false;
		if (bMagic)
		{
			if (TTH <= 0.12f)
			{
				BotDash(Right * BotStrafe);
				bReact = true;
			}
		}
		else if (Kind == EBFPerilous::Sweep)
		{
			if (TTH <= 0.15f)
			{
				SetSprint(false);
				BotJump();
				bReact = true;
			}
		}
		else if (Kind == EBFPerilous::Thrust)
		{
			if (TTH <= 0.12f)
			{
				BotDash(Dir); // mikiri: into the thrust
				bReact = true;
			}
		}
		else if (Kind == EBFPerilous::Grab)
		{
			if (TTH <= 0.12f)
			{
				BotDash(Right * BotStrafe);
				bReact = true;
			}
		}
		else if (Enemy->IsCurrentAttackHeavy())
		{
			if (TTH <= 0.08f)
			{
				OnGuardPressed();
				BotGuardRelease = Now + 0.15;
				bReact = true;
			}
		}
		else
		{
			const int32 Mode = BotDefense % 5; // parry, dodge, parry, block, dodge
			if ((Mode == 1 || Mode == 4) && TTH <= 0.12f)
			{
				BotDash((Mode == 1 ? Right : -Right) + (Mode == 4 ? -Dir * 0.6f : FVector::ZeroVector));
				bReact = true;
			}
			else if (Mode == 3 && TTH <= 0.32f)
			{
				OnGuardPressed();
				BotGuardRelease = Now + 0.55;
				bReact = true;
			}
			else if ((Mode == 0 || Mode == 2) && TTH <= 0.08f)
			{
				OnGuardPressed();
				BotGuardRelease = Now + 0.15;
				bReact = true;
			}
		}
		if (bReact)
		{
			UE_LOG(LogTemp, Display, TEXT("BFTEST bot react t=%.2f tth=%.2f kind=%d heavy=%d magic=%d mode=%d"), ShowT, TTH, int32(Kind),
				Enemy->IsCurrentAttackHeavy() ? 1 : 0, bMagic ? 1 : 0, BotDefense % 5);
			BotLastReact = Now;
			++BotDefense;
			BotRoutine = -1;
			BotRestUntil = Now + 0.25;
			BotStrafe = -BotStrafe;
			SetSprint(false);
			return;
		}
	}

	// A swing or spell on its way soon: no new combo, keep moving instead.
	const bool bThreat = (Enemy->IsAttacking() && !Enemy->IsPunishable() && (TTH < 0.f || TTH < 0.95f)) || bMagic;
	if (Now >= BotStrafeFlip)
	{
		BotStrafe = -BotStrafe;
		BotStrafeFlip = Now + FMath::FRandRange(1.2f, 2.2f);
	}

	// Combo in progress.
	if (BotRoutine >= 0)
	{
		const TArray<FBotStep>& Steps = BotRoutines()[BotRoutine];
		if (bThreat && BotStep > 0 && Steps[BotStep].Act != 'H')
		{
			BotRoutine = -1; // bail out, the boss is answering
			BotRestUntil = Now + 0.1;
		}
		else if (Now >= BotStepAt)
		{
			switch (Steps[BotStep].Act)
			{
			case 'L': OnLightPressed(); break;
			case 'H': OnHeavyPressed(); break;
			case 'J': BotJump(); break;
			case 'D': BotDash(Dir); break;
			case 'S': BotDash(Right * BotStrafe); break;
			case 'B': BotDash(-Dir); break;
			default: break;
			}
			++BotStep;
			if (BotStep >= Steps.Num())
			{
				BotRoutine = -1;
				// Give him his turn now and then: circle at range instead of chaining another combo.
				BotRestUntil = Now + ((BotRoutineCount % 2) ? FMath::FRandRange(1.1f, 1.8f) : FMath::FRandRange(0.4f, 0.8f));
			}
			else
			{
				BotStepAt = Now + Steps[BotStep].Delay;
			}
		}
		return;
	}

	// Openings: a broken or staggered boss gets punished right away.
	const bool bOpening = Enemy->IsBroken() || Enemy->IsStaggered() || Enemy->IsPunishable();
	if (bMagic && !Enemy->IsAttacking())
	{
		// Spells on the floor: run across them, never into them.
		SetSprint(true);
		BotMove(Right * BotStrafe + Dir * 0.25f, 1.f);
		return;
	}
	if (Dist > 330.f)
	{
		SetSprint(Dist > 850.f && !bThreat);
		BotMove(bThreat ? (Right * BotStrafe * 0.7f + Dir * 0.5f) : Dir, 1.f);
		// Gap close: dash at him now and then (front blink).
		if (!bThreat && Dist > 420.f && Dist < 620.f && State == EBFPlayerState::Free && Now >= BotRestUntil && (BotRoutineCount % 3) == 1 && DashCharges > 1)
		{
			BotDash(Dir);
			BotRestUntil = Now + 0.6;
			++BotRoutineCount;
		}
		return;
	}
	SetSprint(false);
	if ((!bThreat || bOpening) && Now >= BotRestUntil && State == EBFPlayerState::Free)
	{
		BotRoutine = bOpening && Enemy->IsBroken() ? 0 : (BotRoutineCount % BotRoutines().Num());
		++BotRoutineCount;
		BotStep = 0;
		BotStepAt = Now;
		UE_LOG(LogTemp, Display, TEXT("BFTEST bot routine %d t=%.2f dist=%.0f"), BotRoutine, ShowT, Dist);
		return;
	}
	// Neutral: circle him at sword range, step back if he crowds us.
	const FVector Move = Right * BotStrafe * 0.65f + (Dist < 200.f ? -Dir * 0.6f : (Dist > 280.f ? Dir * 0.4f : FVector::ZeroVector));
	BotMove(Move, 0.6f);
}

void ABFPlayerCharacter::TickTrailerCamera(ABFEnemyBase* Enemy, float Dt)
{
	APlayerController* PC = Cast<APlayerController>(GetController());
	if (!ShowCam || !PC)
	{
		return;
	}
	UCameraComponent* Cam = ShowCam->GetCameraComponent();
	const float T = ShowT;

	// The game's own cinematics (clash, phase-2 cutscene) film through the player camera.
	const bool bGameCam = bClashCam || bStruggle || bCinematic;
	AActor* WantView = bGameCam ? static_cast<AActor*>(this) : static_cast<AActor*>(ShowCam);
	if (PC->GetViewTarget() != WantView)
	{
		PC->SetViewTarget(WantView);
	}

	// Shot list.
	int32 Shot;
	if (T < 6.f) Shot = 0;
	else if (T < 11.f) Shot = 1;
	else if (T < 15.f) Shot = 2;
	else if (T < 17.5f) Shot = 3;
	else if (T < 20.5f) Shot = 4;
	else if (T < 23.5f) Shot = 5;
	else if (T < 56.f) Shot = 6 + int32((T - 23.5f) / 2.7f);
	else Shot = 1000;
	const bool bCut = Shot != TrailerShot;
	if (bCut)
	{
		TrailerShot = Shot;
		TrailerShotStart = T;
		UE_LOG(LogTemp, Display, TEXT("BFTEST trailer shot %d t=%.2f"), Shot, T);
	}
	const float U = T - TrailerShotStart;

	const FVector Me = GetActorLocation();
	const FVector Feet = Me - FVector(0.f, 0.f, GetCapsuleComponent()->GetScaledCapsuleHalfHeight());
	const FVector Head = GetMesh()->GetBoneLocation(TEXT("head"));
	const FVector Chest = Feet + FVector(0.f, 0.f, 125.f);
	const FVector Fwd = GetActorForwardVector().GetSafeNormal2D();
	const FVector MyRight = FVector::CrossProduct(FVector::UpVector, Fwd);
	const FVector BossLoc = Enemy ? Enemy->GetActorLocation() : Me + Fwd * 800.f;
	const float BossH = Enemy ? Enemy->GetHalfHeight() : 150.f;
	const FVector BossFeet = BossLoc - FVector(0.f, 0.f, BossH);
	FVector BossHead = BossFeet + FVector(0.f, 0.f, BossH * 1.75f);
	if (Enemy && Enemy->GetMesh() && Enemy->GetMesh()->GetBoneIndex(TEXT("head")) != INDEX_NONE)
	{
		BossHead = Enemy->GetMesh()->GetBoneLocation(TEXT("head"));
	}
	const FVector ToBoss = (BossLoc - Me).GetSafeNormal2D();
	const FVector Perp = FVector::CrossProduct(FVector::UpVector, ToBoss);
	const FVector Mid = (Feet + BossFeet) * 0.5f;
	const float Gap = FVector::Dist2D(Me, BossLoc);

	FVector Loc;
	FVector Look;
	float Fov = 50.f;
	float Follow = 0.f; // 0 = locked to the rig, >0 = interp speed toward it
	switch (Shot)
	{
	case 0:
	{
		// Establishing crane: high over the temple, sinking toward her.
		const float A = Ease01(U / 6.f);
		const FVector Out = (-Fwd * 0.8f + MyRight * 0.6f).GetSafeNormal2D();
		Loc = Feet + Out * FMath::Lerp(2600.f, 900.f, A) + FVector(0.f, 0.f, FMath::Lerp(1700.f, 380.f, A));
		Look = FMath::Lerp(Feet + Fwd * 900.f, Chest, A);
		Fov = FMath::Lerp(58.f, 48.f, A);
		break;
	}
	case 1:
	{
		// Side tracking shot while she walks, low and close.
		if (bCut)
		{
			TrailerA = MyRight;
		}
		Loc = Feet + TrailerA * FMath::Lerp(420.f, 330.f, Ease01(U / 5.f)) + Fwd * 40.f + FVector(0.f, 0.f, 95.f);
		Look = Chest + Fwd * 30.f;
		Fov = 40.f;
		break;
	}
	case 2:
	{
		// Front close-up on her face, backing away as she walks in.
		Loc = Head + Fwd * FMath::Lerp(170.f, 105.f, Ease01(U / 4.f)) + MyRight * 18.f + FVector(0.f, 0.f, -6.f);
		Look = Head + FVector(0.f, 0.f, -4.f);
		Fov = 36.f;
		break;
	}
	case 3:
	{
		// Slow orbit round the sword.
		TArray<FVector> Blade;
		GetBladePoints(Blade);
		const FVector SwordMid = Blade.Num() >= 2 ? (Blade[0] + Blade.Last()) * 0.5f : Chest;
		const FVector Around = FRotator(0.f, Fwd.Rotation().Yaw + 40.f + U * 22.f, 0.f).Vector();
		Loc = SwordMid + Around * 95.f + FVector(0.f, 0.f, 18.f);
		Look = SwordMid;
		Fov = 34.f;
		break;
	}
	case 4:
	{
		// Over her shoulder: he appears.
		Loc = Head - ToBoss * 170.f + Perp * 55.f + FVector(0.f, 0.f, 18.f);
		Look = FMath::Lerp(BossLoc, BossHead, 0.6f);
		Fov = FMath::Lerp(44.f, 36.f, Ease01(U / 3.f));
		Follow = 6.f;
		break;
	}
	case 5:
	{
		// Low angle on the boss, slow push-in.
		const FVector BFwd = Enemy ? Enemy->GetActorForwardVector().GetSafeNormal2D() : -ToBoss;
		const FVector BRight = FVector::CrossProduct(FVector::UpVector, BFwd);
		Loc = BossFeet + BFwd * FMath::Lerp(520.f, 400.f, Ease01(U / 3.f)) + BRight * 90.f + FVector(0.f, 0.f, 40.f);
		Look = BossHead - FVector(0.f, 0.f, 20.f);
		Fov = 46.f;
		Follow = 8.f;
		break;
	}
	case 1000:
	{
		// Finale: crane up and away into the sky.
		if (bCut)
		{
			TrailerA = Perp;
			TrailerB = Mid;
		}
		const float A = Ease01(U / 4.f);
		Loc = TrailerB + TrailerA * FMath::Lerp(700.f, 1500.f, A) + FVector(0.f, 0.f, FMath::Lerp(220.f, 1300.f, A));
		Look = TrailerB + FVector(0.f, 0.f, FMath::Lerp(120.f, 900.f, A));
		Fov = 50.f;
		break;
	}
	default:
	{
		// Fight montage: a new angle every few seconds. Every angle keeps her in frame (9:16):
		// the two fighters stack in depth instead of standing side by side across the narrow width.
		const int32 Style = (Shot - 6) % 5;
		if (bCut)
		{
			TrailerA = FVector(((Shot / 5) % 2) ? -1.f : 1.f, 0.f, 0.f);
		}
		const float Side = TrailerA.X;
		const FVector BossChest = FMath::Lerp(BossFeet, BossHead, 0.55f);
		Follow = 5.f;
		// He is huge and fights close, so every angle sits on her side of the fight, swung off the line:
		// she is in the foreground, he towers behind her, and the lens never ends up inside him.
		struct FAngle { float Yaw, Dist, Height, LookUp, Fov; };
		static const FAngle Angles[5] = {
			{ 38.f, 430.f, 120.f, 0.18f, 50.f },  // three-quarter behind her
			{ 62.f, 650.f, 260.f, 0.25f, 52.f },  // wide, slow drift
			{ 85.f, 400.f, 60.f, 0.12f, 48.f },   // low, almost side-on
			{ 30.f, 560.f, 480.f, 0.20f, 54.f },  // high crane over her shoulder
			{ 55.f, 480.f, 30.f, 0.30f, 50.f },   // ground level, looking up at him
		};
		const FAngle& Ang = Angles[Style];
		const float Yaw = (-ToBoss).Rotation().Yaw + Side * (Ang.Yaw + U * 4.f);
		const float Dist = FMath::Max(Ang.Dist, Gap * 0.5f + 330.f);
		Loc = Me + FRotator(0.f, Yaw, 0.f).Vector() * Dist + FVector(0.f, 0.f, Ang.Height);
		Look = FMath::Lerp(Chest, BossChest, Ang.LookUp);
		Fov = Ang.Fov;
		break;
	}
	}

	// Keep the lens out of walls / props between it and what it films.
	{
		FCollisionQueryParams Params(SCENE_QUERY_STAT(BFTrailerCam), false, this);
		if (Enemy)
		{
			Params.AddIgnoredActor(Enemy);
		}
		FHitResult Hit;
		if (GetWorld()->SweepSingleByChannel(Hit, Look, Loc, FQuat::Identity, ECC_Camera, FCollisionShape::MakeSphere(20.f), Params))
		{
			// Blocked montage angle: mirror it across the fight line before settling for a cramped lens.
			if (Shot >= 6 && Shot < 1000 && Hit.Distance < FVector::Dist(Look, Loc) * 0.6f)
			{
				const FVector Rel = Loc - Look;
				const FVector Mirror = Look + Rel - 2.f * FVector::DotProduct(Rel, Perp) * Perp;
				FHitResult Hit2;
				if (!GetWorld()->SweepSingleByChannel(Hit2, Look, Mirror, FQuat::Identity, ECC_Camera, FCollisionShape::MakeSphere(20.f), Params))
				{
					Loc = Mirror;
					TrailerA.X = -TrailerA.X;
				}
				else
				{
					Loc = Hit2.Distance > Hit.Distance ? Hit2.Location : Hit.Location;
				}
			}
			else
			{
				Loc = Hit.Location;
			}
		}
	}

	FVector NewLoc = Loc;
	FRotator NewRot = (Look - Loc).Rotation();
	if (!bCut && Follow > 0.f)
	{
		NewLoc = FMath::VInterpTo(ShowCam->GetActorLocation(), Loc, Dt, Follow);
		NewRot = FMath::RInterpTo(ShowCam->GetActorRotation(), (Look - NewLoc).Rotation(), Dt, Follow * 1.6f);
	}
	ShowCam->SetActorLocationAndRotation(NewLoc, NewRot);
	Cam->SetFieldOfView(bCut || Follow <= 0.f ? Fov : FMath::FInterpTo(Cam->FieldOfView, Fov, Dt, 4.f));

	// Slow motion on the big moments of the montage (a broken guard or a stagger).
	if (Enemy && Shot >= 6 && Shot < 1000 && (Enemy->IsBroken() || Enemy->IsStaggered()) && TrailerSlowUntil == -1.f)
	{
		TrailerSlowUntil = T + 1.1f;
		UGameplayStatics::SetGlobalTimeDilation(this, 0.35f);
	}
	if (TrailerSlowUntil > 0.f && T >= TrailerSlowUntil)
	{
		UGameplayStatics::SetGlobalTimeDilation(this, 1.f);
		TrailerSlowUntil = -2.f; // once per stagger window
	}
	if (TrailerSlowUntil < -1.f && Enemy && !Enemy->IsBroken() && !Enemy->IsStaggered())
	{
		TrailerSlowUntil = -1.f;
	}
}

void ABFPlayerCharacter::TickTutorialBot(ABFEnemyBase* Enemy, float Dt)
{
	// Dash tutorial footage. One scene per run (-BFTut=):
	//   L_Training: dash4 (W/S/A/D slides), spam (charges run dry, refill), plunge (dash button in the air)
	//   L_Arena (+ -BFForceAttacks): perfect (dodge on time), early (dodge too soon, gets hit), clash (dodge a heavy or grab),
	//   mikiri (dash into the thrust), jump (jump the ground wave, stomp), blink (combo -> dash -> behind him)
	const double Now = GetWorld()->GetRealTimeSeconds();
	const float T = ShowT;
	if (TutScene.IsEmpty())
	{
		TutScene = ShowFlagStr(TEXT("BFTut="), TEXT("perfect"));
		TutStep = -1;
		UE_LOG(LogTemp, Display, TEXT("BFTUT scene=%s"), *TutScene);
	}
	if (BotJumpRelease > 0.0 && Now >= BotJumpRelease)
	{
		StopJumping();
		BotJumpRelease = 0.0;
	}
	if (BotGuardRelease > 0.0 && Now >= BotGuardRelease)
	{
		OnGuardReleased();
		BotGuardRelease = 0.0;
	}
	const bool bTraining = TutScene == TEXT("dash4") || TutScene == TEXT("spam") || TutScene == TEXT("plunge");
	if (bTraining)
	{
		if (TutNextAt == 0.f)
		{
			// Side-on to the dummy, so no dash runs at him (that would be a gap-close blink).
			float Yaw = GetActorRotation().Yaw;
			if (Enemy)
			{
				Enemy->bAutoAttack = false;
				Yaw = (Enemy->GetActorLocation() - GetActorLocation()).Rotation().Yaw + 90.f;
				// -BFHideEnemy: empty training ground (the dummy is hidden and out of the way).
				if (FParse::Param(FCommandLine::Get(), TEXT("BFHideEnemy")))
				{
					Enemy->SetActorHiddenInGame(true);
					Enemy->SetActorEnableCollision(false);
					UE_LOG(LogTemp, Display, TEXT("BFTUT enemy hidden"));
				}
			}
			TutFwd = FRotator(0.f, Yaw, 0.f).Vector();
			SetActorRotation(FRotator(0.f, Yaw, 0.f));
			if (Controller)
			{
				Controller->SetControlRotation(FRotator(-12.f, Yaw, 0.f));
			}
			TutNextAt = 1.f;
			TutStep = 0;
			bTutNoBlink = true; // plain dashes only (the dummy is close: no gap-close blink)
		}
		const FVector Fwd = TutFwd;
		const FVector Right = FVector::CrossProduct(FVector::UpVector, Fwd);
		if (T < TutNextAt)
		{
			return;
		}
		if (TutScene == TEXT("dash4") && TutStep < 4)
		{
			static const TCHAR* Names[4] = { TEXT("W"), TEXT("S"), TEXT("A"), TEXT("D") };
			const FVector Dirs[4] = { Fwd, -Fwd, -Right, Right };
			BotDash(Dirs[TutStep]);
			UE_LOG(LogTemp, Display, TEXT("BFTUT event=dash_%s frame=%d t=%.2f"), Names[TutStep], ShowFrame, T);
			++TutStep;
			TutNextAt = T + ShowFlag(TEXT("BFTutGap="), 1.4f);
		}
		else if (TutScene == TEXT("spam"))
		{
			// Roll back and forth as soon as each roll ends until the charges are gone, press twice more
			// (refused: the HUD pips flash red), wait for the refill, then roll once more.
			if (TutStep < 100 && State == EBFPlayerState::Free)
			{
				const int32 Before = DashCharges;
				BotDash(TutStep % 2 ? -Fwd : Fwd);
				UE_LOG(LogTemp, Display, TEXT("BFTUT event=spam_%d charges=%d frame=%d t=%.2f"), TutStep, Before, ShowFrame, T);
				++TutStep;
				TutNextAt = T + 0.1f;
				if (Before <= 0)
				{
					TutStep = 100; // refused: two more presses
					TutNextAt = T + 0.45f;
				}
			}
			else if (TutStep >= 100 && TutStep < 102)
			{
				BotDash(Fwd);
				UE_LOG(LogTemp, Display, TEXT("BFTUT event=refused frame=%d t=%.2f"), ShowFrame, T);
				++TutStep;
				TutNextAt = TutStep == 102 ? T + 8.6f : T + 0.45f;
			}
			else if (TutStep == 102)
			{
				BotDash(-Fwd);
				UE_LOG(LogTemp, Display, TEXT("BFTUT event=refilled charges=%d frame=%d t=%.2f"), DashCharges, ShowFrame, T);
				++TutStep;
			}
		}
		else if (TutScene == TEXT("plunge") && TutStep < 4)
		{
			if (TutStep % 2 == 0)
			{
				BotJump();
				TutNextAt = T + 0.38f;
			}
			else
			{
				LastMoveInput = Fwd;
				LastMoveInputTime = Now;
				OnDashPressed();
				UE_LOG(LogTemp, Display, TEXT("BFTUT event=plunge frame=%d t=%.2f"), ShowFrame, T);
				TutNextAt = T + 3.f;
			}
			++TutStep;
		}
		return;
	}

	if (!Enemy || Enemy->IsDead())
	{
		return;
	}
	// Strength clash: mash.
	if (bStruggle || State == EBFPlayerState::Clashing)
	{
		BotMash += Dt;
		if (BotMash >= 0.085f)
		{
			BotMash = 0.f;
			OnLightDown();
			OnLightUp();
		}
		return;
	}
	if (bGrabbed || bCinematic || bKnockedDown || Enemy->IsInTransition())
	{
		return;
	}
	if (!bLockedOn && !Enemy->IsHidden())
	{
		SetLockTarget(Enemy);
	}
	// Jumped the wave: drop onto him.
	if (CanStomp())
	{
		if (BotStompAt < 0.0)
		{
			BotStompAt = Now + 0.12;
		}
		else if (Now >= BotStompAt)
		{
			OnLightPressed();
			BotStompAt = -1.0;
		}
		return;
	}
	BotStompAt = -1.0;

	const FVector ToB = Enemy->GetActorLocation() - GetActorLocation();
	const float Dist = ToB.Size2D();
	const FVector Dir = ToB.GetSafeNormal2D();
	const FVector Right = FVector::CrossProduct(FVector::UpVector, Dir);

	if (TutScene == TEXT("combo6"))
	{
		// Full light string on a passive target: tap light every 0.2 s (the buffer chains each hit at its
		// cancel time) until the finisher plays, then rest and go again.
		Enemy->HoldAttacks(1.f);
		// -BFHideEnemy: swing at the air (the dummy is hidden, out of the way, and never approached).
		static const bool bNoTarget = FParse::Param(FCommandLine::Get(), TEXT("BFHideEnemy"));
		if (bNoTarget && !Enemy->IsHidden())
		{
			Enemy->SetActorHiddenInGame(true);
			Enemy->SetActorEnableCollision(false);
			Enemy->SetActorTickEnabled(false);
			SetLockTarget(nullptr);
			UE_LOG(LogTemp, Display, TEXT("BFTUT enemy hidden"));
		}
		if (State == EBFPlayerState::Attacking || (BotRoutine >= 0 && T < TutNextAt))
		{
			if (BotRoutine >= 0 && CurrentChain == EBFChain::Light && Now - BotStepAt >= 0.2)
			{
				BotStepAt = Now;
				if (ComboIndex >= LightChain.Num() - 1)
				{
					BotRoutine = -1; // finisher running: stop pressing
					TutNextAt = T + 2.f;
					UE_LOG(LogTemp, Display, TEXT("BFTUT event=combo6_finisher frame=%d t=%.2f"), ShowFrame, T);
				}
				else
				{
					OnLightPressed();
				}
			}
			return;
		}
		if (Dist > 200.f && !bNoTarget)
		{
			BotMove(Dir, 1.f);
			return;
		}
		if (State == EBFPlayerState::Free && T >= TutNextAt)
		{
			BotRoutine = 0;
			BotStepAt = Now;
			OnLightPressed();
			UE_LOG(LogTemp, Display, TEXT("BFTUT event=combo6_start frame=%d t=%.2f"), ShowFrame, T);
		}
		return;
	}
	if (TutScene == TEXT("blink"))
	{
		// He stays passive; we run in, swing twice and dash out of the swing: blink to his back.
		Enemy->HoldAttacks(1.f);
		if (BotRoutine < 0 && Dist < 260.f && State == EBFPlayerState::Free && T >= TutNextAt)
		{
			BotRoutine = 0;
			BotStep = 0;
			BotStepAt = Now;
		}
		if (BotRoutine >= 0)
		{
			static const float At[5] = { 0.f, 0.36f, 0.72f, 1.25f, 1.6f };
			if (Now - BotStepAt >= At[BotStep])
			{
				if (BotStep == 2)
				{
					BotDash(Dir);
					UE_LOG(LogTemp, Display, TEXT("BFTUT event=blink_press frame=%d t=%.2f"), ShowFrame, T);
				}
				else
				{
					OnLightPressed();
				}
				if (++BotStep >= 5)
				{
					BotRoutine = -1;
					TutNextAt = T + 2.2f;
				}
			}
			return;
		}
		BotMove(Dist > 230.f ? Dir : Right * BotStrafe, Dist > 230.f ? 1.f : 0.5f);
		return;
	}

	// Defence scenes: answer each swing once, the way the scene shows.
	const float TTH = Enemy->GetTimeToHit();
	const EBFPerilous Kind = Enemy->GetPerilous();
	const int32 N = Enemy->GetAttackCount();
	if (TTH >= 0.f && N != TutStep)
	{
		// "parry" (+ -BFForceAttacks=2, the slam): parry the heavy swing on time -> strength clash -> mash.
		if (TutScene == TEXT("parry"))
		{
			if (Enemy->IsCurrentAttackHeavy() && TTH <= 0.1f)
			{
				TutStep = N;
				OnGuardPressed();
				BotGuardRelease = Now + 0.15;
				UE_LOG(LogTemp, Display, TEXT("BFTUT event=parry tth=%.2f frame=%d t=%.2f"), TTH, ShowFrame, T);
			}
			return; // never dodge in this scene
		}
		const bool bEarly = TutScene == TEXT("early");
		const float When = bEarly ? 0.72f : (Kind == EBFPerilous::Sweep ? 0.15f : (Kind == EBFPerilous::Thrust ? 0.12f : 0.1f));
		if (TTH <= When)
		{
			TutStep = N;
			if (Kind == EBFPerilous::Sweep)
			{
				BotJump();
			}
			else if (Kind == EBFPerilous::Thrust)
			{
				BotDash(Dir);
			}
			else
			{
				BotDash(Right * BotStrafe);
				BotStrafe = -BotStrafe;
			}
			UE_LOG(LogTemp, Display, TEXT("BFTUT event=react kind=%d heavy=%d tth=%.2f frame=%d t=%.2f"), int32(Kind), Enemy->IsCurrentAttackHeavy() ? 1 : 0, TTH, ShowFrame, T);
			return;
		}
	}
	// Neutral: circle him at sword range.
	if (Now >= BotStrafeFlip)
	{
		BotStrafe = -BotStrafe;
		BotStrafeFlip = Now + FMath::FRandRange(1.4f, 2.4f);
	}
	const FVector Move = Right * BotStrafe * 0.6f + (Dist < 230.f ? -Dir * 0.6f : (Dist > 330.f ? Dir * 0.7f : FVector::ZeroVector));
	BotMove(Move, 0.6f);
}
