#include "BFEditorTools.h"

#include "Engine/Selection.h"

#include "AnimGraphNode_BFClothSway.h"
#include "Kismet2/CompilerResultsLog.h"
#include "AnimGraphNode_BlendListByBool.h"
#include "AnimGraphNode_Inertialization.h"
#include "AnimGraphNode_BlendSpacePlayer.h"
#include "AnimGraphNode_ComponentToLocalSpace.h"
#include "AnimGraphNode_LocalToComponentSpace.h"
#include "AnimGraphNode_ModifyBone.h"
#include "AnimGraphNode_Root.h"
#include "AnimGraphNode_RotationOffsetBlendSpace.h"
#include "Animation/AimOffsetBlendSpace.h"
#include "AnimGraphNode_SequencePlayer.h"
#include "AnimGraphNode_Slot.h"
#include "AnimationGraph.h"
#include "Animation/AnimBlueprint.h"
#include "Animation/AnimSequence.h"
#include "Animation/BlendSpace.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "BFAnimInstance.h"
#include "EdGraph/EdGraphPin.h"
#include "EdGraphSchema_K2.h"
#include "EditorAssetLibrary.h"
#include "Factories/AnimBlueprintFactory.h"
#include "Factories/BlendSpaceFactoryNew.h"
#include "K2Node_VariableGet.h"
#include "NiagaraSystem.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "UObject/SavePackage.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Editor.h"
#include "Engine/StaticMesh.h"

namespace
{
	const TCHAR* AnimFolder = TEXT("/Game/BossFight/Anim");
	const TCHAR* SkeletonPath = TEXT("/Game/InsaneAirCombo/Animation/Skeleton/UE4_Mannequin_Skeleton.UE4_Mannequin_Skeleton");
	const TCHAR* PreviewMeshPath = TEXT("/Game/InsaneAirCombo/Animation/Skeleton/SK_Mannequin.SK_Mannequin");
	const TCHAR* AnimRoot = TEXT("/Game/InsaneAirCombo/Animation/");

	UAnimSequence* LoadAnim(const FString& Name)
	{
		const FString Path = FString(AnimRoot) + Name + TEXT(".") + Name;
		return LoadObject<UAnimSequence>(nullptr, *Path);
	}

	/** Deletes an asset if it exists so the builder can recreate it from scratch. */
	void DeleteIfExists(const FString& PackagePath)
	{
		if (UEditorAssetLibrary::DoesAssetExist(PackagePath))
		{
			// Load it fully first: if nothing loaded it at startup, the delete leaves a partially loaded
			// package behind and the recreated asset then refuses to save.
			UEditorAssetLibrary::LoadAsset(PackagePath);
			FlushAsyncLoading();
			UEditorAssetLibrary::DeleteAsset(PackagePath);
			CollectGarbage(GARBAGE_COLLECTION_KEEPFLAGS);
		}
	}

	bool SavePackageOf(UObject* Asset)
	{
		UPackage* Package = Asset->GetPackage();
		Package->MarkPackageDirty();
		const FString FileName = FPackageName::LongPackageNameToFilename(Package->GetName(), FPackageName::GetAssetPackageExtension());
		FSavePackageArgs Args;
		Args.TopLevelFlags = RF_Public | RF_Standalone;
		return UPackage::SavePackage(Package, Asset, *FileName, Args);
	}

	/** Sets one blend space axis through reflection, since BlendParameters is protected. */
	void SetAxis(UBlendSpace* BlendSpace, int32 Index, const FString& Name, float Min, float Max, int32 Grid, bool bWrap)
	{
		FStructProperty* Prop = FindFProperty<FStructProperty>(UBlendSpace::StaticClass(), TEXT("BlendParameters"));
		check(Prop);
		FBlendParameter* Param = Prop->ContainerPtrToValuePtr<FBlendParameter>(BlendSpace, Index);
		Param->DisplayName = Name;
		Param->Min = Min;
		Param->Max = Max;
		Param->GridNum = Grid;
		Param->bWrapInput = bWrap;
	}

	/** Pose pins are struct pins of FPoseLink type. Picks the first pose pin in a direction. */
	UEdGraphPin* FindPosePin(UEdGraphNode* Node, EEdGraphPinDirection Dir, const FString& PreferredName = FString())
	{
		UEdGraphPin* Fallback = nullptr;
		for (UEdGraphPin* Pin : Node->Pins)
		{
			if (Pin->Direction != Dir || Pin->PinType.PinCategory != UEdGraphSchema_K2::PC_Struct)
			{
				continue;
			}
			const UScriptStruct* Struct = Cast<UScriptStruct>(Pin->PinType.PinSubCategoryObject.Get());
			if (!Struct || !Struct->GetName().Contains(TEXT("PoseLink")))
			{
				continue;
			}
			if (PreferredName.IsEmpty() || Pin->PinName.ToString() == PreferredName)
			{
				return Pin;
			}
			if (!Fallback)
			{
				Fallback = Pin;
			}
		}
		return PreferredName.IsEmpty() ? Fallback : nullptr;
	}

