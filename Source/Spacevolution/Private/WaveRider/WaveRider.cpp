#include "WaveRider/WaveRider.h"
#include "Ocean/Ocean.h"
#include "Spacevolution.h"
#include "Camera/CameraComponent.h"
#include "Components/BoxComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "Engine/CollisionProfile.h"
#include "Engine/LocalPlayer.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/SpringArmComponent.h"
#include "InputActionValue.h"
#include "Materials/MaterialInstanceDynamic.h"

namespace
{
	constexpr float CmPerM = 100.f;
	constexpr float KmhToCms = 100.f / 3.6f;
	// Gentle linear drag on the surface so the rider coasts to a stop with the throttle off (per second).
	constexpr float CoastDrag = 0.04f;
	// Air resistance in flight: about 1 m/s^2 at 40 m/s.
	constexpr float AirDrag = 6.25e-6f;
	// The cushion stops pulling down this long after a jump, so the jump isn't swallowed.
	constexpr float JumpRelease = 0.4f;
	constexpr float BurstDelay = 0.12f;
	constexpr float BaseBoomPitch = -10.f;
	// Ploughing into a wave face shoves back hard, but never more than this many g per ring, so a nose-first
	// landing can't kick the hull into a somersault.
	constexpr float PloughLimit = 3.f;
	// In the air the lift rings hold attitude harder than on the water, and harder again while bursting.
	constexpr float AirAssist = 1.5f;
	constexpr float BurstAssist = 2.f;
	// Spin beyond this (rad/s) in the air is damped hard.
	constexpr float SpinLimit = 2.5f;
}

AWaveRider::AWaveRider()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickGroup = TG_PrePhysics;
	bUseControllerRotationPitch = false;
	bUseControllerRotationYaw = false;
	bUseControllerRotationRoll = false;
	// A rider placed in a level waits for a player rather than getting an AI of its own.
	AutoPossessAI = EAutoPossessAI::Disabled;

	// 3.4 x 1.2 m hull (PWC-01 spec sheet), 280 kg dry plus a rider.
	Body = CreateDefaultSubobject<UBoxComponent>(TEXT("Body"));
	Body->InitBoxExtent(FVector(165.f, 58.f, 30.f));
	Body->SetCollisionProfileName(UCollisionProfile::PhysicsActor_ProfileName);
	Body->SetSimulatePhysics(true);
	Body->SetEnableGravity(true);
	Body->SetLinearDamping(0.02f);
	Body->SetAngularDamping(1.2f);
	Body->BodyInstance.SetMassOverride(360.f, true);
	Body->BodyInstance.COMNudge = FVector(0.f, 0.f, -12.f);
	Body->BodyInstance.bUseCCD = true;
	Body->SetCanEverAffectNavigation(false);
	SetRootComponent(Body);

	Lean = CreateDefaultSubobject<USceneComponent>(TEXT("Lean"));
	Lean->SetupAttachment(Body);

	Hull = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Hull"));
	Hull->SetupAttachment(Lean);
	Hull->SetCollisionEnabled(ECollisionEnabled::NoCollision);

	RiderFigure = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("RiderFigure"));
	RiderFigure->SetupAttachment(Lean);
	RiderFigure->SetCollisionEnabled(ECollisionEnabled::NoCollision);

	auto MakeSpray = [this](const TCHAR* Name, const FVector& Location, const FVector& Scale)
	{
		UStaticMeshComponent* Sheet = CreateDefaultSubobject<UStaticMeshComponent>(Name);
		Sheet->SetupAttachment(Body);
		Sheet->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		Sheet->SetCastShadow(false);
		Sheet->SetRelativeLocation(Location);
		Sheet->SetRelativeScale3D(Scale);
		Sheet->SetHiddenInGame(true);
		return Sheet;
	};
	SprayLeft = MakeSpray(TEXT("SprayLeft"), FVector(70.f, -50.f, -32.f), FVector(1.f, 1.f, 1.f));
	// Mirrored for the right side; the spray material is two-sided.
	SprayRight = MakeSpray(TEXT("SprayRight"), FVector(70.f, 50.f, -32.f), FVector(1.f, -1.f, 1.f));
	Wake = MakeSpray(TEXT("Wake"), FVector(-175.f, 0.f, -28.f), FVector(1.f, 1.f, 1.f));

	LiftGlow = CreateDefaultSubobject<UPointLightComponent>(TEXT("LiftGlow"));
	LiftGlow->SetupAttachment(Body);
	LiftGlow->SetRelativeLocation(FVector(0.f, 0.f, -55.f));
	LiftGlow->SetIntensityUnits(ELightUnits::Candelas);
	LiftGlow->SetIntensity(LiftLightRange.X);
	LiftGlow->SetLightColor(FLinearColor(1.f, 0.52f, 0.16f));
	LiftGlow->SetAttenuationRadius(650.f);
	LiftGlow->SetSourceRadius(40.f);
	LiftGlow->SetCastShadows(false);

	Boom = CreateDefaultSubobject<USpringArmComponent>(TEXT("Boom"));
	Boom->SetupAttachment(Body);
	Boom->TargetArmLength = 560.f;
	Boom->SocketOffset = FVector(0.f, 0.f, 135.f);
	Boom->SetRelativeRotation(FRotator(BaseBoomPitch, 0.f, 0.f));
	Boom->bUsePawnControlRotation = false;
	Boom->bInheritPitch = false;
	Boom->bInheritRoll = false;
	Boom->bInheritYaw = true;
	Boom->bEnableCameraLag = true;
	Boom->CameraLagSpeed = 9.f;
	Boom->CameraLagMaxDistance = 500.f;
	Boom->bEnableCameraRotationLag = true;
	Boom->CameraRotationLagSpeed = 5.f;
	Boom->ProbeSize = 20.f;

	Camera = CreateDefaultSubobject<UCameraComponent>(TEXT("Camera"));
	Camera->SetupAttachment(Boom, USpringArmComponent::SocketName);
	Camera->SetRelativeRotation(FRotator(-4.f, 0.f, 0.f));
	Camera->SetFieldOfView(FieldOfView);

	// Light enough that a crest taken at speed throws the hull clear.
	HoldDown = 0.15f;

	// Two rings forward and two aft, either side of the keel, on the underside.
	Thrusters = {FVector(95.f, -36.f, -30.f), FVector(95.f, 36.f, -30.f), FVector(-85.f, -36.f, -30.f), FVector(-85.f, 36.f, -30.f)};
}

