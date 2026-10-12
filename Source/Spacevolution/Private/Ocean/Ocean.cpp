#include "Ocean/Ocean.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "Materials/MaterialInstanceDynamic.h"

namespace
{
	constexpr float Gravity = 9.81f;          // m/s^2
	constexpr float PhaseStep = 2.39996f;     // golden angle, so no two waves start in step
	constexpr float CmPerM = 100.f;


	FName IndexedName(const TCHAR* Prefix, int32 Index)
	{
		return FName(*FString::Printf(TEXT("%s%d"), Prefix, Index));
	}
}

AOcean::AOcean()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickGroup = TG_PrePhysics;

	SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("Root")));

	Surface = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Surface"));
	Surface->SetupAttachment(GetRootComponent());
	Surface->SetUsingAbsoluteLocation(true);
	Surface->SetMobility(EComponentMobility::Movable);
	Surface->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Surface->SetCastShadow(false);
	Surface->bAffectDistanceFieldLighting = false;
	Surface->bNeverDistanceCull = true;
}

AOcean* AOcean::FindOcean(const UObject* WorldContextObject)
{
	UWorld* World = WorldContextObject ? WorldContextObject->GetWorld() : nullptr;
	if (!World)
	{
		return nullptr;
	}
	TActorIterator<AOcean> It(World);
	return It ? *It : nullptr;
}

void AOcean::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);
	EnsureMaterial();
	FollowView();
	PushParameters();
}

void AOcean::BeginPlay()
{
	Super::BeginPlay();
	EnsureMaterial();
	FollowView();
	PushParameters();
}

void AOcean::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	OceanTime += DeltaSeconds * TimeScale;
	EnsureMaterial();
	FollowView();
	PushParameters();
}

void AOcean::EnsureMaterial()
{
	if (!Surface || !OceanMaterial)
	{
		return;
	}
	if (!SurfaceMaterial || SurfaceMaterial->Parent != OceanMaterial || Surface->GetMaterial(0) != SurfaceMaterial)
	{
		SurfaceMaterial = UMaterialInstanceDynamic::Create(OceanMaterial, this);
		// Rebuilt on load; never saved into the level.
		SurfaceMaterial->SetFlags(RF_Transient);
		Surface->SetMaterial(0, SurfaceMaterial);
	}
}

void AOcean::FollowView()
{
	if (!Surface)
	{
		return;
	}
	const UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}
	FVector View = Surface->GetComponentLocation();
	const APlayerController* Player = World->GetFirstPlayerController();
	if (Player && Player->PlayerCameraManager)
	{
		View = Player->PlayerCameraManager->GetCameraLocation();
	}
	else if (World->ViewLocationsRenderedLastFrame.Num() > 0)
	{
		View = World->ViewLocationsRenderedLastFrame[0];
	}
	const double Height = View.Z - GetActorLocation().Z;
	SurfaceScale = static_cast<float>(FMath::Max(1.0, Height / (GrowAboveHeight * CmPerM)));
	const double Step = static_cast<double>(SnapSize) * SurfaceScale;
	const FVector Target(FMath::GridSnap(View.X, Step), FMath::GridSnap(View.Y, Step), GetActorLocation().Z);
	if (!Surface->GetComponentLocation().Equals(Target, 1.0))
	{
		Surface->SetWorldLocation(Target);
	}
	if (!FMath::IsNearlyEqual(static_cast<float>(Surface->GetComponentScale().X), SurfaceScale, 1e-3f))
	{
		Surface->SetWorldScale3D(FVector(SurfaceScale, SurfaceScale, 1.0));
	}
}

void AOcean::PushParameters()
{
	UMaterialInstanceDynamic* Mid = SurfaceMaterial;
	if (!Mid)
	{
		return;
	}
	Mid->SetScalarParameterValue(TEXT("OceanTime"), static_cast<float>(OceanTime));
	Mid->SetScalarParameterValue(TEXT("Steepness"), Steepness);
	Mid->SetScalarParameterValue(TEXT("CalmFloor"), CalmFloor);
	// The mesh's vertices spread out as it grows, so the waves fade nearer in.
	Mid->SetScalarParameterValue(TEXT("FadeWavelengths"), FadeWavelengths * SurfaceScale);
	Mid->SetScalarParameterValue(TEXT("PlanetRadius"), PlanetRadiusKm > 0.f ? PlanetRadiusKm * 1000.f : 1.0e12f);
	Mid->SetScalarParameterValue(TEXT("WaveCount"), static_cast<float>(FMath::Max(ActiveWaveCount(), 1)));
	Mid->SetScalarParameterValue(TEXT("SeaLevel"), static_cast<float>(GetActorLocation().Z));
	const FVector Centre = Surface ? Surface->GetComponentLocation() / CmPerM : FVector::ZeroVector;
	Mid->SetVectorParameterValue(TEXT("SurfaceCentre"), FLinearColor(static_cast<float>(Centre.X), static_cast<float>(Centre.Y), 0.f, 0.f));

	for (int32 i = 0; i < MaxWaves; ++i)
	{
		FLinearColor Packed(1.f, 0.f, 10.f, 0.f);
		if (Waves.IsValidIndex(i) && Waves[i].Amplitude > 0.f && Waves[i].Wavelength > 0.f)
		{
			const FOceanWave& W = Waves[i];
			const float Rad = FMath::DegreesToRadians(W.DirectionDegrees);
			Packed = FLinearColor(FMath::Cos(Rad), FMath::Sin(Rad), W.Wavelength, W.Amplitude);
		}
		Mid->SetVectorParameterValue(IndexedName(TEXT("Wave"), i), Packed);
	}
	for (int32 i = 0; i < MaxCalmZones; ++i)
	{
		FLinearColor Packed(0.f, 0.f, 0.f, 0.f);
		if (CalmZones.IsValidIndex(i))
		{
			const FOceanCalmZone& Z = CalmZones[i];
			Packed = FLinearColor(static_cast<float>(Z.Centre.X), static_cast<float>(Z.Centre.Y), Z.InnerRadius, FMath::Max(Z.OuterRadius, Z.InnerRadius + 1.f));
		}
		Mid->SetVectorParameterValue(IndexedName(TEXT("Calm"), i), Packed);
	}
}