	FString DescribePins(UEdGraphNode* Node)
	{
		TArray<FString> Names;
		for (const UEdGraphPin* Pin : Node->Pins)
		{
			Names.Add(FString::Printf(TEXT("%s(%s)"), *Pin->PinName.ToString(), Pin->Direction == EGPD_Input ? TEXT("in") : TEXT("out")));
		}
		return FString::Join(Names, TEXT(", "));
	}

	template <typename TNode>
	TNode* SpawnNode(UEdGraph* Graph, const FVector2D& Pos)
	{
		FGraphNodeCreator<TNode> Creator(*Graph);
		TNode* Node = Creator.CreateNode();
		Node->NodePosX = static_cast<int32>(Pos.X);
		Node->NodePosY = static_cast<int32>(Pos.Y);
		Creator.Finalize();
		return Node;
	}

	/** Creates a getter for a native property on the Anim Blueprint's parent class. */
	UK2Node_VariableGet* SpawnGetter(UEdGraph* Graph, FName Property, const FVector2D& Pos)
	{
		FGraphNodeCreator<UK2Node_VariableGet> Creator(*Graph);
		UK2Node_VariableGet* Node = Creator.CreateNode();
		Node->VariableReference.SetSelfMember(Property);
		Node->NodePosX = static_cast<int32>(Pos.X);
		Node->NodePosY = static_cast<int32>(Pos.Y);
		Creator.Finalize();
		return Node;
	}

	bool Link(UEdGraphPin* From, UEdGraphPin* To, TArray<FString>& Log, const TCHAR* What)
	{
		if (!From || !To)
		{
			Log.Add(FString::Printf(TEXT("ERROR missing pin for %s"), What));
			return false;
		}
		From->MakeLinkTo(To);
		return true;
	}
}

namespace
{
	/** Dir: a direction column (-180..180, +-180 fill both ends), AllColumns for every 45-degree column,
	 * or ForwardColumns (default) for the old forward-only layout {-180, 0, 180}. */
	constexpr float AllColumns = -1000.f;
	constexpr float ForwardColumns = 999.f;
	struct FLocoSample { FString AnimPath; float Speed; float Dir = ForwardColumns; float RateScale = 1.f; };