void AWaveRider::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);
	Hull->SetStaticMesh(HullMesh);
	RiderFigure->SetStaticMesh(RiderMesh);
	SprayLeft->SetStaticMesh(SprayMesh);
	SprayRight->SetStaticMesh(SprayMesh);
	Wake->SetStaticMesh(WakeMesh);
}

void AWaveRider::BeginPlay()
{
	Super::BeginPlay();

	Ocean = AOcean::FindOcean(this);
	if (AOcean* Found = Ocean.Get())
	{
		// Sample the waves after the ocean has stepped them for this frame.
		AddTickPrerequisiteActor(Found);
	}
	else
	{
		UE_LOG(LogShip, Warning, TEXT("%s: no ocean in the level; the lift rings will only find solid ground"), *GetName());
	}

	GlowMaterials.Reset();
	for (const FName& Slot : GlowSlots)
	{
		const int32 Index = Hull->GetMaterialIndex(Slot);
		if (Index != INDEX_NONE)
		{
			GlowMaterials.Add(Hull->CreateDynamicMaterialInstance(Index));
		}
	}
	Camera->SetFieldOfView(FieldOfView);
	// Nobody aboard until a player boards it.
	RiderFigure->SetHiddenInGame(Controller == nullptr);

	SprayMaterials.Reset();
	for (UStaticMeshComponent* Sheet : {SprayLeft.Get(), SprayRight.Get(), Wake.Get()})
	{
		if (Sheet && Sheet->GetStaticMesh())
		{
			SprayMaterials.Add(Sheet->CreateDynamicMaterialInstance(0));
		}
	}
}

void AWaveRider::NotifyControllerChanged()
{
	Super::NotifyControllerChanged();

	if (const APlayerController* PlayerController = Cast<APlayerController>(Controller))
	{
		if (UEnhancedInputLocalPlayerSubsystem* Subsystem =
				ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(PlayerController->GetLocalPlayer()))
		{
			if (RiderMappingContext)
			{
				Subsystem->AddMappingContext(RiderMappingContext, 0);
			}
		}
	}
}

