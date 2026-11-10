// Still-poster staging (-BFAutoTest=poster -BFPosterFile=<scene.txt>). One line per item, "kind key=value ...":
//   res W H                      HighResShot size (keep the window aspect the same)
//   warm S                       seconds to let effects run after shaders finish, before the first shot
//   gap S                        seconds between shots
//   cam name=N loc=x,y,z rot=pitch,yaw,roll fov=F       one still per cam line, in order
//   hero loc=x,y,z yaw=Y anim=/Game/.. t=T              the player (swordswoman), feet at loc; look=deg tilts her head up
//   rig mesh=/Game/.. abp=/Game/.. loc= yaw= anim= t= scale=S meshyaw=Y   extra character: a hidden IAC mannequin plays
//                                the clip, the visible mesh copies it through its Retarget-Pose-From-Mesh anim blueprint
//   boss loc= yaw= anim= t= scale=S | boss hide         the first enemy in the level
//   light kind=point|spot|rect loc= rot= color=r,g,b intensity=I radius=R inner=A outer=B shadows=0|1
//   fx path=/Game/..NS loc= rot= scale=S age=S float=Name:V color=Name:r,g,b   (age: freeze the effect at that age;
//                                                       lead=S instead: fire it live S seconds before each capture, for burst slashes)
//   boss ... aura=0                                    hides the boss's green aura shell
//   trail path=/Game/..NS from= to= lead=S width= life= color=Name:r,g,b   ribbon trail swept from -> to before each capture
//   mesh path=/Game/..SM loc= rot= scale=x,y,z
//   sun rot=p,y,r intensity=I color=r,g,b              the level's directional light
//   hide match=Text              hides actors whose name or label contains Text
//   cmd <console command>        run at setup (cvars and the like)
// '#' starts a comment. Feet positions are world space in cm; yaw in degrees.
#include "BFPosterDirector.h"
#include "BFPlayerCharacter.h"
#include "BFEnemyBase.h"
#include "AssetCompilingManager.h"
#include "ShaderCompiler.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/ExponentialHeightFogComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/PoseableMeshComponent.h"
#include "Components/RectLightComponent.h"
#include "Components/SkyLightComponent.h"
#include "Components/SpotLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/DirectionalLight.h"
#include "Engine/ExponentialHeightFog.h"
#include "Engine/PostProcessVolume.h"
#include "Engine/SkyLight.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/SkeletalMesh.h"
#include "EngineUtils.h"
#include "Animation/AnimInstance.h"
#include "Animation/AnimSequenceBase.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/HUD.h"
#include "GameFramework/PlayerController.h"
#include "Misc/FileHelper.h"
#include "NiagaraComponent.h"
#include "NiagaraFunctionLibrary.h"
#include "NiagaraSystem.h"

namespace
{
	FString ObjPath(FString P)
	{
		P.TrimStartAndEndInline();
		if (!P.Contains(TEXT(".")))
		{
			P += TEXT(".") + FPaths::GetBaseFilename(P);
		}
		return P;
	}

	TMap<FString, FString> Keys(const TArray<FString>& Tok)
	{
		TMap<FString, FString> M;
		for (int32 i = 1; i < Tok.Num(); ++i)
		{
			FString K, V;
			if (Tok[i].Split(TEXT("="), &K, &V))
			{
				M.Add(K.ToLower(), V);
			}
			else
			{
				M.Add(Tok[i].ToLower(), FString()); // bare flag such as "hide"
			}
		}
		return M;
	}

	TArray<float> Nums(const FString& S)
	{
		TArray<FString> Parts;
		S.ParseIntoArray(Parts, TEXT(","));
		TArray<float> Out;
		for (const FString& P : Parts)
		{
			Out.Add(FCString::Atof(*P));
		}
		return Out;
	}

	FVector Vec(const TMap<FString, FString>& M, const TCHAR* Key, const FVector& Def = FVector::ZeroVector)
	{
		const FString* S = M.Find(Key);
		if (!S)
		{
			return Def;
		}
		const TArray<float> N = Nums(*S);
		return N.Num() >= 3 ? FVector(N[0], N[1], N[2]) : (N.Num() == 1 ? FVector(N[0]) : Def);
	}

	FRotator Rot(const TMap<FString, FString>& M, const TCHAR* Key)
	{
		const FVector V = Vec(M, Key);
		return FRotator(V.X, V.Y, V.Z); // pitch, yaw, roll
	}

	float Num(const TMap<FString, FString>& M, const TCHAR* Key, float Def)
	{
		const FString* S = M.Find(Key);
		return S ? FCString::Atof(**S) : Def;
	}

	FLinearColor Col(const TMap<FString, FString>& M, const TCHAR* Key, const FLinearColor& Def)
	{
		const FVector V = Vec(M, Key, FVector(Def.R, Def.G, Def.B));
		return FLinearColor(V.X, V.Y, V.Z);
	}
}

ABFPosterDirector::ABFPosterDirector()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickGroup = TG_PostPhysics;
	RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
}

