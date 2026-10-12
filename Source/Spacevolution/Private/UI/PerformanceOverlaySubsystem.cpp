#include "UI/PerformanceOverlaySubsystem.h"
#include "CanvasItem.h"
#include "Debug/DebugDrawService.h"
#include "DynamicRHI.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/Font.h"
#include "Engine/GameInstance.h"
#include "GameFramework/PlayerController.h"
#include "HAL/IConsoleManager.h"
#include "HAL/PlatformMemory.h"
#include "HAL/PlatformTime.h"
#include "Misc/App.h"
#include "RHI.h"
#include "RHIGlobals.h"
#include "RHIStats.h"
#include "RenderTimer.h"

namespace PerformanceOverlay
{
	static TAutoConsoleVariable<int32> CVarMode(
		TEXT("Ship.PerfOverlay"),
#if UE_BUILD_SHIPPING
		0,
#else
		2,
#endif
		TEXT("CPU/GPU performance overlay. 0: off, 1: compact, 2: full (per-thread CPU, GPU usage, memory, frame graph)."));

	constexpr int32 HistoryLength = 160;
	constexpr float GraphCeilingMs = 40.f;
	constexpr float BarCeilingMs = 33.3f;

	const FLinearColor PanelColor(0.015f, 0.02f, 0.03f, 0.72f);
	const FLinearColor GraphBackColor(0.f, 0.f, 0.f, 0.35f);
	const FLinearColor DividerColor(1.f, 1.f, 1.f, 0.12f);
	const FLinearColor LabelColor(0.60f, 0.65f, 0.72f);
	const FLinearColor ValueColor(0.94f, 0.96f, 0.98f);
	const FLinearColor FrameColor(0.92f, 0.94f, 1.f);
	const FLinearColor GameColor(1.f, 0.60f, 0.20f);
	const FLinearColor RenderColor(1.f, 0.84f, 0.32f);
	const FLinearColor RhiColor(0.80f, 0.68f, 0.45f);
	const FLinearColor GpuColor(0.30f, 0.80f, 1.f);

	/** Green inside a 60 fps budget, amber inside 30 fps, red beyond. */
	FLinearColor Budget(float Ms)
	{
		return Ms <= 16.7f ? FLinearColor(0.38f, 0.92f, 0.48f)
			: Ms <= 33.4f ? FLinearColor(1.f, 0.76f, 0.22f)
			: FLinearColor(1.f, 0.32f, 0.26f);
	}

	FString Gigabytes(uint64 Bytes)
	{
		return FString::Printf(TEXT("%.1f"), Bytes / (1024.0 * 1024.0 * 1024.0));
	}

	/** Thin helper so the layout code reads as rows of text, bars and lines. */
	struct FPainter
	{
		UCanvas* Canvas;
		const UFont* Font;
		float Scale;

		float LineHeight() const { return Font->GetMaxCharHeight() * Scale + 3.f * Scale; }

		float Width(const FString& String) const
		{
			float XL = 0.f, YL = 0.f;
			Canvas->TextSize(Font, String, XL, YL, Scale, Scale);
			return XL;
		}

		void Text(float X, float Y, const FString& String, const FLinearColor& Color) const
		{
			FCanvasTextItem Item(FVector2D(X, Y), FText::FromString(String), Font, Color);
			Item.Scale = FVector2D(Scale, Scale);
			Item.EnableShadow(FLinearColor(0.f, 0.f, 0.f, 0.8f));
			Canvas->DrawItem(Item);
		}

		void TextRight(float Right, float Y, const FString& String, const FLinearColor& Color) const
		{
			Text(Right - Width(String), Y, String, Color);
		}

		void Rect(float X, float Y, float W, float H, const FLinearColor& Color) const
		{
			FCanvasTileItem Tile(FVector2D(X, Y), FVector2D(W, H), Color);
			Tile.BlendMode = SE_BLEND_Translucent;
			Canvas->DrawItem(Tile);
		}

		void Line(const FVector2D& A, const FVector2D& B, const FLinearColor& Color, float Thickness = 1.f) const
		{
			FCanvasLineItem Item(A, B);
			Item.SetColor(Color);
			Item.LineThickness = Thickness * Scale;
			Canvas->DrawItem(Item);
		}
	};
}