void AWaveRider::PossessedBy(AController* NewController)
{
	Super::PossessedBy(NewController);
	RiderFigure->SetHiddenInGame(false);
	BoardedTime = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.f;
}

void AWaveRider::UnPossessed()
{
	Super::UnPossessed();
	RiderFigure->SetHiddenInGame(true);
	ThrottleInput = SteerInput = PitchInput = 0.f;
	bJumpHeld = bBoostHeld = bJumpQueued = false;
}

float AWaveRider::GetRiddenSeconds() const
{
	const UWorld* World = GetWorld();
	return Controller && World ? World->GetTimeSeconds() - BoardedTime : 0.f;
}

void AWaveRider::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
	Super::SetupPlayerInputComponent(PlayerInputComponent);

	UEnhancedInputComponent* Input = Cast<UEnhancedInputComponent>(PlayerInputComponent);
	if (!Input)
	{
		UE_LOG(LogShip, Error, TEXT("%s needs the Enhanced Input component"), *GetName());
		return;
	}
	if (ThrottleAction)
	{
		Input->BindAction(ThrottleAction, ETriggerEvent::Triggered, this, &ThisClass::OnThrottle);
		Input->BindAction(ThrottleAction, ETriggerEvent::Completed, this, &ThisClass::OnThrottleEnd);
	}
	if (SteerAction)
	{
		Input->BindAction(SteerAction, ETriggerEvent::Triggered, this, &ThisClass::OnSteer);
		Input->BindAction(SteerAction, ETriggerEvent::Completed, this, &ThisClass::OnSteerEnd);
	}
	if (PitchAction)
	{
		Input->BindAction(PitchAction, ETriggerEvent::Triggered, this, &ThisClass::OnPitch);
		Input->BindAction(PitchAction, ETriggerEvent::Completed, this, &ThisClass::OnPitchEnd);
	}
	if (LookAction)
	{
		Input->BindAction(LookAction, ETriggerEvent::Triggered, this, &ThisClass::OnLook);
	}
	if (JumpAction)
	{
		Input->BindAction(JumpAction, ETriggerEvent::Started, this, &ThisClass::OnJumpStart);
		Input->BindAction(JumpAction, ETriggerEvent::Completed, this, &ThisClass::OnJumpEnd);
	}
	if (BoostAction)
	{
		Input->BindAction(BoostAction, ETriggerEvent::Started, this, &ThisClass::OnBoostStart);
		Input->BindAction(BoostAction, ETriggerEvent::Completed, this, &ThisClass::OnBoostEnd);
	}
	if (ResetAction)
	{
		Input->BindAction(ResetAction, ETriggerEvent::Started, this, &ThisClass::ResetRider);
	}
}

void AWaveRider::OnThrottle(const FInputActionValue& Value)
{
	ThrottleInput = Value.Get<float>();
}

void AWaveRider::OnSteer(const FInputActionValue& Value)
{
	SteerInput = Value.Get<float>();
}

void AWaveRider::OnPitch(const FInputActionValue& Value)
{
	PitchInput = Value.Get<float>();
}

void AWaveRider::OnJumpStart()
{
	bJumpHeld = true;
	bJumpQueued = true;
}

void AWaveRider::OnLook(const FInputActionValue& Value)
{
	const FVector2D Delta = Value.Get<FVector2D>();
	LookOffset.X = FRotator::NormalizeAxis(LookOffset.X + Delta.X);
	LookOffset.Y = FMath::Clamp(LookOffset.Y + Delta.Y, -45.f, 40.f);
	LookIdle = 0.f;
}

float AWaveRider::GetSpeedKmh() const
{
	return Body ? static_cast<float>(Body->GetPhysicsLinearVelocity().Size()) / KmhToCms : 0.f;
}

float AWaveRider::GetAirTime() const
{
	const UWorld* World = GetWorld();
	return bAirborne && World ? World->GetTimeSeconds() - AirStartTime : 0.f;
}