void ABFPosterDirector::Setup(ABFPlayerCharacter* InPlayer)
{
	Player = InPlayer;
	FString File;
	FParse::Value(FCommandLine::Get(), TEXT("BFPosterFile="), File);
	TArray<FString> Lines;
	if (File.IsEmpty() || !FFileHelper::LoadFileToStringArray(Lines, *File))
	{
		UE_LOG(LogTemp, Error, TEXT("BFPOSTER cannot read scene file '%s'"), *File);
		return;
	}
	APlayerController* PC = Player ? Cast<APlayerController>(Player->GetController()) : nullptr;
	if (PC && PC->GetHUD())
	{
		PC->GetHUD()->bShowHUD = false;
	}
	if (PC)
	{
		PC->ConsoleCommand(TEXT("r.MotionBlurQuality 0"));
	}
	FActorSpawnParameters Params;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	Cam = GetWorld()->SpawnActor<ACameraActor>(ACameraActor::StaticClass(), FTransform::Identity, Params);
	Cam->GetCameraComponent()->bConstrainAspectRatio = false;
	// fov= in scene files is the horizontal angle (portrait shots otherwise get a much narrower view than asked for).
	Cam->GetCameraComponent()->bOverrideAspectRatioAxisConstraint = true;
	Cam->GetCameraComponent()->AspectRatioAxisConstraint = EAspectRatioAxisConstraint::AspectRatio_MaintainXFOV;
	if (PC)
	{
		PC->SetViewTarget(Cam);
	}
	for (FString L : Lines)
	{
		int32 Hash;
		if (L.FindChar(TEXT('#'), Hash))
		{
			L.LeftInline(Hash);
		}
		L.TrimStartAndEndInline();
		if (!L.IsEmpty())
		{
			ParseLine(L);
		}
	}
	if (PC)
	{
		for (const FString& C : PostCommands)
		{
			PC->ConsoleCommand(C);
		}
	}
	if (Shots.Num() > 0)
	{
		Cam->SetActorLocationAndRotation(Shots[0].Loc, Shots[0].Rot);
		Cam->GetCameraComponent()->SetFieldOfView(Shots[0].Fov);
	}
	UE_LOG(LogTemp, Display, TEXT("BFPOSTER setup file=%s shots=%d posed=%d res=%dx%d"), *File, Shots.Num(), Posed.Num(), ResX, ResY);
}

void ABFPosterDirector::Pose(USkeletalMeshComponent* Mesh, const FString& AnimPath, float Time)
{
	UAnimSequenceBase* Anim = AnimPath.IsEmpty() ? nullptr : LoadObject<UAnimSequenceBase>(nullptr, *ObjPath(AnimPath));
	if (!Mesh || !Anim)
	{
		UE_LOG(LogTemp, Warning, TEXT("BFPOSTER pose failed mesh=%s anim=%s"), Mesh ? *Mesh->GetName() : TEXT("none"), *AnimPath);
		return;
	}
	Mesh->SetAnimationMode(EAnimationMode::AnimationSingleNode);
	Mesh->PlayAnimation(Anim, false);
	Mesh->SetPosition(Time, false);
	Mesh->SetPlayRate(0.f);
	Mesh->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
	Posed.Add({Mesh, Anim, Time});
	UE_LOG(LogTemp, Display, TEXT("BFPOSTER pose %s <- %s t=%.2f (len %.2f)"), *Mesh->GetOwner()->GetName(), *Anim->GetName(), Time, Anim->GetPlayLength());
}