bool UPerformanceOverlaySubsystem::ShouldCreateSubsystem(UObject* Outer) const
{
	return !IsRunningDedicatedServer() && Super::ShouldCreateSubsystem(Outer);
}

void UPerformanceOverlaySubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	using namespace PerformanceOverlay;
	Super::Initialize(Collection);

	History.SetNum(HistoryLength);
	CpuName = FPlatformMisc::GetCPUBrand().TrimStartAndEnd();
	CpuThreads = FPlatformMisc::NumberOfCoresIncludingHyperthreads();
	GpuName = GRHIAdapterName.TrimStartAndEnd();
	RhiName = GDynamicRHI ? FString(GDynamicRHI->GetName()) : FString();

	DrawHandle = UDebugDrawService::Register(TEXT("Game"),
		FDebugDrawDelegate::CreateUObject(this, &UPerformanceOverlaySubsystem::Draw));
}

void UPerformanceOverlaySubsystem::Deinitialize()
{
	UDebugDrawService::Unregister(DrawHandle);
	Super::Deinitialize();
}

EPerformanceOverlayMode UPerformanceOverlaySubsystem::GetMode() const
{
	using namespace PerformanceOverlay;
	return static_cast<EPerformanceOverlayMode>(FMath::Clamp(CVarMode.GetValueOnGameThread(), 0, 2));
}

void UPerformanceOverlaySubsystem::SetMode(EPerformanceOverlayMode Mode)
{
	using namespace PerformanceOverlay;
	CVarMode->Set(static_cast<int32>(Mode), ECVF_SetByCode);
}

void UPerformanceOverlaySubsystem::CycleMode()
{
	switch (GetMode())
	{
	case EPerformanceOverlayMode::Full:		SetMode(EPerformanceOverlayMode::Compact); break;
	case EPerformanceOverlayMode::Compact:	SetMode(EPerformanceOverlayMode::Off); break;
	default:								SetMode(EPerformanceOverlayMode::Full); break;
	}
}

void UPerformanceOverlaySubsystem::Sample()
{
	using namespace PerformanceOverlay;
	FFrameSample Raw;
	// Same sources as `stat unit`, so the two always agree.
	Raw.FrameMs = static_cast<float>((FApp::GetCurrentTime() - FApp::GetLastTime()) * 1000.0);
	Raw.GameMs = FPlatformTime::ToMilliseconds(GGameThreadTime);
	Raw.RenderMs = FPlatformTime::ToMilliseconds(GRenderThreadTime);
	Raw.RhiMs = FPlatformTime::ToMilliseconds(GRHIThreadTime);
	Raw.GpuMs = FPlatformTime::ToMilliseconds(RHIGetGPUFrameCycles(0));

	auto Smooth = [](float& Current, float New) { Current = 0.9f * Current + 0.1f * New; };
	Smooth(Smoothed.FrameMs, Raw.FrameMs);
	Smooth(Smoothed.GameMs, Raw.GameMs);
	Smooth(Smoothed.RenderMs, Raw.RenderMs);
	Smooth(Smoothed.RhiMs, Raw.RhiMs);
	Smooth(Smoothed.GpuMs, Raw.GpuMs);

	HistoryHead = (HistoryHead + 1) % HistoryLength;
	History[HistoryHead] = Raw;
}