void AWaveRider::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (!Body || !Body->IsSimulatingPhysics())
	{
		return;
	}
	const float Dt = FMath::Min(DeltaSeconds, 0.05f);
	const float Now = GetWorld()->GetTimeSeconds();
	if (!Ocean.IsValid())
	{
		// A streamed-in sublevel may bring the ocean after this rider began play.
		if (AOcean* Found = AOcean::FindOcean(this))
		{
			Ocean = Found;
			AddTickPrerequisiteActor(Found);
		}
	}

	int32 InRange = 0;
	FVector SurfaceNormal = FVector::UpVector;
	bool bOnWater = false;
	Hover(Dt, InRange, SurfaceNormal, bOnWater);
	const float Grounded = Thrusters.Num() > 0 ? InRange / static_cast<float>(Thrusters.Num()) : 0.f;
	const bool bOnSurface = InRange > 0;

	if (!bOnSurface && !bAirborne)
	{
		bAirborne = true;
		AirStartTime = Now;
	}
	else if (bOnSurface && bAirborne)
	{
		bAirborne = false;
		const float Air = Now - AirStartTime;
		if (Air > 0.3f)
		{
			LastAirTime = Air;
			BestAirTime = FMath::Max(BestAirTime, Air);
			// Landing throws up a sheet of water, bigger the longer the fall.
			SprayKick = FMath::Clamp(Air * 0.35f, 0.3f, 1.f);
		}
	}

	if (bJumpQueued)
	{
		bJumpQueued = false;
		if (InRange >= 1 && Now - LastJumpTime > JumpRelease)
		{
			Body->AddImpulse(FVector(0.f, 0.f, JumpSpeed * CmPerM), NAME_None, /*bVelChange*/ true);
			LastJumpTime = Now;
		}
	}

	Drive(Dt, Grounded, SurfaceNormal);
	Attitude(Dt, Grounded, SurfaceNormal);
	UpdateBurst(Dt, bOnSurface);
	UpdateLook(Dt);
	UpdateFeedback(Dt);
	UpdateSpray(Dt);
	CheckUpset(Dt);
}

AWaveRider::FSurfaceHit AWaveRider::FindSurface(const FVector& Point) const
{
	FSurfaceHit Hit;
	if (const AOcean* Water = Ocean.Get())
	{
		Water->SampleSurface(Point, Hit.Height, Hit.Normal, Hit.RiseSpeed);
		Hit.bWater = true;
	}
	// Beaches, bridges and anything else solid under the ring.
	FHitResult Trace;
	const FCollisionQueryParams Params(SCENE_QUERY_STAT(WaveRiderHover), false, this);
	const FVector Start = Point + FVector(0.f, 0.f, 100.f);
	const FVector End = Point - FVector(0.f, 0.f, HoverRange + 200.f);
	if (GetWorld()->LineTraceSingleByChannel(Trace, Start, End, ECC_Visibility, Params) && Trace.ImpactPoint.Z > Hit.Height)
	{
		Hit.Height = static_cast<float>(Trace.ImpactPoint.Z);
		Hit.Normal = Trace.ImpactNormal;
		Hit.RiseSpeed = 0.f;
		Hit.bWater = false;
	}
	return Hit;
}

void AWaveRider::Hover(float DeltaSeconds, int32& OutInRange, FVector& OutSurfaceNormal, bool& OutOnWater)
{
	const FTransform Xf = Body->GetComponentTransform();
	const float Share = Body->GetMass() / FMath::Max(Thrusters.Num(), 1);
	const float Omega = UE_TWO_PI * HoverFrequency;
	const float Stiffness = Omega * Omega;
	const float Damping = 2.f * HoverDamping * Omega;
	const float Gravity = -GetWorld()->GetGravityZ();
	const bool bJustJumped = GetWorld()->GetTimeSeconds() - LastJumpTime < JumpRelease;

	FVector NormalSum = FVector::ZeroVector;
	float LowestGap = UE_BIG_NUMBER;
	int32 Skimming = 0;
	OutInRange = 0;
	OutOnWater = false;
	for (const FVector& Local : Thrusters)
	{
		const FVector Point = Xf.TransformPosition(Local);
		const FSurfaceHit Surface = FindSurface(Point);
		const float Gap = static_cast<float>(Point.Z) - Surface.Height;
		LowestGap = FMath::Min(LowestGap, Gap);
		if (Gap > HoverRange)
		{
			continue;
		}
		++OutInRange;
		NormalSum += Surface.Normal;
		OutOnWater |= Surface.bWater;
		Skimming += (Surface.bWater && Gap < HoverHeight * 1.6f) ? 1 : 0;

		// Spring-damper on this ring's share of the mass, measured against the moving surface.
		const float Closing = static_cast<float>(Body->GetPhysicsLinearVelocityAtPoint(Point).Z) - Surface.RiseSpeed;
		float Accel = Stiffness * (HoverHeight - Gap) - Damping * Closing;
		Accel = FMath::Max(Accel, bJustJumped ? 0.f : -HoldDown * Gravity);
		if (Gap < 0.f)
		{
			// Ploughed under: the water shoves back much harder than the cushion.
			Accel += FMath::Min(3.f * Stiffness * -Gap, PloughLimit * Gravity);
		}
		Body->AddForceAtLocation(FVector(0.f, 0.f, Accel * Share), Point);
	}
	OutSurfaceNormal = OutInRange > 0 ? NormalSum.GetSafeNormal() : FVector::UpVector;
	HeightAboveSurface = LowestGap;
	WaterContact = Thrusters.Num() > 0 ? Skimming / static_cast<float>(Thrusters.Num()) : 0.f;
}