void ABFPosterDirector::ParseLine(const FString& Line)
{
	TArray<FString> Tok;
	Line.ParseIntoArrayWS(Tok);
	const FString Kind = Tok[0].ToLower();
	TMap<FString, FString> M = Keys(Tok);
	FActorSpawnParameters Params;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	UWorld* W = GetWorld();

	// snap=1: drop loc onto the static ground under it (trace from 3000 above loc down to 20000 below), so loc's z only needs to be
	// roughly right. lift=Z raises the snapped point (e.g. a caster in mid-air).
	if (M.Contains(TEXT("snap")) && M.Contains(TEXT("loc")))
	{
		const FVector L = Vec(M, TEXT("loc"));
		FHitResult Hit;
		FCollisionQueryParams Q(TEXT("BFPosterSnap"), true);
		const bool bHit = W->LineTraceSingleByObjectType(Hit, L + FVector(0.f, 0.f, 3000.f), L - FVector(0.f, 0.f, 20000.f),
			FCollisionObjectQueryParams(ECC_WorldStatic), Q);
		const FVector P = (bHit ? Hit.ImpactPoint : L) + FVector(0.f, 0.f, Num(M, TEXT("lift"), 0.f));
		M.Add(TEXT("loc"), FString::Printf(TEXT("%.1f,%.1f,%.1f"), P.X, P.Y, P.Z));
		UE_LOG(LogTemp, Display, TEXT("BFPOSTER snap %s %s -> %s (%s)"), *Kind, *L.ToCompactString(), *P.ToCompactString(),
			bHit && Hit.GetActor() ? *Hit.GetActor()->GetName() : TEXT("no hit"));
	}

	if (Kind == TEXT("res") && Tok.Num() >= 3)
	{
		ResX = FCString::Atoi(*Tok[1]);
		ResY = FCString::Atoi(*Tok[2]);
	}
	else if (Kind == TEXT("warm") && Tok.Num() >= 2)
	{
		Warm = FCString::Atof(*Tok[1]);
	}
	else if (Kind == TEXT("gap") && Tok.Num() >= 2)
	{
		ShotGap = FCString::Atof(*Tok[1]);
	}
	else if (Kind == TEXT("cmd"))
	{
		PostCommands.Add(Line.Mid(4).TrimStartAndEnd());
	}
	else if (Kind == TEXT("cam"))
	{
		FShot S;
		S.Loc = Vec(M, TEXT("loc"));
		S.Rot = Rot(M, TEXT("rot"));
		S.Fov = Num(M, TEXT("fov"), 40.f);
		S.Name = M.Contains(TEXT("name")) ? M[TEXT("name")] : FString::Printf(TEXT("%d"), Shots.Num());
		Shots.Add(S);
	}
	else if (Kind == TEXT("hero") && Player)
	{
		if (M.Contains(TEXT("hide")))
		{
			Player->SetActorHiddenInGame(true);
			return;
		}
		Player->GetCharacterMovement()->DisableMovement();
		Player->SetActorEnableCollision(false);
		const float Half = Player->GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
		Player->SetActorLocationAndRotation(Vec(M, TEXT("loc")) + FVector(0.f, 0.f, Half), FRotator(0.f, Num(M, TEXT("yaw"), 0.f), 0.f),
			false, nullptr, ETeleportType::ResetPhysics);
		if (AController* C = Player->GetController())
		{
			C->SetControlRotation(Player->GetActorRotation());
		}
		HeroXform = Player->GetActorTransform();
		bHeroPlaced = true;
		Pose(Player->GetMesh(), M.FindRef(TEXT("anim")), Num(M, TEXT("t"), 0.f));
		// look=deg: tilts her head up (chin up; negative looks down). Her body is retargeted from the hidden mannequin,
		// so a poseable copy of it is shown instead, re-copied every tick with the neck and head turned (TickHeadLook).
		USkeletalMeshComponent* Body = HeroBody();
		if (M.Contains(TEXT("look")) && Body && Body != Player->GetMesh())
		{
			HeadLook = Num(M, TEXT("look"), 0.f);
			HeroPose = NewObject<UPoseableMeshComponent>(Player, TEXT("PosterBody"));
			HeroPose->SetSkinnedAssetAndUpdate(Body->GetSkeletalMeshAsset());
			HeroPose->SetupAttachment(Body->GetAttachParent(), Body->GetAttachSocketName());
			HeroPose->SetRelativeTransform(Body->GetRelativeTransform());
			HeroPose->RegisterComponent();
			for (int32 I = 0; I < Body->GetNumMaterials(); ++I)
			{
				HeroPose->SetMaterial(I, Body->GetMaterial(I));
			}
			Body->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
			Body->SetVisibility(false, false);
			UE_LOG(LogTemp, Display, TEXT("BFPOSTER hero look %.1f deg (poseable copy of %s)"), HeadLook, *Body->GetName());
		}
	}
	else if (Kind == TEXT("rig"))
	{
		USkeletalMesh* Mann = LoadObject<USkeletalMesh>(nullptr, TEXT("/Game/InsaneAirCombo/Animation/Skeleton/SK_Mannequin.SK_Mannequin"));
		USkeletalMesh* Body = LoadObject<USkeletalMesh>(nullptr, *ObjPath(M.FindRef(TEXT("mesh"))));
		UClass* Abp = LoadClass<UAnimInstance>(nullptr, *(ObjPath(M.FindRef(TEXT("abp"))) + TEXT("_C")));
		AActor* A = W->SpawnActor<AActor>(AActor::StaticClass(), FTransform(FRotator(0.f, Num(M, TEXT("yaw"), 0.f), 0.f), Vec(M, TEXT("loc"))), Params);
		USceneComponent* Root = NewObject<USceneComponent>(A, TEXT("Root"));
		A->SetRootComponent(Root);
		Root->RegisterComponent();
		A->SetActorLocationAndRotation(Vec(M, TEXT("loc")), FRotator(0.f, Num(M, TEXT("yaw"), 0.f), 0.f));
		USkeletalMeshComponent* Src = NewObject<USkeletalMeshComponent>(A, TEXT("Mannequin"));
		Src->SetSkeletalMeshAsset(Mann);
		Src->SetupAttachment(Root);
		Src->SetRelativeRotation(FRotator(0.f, -90.f, 0.f));
		Src->SetHiddenInGame(true);
		Src->SetCastShadow(false);
		Src->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
		Src->RegisterComponent();
		USkeletalMeshComponent* Vis = NewObject<USkeletalMeshComponent>(A, TEXT("Body"));
		Vis->SetSkeletalMeshAsset(Body);
		Vis->SetupAttachment(Src);
		Vis->SetRelativeRotation(FRotator(0.f, Num(M, TEXT("meshyaw"), 0.f), 0.f));
		Vis->SetRelativeScale3D(FVector(Num(M, TEXT("scale"), 1.f)));
		Vis->SetAnimInstanceClass(Abp);
		Vis->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
		Vis->bCastDynamicShadow = true;
		Vis->RegisterComponent();
		Vis->AddTickPrerequisiteComponent(Src);
		Keep.Add(A);
		UE_LOG(LogTemp, Display, TEXT("BFPOSTER rig %s mesh=%s abp=%s"), *A->GetName(), Body ? *Body->GetName() : TEXT("MISSING"), Abp ? *Abp->GetName() : TEXT("MISSING"));
		Pose(Src, M.FindRef(TEXT("anim")), Num(M, TEXT("t"), 0.f));
		UE_LOG(LogTemp, Display, TEXT("BFPOSTER rig %s at %s body bounds %s r=%.0f"), *A->GetName(), *A->GetActorLocation().ToString(),
			*Vis->Bounds.Origin.ToString(), Vis->Bounds.SphereRadius);
	}
	else if (Kind == TEXT("boss"))
	{
		ABFEnemyBase* E = nullptr;
		for (TActorIterator<ABFEnemyBase> It(W); It; ++It)
		{
			E = *It;
			break;
		}
		if (!E)
		{
			UE_LOG(LogTemp, Warning, TEXT("BFPOSTER no boss in level"));
			return;
		}
		E->SetActorTickEnabled(false);
		E->SetActorEnableCollision(false);
		if (M.Contains(TEXT("hide")))
		{
			E->SetActorHiddenInGame(true);
			TArray<AActor*> Att;
			E->GetAttachedActors(Att, true, true);
			for (AActor* X : Att)
			{
				X->SetActorHiddenInGame(true);
			}
			return;
		}
		if (UCharacterMovementComponent* Move = E->FindComponentByClass<UCharacterMovementComponent>())
		{
			Move->DisableMovement();
		}
		if (M.Contains(TEXT("scale")))
		{
			E->SetActorScale3D(FVector(Num(M, TEXT("scale"), 1.f)));
		}
		const float Half = E->GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
		E->SetActorLocationAndRotation(Vec(M, TEXT("loc")) + FVector(0.f, 0.f, Half), FRotator(0.f, Num(M, TEXT("yaw"), 0.f), 0.f),
			false, nullptr, ETeleportType::ResetPhysics);
		Pose(E->GetMesh(), M.FindRef(TEXT("anim")), Num(M, TEXT("t"), 0.f));
		USkeletalMeshComponent* BodyMesh = E->GetMesh();
		UE_LOG(LogTemp, Display, TEXT("BFPOSTER boss mesh visible=%d hidden=%d owner_hidden=%d"), BodyMesh->IsVisible(), BodyMesh->bHiddenInGame, E->IsHidden());
		BodyMesh->SetHiddenInGame(false);
		BodyMesh->SetVisibility(true);
		// aura=0 hides the green aura shell (boss tick is off, so nothing turns it back on).
		const bool bAura = Num(M, TEXT("aura"), 1.f) > 0.f;
		TArray<USkeletalMeshComponent*> Skels;
		E->GetComponents<USkeletalMeshComponent>(Skels);
		for (USkeletalMeshComponent* S : Skels)
		{
			if (S != BodyMesh && S->GetFName() == TEXT("AuraShell"))
			{
				S->SetVisibility(bAura);
			}
		}
	}
	else if (Kind == TEXT("light"))
	{
		const FString K = M.FindRef(TEXT("kind")).ToLower();
		AActor* A = W->SpawnActor<AActor>(AActor::StaticClass(), FTransform(Rot(M, TEXT("rot")), Vec(M, TEXT("loc"))), Params);
		ULocalLightComponent* Lc = nullptr;
		if (K == TEXT("spot"))
		{
			USpotLightComponent* S = NewObject<USpotLightComponent>(A);
			S->SetInnerConeAngle(Num(M, TEXT("inner"), 15.f));
			S->SetOuterConeAngle(Num(M, TEXT("outer"), 35.f));
			Lc = S;
		}
		else if (K == TEXT("rect"))
		{
			URectLightComponent* R = NewObject<URectLightComponent>(A);
			R->SetSourceWidth(Num(M, TEXT("width"), 200.f));
			R->SetSourceHeight(Num(M, TEXT("height"), 200.f));
			Lc = R;
		}
		else
		{
			Lc = NewObject<UPointLightComponent>(A);
		}
		A->SetRootComponent(Lc);
		Lc->SetMobility(EComponentMobility::Movable);
		Lc->SetIntensityUnits(ELightUnits::Candelas);
		Lc->SetIntensity(Num(M, TEXT("intensity"), 50.f));
		Lc->SetLightColor(Col(M, TEXT("color"), FLinearColor::White));
		Lc->SetAttenuationRadius(Num(M, TEXT("radius"), 1000.f));
		Lc->SetCastShadows(Num(M, TEXT("shadows"), 0.f) > 0.5f);
		Lc->RegisterComponent();
		A->SetActorLocationAndRotation(Vec(M, TEXT("loc")), Rot(M, TEXT("rot")));
		Keep.Add(A);
	}
	else if (Kind == TEXT("fx"))
	{
		UNiagaraSystem* Sys = LoadObject<UNiagaraSystem>(nullptr, *ObjPath(M.FindRef(TEXT("path"))));
		if (!Sys)
		{
			UE_LOG(LogTemp, Warning, TEXT("BFPOSTER fx missing %s"), *M.FindRef(TEXT("path")));
			return;
		}
		const bool bLead = M.Contains(TEXT("lead"));
		UNiagaraComponent* N = UNiagaraFunctionLibrary::SpawnSystemAtLocation(W, Sys, Vec(M, TEXT("loc")), Rot(M, TEXT("rot")),
			Vec(M, TEXT("scale"), FVector::OneVector), false, true, ENCPoolMethod::None, true);
		// Lead effects play once right away too: the first activation of a system never shows up in a capture.
		if (N)
		{
			if (bLead)
			{
				// Fired live shortly before each capture (see Tick); frozen ages lose burst-spawned slashes.
				LeadFx.Add({N, Num(M, TEXT("lead"), 0.2f), -1});
			}
			else if (M.Contains(TEXT("age")))
			{
				// Freeze the effect at this age (seconds): it simulates up to it and holds there.
				N->SetAgeUpdateMode(ENiagaraAgeUpdateMode::DesiredAge);
				N->SetSeekDelta(1.f / 60.f);
				N->SetDesiredAge(Num(M, TEXT("age"), 0.5f));
			}
			for (const TPair<FString, FString>& P : M)
			{
				FString Name, Val;
				if (P.Key.StartsWith(TEXT("float")) && P.Value.Split(TEXT(":"), &Name, &Val))
				{
					N->SetVariableFloat(FName(*Name), FCString::Atof(*Val));
				}
				else if (P.Key.StartsWith(TEXT("color")) && P.Value.Split(TEXT(":"), &Name, &Val))
				{
					const TArray<float> C = Nums(Val);
					if (C.Num() >= 3)
					{
						N->SetVariableLinearColor(FName(*Name), FLinearColor(C[0], C[1], C[2], C.Num() > 3 ? C[3] : 1.f));
					}
				}
			}
			Keep.Add(N);
		}
		UE_LOG(LogTemp, Display, TEXT("BFPOSTER fx %s ok=%d"), *Sys->GetName(), N ? 1 : 0);
	}
	else if (Kind == TEXT("trail"))
	{
		// trail path=NS from=x,y,z to=x,y,z lead=S width=W life=S color=Name:r,g,b ...  ribbon swept from -> to right before each capture.
		UNiagaraSystem* Sys = LoadObject<UNiagaraSystem>(nullptr, *ObjPath(M.FindRef(TEXT("path"))));
		if (!Sys)
		{
			UE_LOG(LogTemp, Warning, TEXT("BFPOSTER trail missing %s"), *M.FindRef(TEXT("path")));
			return;
		}
		FTrail T;
		T.From = Vec(M, TEXT("from"));
		T.To = Vec(M, TEXT("to"));
		T.Lead = Num(M, TEXT("lead"), 0.35f);
		// Plays once at spawn as a warm-up (the first activation of a system never shows up in a capture).
		UNiagaraComponent* N = UNiagaraFunctionLibrary::SpawnSystemAtLocation(W, Sys, T.From, Rot(M, TEXT("rot")), FVector::OneVector, false, true,
			ENCPoolMethod::None, false);
		if (N)
		{
			N->SetVariableFloat(TEXT("Width"), Num(M, TEXT("width"), 40.f));
			N->SetVariableFloat(TEXT("Life"), Num(M, TEXT("life"), T.Lead + 0.4f));
			N->SetVariableFloat(TEXT("AllSizeScale"), Num(M, TEXT("size"), 1.f));
			for (const TPair<FString, FString>& P : M)
			{
				FString Name, Val;
				if (P.Key.StartsWith(TEXT("float")) && P.Value.Split(TEXT(":"), &Name, &Val))
				{
					N->SetVariableFloat(FName(*Name), FCString::Atof(*Val));
				}
				else if (P.Key.StartsWith(TEXT("color")) && P.Value.Split(TEXT(":"), &Name, &Val))
				{
					const TArray<float> C = Nums(Val);
					if (C.Num() >= 3)
					{
						N->SetVariableLinearColor(FName(*Name), FLinearColor(C[0], C[1], C[2], C.Num() > 3 ? C[3] : 1.f));
					}
				}
			}
			T.Fx = N;
			Trails.Add(T);
			Keep.Add(N);
		}
		UE_LOG(LogTemp, Display, TEXT("BFPOSTER trail %s %s -> %s ok=%d"), *Sys->GetName(), *T.From.ToCompactString(), *T.To.ToCompactString(), N ? 1 : 0);
	}
	else if (Kind == TEXT("mesh"))
	{
		UStaticMesh* SM = LoadObject<UStaticMesh>(nullptr, *ObjPath(M.FindRef(TEXT("path"))));
		if (!SM)
		{
			UE_LOG(LogTemp, Warning, TEXT("BFPOSTER mesh missing %s"), *M.FindRef(TEXT("path")));
			return;
		}
		AStaticMeshActor* A = W->SpawnActor<AStaticMeshActor>(AStaticMeshActor::StaticClass(), FTransform(Rot(M, TEXT("rot")), Vec(M, TEXT("loc"))), Params);
		A->GetStaticMeshComponent()->SetMobility(EComponentMobility::Movable);
		A->GetStaticMeshComponent()->SetStaticMesh(SM);
		A->SetActorScale3D(Vec(M, TEXT("scale"), FVector::OneVector));
		A->SetActorEnableCollision(false);
		Keep.Add(A);
	}
	else if (Kind == TEXT("sun"))
	{
		for (TActorIterator<ADirectionalLight> It(W); It; ++It)
		{
			UDirectionalLightComponent* D = Cast<UDirectionalLightComponent>(It->GetLightComponent());
			if (M.Contains(TEXT("rot")))
			{
				It->GetRootComponent()->SetMobility(EComponentMobility::Movable);
				It->SetActorRotation(Rot(M, TEXT("rot")));
			}
			if (D && M.Contains(TEXT("intensity")))
			{
				D->SetIntensity(Num(M, TEXT("intensity"), 5.f));
			}
			if (D && M.Contains(TEXT("color")))
			{
				D->SetLightColor(Col(M, TEXT("color"), FLinearColor::White));
			}
			UE_LOG(LogTemp, Display, TEXT("BFPOSTER sun %s rot=%s"), *It->GetName(), *It->GetActorRotation().ToString());
			break;
		}
		for (TActorIterator<ASkyLight> It(W); It; ++It)
		{
			if (M.Contains(TEXT("sky")))
			{
				It->GetLightComponent()->SetIntensity(Num(M, TEXT("sky"), 1.f));
			}
			It->GetLightComponent()->RecaptureSky();
		}
	}
	else if (Kind == TEXT("clear"))
	{
		// Removes foliage instances (grass, flowers, bushes) within radius of loc, in this run only.
		const FVector C = Vec(M, TEXT("loc"));
		const float R = Num(M, TEXT("radius"), 300.f);
		int32 Removed = 0;
		for (TActorIterator<AActor> It(W); It; ++It)
		{
			if (!It->GetClass()->GetName().Contains(TEXT("InstancedFoliageActor")))
			{
				continue;
			}
			TArray<UInstancedStaticMeshComponent*> Comps;
			It->GetComponents<UInstancedStaticMeshComponent>(Comps);
			for (UInstancedStaticMeshComponent* Ism : Comps)
			{
				TArray<int32> Hits = Ism->GetInstancesOverlappingSphere(C, R, true);
				if (Hits.Num() > 0)
				{
					Removed += Hits.Num();
					Ism->RemoveInstances(Hits);
				}
			}
		}
		UE_LOG(LogTemp, Display, TEXT("BFPOSTER clear %s r=%.0f -> %d foliage instances"), *C.ToCompactString(), R, Removed);
	}
	else if (Kind == TEXT("grade"))
	{
		// An unbound post-process volume on top of the level's: temp=K tint= sat= contrast= gain=r,g,b exposure=EV bloom= vignette=
		APostProcessVolume* V = W->SpawnActor<APostProcessVolume>(APostProcessVolume::StaticClass(), FTransform::Identity, Params);
		V->bUnbound = true;
		V->Priority = 1000.f;
		FPostProcessSettings& S = V->Settings;
		if (M.Contains(TEXT("temp"))) { S.bOverride_WhiteTemp = true; S.WhiteTemp = Num(M, TEXT("temp"), 6500.f); }
		if (M.Contains(TEXT("tint"))) { S.bOverride_WhiteTint = true; S.WhiteTint = Num(M, TEXT("tint"), 0.f); }
		if (M.Contains(TEXT("sat"))) { S.bOverride_ColorSaturation = true; const float Sv = Num(M, TEXT("sat"), 1.f); S.ColorSaturation = FVector4(Sv, Sv, Sv, 1.f); }
		if (M.Contains(TEXT("contrast"))) { S.bOverride_ColorContrast = true; const float Cv = Num(M, TEXT("contrast"), 1.f); S.ColorContrast = FVector4(Cv, Cv, Cv, 1.f); }
		if (M.Contains(TEXT("gain"))) { S.bOverride_ColorGain = true; const FLinearColor G = Col(M, TEXT("gain"), FLinearColor::White); S.ColorGain = FVector4(G.R, G.G, G.B, 1.f); }
		if (M.Contains(TEXT("exposure"))) { S.bOverride_AutoExposureBias = true; S.AutoExposureBias = Num(M, TEXT("exposure"), 0.f); }
		if (M.Contains(TEXT("bloom"))) { S.bOverride_BloomIntensity = true; S.BloomIntensity = Num(M, TEXT("bloom"), 0.675f); }
		if (M.Contains(TEXT("vignette"))) { S.bOverride_VignetteIntensity = true; S.VignetteIntensity = Num(M, TEXT("vignette"), 0.4f); }
		Keep.Add(V);
		UE_LOG(LogTemp, Display, TEXT("BFPOSTER grade added"));
	}
	else if (Kind == TEXT("fog"))
	{
		// The level's height fog: color=r,g,b (inscattering) dircolor=r,g,b (toward the sun) density=
		for (TActorIterator<AExponentialHeightFog> It(W); It; ++It)
		{
			UExponentialHeightFogComponent* F = It->GetComponent();
			if (M.Contains(TEXT("color"))) { F->SetFogInscatteringColor(Col(M, TEXT("color"), FLinearColor::White)); }
			if (M.Contains(TEXT("dircolor"))) { F->SetDirectionalInscatteringColor(Col(M, TEXT("dircolor"), FLinearColor::White)); }
			if (M.Contains(TEXT("density"))) { F->SetFogDensity(Num(M, TEXT("density"), 0.02f)); }
			UE_LOG(LogTemp, Display, TEXT("BFPOSTER fog %s"), *It->GetName());
		}
	}
	else if (Kind == TEXT("call"))
	{
		// Calls a parameterless function (e.g. a blueprint's RefreshMaterial) on actors whose name or label contains match.
		const FString Match = M.FindRef(TEXT("match"));
		const FName Fn(*M.FindRef(TEXT("fn")));
		for (TActorIterator<AActor> It(W); It; ++It)
		{
			if (!Match.IsEmpty() && (It->GetName().Contains(Match) || It->GetActorNameOrLabel().Contains(Match)))
			{
				UFunction* F = It->FindFunction(Fn);
				if (F && F->ParmsSize == 0)
				{
					It->ProcessEvent(F, nullptr);
				}
				UE_LOG(LogTemp, Display, TEXT("BFPOSTER call %s.%s %s"), *It->GetName(), *Fn.ToString(), F ? (F->ParmsSize == 0 ? TEXT("ok") : TEXT("needs params")) : TEXT("missing"));
			}
		}
	}
	else if (Kind == TEXT("hide"))
	{
		const FString Match = M.FindRef(TEXT("match"));
		int32 N = 0;
		for (TActorIterator<AActor> It(W); It; ++It)
		{
			if (!Match.IsEmpty() && (It->GetName().Contains(Match) || It->GetActorNameOrLabel().Contains(Match)))
			{
				It->SetActorHiddenInGame(true);
				++N;
			}
		}
		UE_LOG(LogTemp, Display, TEXT("BFPOSTER hide '%s' -> %d actors"), *Match, N);
	}
	else
	{
		UE_LOG(LogTemp, Warning, TEXT("BFPOSTER unknown line: %s"), *Line);
	}
}

