#include "BFClothSwayNode.h"
#include "Animation/AnimInstanceProxy.h"
#include "Animation/Skeleton.h"
#include "BonePose.h"
#include "BFEnemyBase.h"

namespace
{
	/** Converts a per-1/60 s factor to a step of H seconds. */
	float StepFactor(float PerStep60, float H)
	{
		return 1.f - FMath::Pow(1.f - FMath::Clamp(PerStep60, 0.f, 1.f), H * 60.f);
	}

	/** Pushes P out of the capsule A-B of radius R. */
	void PushOutOfCapsule(FVector& P, const FVector& A, const FVector& B, float R)
	{
		const FVector Closest = FMath::ClosestPointOnSegment(P, A, B);
		const FVector D = P - Closest;
		const float Dist = D.Size();
		if (Dist < R)
		{
			P = Closest + (Dist > KINDA_SMALL_NUMBER ? D / Dist : FVector::UpVector) * R;
		}
	}
}

void FAnimNode_BFClothSway::Initialize_AnyThread(const FAnimationInitializeContext& Context)
{
	FAnimNode_SkeletalControlBase::Initialize_AnyThread(Context);
	for (FChainState& S : State)
	{
		S.bInit = false;
	}
	PendingDt = 0.f;
}

void FAnimNode_BFClothSway::UpdateInternal(const FAnimationUpdateContext& Context)
{
	FAnimNode_SkeletalControlBase::UpdateInternal(Context);
	PendingDt += Context.GetDeltaTime();
	const USkeletalMeshComponent* Comp = Context.AnimInstanceProxy ? Context.AnimInstanceProxy->GetSkelMeshComponent() : nullptr;
	const ABFEnemyBase* Owner = Comp ? Cast<ABFEnemyBase>(Comp->GetOwner()) : nullptr;
	Loose = Owner ? Owner->GetClothLoose() : 0.f;
	Settle = Owner ? Owner->GetDeathSettle() : 0.f;
	FloorZ = Owner ? Owner->GetFloorZ() : 0.f;
}

void FAnimNode_BFClothSway::ApplyArmDrop(FComponentSpacePoseContext& Output, const FTransform& CompT) const
{
	TArray<FBoneTransform, TInlineAllocator<2>> Drop;
	const FQuat CompQ = CompT.GetRotation();
	for (const FArmDropState& A : ArmState)
	{
		const FTransform U = Output.Pose.GetComponentSpaceTransform(A.Upper);
		const FVector Shoulder = CompT.TransformPosition(U.GetLocation());
		const FVector Hand = CompT.TransformPosition(Output.Pose.GetComponentSpaceTransform(A.Hand).GetLocation());
		const FVector Chest = CompT.TransformPosition(Output.Pose.GetComponentSpaceTransform(A.Chest).GetLocation());
		const FVector Arm = Hand - Shoulder;
		const float L = Arm.Size();
		if (L < 1.f || Hand.Z - FloorZ < 25.f)
		{
			continue; // already down
		}
		// Swing out the way the arm already leans; a straight-up arm goes out to its side of the chest.
		FVector Out(Arm.X, Arm.Y, 0.f);
		if (Out.Size() < 0.35f * L)
		{
			Out = FVector(Shoulder.X - Chest.X, Shoulder.Y - Chest.Y, 0.f);
		}
		Out = Out.GetSafeNormal();
		if (Out.IsNearlyZero())
		{
			continue;
		}
		const float Down = FMath::Clamp(Shoulder.Z - (FloorZ + 12.f), -0.95f * L, 0.95f * L);
		const FVector Want = (Out * FMath::Sqrt(L * L - Down * Down) - FVector::UpVector * Down).GetSafeNormal();
		const FQuat World = FQuat::FindBetweenNormals(Arm / L, Want);
		const FQuat Q = FQuat::Slerp(FQuat::Identity, CompQ.Inverse() * World * CompQ, Settle);
		FTransform NewU = U;
		NewU.SetRotation((Q * U.GetRotation()).GetNormalized());
		Drop.Add(FBoneTransform(A.Upper, NewU));
	}
	if (Drop.Num() > 0)
	{
		Drop.Sort(FCompareBoneTransformIndex());
		Output.Pose.SafeSetCSBoneTransforms(Drop);
	}
}