void AWaveRider::Drive(float DeltaSeconds, float Grounded, const FVector& SurfaceNormal)
{
	const FVector Velocity = Body->GetPhysicsLinearVelocity();
	if (Grounded <= 0.f)
	{
		bBoosting = false;
		Body->AddForce(-Velocity * (Velocity.Size() * AirDrag), NAME_None, /*bAccelChange*/ true);
		return;
	}

	const FVector Forward = FVector::VectorPlaneProject(Body->GetForwardVector(), SurfaceNormal).GetSafeNormal();
	const FVector Right = FVector::CrossProduct(SurfaceNormal, Forward);
	bBoosting = bBoostHeld && BurstCharge > 0.f && ThrottleInput > 0.1f;

	const float Push = (bBoosting ? BoostThrust : Thrust) * CmPerM;
	const float Top = (bBoosting ? BoostTopSpeed : TopSpeed) * KmhToCms;
	// Quadratic drag sized so full throttle settles at the top speed.
	const float Drag = FMath::Max(Push - CoastDrag * Top, 0.f) / (Top * Top);
	const float Accel = ThrottleInput >= 0.f ? ThrottleInput * Push : ThrottleInput * ReverseThrust * CmPerM;

	const FVector Planar = FVector::VectorPlaneProject(Velocity, SurfaceNormal);
	FVector A = Forward * Accel;
	A -= Planar * (Drag * Planar.Size() + CoastDrag);
	A -= Right * (FVector::DotProduct(Velocity, Right) * Grip);
	Body->AddForce(A * Grounded, NAME_None, /*bAccelChange*/ true);
}