void ABFPosterDirector::HoldPoses()
{
	if (bHeroPlaced && Player && !Player->GetActorTransform().Equals(HeroXform, 0.1f))
	{
		Player->SetActorTransform(HeroXform, false, nullptr, ETeleportType::TeleportPhysics);
		if (AController* C = Player->GetController())
		{
			C->SetControlRotation(HeroXform.Rotator());
		}
	}
	for (const FPosed& P : Posed)
	{
		if (USkeletalMeshComponent* Mesh = P.Mesh.Get())
		{
			if (Mesh->GetSingleNodeInstance() && Mesh->GetAnimationMode() == EAnimationMode::AnimationSingleNode)
			{
				Mesh->SetPosition(P.Time, false);
				Mesh->SetPlayRate(0.f);
			}
			else if (P.Anim.IsValid())
			{
				// Something switched it back to its blueprint: put the frozen clip back.
				Mesh->SetAnimationMode(EAnimationMode::AnimationSingleNode);
				Mesh->PlayAnimation(P.Anim.Get(), false);
				Mesh->SetPosition(P.Time, false);
				Mesh->SetPlayRate(0.f);
			}
		}
	}
}

USkeletalMeshComponent* ABFPosterDirector::HeroBody() const
{
	// The player's visible anime body (its AnimeBody component; GetVisibleBody is not public).
	if (!Player)
	{
		return nullptr;
	}
	TArray<USkeletalMeshComponent*> Skels;
	Player->GetComponents<USkeletalMeshComponent>(Skels);
	for (USkeletalMeshComponent* S : Skels)
	{
		if (S->GetFName() == TEXT("AnimeBody") && S->GetSkeletalMeshAsset())
		{
			return S;
		}
	}
	return nullptr;
}