	/** Builds BS_<Name>Loco (Direction x Speed, forward clip in every column) and ABP_<Name>
	 * (blend space or air pose, then DefaultSlot) on a UBFAnimInstance parent. */
	FString BuildLocoAnimBlueprint(const TCHAR* InSkeletonPath, const TCHAR* InPreviewMeshPath, const FString& BSName, const FString& ABPName,
		const TArray<FLocoSample>& Samples, const FString& AirAnimPath, float MaxSpeed, FName FlinchBone, FName HeadBone = NAME_None,
		const FString& AimOffsetPath = FString(), const TArray<TPair<FName, FName>>& ClothChains = {},
		const TArray<FBFClothCollider>& ClothColliders = {})
	{
	TArray<FString> Log;

	USkeleton* Skeleton = LoadObject<USkeleton>(nullptr, InSkeletonPath);
	USkeletalMesh* PreviewMesh = LoadObject<USkeletalMesh>(nullptr, InPreviewMeshPath);
	if (!Skeleton)
	{
		return TEXT("ERROR skeleton not found");
	}

	// Locomotion blend space. X = direction (-180..180), Y = speed (0..700).
	const FString BSPath = FString(AnimFolder) / BSName;
	const FString ABPPath = FString(AnimFolder) / ABPName;
	DeleteIfExists(ABPPath);
	DeleteIfExists(BSPath);

	UBlendSpaceFactoryNew* BSFactory = NewObject<UBlendSpaceFactoryNew>();
	BSFactory->TargetSkeleton = Skeleton;
	UPackage* BSPackage = CreatePackage(*BSPath);
	UBlendSpace* BlendSpace = Cast<UBlendSpace>(BSFactory->FactoryCreateNew(UBlendSpace::StaticClass(), BSPackage, *BSName, RF_Public | RF_Standalone, nullptr, GWarn));
	if (!BlendSpace)
	{
		return TEXT("ERROR blend space creation failed");
	}
	SetAxis(BlendSpace, 0, TEXT("Direction"), -180.f, 180.f, 8, true);
	SetAxis(BlendSpace, 1, TEXT("Speed"), 0.f, MaxSpeed, 6, false);

	// Free locomotion keeps Direction at 0 (the body turns toward movement), so column 0 holds the
	// forward clips. Strafing (lock-on, boss circling) feeds Direction, which pulls in the directional
	// clips placed in the other columns. Speeds are each clip's native root speed
	// (Scripts/13_loco_analyze.py), so the feet do not slide.
	int32 Added = 0;
	for (const FLocoSample& S : Samples)
	{
		TArray<float> Columns;
		if (S.Dir == ForwardColumns)
		{
			Columns = { -180.f, 0.f, 180.f };
		}
		else if (S.Dir == AllColumns)
		{
			for (int32 i = -4; i <= 4; ++i)
			{
				Columns.Add(i * 45.f);
			}
		}
		else if (FMath::Abs(S.Dir) >= 179.f)
		{
			Columns = { -180.f, 180.f };
		}
		else
		{
			Columns = { S.Dir };
		}
		if (UAnimSequence* Seq = LoadObject<UAnimSequence>(nullptr, *S.AnimPath))
		{
			for (const float Dir : Columns)
			{
				const int32 Index = BlendSpace->AddSample(Seq, FVector(Dir, S.Speed, 0.f));
				++Added;
				if (S.RateScale != 1.f && Index != INDEX_NONE)
				{
					// SampleData is protected; set the sample's play rate through reflection.
					if (FArrayProperty* Prop = FindFProperty<FArrayProperty>(UBlendSpace::StaticClass(), TEXT("SampleData")))
					{
						FScriptArrayHelper Helper(Prop, Prop->ContainerPtrToValuePtr<void>(BlendSpace));
						if (Helper.IsValidIndex(Index))
						{
							reinterpret_cast<FBlendSample*>(Helper.GetRawPtr(Index))->RateScale = S.RateScale;
						}
					}
				}
			}
		}
		else
		{
			Log.Add(FString::Printf(TEXT("WARN missing anim %s"), *S.AnimPath));
		}
	}
	BlendSpace->ResampleData();
	FAssetRegistryModule::AssetCreated(BlendSpace);
	SavePackageOf(BlendSpace);
	Log.Add(FString::Printf(TEXT("BlendSpace %s with %d samples"), *BSPath, Added));

	// Anim Blueprint with native parent so the graph reads Speed / Direction / bIsInAir.
	UAnimBlueprintFactory* ABPFactory = NewObject<UAnimBlueprintFactory>();
	ABPFactory->ParentClass = UBFAnimInstance::StaticClass();
	ABPFactory->TargetSkeleton = Skeleton;
	ABPFactory->PreviewSkeletalMesh = PreviewMesh;
	UPackage* ABPPackage = CreatePackage(*ABPPath);
	UAnimBlueprint* AnimBP = Cast<UAnimBlueprint>(ABPFactory->FactoryCreateNew(UAnimBlueprint::StaticClass(), ABPPackage, *ABPName, RF_Public | RF_Standalone, nullptr, GWarn));
	if (!AnimBP)
	{
		return TEXT("ERROR anim blueprint creation failed");
	}

	UAnimationGraph* Graph = nullptr;
	for (UEdGraph* G : AnimBP->FunctionGraphs)
	{
		if (UAnimationGraph* AG = Cast<UAnimationGraph>(G))
		{
			Graph = AG;
			break;
		}
	}
	if (!Graph)
	{
		return TEXT("ERROR AnimGraph not found");
	}

	UAnimGraphNode_Root* Root = nullptr;
	for (UEdGraphNode* N : Graph->Nodes)
	{
		if (UAnimGraphNode_Root* R = Cast<UAnimGraphNode_Root>(N))
		{
			Root = R;
		}
	}

	UAnimGraphNode_BlendSpacePlayer* BSNode = SpawnNode<UAnimGraphNode_BlendSpacePlayer>(Graph, FVector2D(-900, 0));
	BSNode->SetAnimationAsset(BlendSpace);
	BSNode->ReconstructNode();

	UAnimGraphNode_SequencePlayer* AirNode = SpawnNode<UAnimGraphNode_SequencePlayer>(Graph, FVector2D(-900, 300));
	AirNode->SetAnimationAsset(LoadObject<UAnimSequence>(nullptr, *AirAnimPath));
	AirNode->ReconstructNode();

	UAnimGraphNode_BlendListByBool* AirSwitch = SpawnNode<UAnimGraphNode_BlendListByBool>(Graph, FVector2D(-500, 100));
	AirSwitch->ReconstructNode();

	UAnimGraphNode_Slot* SlotNode = SpawnNode<UAnimGraphNode_Slot>(Graph, FVector2D(-250, 100));
	SlotNode->Node.SlotName = FName(TEXT("DefaultSlot"));
	SlotNode->ReconstructNode();

	UK2Node_VariableGet* GetDir = SpawnGetter(Graph, GET_MEMBER_NAME_CHECKED(UBFAnimInstance, Direction), FVector2D(-1200, 0));
	UK2Node_VariableGet* GetSpeed = SpawnGetter(Graph, GET_MEMBER_NAME_CHECKED(UBFAnimInstance, Speed), FVector2D(-1200, 80));
	UK2Node_VariableGet* GetAir = SpawnGetter(Graph, GET_MEMBER_NAME_CHECKED(UBFAnimInstance, bIsInAir), FVector2D(-800, 180));

	Log.Add(TEXT("pins BS: ") + DescribePins(BSNode));
	Log.Add(TEXT("pins Switch: ") + DescribePins(AirSwitch));
	Log.Add(TEXT("pins Slot: ") + DescribePins(SlotNode));

	bool bOk = true;
	bOk &= Link(GetDir->GetValuePin(), BSNode->FindPin(TEXT("X")), Log, TEXT("Direction->X"));
	bOk &= Link(GetSpeed->GetValuePin(), BSNode->FindPin(TEXT("Y")), Log, TEXT("Speed->Y"));
	bOk &= Link(GetAir->GetValuePin(), AirSwitch->FindPin(TEXT("bActiveValue")), Log, TEXT("bIsInAir->bActiveValue"));
	// BlendListByBool: pose 0 is used when the value is true, pose 1 when false.
	bOk &= Link(FindPosePin(AirNode, EGPD_Output), FindPosePin(AirSwitch, EGPD_Input, TEXT("BlendPose_0")), Log, TEXT("Air->True"));
	bOk &= Link(FindPosePin(BSNode, EGPD_Output), FindPosePin(AirSwitch, EGPD_Input, TEXT("BlendPose_1")), Log, TEXT("BS->False"));
	UEdGraphPin* LocoOut = FindPosePin(AirSwitch, EGPD_Output);
	if (!AimOffsetPath.IsEmpty())
	{
		// Look-at aim offset on the locomotion pose only (under the slot): UBFAnimInstance::AimYaw/AimPitch/AimAlpha.
		if (UAimOffsetBlendSpace* AO = LoadObject<UAimOffsetBlendSpace>(nullptr, *AimOffsetPath))
		{
			UAnimGraphNode_RotationOffsetBlendSpace* AONode = SpawnNode<UAnimGraphNode_RotationOffsetBlendSpace>(Graph, FVector2D(-380, 250));
			AONode->SetAnimationAsset(AO);
			AONode->ReconstructNode();
			Log.Add(TEXT("pins AO: ") + DescribePins(AONode));
			UK2Node_VariableGet* GetYaw = SpawnGetter(Graph, GET_MEMBER_NAME_CHECKED(UBFAnimInstance, AimYaw), FVector2D(-650, 400));
			UK2Node_VariableGet* GetPitch = SpawnGetter(Graph, GET_MEMBER_NAME_CHECKED(UBFAnimInstance, AimPitch), FVector2D(-650, 480));
			UK2Node_VariableGet* GetAlpha = SpawnGetter(Graph, GET_MEMBER_NAME_CHECKED(UBFAnimInstance, AimAlpha), FVector2D(-650, 560));
			bOk &= Link(LocoOut, FindPosePin(AONode, EGPD_Input), Log, TEXT("Switch->AO"));
			bOk &= Link(GetYaw->GetValuePin(), AONode->FindPin(TEXT("X")), Log, TEXT("AimYaw->X"));
			bOk &= Link(GetPitch->GetValuePin(), AONode->FindPin(TEXT("Y")), Log, TEXT("AimPitch->Y"));
			bOk &= Link(GetAlpha->GetValuePin(), AONode->FindPin(TEXT("Alpha")), Log, TEXT("AimAlpha->Alpha"));
			LocoOut = FindPosePin(AONode, EGPD_Output);
		}
		else
		{
			Log.Add(FString::Printf(TEXT("WARN missing aim offset %s"), *AimOffsetPath));
		}
	}
	bOk &= Link(LocoOut, FindPosePin(SlotNode, EGPD_Input), Log, TEXT("Loco->Slot"));
	// Hit flinch: additive component-space spine rotation driven by UBFAnimInstance::FlinchRot,
	// applied after the slot so it layers over attacks and hit reacts too.
	UAnimGraphNode_LocalToComponentSpace* ToCS = SpawnNode<UAnimGraphNode_LocalToComponentSpace>(Graph, FVector2D(-20, 100));
	UAnimGraphNode_ModifyBone* Flinch = SpawnNode<UAnimGraphNode_ModifyBone>(Graph, FVector2D(200, 100));
	Flinch->Node.BoneToModify.BoneName = FlinchBone;
	Flinch->Node.RotationMode = BMM_Additive;
	Flinch->Node.RotationSpace = BCS_ComponentSpace;
	Flinch->Node.TranslationMode = BMM_Ignore;
	Flinch->Node.ScaleMode = BMM_Ignore;
	Flinch->ReconstructNode();
	UAnimGraphNode_ComponentToLocalSpace* ToLocal = SpawnNode<UAnimGraphNode_ComponentToLocalSpace>(Graph, FVector2D(450, 100));
	UK2Node_VariableGet* GetFlinch = SpawnGetter(Graph, GET_MEMBER_NAME_CHECKED(UBFAnimInstance, FlinchRot), FVector2D(0, 300));
	Log.Add(TEXT("pins ModifyBone: ") + DescribePins(Flinch));
	// Inertialization right after the slot: montages blend in / out inertially (BFAnimBlend::Inert).
	UAnimGraphNode_Inertialization* Inert = SpawnNode<UAnimGraphNode_Inertialization>(Graph, FVector2D(-160, 100));
	bOk &= Link(FindPosePin(SlotNode, EGPD_Output), FindPosePin(Inert, EGPD_Input), Log, TEXT("Slot->Inertialization"));
	bOk &= Link(FindPosePin(Inert, EGPD_Output), FindPosePin(ToCS, EGPD_Input), Log, TEXT("Inertialization->ToCS"));
	bOk &= Link(FindPosePin(ToCS, EGPD_Output), FindPosePin(Flinch, EGPD_Input), Log, TEXT("ToCS->Flinch"));
	bOk &= Link(GetFlinch->GetValuePin(), Flinch->FindPin(TEXT("Rotation")), Log, TEXT("FlinchRot->Rotation"));
	UEdGraphPin* LastOut = FindPosePin(Flinch, EGPD_Output);
	if (!HeadBone.IsNone())
	{
		// Constant head lift (UBFAnimInstance::HeadLift), additive in component space after the flinch.
		UAnimGraphNode_ModifyBone* Head = SpawnNode<UAnimGraphNode_ModifyBone>(Graph, FVector2D(330, 250));
		Head->Node.BoneToModify.BoneName = HeadBone;
		Head->Node.RotationMode = BMM_Additive;
		Head->Node.RotationSpace = BCS_ComponentSpace;
		Head->Node.TranslationMode = BMM_Ignore;
		Head->Node.ScaleMode = BMM_Ignore;
		Head->ReconstructNode();
		UK2Node_VariableGet* GetHead = SpawnGetter(Graph, GET_MEMBER_NAME_CHECKED(UBFAnimInstance, HeadLift), FVector2D(130, 450));
		bOk &= Link(LastOut, FindPosePin(Head, EGPD_Input), Log, TEXT("Flinch->Head"));
		bOk &= Link(GetHead->GetValuePin(), Head->FindPin(TEXT("Rotation")), Log, TEXT("HeadLift->Rotation"));
		LastOut = FindPosePin(Head, EGPD_Output);
	}
	// Cloth: verlet particle chain per robe strip with leg/torso colliders (FAnimNode_BFClothSway). After the slot, so idles,
	// attacks and reactions all get secondary motion. (AnimDynamics chains blew up on these bones.)
	if (ClothChains.Num() > 0)
	{
		UAnimGraphNode_BFClothSway* Sway = SpawnNode<UAnimGraphNode_BFClothSway>(Graph, FVector2D(330, 450));
		for (const TPair<FName, FName>& Chain : ClothChains)
		{
			FBFClothChain& C = Sway->Node.Chains.AddDefaulted_GetRef();
			C.StartBone = Chain.Key;
			C.EndBone = Chain.Value;
			// Sleeve strips (*arm_cloth*) ride the weapon arms; loose they lag too far and whirl on every
			// swing, so they get 1.1x stiffness, a 60 deg limit and a bit less lag.
			if (Chain.Key.ToString().Contains(TEXT("arm_cloth")))
			{
				C.StiffnessScale = 1.1f;
				C.MaxAngleDeg = 60.f;
				C.Inertia = 0.65f;
			}
		}
		Sway->Node.Colliders = ClothColliders;
		Sway->ReconstructNode();
		bOk &= Link(LastOut, FindPosePin(Sway, EGPD_Input), Log, TEXT("Pose->ClothSway"));
		LastOut = FindPosePin(Sway, EGPD_Output);
		Log.Add(FString::Printf(TEXT("cloth sway chains=%d"), ClothChains.Num()));
	}
	bOk &= Link(LastOut, FindPosePin(ToLocal, EGPD_Input), Log, TEXT("Pose->ToLocal"));
	bOk &= Link(FindPosePin(ToLocal, EGPD_Output), Root ? FindPosePin(Root, EGPD_Input) : nullptr, Log, TEXT("ToLocal->Root"));

	// Short blend in and out of the air pose. BlendTime is private, so set it through reflection.
	if (FArrayProperty* BlendTimeProp = FindFProperty<FArrayProperty>(FAnimNode_BlendListBase::StaticStruct(), TEXT("BlendTime")))
	{
		TArray<float>* BlendTimes = BlendTimeProp->ContainerPtrToValuePtr<TArray<float>>(&AirSwitch->Node);
		if (BlendTimes->Num() >= 2)
		{
			(*BlendTimes)[0] = 0.15f;
			(*BlendTimes)[1] = 0.2f;
		}
	}

	FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(AnimBP);
	FCompilerResultsLog Results;
	FKismetEditorUtilities::CompileBlueprint(AnimBP, EBlueprintCompileOptions::None, &Results);
	Log.Add(FString::Printf(TEXT("ABP compile status=%d (2 error,3 uptodate,5 uptodate with warnings)"), static_cast<int32>(AnimBP->Status)));
	for (const TSharedRef<FTokenizedMessage>& Msg : Results.Messages)
	{
		Log.Add(FString::Printf(TEXT("compile msg: %s"), *Msg->ToText().ToString()));
	}

	FAssetRegistryModule::AssetCreated(AnimBP);
	SavePackageOf(AnimBP);
	Log.Add(FString::Printf(TEXT("AnimBlueprint %s links_ok=%d"), *ABPPath, bOk ? 1 : 0));

	return FString::Join(Log, TEXT("\n"));
	}
}

