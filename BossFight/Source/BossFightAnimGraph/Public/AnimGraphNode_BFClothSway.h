// Editor wrapper for FAnimNode_BFClothSway (procedural robe sway).
#pragma once

#include "AnimGraphNode_SkeletalControlBase.h"
#include "BFClothSwayNode.h"
#include "AnimGraphNode_BFClothSway.generated.h"

UCLASS()
class BOSSFIGHTANIMGRAPH_API UAnimGraphNode_BFClothSway : public UAnimGraphNode_SkeletalControlBase
{
	GENERATED_BODY()

public:
	UPROPERTY(EditAnywhere, Category = Settings)
	FAnimNode_BFClothSway Node;

	virtual FText GetNodeTitle(ENodeTitleType::Type TitleType) const override { return FText::FromString(TEXT("BF Cloth Sway")); }

protected:
	virtual FText GetControllerDescription() const override { return FText::FromString(TEXT("BF Cloth Sway")); }
	virtual const FAnimNode_SkeletalControlBase* GetNode() const override { return &Node; }
};
