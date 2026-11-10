#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "BFEditorTools.generated.h"

/**
 * Editor-only builders called from Python (unreal.BFEditorTools.*).
 * They generate assets that Python cannot author, such as Anim Blueprint graphs.
 * Each builder overwrites its output, so it is safe to run again.
 */
UCLASS()
class BOSSFIGHTEDITOR_API UBFEditorTools : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/**
	 * Builds /Game/BossFight/Anim/BS_PlayerLoco (Direction x Speed) and
	 * /Game/BossFight/Anim/ABP_Player (parent UBFAnimInstance).
	 * Graph: BlendSpace or air loop (by bIsInAir) -> Slot DefaultSlot -> Output.
	 * Returns a log of what was built, or an error message.
	 */
	UFUNCTION(BlueprintCallable, Category = "BossFight|Editor")
	static FString BuildPlayerAnimBlueprint();

	/** Sevarog boss locomotion + DefaultSlot Anim Blueprint (ABP_Sevarog). */
	UFUNCTION(BlueprintCallable, Category = "BossFight|Editor")
	static FString BuildSevarogAnimBlueprint();

	/** Lists a Niagara system's user parameters (name and type), one per line, for tuning VFX from code. */
	UFUNCTION(BlueprintCallable, Category = "BossFight|Editor")
	static FString DumpNiagaraUserParams(const FString& SystemPath);

	/**
	 * Spawns an actor in the editor world holding one hierarchical instanced mesh with the given instances
	 * (grass, flowers, scattered rocks). Cull distances in cm (0 = never culled); collision off unless asked.
	 */
	UFUNCTION(BlueprintCallable, Category = "BossFight|Editor")
	static AActor* SpawnInstancedMeshActor(const FString& Label, UStaticMesh* Mesh, const TArray<FTransform>& Instances,
		bool bCollision = false, float CullStart = 0.f, float CullEnd = 0.f, bool bCastShadow = true);

	/** Lists an object's properties as "Name = Value", one per line; with bOnlyChanged only those differing from its archetype. */
	UFUNCTION(BlueprintCallable, Category = "BossFight|Editor")
	static FString DumpProperties(UObject* Object, bool bOnlyChanged = true);

	/** Copies actors to editor clipboard text (T3D, as Ctrl+C does), so they can be pasted into another level. */
	UFUNCTION(BlueprintCallable, Category = "BossFight|Editor")
	static FString CopyActorsToText(const TArray<AActor*>& Actors);

	/** Pastes T3D text from CopyActorsToText into the current editor level (as Ctrl+V does) and returns the new actors. */
	UFUNCTION(BlueprintCallable, Category = "BossFight|Editor")
	static TArray<AActor*> PasteActorsFromText(const FString& Text);

	/**
	 * Sets one property from its text form (as in Copy/Paste of a details row), with the usual edit notifications.
	 * Works for Blueprint enums ("NewEnumerator5") and for variables not editable on instances. False when not found.
	 */
	UFUNCTION(BlueprintCallable, Category = "BossFight|Editor")
	static bool SetPropertyText(UObject* Object, const FString& PropertyName, const FString& Value);
};