FString UBFEditorTools::BuildPlayerAnimBlueprint()
{
	const FString Root = AnimRoot;
	auto P = [&Root](const TCHAR* N) { return Root + N + TEXT(".") + N; };
	return BuildLocoAnimBlueprint(SkeletonPath, PreviewMeshPath, TEXT("BS_PlayerLoco"), TEXT("ABP_Player"),
		{
			{ P(TEXT("Idle")), 0.f, AllColumns },
			{ P(TEXT("strafe_walk_F")), 107.f, 0.f }, { P(TEXT("run")), 488.f, 0.f },
			// Shift sprint (760 cm/s): run_fast's native 527 cm/s, played faster so the feet keep up.
			{ P(TEXT("run_fast")), 760.f, 0.f, 760.f / 527.f },
			// Lock-on strafing (CalculateDirection: positive = right).
			{ P(TEXT("strafe_walk_R45")), 107.f, 45.f }, { P(TEXT("strafe_run_R45")), 427.f, 45.f },
			{ P(TEXT("strafe_walk_R")), 107.f, 90.f }, { P(TEXT("strafe_run_R")), 427.f, 90.f },
			{ P(TEXT("strafe_walk_R135")), 107.f, 135.f }, { P(TEXT("strafe_run_R135")), 427.f, 135.f },
			{ P(TEXT("strafe_walk_B")), 107.f, 180.f }, { P(TEXT("strafe_run_B")), 427.f, 180.f },
			{ P(TEXT("strafe_walk_L45")), 107.f, -45.f }, { P(TEXT("strafe_run_L45")), 427.f, -45.f },
			{ P(TEXT("strafe_walk_L")), 107.f, -90.f }, { P(TEXT("strafe_run_L")), 427.f, -90.f },
			{ P(TEXT("strafe_walk_L135")), 107.f, -135.f }, { P(TEXT("strafe_run_L135")), 427.f, -135.f },
		}, P(TEXT("jump_loop")), 800.f, TEXT("spine_02"));
}