bool FAnimNode_BFClothSway::IsValidToEvaluate(const USkeleton* Skeleton, const FBoneContainer& RequiredBones)
{
	for (const FChainState& S : State)
	{
		if (S.Bones.Num() >= 2)
		{
			return true;
		}
	}
	// Editor compile validation runs before InitializeBoneReferences: check the names instead.
	if (State.Num() == 0 && Skeleton)
	{
		const FReferenceSkeleton& Ref = Skeleton->GetReferenceSkeleton();
		for (const FBFClothChain& C : Chains)
		{
			if (Ref.FindBoneIndex(C.StartBone) != INDEX_NONE && Ref.FindBoneIndex(C.EndBone) != INDEX_NONE)
			{
				return true;
			}
		}
	}
	return false;
}

void FAnimNode_BFClothSway::InitializeBoneReferences(const FBoneContainer& RequiredBones)
{
	const FReferenceSkeleton& Ref = RequiredBones.GetReferenceSkeleton();
	auto ToCompact = [&](FName Name)
	{
		const int32 M = Name.IsNone() ? INDEX_NONE : Ref.FindBoneIndex(Name);
		return M == INDEX_NONE ? FCompactPoseBoneIndex(INDEX_NONE) : RequiredBones.MakeCompactPoseIndex(FMeshPoseBoneIndex(M));
	};

	State.SetNum(Chains.Num());
	for (int32 C = 0; C < Chains.Num(); ++C)
	{
		FChainState& S = State[C];
		S.Bones.Reset();
		S.bInit = false;
		S.Phase = C * 1.7f;
		const int32 Start = Ref.FindBoneIndex(Chains[C].StartBone);
		int32 B = Ref.FindBoneIndex(Chains[C].EndBone);
		TArray<int32> MeshBones;
		while (B != INDEX_NONE)
		{
			MeshBones.Insert(B, 0);
			if (B == Start)
			{
				break;
			}
			B = Ref.GetParentIndex(B);
		}
		if (Start == INDEX_NONE || MeshBones.Num() < 2 || MeshBones[0] != Start)
		{
			continue;
		}
		for (int32 M : MeshBones)
		{
			const FCompactPoseBoneIndex CI = RequiredBones.MakeCompactPoseIndex(FMeshPoseBoneIndex(M));
			if (!CI.IsValid())
			{
				break; // LOD dropped the rest of the strip
			}
			S.Bones.Add(CI);
		}
		if (S.Bones.Num() < 2)
		{
			S.Bones.Reset();
		}
	}

	ArmState.Reset();
	for (int32 I = 0; I < FMath::Min(DropArms.Num(), DropHands.Num()); ++I)
	{
		FArmDropState A;
		A.Upper = ToCompact(DropArms[I]);
		A.Hand = ToCompact(DropHands[I]);
		if (!A.Upper.IsValid() || !A.Hand.IsValid())
		{
			continue;
		}
		const FCompactPoseBoneIndex Clav = RequiredBones.GetParentBoneIndex(A.Upper);
		A.Chest = Clav.IsValid() ? RequiredBones.GetParentBoneIndex(Clav) : FCompactPoseBoneIndex(INDEX_NONE);
		if (A.Chest.IsValid())
		{
			ArmState.Add(A);
		}
	}

	// Reference pose in component space (mesh bone indices), for collider offsets and rest gaps.
	const TArray<FTransform>& RefLocal = Ref.GetRefBonePose();
	TArray<FTransform> RefCS;
	RefCS.SetNum(RefLocal.Num());
	for (int32 M = 0; M < RefLocal.Num(); ++M)
	{
		const int32 P = Ref.GetParentIndex(M);
		RefCS[M] = P == INDEX_NONE ? RefLocal[M] : RefLocal[M] * RefCS[P];
	}

	ColliderState.Reset();
	TArray<FVector> RefCapA, RefCapB;
	for (const FBFClothCollider& Col : Colliders)
	{
		FColliderState CS;
		CS.A = ToCompact(Col.Bone);
		CS.B = Col.EndBone.IsNone() ? CS.A : ToCompact(Col.EndBone);
		CS.Radius = Col.Radius;
		const int32 MA = Ref.FindBoneIndex(Col.Bone);
		const int32 MB = Col.EndBone.IsNone() ? MA : Ref.FindBoneIndex(Col.EndBone);
		if (CS.A.IsValid() && CS.B.IsValid() && MA != INDEX_NONE && MB != INDEX_NONE)
		{
			CS.LocalA = RefCS[MA].InverseTransformVectorNoScale(Col.OffsetA);
			CS.LocalB = RefCS[MB].InverseTransformVectorNoScale(Col.OffsetB);
			RefCapA.Add(RefCS[MA].GetLocation() + Col.OffsetA);
			RefCapB.Add(RefCS[MB].GetLocation() + Col.OffsetB);
			ColliderState.Add(CS);
		}
	}

	// Rest gaps: a particle (or segment midpoint) that rests closer to a capsule than its radius keeps that gap.
	const int32 NC = ColliderState.Num();
	for (int32 C = 0; C < State.Num(); ++C)
	{
		FChainState& S = State[C];
		S.Radius.Reset();
		S.MidRadius.Reset();
		if (!bRestRadius || S.Bones.Num() < 2)
		{
			continue;
		}
		TArray<FVector> RP;
		for (const FCompactPoseBoneIndex& B : S.Bones)
		{
			RP.Add(RefCS[RequiredBones.MakeMeshPoseIndex(B).GetInt()].GetLocation());
		}
		auto Gap = [&](const FVector& P, int32 K)
		{
			const float D = FMath::PointDistToSegment(P, RefCapA[K], RefCapB[K]);
			const float R = ColliderState[K].Radius;
			return D < R ? D * RestRadiusScale : R;
		};
		for (int32 I = 0; I < RP.Num(); ++I)
		{
			for (int32 K = 0; K < NC; ++K)
			{
				S.Radius.Add(Gap(RP[I], K));
				S.MidRadius.Add(I > 0 ? Gap(0.5f * (RP[I] + RP[I - 1]), K) : 0.f);
			}
		}
	}
}