void AWaveRider::Attitude(float DeltaSeconds, float Grounded, const FVector& SurfaceNormal)
{
	const FVector Up = Body->GetUpVector();
	const FVector Forward = Body->GetForwardVector();
	const FVector Right = Body->GetRightVector();
	const FVector Spin = Body->GetPhysicsAngularVelocityInRadians();
	const FVector Velocity = Body->GetPhysicsLinearVelocity();
	const float ForwardSpeed = static_cast<float>(FVector::DotProduct(Velocity, Forward));
	const float SpeedAlpha = FMath::Clamp(FMath::Abs(ForwardSpeed) / (TopSpeed * KmhToCms), 0.f, 1.f);
	const bool bOnSurface = Grounded > 0.f;

	FVector AngularAccel = FVector::ZeroVector;

	// Yaw chases a turn rate; it steers like a car going backwards.
	const FVector YawAxis = bOnSurface ? SurfaceNormal : FVector::UpVector;
	const float Rate = bOnSurface ? FMath::Lerp(TurnRate.X, TurnRate.Y, SpeedAlpha) : AirTurnRate.Y;
	const float Reverse = ForwardSpeed < -150.f ? -1.f : 1.f;
	const float TargetYaw = FMath::DegreesToRadians(SteerInput * Rate) * Reverse;
	const float Yaw = static_cast<float>(FVector::DotProduct(Spin, YawAxis));
	AngularAccel += YawAxis * ((TargetYaw - Yaw) * (bOnSurface ? 7.f : 4.f));

	// Stability assist: keep the hull from rolling over, on the water and in the air.
	const float Assist = StabilityAssist * (bOnSurface ? 1.f : (bBursting ? BurstAssist : AirAssist));
	const float Kp = Assist * Assist;
	const float Kd = 2.f * Assist;
	const FVector TargetUp = bOnSurface ? FMath::Lerp(FVector::UpVector, SurfaceNormal, 0.6f).GetSafeNormal() : FVector::UpVector;
	const FVector Correction = FVector::CrossProduct(Up, TargetUp);
	const float RollRate = static_cast<float>(FVector::DotProduct(Spin, Forward));
	const float PitchRate = static_cast<float>(FVector::DotProduct(Spin, Right));
	AngularAccel += Forward * (Kp * static_cast<float>(FVector::DotProduct(Correction, Forward)) - Kd * RollRate);

	if (!bOnSurface)
	{
		// A positive spin about the right axis drops the nose.
		if (FMath::Abs(PitchInput) > 0.05f)
		{
			const float TargetPitchRate = FMath::DegreesToRadians(PitchInput * AirTurnRate.X);
			AngularAccel += Right * ((TargetPitchRate - PitchRate) * 6.f);
		}
		else
		{
			// Hands off, the nose follows the flight path, so jumps arc and land nose first.
			const float Pitch = FMath::Asin(FMath::Clamp(static_cast<float>(Forward.Z), -1.f, 1.f));
			const float Speed = static_cast<float>(Velocity.Size());
			const float PathPitch = Speed > 500.f ? FMath::Asin(FMath::Clamp(static_cast<float>(Velocity.Z) / Speed, -1.f, 1.f)) : 0.f;
			const float TargetPitch = FMath::Clamp(PathPitch, FMath::DegreesToRadians(-30.f), FMath::DegreesToRadians(18.f));
			AngularAccel += Right * (Kp * (Pitch - TargetPitch) - Kd * PitchRate);
		}
		// Anything spinning faster than a rider could want is a knock from the water: soak it up.
		const float SpinRate = static_cast<float>(Spin.Size());
		if (SpinRate > SpinLimit)
		{
			AngularAccel -= Spin * ((SpinRate - SpinLimit) / SpinRate * 12.f);
		}
	}
	Body->AddTorqueInRadians(AngularAccel, NAME_None, /*bAccelChange*/ true);
}

void AWaveRider::UpdateBurst(float DeltaSeconds, bool bOnSurface)
{
	bBursting = false;
	if (!bOnSurface && bJumpHeld && BurstCharge > 0.f && GetAirTime() > BurstDelay)
	{
		bBursting = true;
		BurstCharge = FMath::Max(0.f, BurstCharge - DeltaSeconds / FMath::Max(BurstSeconds, 0.1f));

		// Cancel gravity, then push toward a gentle climb with whatever lift is left over.
		const float Gravity = -GetWorld()->GetGravityZ();
		const float Climb = static_cast<float>(Body->GetPhysicsLinearVelocity().Z);
		const float Extra = FMath::Clamp((BurstClimbSpeed * CmPerM - Climb) * 4.f, -0.5f * Gravity, (BurstLift - 1.f) * Gravity);
		const FVector Ahead = FVector(Body->GetForwardVector().X, Body->GetForwardVector().Y, 0.0).GetSafeNormal();
		Body->AddForce(FVector(0.f, 0.f, Gravity + Extra) + Ahead * BurstThrust * CmPerM, NAME_None, /*bAccelChange*/ true);
	}
	if (bBoosting)
	{
		BurstCharge = FMath::Max(0.f, BurstCharge - DeltaSeconds * BoostDrain);
	}
	else if (bOnSurface)
	{
		BurstCharge = FMath::Min(1.f, BurstCharge + DeltaSeconds / FMath::Max(RechargeSeconds, 0.1f));
	}
}

void AWaveRider::UpdateLook(float DeltaSeconds)
{
	LookIdle += DeltaSeconds;
	if (LookIdle > LookRecentreDelay)
	{
		LookOffset = FMath::Vector2DInterpTo(LookOffset, FVector2D::ZeroVector, DeltaSeconds, 2.5f);
	}
	Boom->SetRelativeRotation(FRotator(BaseBoomPitch + LookOffset.Y, LookOffset.X, 0.f));
}