void UPerformanceOverlaySubsystem::SampleSlowStats()
{
	const double Now = FPlatformTime::Seconds();
	if (Now < NextSlowUpdate)
	{
		return;
	}
	NextSlowUpdate = Now + 0.25;

	// Process CPU use as a share of the whole machine; refreshed by the platform's own ticker.
	ProcessCpuPercent = FPlatformTime::GetCPUTime().CPUTimePct;

	const FPlatformMemoryStats Memory = FPlatformMemory::GetStats();
	ProcessMemoryBytes = Memory.UsedPhysical;
	TotalMemoryBytes = Memory.TotalPhysical;

	// VRAM: the OS budget and current use (cached by the RHI each frame), else the card's dedicated size.
	FRHIMemoryStats RhiMemory;
	RHIGetMemoryStats(RhiMemory);
	if (RhiMemory.IsValid())
	{
		VideoMemoryUsedBytes = RhiMemory.UsedLocal;
		VideoMemoryTotalBytes = static_cast<int64>(RhiMemory.BudgetLocal);
	}
	else
	{
		FTextureMemoryStats TextureMemory;
		RHIGetTextureMemoryStats(TextureMemory);
		VideoMemoryTotalBytes = TextureMemory.DedicatedVideoMemory;
	}

	// True GPU utilisation needs a provider such as the ExternalGPUStatistics plugin; otherwise it is estimated.
	if (GRHISupportsGPUUsage && RHIGetGPUUsage)
	{
		const FRHIGPUUsageFractions Usage = RHIGetGPUUsage(0);
		GpuUsagePercent = Usage.CurrentProcessMHz * 100.f;
		if (!RhiMemory.IsValid())
		{
			VideoMemoryUsedBytes = Usage.CurrentProcessMemoryUsage;
		}
	}
	else
	{
		GpuUsagePercent = -1.f;
	}

	DrawCalls = GNumDrawCallsRHI[0];
	PrimitivesDrawn = GNumPrimitivesDrawnRHI[0];
}

FString UPerformanceOverlaySubsystem::GetBoundBy(FLinearColor& OutColor) const
{
	using namespace PerformanceOverlay;
	const float CpuMs = FMath::Max3(Smoothed.GameMs, Smoothed.RenderMs, Smoothed.RhiMs);
	const float Slowest = FMath::Max(CpuMs, Smoothed.GpuMs);

	// Neither side fills the frame: a frame-rate cap or vsync is holding it back.
	if (Smoothed.FrameMs > Slowest * 1.2f + 1.f)
	{
		OutColor = LabelColor;
		return TEXT("Frame cap / vsync");
	}
	if (Smoothed.GpuMs >= CpuMs)
	{
		OutColor = GpuColor;
		return TEXT("GPU bound");
	}
	if (Smoothed.GameMs >= Smoothed.RenderMs && Smoothed.GameMs >= Smoothed.RhiMs)
	{
		OutColor = GameColor;
		return TEXT("CPU bound (game)");
	}
	OutColor = Smoothed.RenderMs >= Smoothed.RhiMs ? RenderColor : RhiColor;
	return Smoothed.RenderMs >= Smoothed.RhiMs ? TEXT("CPU bound (render)") : TEXT("CPU bound (RHI)");
}

void UPerformanceOverlaySubsystem::Draw(UCanvas* Canvas, APlayerController* PlayerController)
{
	const EPerformanceOverlayMode Mode = GetMode();
	// The draw service is global: only draw into viewports that belong to this game instance.
	if (Mode == EPerformanceOverlayMode::Off || !Canvas || !PlayerController || PlayerController->GetGameInstance() != GetGameInstance())
	{
		return;
	}

	Sample();
	SampleSlowStats();

	const float Scale = FMath::Clamp(Canvas->ClipY / 1080.f, 0.85f, 2.5f);
	if (Mode == EPerformanceOverlayMode::Compact)
	{
		DrawCompact(Canvas, Scale);
	}
	else
	{
		DrawFull(Canvas, Scale);
	}
}

void UPerformanceOverlaySubsystem::DrawCompact(UCanvas* Canvas, float Scale) const
{
	using namespace PerformanceOverlay;
	const FPainter P{ Canvas, GEngine->GetSmallFont(), Scale };
	const float CpuMs = FMath::Max3(Smoothed.GameMs, Smoothed.RenderMs, Smoothed.RhiMs);
	const FString Fps = FString::Printf(TEXT("%.0f FPS  %.1f ms"), 1000.f / FMath::Max(Smoothed.FrameMs, 0.01f), Smoothed.FrameMs);
	const FString Cpu = FString::Printf(TEXT("   CPU %.1f ms"), CpuMs);
	const FString Gpu = FString::Printf(TEXT("   GPU %.1f ms"), Smoothed.GpuMs);

	const float Pad = 8.f * Scale;
	const float W = P.Width(Fps) + P.Width(Cpu) + P.Width(Gpu) + 2 * Pad;
	const float X = Canvas->ClipX - W - 16.f * Scale;
	const float Y = 16.f * Scale;
	P.Rect(X, Y, W, P.LineHeight() + Pad, PanelColor);
	float Cursor = X + Pad;
	P.Text(Cursor, Y + Pad * 0.5f, Fps, Budget(Smoothed.FrameMs));
	Cursor += P.Width(Fps);
	P.Text(Cursor, Y + Pad * 0.5f, Cpu, GameColor);
	Cursor += P.Width(Cpu);
	P.Text(Cursor, Y + Pad * 0.5f, Gpu, GpuColor);
}