FString UBFEditorTools::BuildSevarogAnimBlueprint()
{
	// Paragon clips are in place (no root motion), so the speeds are estimates matched to the
	// boss's walk speed (260): walk ~150, jog ~400.
	const FString Root = TEXT("/Game/ParagonSevarog/Characters/Heroes/Sevarog/Animations/");
	auto P = [&Root](const TCHAR* N) { return Root + N + TEXT(".") + N; };
	// Idle: Sevarog_IdleLoop = Paragon Idle minus its stray first frame (Scripts/30_sevarog_idle_fix.py).
	return BuildLocoAnimBlueprint(TEXT("/Game/ParagonSevarog/Characters/Heroes/Sevarog/Meshes/Sevarog_Skeleton.Sevarog_Skeleton"),
		TEXT("/Game/ParagonSevarog/Characters/Heroes/Sevarog/Meshes/Sevarog.Sevarog"), TEXT("BS_SevarogLoco"), TEXT("ABP_Sevarog"),
		{
			{ FString(TEXT("/Game/BossFight/Anim/Sevarog_IdleLoop.Sevarog_IdleLoop")), 0.f, AllColumns },
			{ P(TEXT("Walk_Fwd")), 150.f, 0.f }, { P(TEXT("Jog_Fwd")), 400.f, 0.f },
			// Circling / backing off (bStrafing): side steps and backpedal.
			{ P(TEXT("Walk_Right")), 150.f, 90.f }, { P(TEXT("Jog_Right")), 400.f, 90.f },
			{ P(TEXT("Walk_Left")), 150.f, -90.f }, { P(TEXT("Jog_Left")), 400.f, -90.f },
			{ P(TEXT("Walk_Bwd")), 150.f, 180.f }, { P(TEXT("Jog_Bwd")), 400.f, 180.f },
		}, P(TEXT("Jump_Fall_Loop")), 450.f, TEXT("spine_02"), TEXT("neck_01"),
		// Paragon look-at aim offset (yaw -90..90 left/right, pitch -90..90).
		Root + TEXT("AimOffsets/Idle_AO.Idle_AO"),
		// Robe strips (Paragon cloth bones, otherwise only baked into the clips).
		{
			{ TEXT("hip_cloth_bk_l_01"), TEXT("hip_cloth_bk_l_03") }, { TEXT("hip_cloth_bk_r_01"), TEXT("hip_cloth_bk_r_03") },
			{ TEXT("hip_cloth_fr_l_01"), TEXT("hip_cloth_fr_l_03") }, { TEXT("hip_cloth_fr_r_01"), TEXT("hip_cloth_fr_r_03") },
			{ TEXT("pelvis_cloth_bk_01"), TEXT("pelvis_cloth_bk_03") }, { TEXT("pelvis_cloth_fr_01"), TEXT("pelvis_cloth_fr_03") },
			{ TEXT("spine_cloth_bk_l_01"), TEXT("spine_cloth_bk_l_04") }, { TEXT("spine_cloth_bk_r_01"), TEXT("spine_cloth_bk_r_04") },
			{ TEXT("spine_cloth_fr_l_01"), TEXT("spine_cloth_fr_l_04") }, { TEXT("spine_cloth_fr_r_01"), TEXT("spine_cloth_fr_r_04") },
			{ TEXT("spine_cloth_l_01"), TEXT("spine_cloth_l_02") }, { TEXT("spine_cloth_r_01"), TEXT("spine_cloth_r_02") },
			{ TEXT("head_cloth_big_l_01"), TEXT("head_cloth_big_l_03") }, { TEXT("head_cloth_big_r_01"), TEXT("head_cloth_big_r_03") },
			{ TEXT("upperarm_cloth_l_01"), TEXT("upperarm_cloth_l_03") }, { TEXT("upperarm_cloth_r_01"), TEXT("upperarm_cloth_r_03") },
			{ TEXT("lowerarm_cloth_fr_l_01"), TEXT("lowerarm_cloth_fr_l_03") }, { TEXT("lowerarm_cloth_fr_r_01"), TEXT("lowerarm_cloth_fr_r_03") },
		},
		// Legs and torso the robe must not pass through when it lags behind.
		{
			{ TEXT("thigh_l"), TEXT("calf_l"), 14.f }, { TEXT("calf_l"), TEXT("foot_l"), 10.f },
			{ TEXT("thigh_r"), TEXT("calf_r"), 14.f }, { TEXT("calf_r"), TEXT("foot_r"), 10.f },
			{ TEXT("pelvis"), TEXT("spine_02"), 24.f }, { TEXT("spine_02"), TEXT("neck_01"), 26.f },
		});
}