void AWaveRider::UpdateFeedback(float DeltaSeconds)
{
	const FVector Velocity = Body->GetPhysicsLinearVelocity();
	const float Speed = static_cast<float>(Velocity.Size());
	const float SpeedAlpha = FMath::Clamp(Speed / (BoostTopSpeed * KmhToCms), 0.f, 1.f);

	const float TargetFov = FieldOfView + SpeedFieldOfView * SpeedAlpha * SpeedAlpha + (bBursting ? 6.f : 0.f);
	Camera->SetFieldOfView(FMath::FInterpTo(Camera->FieldOfView, TargetFov, DeltaSeconds, 4.f));

	// Bank into turns once moving, and lift the nose a touch under power.
	const float Carve = FMath::Clamp(Speed / 1200.f, 0.f, 1.f) * (bAirborne ? 0.5f : 1.f);
	LeanRoll = FMath::FInterpTo(LeanRoll, SteerInput * LeanAngle * Carve, DeltaSeconds, 5.f);
	LeanPitch = FMath::FInterpTo(LeanPitch, bAirborne ? 0.f : ThrottleInput * 3.f, DeltaSeconds, 3.f);
	Lean->SetRelativeRotation(FRotator(LeanPitch, 0.f, LeanRoll));

	float Want = 0.2f + 0.45f * FMath::Abs(ThrottleInput) + (bBoosting ? 0.3f : 0.f);
	if (bBursting)
	{
		Want = 1.f;
	}
	Glow = FMath::FInterpTo(Glow, FMath::Min(Want, 1.f), DeltaSeconds, 8.f);
	const float Strength = FMath::Lerp(GlowRange.X, GlowRange.Y, Glow);
	for (UMaterialInstanceDynamic* Mid : GlowMaterials)
	{
		if (Mid)
		{
			Mid->SetScalarParameterValue(TEXT("EmissiveStrength"), Strength);
		}
	}
	LiftGlow->SetIntensity(FMath::Lerp(LiftLightRange.X, LiftLightRange.Y, Glow));
}

void AWaveRider::UpdateSpray(float DeltaSeconds)
{
	// Spray needs both speed and water under the rings; a landing adds a burst on top.
	const float Pace = FMath::SmoothStep(300.f, 2500.f, static_cast<float>(Body->GetPhysicsLinearVelocity().Size2D()));
	Spray = FMath::FInterpTo(Spray, WaterContact * Pace, DeltaSeconds, 6.f);
	SprayKick = FMath::Max(0.f, SprayKick - DeltaSeconds * 2.f);
	const float Amount = FMath::Clamp(Spray + SprayKick * WaterContact, 0.f, 1.5f);
	for (UMaterialInstanceDynamic* Mid : SprayMaterials)
	{
		if (Mid)
		{
			Mid->SetScalarParameterValue(TEXT("Spray"), Amount);
		}
	}
	const bool bNoSpray = Amount < 0.02f;
	const float Length = 0.5f + 0.8f * Pace + 0.6f * SprayKick;
	const float Height = 0.6f + 0.6f * Amount;
	SprayLeft->SetHiddenInGame(bNoSpray);
	SprayRight->SetHiddenInGame(bNoSpray);
	Wake->SetHiddenInGame(bNoSpray);
	SprayLeft->SetRelativeScale3D(FVector(Length, Length, Height));
	SprayRight->SetRelativeScale3D(FVector(Length, -Length, Height));
	Wake->SetRelativeScale3D(FVector(0.4f + Pace, 0.8f + 0.4f * Pace, 0.4f + 0.9f * Pace));
}

void AWaveRider::CheckUpset(float DeltaSeconds)
{
	// On its side or upside down, or sunk: put it back after a moment.
	const bool bUpset = Body->GetUpVector().Z < 0.1;
	const bool bSunk = HeightAboveSurface < -400.f;
	UpsetTime = (bUpset || bSunk) ? UpsetTime + DeltaSeconds : 0.f;
	if (UpsetTime > 2.f)
	{
		ResetRider();
	}
}

void AWaveRider::ResetRider()
{
	FVector Location = GetActorLocation();
	const FSurfaceHit Surface = FindSurface(Location);
	if (Surface.Height > -UE_BIG_NUMBER * 0.5f)
	{
		Location.Z = Surface.Height + HoverHeight + 60.f;
	}
	Body->SetPhysicsLinearVelocity(FVector::ZeroVector);
	Body->SetPhysicsAngularVelocityInRadians(FVector::ZeroVector);
	SetActorLocationAndRotation(Location, FRotator(0.f, GetActorRotation().Yaw, 0.f), false, nullptr, ETeleportType::ResetPhysics);
	UpsetTime = 0.f;
}