void UPerformanceOverlaySubsystem::DrawFull(UCanvas* Canvas, float Scale) const
{
	using namespace PerformanceOverlay;
	const FPainter P{ Canvas, GEngine->GetSmallFont(), Scale };
	const float LH = P.LineHeight();
	const float Pad = 10.f * Scale;
	const float W = 340.f * Scale;
	const float GraphH = 74.f * Scale;
	const float TextRows = 12.f;
	const float H = Pad * 2 + LH * TextRows + GraphH + 18.f * Scale;
	const float X = Canvas->ClipX - W - 16.f * Scale;
	const float Left = X + Pad;
	const float Right = X + W - Pad;
	float Y = 16.f * Scale;

	P.Rect(X, Y, W, H, PanelColor);
	Y += Pad;

	auto DividerAt = [&](float At) { P.Line(FVector2D(Left, At), FVector2D(Right, At), DividerColor); };
	auto Bar = [&](const FString& Name, float Ms, const FLinearColor& Color)
	{
		P.Text(Left + 8.f * Scale, Y, Name, LabelColor);
		P.TextRight(Right, Y, FString::Printf(TEXT("%.1f ms"), Ms), ValueColor);
		const float BarX = Left + 78.f * Scale;
		const float BarW = W - 2 * Pad - 78.f * Scale - 64.f * Scale;
		const float BarY = Y + LH * 0.3f;
		P.Rect(BarX, BarY, BarW, LH * 0.38f, FLinearColor(1.f, 1.f, 1.f, 0.06f));
		P.Rect(BarX, BarY, BarW * FMath::Clamp(Ms / BarCeilingMs, 0.f, 1.f), LH * 0.38f, Color);
		Y += LH;
	};

	// Header: FPS and what is limiting the frame.
	P.Text(Left, Y, TEXT("PERFORMANCE"), ValueColor);
	P.TextRight(Right, Y, TEXT("F6"), LabelColor);
	Y += LH;
	P.Text(Left, Y, FString::Printf(TEXT("%.0f FPS   %.1f ms"), 1000.f / FMath::Max(Smoothed.FrameMs, 0.01f), Smoothed.FrameMs),
		Budget(Smoothed.FrameMs));
	FLinearColor BoundColor;
	const FString Bound = GetBoundBy(BoundColor);
	P.TextRight(Right, Y, Bound, BoundColor);
	Y += LH + 4.f * Scale;
	DividerAt(Y - 2.f * Scale);

	// CPU
	P.Text(Left, Y, TEXT("CPU"), ValueColor);
	P.TextRight(Right, Y, FString::Printf(TEXT("%s  %d threads"), *CpuName.Left(30), CpuThreads), LabelColor);
	Y += LH;
	Bar(TEXT("Game"), Smoothed.GameMs, GameColor);
	Bar(TEXT("Render"), Smoothed.RenderMs, RenderColor);
	Bar(TEXT("RHI"), Smoothed.RhiMs, RhiColor);
	P.Text(Left + 8.f * Scale, Y, TEXT("Process"), LabelColor);
	P.TextRight(Right, Y, FString::Printf(TEXT("%.0f%% CPU   RAM %s / %s GB"), ProcessCpuPercent,
		*Gigabytes(ProcessMemoryBytes), *Gigabytes(TotalMemoryBytes)), ValueColor);
	Y += LH + 4.f * Scale;
	DividerAt(Y - 2.f * Scale);

	// GPU
	P.Text(Left, Y, TEXT("GPU"), ValueColor);
	P.TextRight(Right, Y, GpuName.Left(36), LabelColor);
	Y += LH;
	Bar(TEXT("Frame"), Smoothed.GpuMs, GpuColor);
	P.Text(Left + 8.f * Scale, Y, TEXT("Usage"), LabelColor);
	const FString Usage = GpuUsagePercent >= 0.f ? FString::Printf(TEXT("%.0f%%"), GpuUsagePercent)
		: FString::Printf(TEXT("~%.0f%%"), 100.f * FMath::Clamp(Smoothed.GpuMs / FMath::Max(Smoothed.FrameMs, 0.01f), 0.f, 1.f));
	const bool bKnownUse = VideoMemoryUsedBytes > 0 && VideoMemoryTotalBytes > 0;
	const FString Vram = bKnownUse
		? FString::Printf(TEXT("VRAM %s / %s GB"), *Gigabytes(VideoMemoryUsedBytes), *Gigabytes(VideoMemoryTotalBytes))
		: VideoMemoryTotalBytes > 0 ? FString::Printf(TEXT("VRAM %s GB"), *Gigabytes(VideoMemoryTotalBytes)) : FString(TEXT("VRAM n/a"));
	// Over the OS budget the driver starts paging VRAM to system memory: flag it red.
	const bool bOverBudget = bKnownUse && VideoMemoryUsedBytes > static_cast<uint64>(VideoMemoryTotalBytes);
	P.TextRight(Right, Y, Vram, bOverBudget ? Budget(1000.f) : ValueColor);
	P.Text(Left + 78.f * Scale, Y, Usage, ValueColor);
	Y += LH;
	P.Text(Left + 8.f * Scale, Y, TEXT("Draws"), LabelColor);
	P.TextRight(Right, Y, FString::Printf(TEXT("%s calls   %.2fM prims"), *FText::AsNumber(DrawCalls).ToString(),
		PrimitivesDrawn / 1.0e6f), ValueColor);
	Y += LH + 6.f * Scale;

	// Frame-time graph with 60 and 30 fps reference lines.
	const float GX = Left, GW = Right - Left, GY = Y;
	P.Rect(GX, GY, GW, GraphH, GraphBackColor);
	auto MsToY = [&](float Ms) { return GY + GraphH - GraphH * FMath::Clamp(Ms / GraphCeilingMs, 0.f, 1.f); };
	for (const float Ref : { 16.7f, 33.3f })
	{
		P.Line(FVector2D(GX, MsToY(Ref)), FVector2D(GX + GW, MsToY(Ref)), FLinearColor(1.f, 1.f, 1.f, 0.16f));
	}
	auto Plot = [&](float FFrameSample::* Field, const FLinearColor& Color, float Thickness)
	{
		FVector2D Previous;
		for (int32 i = 0; i < HistoryLength; ++i)
		{
			const FFrameSample& S = History[(HistoryHead + 1 + i) % HistoryLength];
			const FVector2D Point(GX + GW * i / (HistoryLength - 1), MsToY(S.*Field));
			if (i > 0)
			{
				P.Line(Previous, Point, Color, Thickness);
			}
			Previous = Point;
		}
	};
	Plot(&FFrameSample::GpuMs, GpuColor, 1.4f);
	Plot(&FFrameSample::GameMs, GameColor, 1.4f);
	Plot(&FFrameSample::FrameMs, FrameColor, 1.0f);
	P.Text(GX + 4.f * Scale, MsToY(16.7f) - LH * 0.9f, TEXT("60"), LabelColor);
	P.Text(GX + 4.f * Scale, MsToY(33.3f) - LH * 0.9f, TEXT("30"), LabelColor);
	Y += GraphH + 4.f * Scale;

	// Legend and display info.
	float Cursor = Left;
	for (const TPair<const TCHAR*, FLinearColor>& Entry : { TPair<const TCHAR*, FLinearColor>(TEXT("frame"), FrameColor),
		TPair<const TCHAR*, FLinearColor>(TEXT("game"), GameColor), TPair<const TCHAR*, FLinearColor>(TEXT("GPU"), GpuColor) })
	{
		P.Rect(Cursor, Y + LH * 0.42f, 10.f * Scale, 2.f * Scale, Entry.Value);
		P.Text(Cursor + 14.f * Scale, Y, Entry.Key, LabelColor);
		Cursor += P.Width(Entry.Key) + 28.f * Scale;
	}
	P.TextRight(Right, Y, FString::Printf(TEXT("%dx%d  %s"), FMath::RoundToInt(Canvas->ClipX), FMath::RoundToInt(Canvas->ClipY), *RhiName), LabelColor);
}
