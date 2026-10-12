#pragma once

#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "PerformanceOverlaySubsystem.generated.h"

class APlayerController;
class UCanvas;

UENUM(BlueprintType)
enum class EPerformanceOverlayMode : uint8
{
	Off,
	/** One line: FPS and CPU / GPU frame times. */
	Compact,
	/** Panel with per-thread CPU times, GPU usage, memory, draw calls and a frame-time graph. */
	Full
};

/**
 * Draws a CPU/GPU performance overlay on the game viewport, using the same timings as `stat unit`.
 * The mode lives in the console variable Ship.PerfOverlay (0 off, 1 compact, 2 full), so the console,
 * an ini file and CycleMode() all agree.
 */
UCLASS()
class SPACEVOLUTION_API UPerformanceOverlaySubsystem : public UGameInstanceSubsystem
{
	GENERATED_BODY()

public:
	virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;

	UFUNCTION(BlueprintPure, Category = "Performance")
	EPerformanceOverlayMode GetMode() const;

	UFUNCTION(BlueprintCallable, Category = "Performance")
	void SetMode(EPerformanceOverlayMode Mode);

	/** Full -> Compact -> Off -> Full. */
	UFUNCTION(BlueprintCallable, Category = "Performance")
	void CycleMode();

private:
	struct FFrameSample
	{
		float FrameMs = 0.f;
		float GameMs = 0.f;
		float RenderMs = 0.f;
		float RhiMs = 0.f;
		float GpuMs = 0.f;
	};

	void Draw(UCanvas* Canvas, APlayerController* PlayerController);
	void Sample();
	void SampleSlowStats();
	void DrawCompact(UCanvas* Canvas, float Scale) const;
	void DrawFull(UCanvas* Canvas, float Scale) const;
	FString GetBoundBy(FLinearColor& OutColor) const;

	FDelegateHandle DrawHandle;

	FFrameSample Smoothed;
	TArray<FFrameSample> History;
	int32 HistoryHead = 0;

	// Refreshed a few times a second; they change slowly and some are not free to query.
	double NextSlowUpdate = 0.0;
	float ProcessCpuPercent = 0.f;
	float GpuUsagePercent = -1.f;
	uint64 ProcessMemoryBytes = 0;
	uint64 TotalMemoryBytes = 0;
	uint64 VideoMemoryUsedBytes = 0;
	int64 VideoMemoryTotalBytes = -1;
	int32 DrawCalls = 0;
	int32 PrimitivesDrawn = 0;

	FString CpuName;
	FString GpuName;
	FString RhiName;
	int32 CpuThreads = 0;
};