FString UBFEditorTools::DumpNiagaraUserParams(const FString& SystemPath)
{
	UNiagaraSystem* System = LoadObject<UNiagaraSystem>(nullptr, *SystemPath);
	if (!System)
	{
		return FString::Printf(TEXT("ERROR missing %s"), *SystemPath);
	}
	TArray<FNiagaraVariable> Params;
	System->GetExposedParameters().GetUserParameters(Params);
	TArray<FString> Lines;
	for (const FNiagaraVariable& Var : Params)
	{
		FString Value;
		if (Var.GetType() == FNiagaraTypeDefinition::GetFloatDef())
		{
			Value = FString::Printf(TEXT(" = %.3f"), System->GetExposedParameters().GetParameterValue<float>(Var));
		}
		else if (Var.GetType() == FNiagaraTypeDefinition::GetColorDef())
		{
			Value = TEXT(" = ") + System->GetExposedParameters().GetParameterValue<FLinearColor>(Var).ToString();
		}
		else if (Var.GetType() == FNiagaraTypeDefinition::GetVec3Def())
		{
			Value = TEXT(" = ") + FVector(System->GetExposedParameters().GetParameterValue<FVector3f>(Var)).ToString();
		}
		else if (Var.GetType() == FNiagaraTypeDefinition::GetBoolDef())
		{
			Value = System->GetExposedParameters().GetParameterValue<FNiagaraBool>(Var).GetValue() ? TEXT(" = true") : TEXT(" = false");
		}
		Lines.Add(FString::Printf(TEXT("%s : %s%s"), *Var.GetName().ToString(), *Var.GetType().GetName(), *Value));
	}
	if (Lines.Num() == 0)
	{
		Lines.Add(TEXT("(no user parameters)"));
	}
	return FString::Join(Lines, TEXT("\n"));
}