void FAnimNode_BFClothSway::EvaluateSkeletalControl_AnyThread(FComponentSpacePoseContext& Output, TArray<FBoneTransform>& OutBoneTransforms)
{
	const float Dt = FMath::Min(PendingDt, 0.1f);
	PendingDt = 0.f;
	Time += Dt;
	const FTransform CompT = Output.AnimInstanceProxy->GetComponentTransform();
	if (Settle > 0.f)
	{
		ApplyArmDrop(Output, CompT);
	}

	// Colliders in world space (animated pose).
	struct FCap { FVector A, B; float R; };
	TArray<FCap, TInlineAllocator<16>> Caps;
	for (const FColliderState& C : ColliderState)
	{
		Caps.Add({ CompT.TransformPosition(Output.Pose.GetComponentSpaceTransform(C.A).TransformPosition(C.LocalA)),
			CompT.TransformPosition(Output.Pose.GetComponentSpaceTransform(C.B).TransformPosition(C.LocalB)), C.Radius });
	}

	const int32 Sub = Dt > KINDA_SMALL_NUMBER ? FMath::Clamp(FMath::CeilToInt(Dt * 60.f), 1, 6) : 0;
	const float H = Sub > 0 ? Dt / Sub : 0.f;
	const float DampH = StepFactor(Damping, H);

	TArray<FTransform> AnimCS;
	TArray<FVector> AnimW;
	TArray<FVector> Target;
	for (FChainState& S : State)
	{
		const int32 ChainIdx = int32(&S - State.GetData());
		const FBFClothChain* ChainCfg = Chains.IsValidIndex(ChainIdx) ? &Chains[ChainIdx] : nullptr;
		const float ChainStiffScale = (ChainCfg ? ChainCfg->StiffnessScale : 1.f) * FMath::Lerp(1.f, 0.015f, Loose);
		const float ChainInertia = (ChainCfg && ChainCfg->Inertia >= 0.f) ? ChainCfg->Inertia : Inertia;
		const float CosMax = FMath::Cos(FMath::DegreesToRadians(FMath::Lerp((ChainCfg && ChainCfg->MaxAngleDeg > 0.f) ? ChainCfg->MaxAngleDeg : MaxAngleDeg, 150.f, Loose)));
		const int32 N = S.Bones.Num();
		if (N < 2)
		{
			continue;
		}
		AnimCS.Reset(N);
		AnimW.Reset(N);
		for (const FCompactPoseBoneIndex& B : S.Bones)
		{
			AnimCS.Add(Output.Pose.GetComponentSpaceTransform(B));
			AnimW.Add(CompT.TransformPosition(AnimCS.Last().GetLocation()));
		}

		if (!S.bInit || FVector::Dist(AnimW[0], S.AnimPrev.IsEmpty() ? AnimW[0] : S.AnimPrev[0]) > TeleportDistance)
		{
			S.X = AnimW;
			S.XPrev = AnimW;
			S.AnimPrev = AnimW;
			S.bInit = true;
		}

		// Some cloth points start inside a collider in the animated pose (they hang against the body);
		// those particles skip that collider so the cloth is not shoved off its own rest pose.
		for (int32 Step = 1; Step <= Sub; ++Step)
		{
			const float StepAlpha = float(Step) / Sub;
			Target.Reset(N);
			for (int32 I = 0; I < N; ++I)
			{
				Target.Add(FMath::Lerp(S.AnimPrev[I], AnimW[I], StepAlpha));
			}

			// Root follows the animation; part of its travel is handed to the whole strip (1 - Inertia).
			const FVector RootMove = Target[0] - S.X[0];
			const FVector Carry = RootMove * (1.f - ChainInertia);
			S.X[0] = Target[0];
			S.XPrev[0] = Target[0];

			const float T = Time - Dt + Dt * StepAlpha;
			const float Ph = UE_TWO_PI * T / FMath::Max(0.5f, WindPeriod) + S.Phase;
			const FVector Wind = CompT.TransformVectorNoScale(FVector(FMath::Sin(Ph), 0.6f * FMath::Sin(Ph * 0.71f + 1.3f), 0.f))
				* WindStrength * (0.6f + 0.4f * FMath::Sin(Ph * 0.37f));

			for (int32 I = 1; I < N; ++I)
			{
				S.X[I] += Carry;
				S.XPrev[I] += Carry;
				// Time-corrected verlet: only the first substep follows a step of a different length (the
				// last frame's), and the ratio never amplifies. Applying it to every substep after a hitch or a
				// hit-stop multiplied the velocity many times over and spun the strips like rotor blades.
				const float PrevH = Step == 1 ? LastStep : H;
				const float Ratio = FMath::Min(1.f, H / FMath::Max(PrevH, 1e-4f));
				const FVector Vel = ((S.X[I] - S.XPrev[I]) * (1.f - DampH) * Ratio).GetClampedToMaxSize(MaxSpeed * H);
				S.XPrev[I] = S.X[I];
				S.X[I] += Vel + (Gravity * FMath::Lerp(1.f, 4.f, Loose) + Wind * (1.f - Loose)) * H * H;
			}

			for (int32 I = 1; I < N; ++I)
			{
				const FVector AnimSeg = Target[I] - Target[I - 1];
				const float Len = AnimSeg.Size();
				if (Len < KINDA_SMALL_NUMBER)
				{
					S.X[I] = S.X[I - 1];
					continue;
				}
				const FVector AnimDir = AnimSeg / Len;

				// Shape keeping: pull toward the animated offset from the (simulated) parent.
				const float Frac = N > 2 ? float(I - 1) / float(N - 2) : 1.f;
				const float Stiff = StepFactor(FMath::Min(0.9f, FMath::Lerp(StiffnessRoot, StiffnessTip, Frac) * ChainStiffScale), H);
				S.X[I] = FMath::Lerp(S.X[I], S.X[I - 1] + AnimSeg, Stiff);

				if (!bRestRadius)
				{
					for (const FCap& C : Caps)
					{
						if (FMath::PointDistToSegment(Target[I], C.A, C.B) >= C.R)
						{
							PushOutOfCapsule(S.X[I], C.A, C.B, C.R);
						}
					}
				}

				// Angle clamp against the animated direction, then restore the segment length.
				FVector Dir = (S.X[I] - S.X[I - 1]).GetSafeNormal();
				if (Dir.IsNearlyZero())
				{
					Dir = AnimDir;
				}
				const float Cos = FVector::DotProduct(Dir, AnimDir);
				if (Cos < CosMax)
				{
					FVector Perp = (Dir - AnimDir * Cos).GetSafeNormal();
					if (Perp.IsNearlyZero())
					{
						Perp = FVector::CrossProduct(AnimDir, FVector::UpVector).GetSafeNormal();
					}
					Dir = AnimDir * CosMax + Perp * FMath::Sqrt(FMath::Max(0.f, 1.f - CosMax * CosMax));
					S.X[I] = S.X[I - 1] + Dir * Len;
					// Friction at the limit: drop most of the velocity, or the strip slides round the cone's rim.
					S.XPrev[I] = FMath::Lerp(S.XPrev[I], S.X[I], LimitFriction);
				}
				else
				{
					S.X[I] = S.X[I - 1] + Dir * Len;
				}
				if (bRestRadius && S.Radius.Num() == N * Caps.Num())
				{
					// After the shape and length steps, so nothing moves the particle back inside afterwards
					// except the next length fix, which only slides it along its own segment.
					const int32 NC = Caps.Num();
					for (int32 It = 0; It < FMath::Max(1, CollisionIterations); ++It)
					{
						for (int32 K = 0; K < NC; ++K)
						{
							const FCap& C = Caps[K];
							PushOutOfCapsule(S.X[I], C.A, C.B, S.Radius[I * NC + K]);
							if (bSegmentCollision)
							{
								// Closest approach of the whole segment to the capsule axis (a limb can cross a long
								// segment anywhere, not only at its middle). The parent is already placed, so the
								// correction at that point goes to the child, scaled up by how far along it is.
								const FVector Seg = S.X[I] - S.X[I - 1];
								const float SegLen2 = Seg.SizeSquared();
								FVector P1, P2;
								FMath::SegmentDistToSegmentSafe(S.X[I - 1], S.X[I], C.A, C.B, P1, P2);
								const float SegT = SegLen2 > KINDA_SMALL_NUMBER ? FMath::Clamp(FVector::DotProduct(P1 - S.X[I - 1], Seg) / SegLen2, 0.f, 1.f) : 1.f;
								const float R0 = S.Radius[(I - 1) * NC + K], Rm = S.MidRadius[I * NC + K], R1 = S.Radius[I * NC + K];
								const float Rs = SegT < 0.5f ? FMath::Lerp(R0, Rm, 2.f * SegT) : FMath::Lerp(Rm, R1, 2.f * SegT - 1.f);
								const FVector D = P1 - P2;
								const float Dist = D.Size();
								if (SegT > 0.05f && Dist < Rs && Dist > KINDA_SMALL_NUMBER)
								{
									S.X[I] += D / Dist * (Rs - Dist) / FMath::Max(SegT, 0.3f);
								}
							}
						}
					}
					const FVector Fixed = S.X[I] - S.X[I - 1];
					const float FL = Fixed.Size();
					if (FL > KINDA_SMALL_NUMBER)
					{
						S.X[I] = S.X[I - 1] + Fixed / FL * Len;
					}
					for (int32 K = 0; K < NC; ++K)
					{
						const FCap& C = Caps[K];
						DiagMaxPen = FMath::Max(DiagMaxPen, S.Radius[I * NC + K] - FMath::PointDistToSegment(S.X[I], C.A, C.B));
					}
				}
				if (Loose > 0.f && S.X[I].Z < FloorZ + 4.f)
				{
					S.X[I].Z = FloorZ + 4.f;
					S.XPrev[I] = FMath::Lerp(S.XPrev[I], S.X[I], 0.5f); // floor friction
				}
			}
		}
		if (Dt > KINDA_SMALL_NUMBER && H > KINDA_SMALL_NUMBER)
		{
			const FVector RootVel = (AnimW[0] - S.AnimPrev[0]) / Dt;
			const float Rel = ((S.X[N - 1] - S.XPrev[N - 1]) / H - RootVel).Size();
			DiagMaxRelSpeed = FMath::Max(DiagMaxRelSpeed, Rel);
		}
		S.AnimPrev = AnimW;

		// Back to bones: each bone keeps its animated rotation turned onto its simulated segment.
		FQuat LastQ = FQuat::Identity;
		for (int32 I = 0; I < N; ++I)
		{
			FTransform Out = AnimCS[I];
			Out.SetLocation(CompT.InverseTransformPosition(S.X[I]));
			if (I + 1 < N)
			{
				const FVector A = (AnimCS[I + 1].GetLocation() - AnimCS[I].GetLocation()).GetSafeNormal();
				const FVector B = CompT.InverseTransformVectorNoScale(S.X[I + 1] - S.X[I]).GetSafeNormal();
				LastQ = (A.IsNearlyZero() || B.IsNearlyZero()) ? FQuat::Identity : FQuat::FindBetweenNormals(A, B);
				const float Dev = FMath::RadiansToDegrees(FMath::Acos(FMath::Clamp(FVector::DotProduct(A, B), -1.f, 1.f)));
				if (Dev > DiagMaxDev)
				{
					DiagMaxDev = Dev;
					DiagChain = Chains.IsValidIndex(ChainIdx) ? Chains[ChainIdx].StartBone : NAME_None;
				}
			}
			Out.SetRotation((LastQ * AnimCS[I].GetRotation()).GetNormalized());
			OutBoneTransforms.Add(FBoneTransform(S.Bones[I], Out));
		}
	}
	if (Sub > 0)
	{
		LastStep = H;
	}
	if (Dt > KINDA_SMALL_NUMBER)
	{
		const FQuat Q = CompT.GetRotation();
		const float YawRate = FMath::Abs(FRotator::NormalizeAxis(Q.Rotator().Yaw - DiagPrevCompQ.Rotator().Yaw)) / Dt;
		DiagPrevCompQ = Q;
		DiagMaxYawRate = FMath::Max(DiagMaxYawRate, YawRate);
		DiagTimer += Dt;
		if (DiagTimer >= 0.25f)
		{
			UE_LOG(LogTemp, Display, TEXT("BFCLOTH t=%.2f maxdev=%.0f chain=%s yawrate=%.0f relspeed=%.0f pen=%.1f"), Time, DiagMaxDev, *DiagChain.ToString(), DiagMaxYawRate, DiagMaxRelSpeed, DiagMaxPen);
			DiagMaxPen = 0.f;
			DiagTimer = 0.f;
			DiagMaxDev = 0.f;
			DiagMaxYawRate = 0.f;
			DiagMaxRelSpeed = 0.f;
		}
	}
	OutBoneTransforms.Sort(FCompareBoneTransformIndex());
}