void ABFPosterDirector::TickHeadLook()
{
	USkeletalMeshComponent* Body = HeroBody();
	if (!HeroPose || !Body)
	{
		return;
	}
	HeroPose->CopyPoseFromSkeletalComponent(Body);
	// Chin up: turn the neck (40%) then the head (60%) about her right axis, in world space.
	const FVector Right = Player->GetActorRightVector();
	static const TPair<FName, float> Bones[] = {{TEXT("J_Bip_C_Neck"), 0.4f}, {TEXT("J_Bip_C_Head"), 0.6f}};
	for (const TPair<FName, float>& B : Bones)
	{
		if (HeroPose->GetBoneIndex(B.Key) == INDEX_NONE)
		{
			continue;
		}
		const FQuat Cur = HeroPose->GetBoneRotationByName(B.Key, EBoneSpaces::WorldSpace).Quaternion();
		const FQuat Turn(Right, FMath::DegreesToRadians(-HeadLook * B.Value));
		HeroPose->SetBoneRotationByName(B.Key, (Turn * Cur).Rotator(), EBoneSpaces::WorldSpace);
	}
}

void ABFPosterDirector::Tick(float Dt)
{
	Super::Tick(Dt);
	HoldPoses();
	TickHeadLook();
	Elapsed += Dt;
	APlayerController* PC = Player ? Cast<APlayerController>(Player->GetController()) : nullptr;
	if (PC && Cam && PC->GetViewTarget() != Cam)
	{
		PC->SetViewTarget(Cam);
	}
	if (!bStarted)
	{
		bool bBusy = false;
#if WITH_EDITOR
		bBusy = (GShaderCompilingManager && GShaderCompilingManager->GetNumRemainingJobs() > 0) || FAssetCompilingManager::Get().GetNumRemainingAssets() > 0;
#endif
		Wait = bBusy ? 0.f : Wait + Dt;
		if (Wait >= Warm || Elapsed > 150.f)
		{
			bStarted = true;
			NextShotAt = Elapsed;
			UE_LOG(LogTemp, Display, TEXT("BFPOSTER start after %.1f s"), Elapsed);
		}
		return;
	}
	if (NextShot < Shots.Num())
	{
		const FShot& S = Shots[NextShot];
		if (Elapsed >= NextShotAt && Cam)
		{
			Cam->SetActorLocationAndRotation(S.Loc, S.Rot);
			Cam->GetCameraComponent()->SetFieldOfView(S.Fov);
		}
		for (FLeadFx& L : LeadFx)
		{
			UNiagaraComponent* N = L.Fx.Get();
			if (N && L.FiredFor != NextShot && Elapsed >= NextShotAt + 1.f - L.Lead)
			{
				L.FiredFor = NextShot;
				N->Activate(true);
			}
		}
		const float CaptureAt = NextShotAt + 1.f;
		for (FTrail& T : Trails)
		{
			UNiagaraComponent* N = T.Fx.Get();
			if (!N)
			{
				continue;
			}
			if (T.FiredFor != NextShot && Elapsed >= CaptureAt - T.Lead)
			{
				T.FiredFor = NextShot;
				T.Start = Elapsed;
				N->DeactivateImmediate();
				N->SetWorldLocation(T.From);
				N->Activate(true);
			}
			else if (T.FiredFor == NextShot && Elapsed <= CaptureAt + 0.1f)
			{
				const float A = FMath::Clamp((Elapsed - T.Start) / FMath::Max(T.Lead, 0.01f), 0.f, 1.f);
				N->SetWorldLocation(FMath::Lerp(T.From, T.To, FMath::InterpEaseOut(0.f, 1.f, A, 2.f)));
			}
		}
		// Give temporal AA a second on the new view before capturing.
		if (Elapsed >= NextShotAt + 1.f && PC)
		{
			PC->ConsoleCommand(FString::Printf(TEXT("HighResShot %dx%d filename=Poster_%s"), ResX, ResY, *S.Name));
			UE_LOG(LogTemp, Display, TEXT("BFPOSTER shot %s loc=%s rot=%s fov=%.1f"), *S.Name, *S.Loc.ToCompactString(), *S.Rot.ToCompactString(), S.Fov);
			if (Player)
			{
				UE_LOG(LogTemp, Display, TEXT("BFPOSTER hero actor=%s rot=%s mesh=%s meshrot=%s"), *Player->GetActorLocation().ToCompactString(),
					*Player->GetActorRotation().ToCompactString(), *Player->GetMesh()->GetComponentLocation().ToCompactString(),
					*Player->GetMesh()->GetComponentRotation().ToCompactString());
			}
			for (const TObjectPtr<UObject>& K : Keep)
			{
				if (const AActor* A = Cast<AActor>(K.Get()))
				{
					FVector O, E;
					A->GetActorBounds(false, O, E, true);
					UE_LOG(LogTemp, Display, TEXT("BFPOSTER kept %s at %s bounds %s ext %s"), *A->GetName(), *A->GetActorLocation().ToCompactString(), *O.ToCompactString(), *E.ToCompactString());
				}
			}
			++NextShot;
			NextShotAt = Elapsed + ShotGap;
		}
		return;
	}
	if (Elapsed >= NextShotAt + 2.f)
	{
		UE_LOG(LogTemp, Display, TEXT("BFPOSTER done"));
		FPlatformMisc::RequestExit(false);
		SetActorTickEnabled(false);
	}
}