AActor* UBFEditorTools::SpawnInstancedMeshActor(const FString& Label, UStaticMesh* Mesh, const TArray<FTransform>& Instances,
	bool bCollision, float CullStart, float CullEnd, bool bCastShadow)
{
	UWorld* World = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
	if (!World || !Mesh)
	{
		return nullptr;
	}
	FActorSpawnParameters Params;
	Params.ObjectFlags |= RF_Transactional;
	AActor* Actor = World->SpawnActor<AActor>(AActor::StaticClass(), FTransform::Identity, Params);
	if (!Actor)
	{
		return nullptr;
	}
	UHierarchicalInstancedStaticMeshComponent* Comp =
		NewObject<UHierarchicalInstancedStaticMeshComponent>(Actor, TEXT("Instances"), RF_Transactional);
	Comp->SetMobility(EComponentMobility::Static);
	Comp->SetStaticMesh(Mesh);
	Comp->SetCollisionEnabled(bCollision ? ECollisionEnabled::QueryAndPhysics : ECollisionEnabled::NoCollision);
	Comp->SetCastShadow(bCastShadow);
	Comp->SetCullDistances(FMath::RoundToInt(CullStart), FMath::RoundToInt(CullEnd));
	Actor->SetRootComponent(Comp);
	Actor->AddInstanceComponent(Comp);
	Comp->RegisterComponent();
	Comp->AddInstances(Instances, false, true);
	Actor->SetActorLabel(Label);
	return Actor;
}