int32 AOcean::ActiveWaveCount() const
{
	int32 Count = 0;
	for (int32 i = 0; i < FMath::Min(Waves.Num(), MaxWaves); ++i)
	{
		Count += (Waves[i].Amplitude > 0.f && Waves[i].Wavelength > 0.f) ? 1 : 0;
	}
	return Count;
}

float AOcean::CalmFactor(const FVector2D& P0) const
{
	float Open = 1.f;
	for (int32 i = 0; i < FMath::Min(CalmZones.Num(), MaxCalmZones); ++i)
	{
		const FOceanCalmZone& Z = CalmZones[i];
		const float Outer = FMath::Max(Z.OuterRadius, Z.InnerRadius + 1.f);
		Open = FMath::Min(Open, FMath::SmoothStep(Z.InnerRadius, Outer, static_cast<float>(FVector2D::Distance(P0, Z.Centre))));
	}
	return FMath::Lerp(CalmFloor, 1.f, Open);
}

FVector AOcean::Displace(const FVector2D& P0, FVector* OutNormal, float* OutRiseSpeed) const
{
	// Keep in step with the WPO code in Scripts/town/ocean.py. Its fade with distance from the mesh's centre and the
	// planet's curvature are left out: both are nothing near the view, which is where anything rides the waves.
	const int32 Count = FMath::Max(ActiveWaveCount(), 1);
	const float Calm = CalmFactor(P0);
	const float T = static_cast<float>(OceanTime);

	FVector Offset = FVector::ZeroVector;
	FVector Normal(0.0, 0.0, 1.0);
	float Rise = 0.f;
	for (int32 i = 0; i < FMath::Min(Waves.Num(), MaxWaves); ++i)
	{
		const FOceanWave& W = Waves[i];
		if (W.Amplitude <= 0.f || W.Wavelength <= 0.f)
		{
			continue;
		}
		const float Rad = FMath::DegreesToRadians(W.DirectionDegrees);
		const FVector2D Dir(FMath::Cos(Rad), FMath::Sin(Rad));
		const float K = UE_TWO_PI / W.Wavelength;
		const float Omega = FMath::Sqrt(Gravity * K);
		const float A = W.Amplitude * Calm;
		const float Q = Steepness / (K * W.Amplitude * Count);
		const float Theta = K * static_cast<float>(FVector2D::DotProduct(Dir, P0)) - Omega * T + i * PhaseStep;
		float S, C;
		FMath::SinCos(&S, &C, Theta);

		Offset.X += Q * A * Dir.X * C;
		Offset.Y += Q * A * Dir.Y * C;
		Offset.Z += A * S;
		Normal.X -= Dir.X * K * A * C;
		Normal.Y -= Dir.Y * K * A * C;
		Normal.Z -= Q * K * A * S;
		Rise -= A * Omega * C;
	}
	if (OutNormal)
	{
		*OutNormal = Normal.GetSafeNormal(UE_SMALL_NUMBER, FVector::UpVector);
	}
	if (OutRiseSpeed)
	{
		*OutRiseSpeed = Rise;
	}
	return Offset;
}

void AOcean::SampleSurface(const FVector& WorldLocation, float& OutHeight, FVector& OutNormal, float& OutRiseSpeed) const
{
	// Gerstner waves also move water sideways, so find the undisplaced point that ends up under this location.
	const FVector2D Target(WorldLocation.X / CmPerM, WorldLocation.Y / CmPerM);
	FVector2D P0 = Target;
	for (int32 Iteration = 0; Iteration < 4; ++Iteration)
	{
		const FVector Offset = Displace(P0, nullptr, nullptr);
		P0 = Target - FVector2D(Offset.X, Offset.Y);
	}
	float Rise = 0.f;
	const FVector Offset = Displace(P0, &OutNormal, &Rise);
	OutHeight = static_cast<float>(GetActorLocation().Z + Offset.Z * CmPerM);
	OutRiseSpeed = Rise * CmPerM;
}

float AOcean::GetWaterHeight(const FVector& WorldLocation) const
{
	float Height = 0.f, Rise = 0.f;
	FVector Normal;
	SampleSurface(WorldLocation, Height, Normal, Rise);
	return Height;
}