FString UBFEditorTools::DumpProperties(UObject* Object, bool bOnlyChanged)
{
	if (!Object)
	{
		return TEXT("null object");
	}
	FString Out;
	UObject* Archetype = Object->GetArchetype();
	for (TFieldIterator<FProperty> It(Object->GetClass()); It; ++It)
	{
		FProperty* Prop = *It;
		if (bOnlyChanged && Archetype && Archetype->GetClass()->IsChildOf(Prop->GetOwnerClass()) && Prop->Identical_InContainer(Object, Archetype))
		{
			continue;
		}
		FString Value;
		Prop->ExportTextItem_Direct(Value, Prop->ContainerPtrToValuePtr<void>(Object), nullptr, Object, PPF_None);
		Out += FString::Printf(TEXT("%s [%s] = %s\n"), *Prop->GetName(), *Prop->GetOwnerClass()->GetName(), *Value.Left(600));
	}
	return Out;
}

FString UBFEditorTools::CopyActorsToText(const TArray<AActor*>& Actors)
{
	UWorld* World = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
	if (!World)
	{
		return FString();
	}
	GEditor->SelectNone(false, true, false);
	for (AActor* Actor : Actors)
	{
		if (Actor)
		{
			GEditor->SelectActor(Actor, true, false, true);
		}
	}
	FString Text;
	GEditor->edactCopySelected(World, &Text);
	GEditor->SelectNone(false, true, false);
	return Text;
}

TArray<AActor*> UBFEditorTools::PasteActorsFromText(const FString& Text)
{
	TArray<AActor*> Result;
	UWorld* World = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
	if (!World || Text.IsEmpty())
	{
		return Result;
	}
	GEditor->SelectNone(false, true, false);
	GEditor->edactPasteSelected(World, false, false, false, &Text);
	for (FSelectionIterator It(GEditor->GetSelectedActorIterator()); It; ++It)
	{
		if (AActor* Actor = Cast<AActor>(*It))
		{
			Result.Add(Actor);
		}
	}
	GEditor->SelectNone(false, true, false);
	return Result;
}

bool UBFEditorTools::SetPropertyText(UObject* Object, const FString& PropertyName, const FString& Value)
{
	if (!Object)
	{
		return false;
	}
	FProperty* Prop = FindFProperty<FProperty>(Object->GetClass(), *PropertyName);
	if (!Prop)
	{
		return false;
	}
	Object->PreEditChange(Prop);
	const TCHAR* Result = Prop->ImportText_InContainer(*Value, Object, Object, PPF_None);
	FPropertyChangedEvent Event(Prop, EPropertyChangeType::ValueSet);
	Object->PostEditChangeProperty(Event);
	return Result != nullptr;
}
