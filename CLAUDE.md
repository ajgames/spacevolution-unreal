# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Spacevolution is an Unreal Engine 5.8 project: DX12/SM6, Lumen, Substrate and ray tracing, with no static lighting. It has two halves:

- **C++ runtime module `Spacevolution`** (`Source/Spacevolution`) holds the gameplay frameworks: the modular ship, zero-point flight, the ocean and the wave rider.
- **Python generators** (`Scripts/`) run inside the editor and produce nearly all content: Geometry Script meshes, materials, Blueprints, data assets, input assets and the levels themselves.

Work happens from WSL against the Windows project folder (`/home/jake/games/Spacevolution-unreal` is a symlink to it). **The project is not under git**, so there's no way to recover an overwritten source file or asset.

## Commands

There is no test suite or linter. To verify a change, build the C++, rerun the generator, then check hero-camera screenshots or play in PIE.

**Build C++.** The editor must be closed, and new classes, UPROPERTYs or UFUNCTIONs need an editor restart anyway. Quoting through `cmd.exe` breaks from WSL, so go through PowerShell:

```bash
powershell.exe -Command "& 'C:\Program Files\Epic Games\UE_5.8\Engine\Build\BatchFiles\Build.bat' SpacevolutionEditor Win64 Development '-Project=C:\Users\Jake\Documents\Unreal Projects\Spacevolution\Spacevolution.uproject' -WaitMutex"
```

Ask the user before closing their editor. Close it with `taskkill.exe /IM UnrealEditor.exe` and no `/F`, so the save prompt still protects unsaved work. For `.cpp`-only changes, Live Coding (console command `LiveCoding.Compile`) patches the running editor. That patch lives only in memory, so do a real build before finishing. UBT refuses to build while Live Coding is active. Constructor changes don't reach existing CDOs until a restart.

**Run Python in the live editor.** Python Remote Execution is enabled in `Config/DefaultEngine.ini`. Use the engine's *Windows* Python, not WSL's. Pass the script as a quoted Windows path (`wslpath -w`), not as pasted source:

```bash
"/mnt/c/Program Files/Epic Games/UE_5.8/Engine/Binaries/ThirdParty/Python3/Win64/python.exe" - "$(wslpath -w Scripts/build_ship.py)" <<'EOF'
import sys, time
sys.path.insert(0, r'C:\Program Files\Epic Games\UE_5.8\Engine\Plugins\Experimental\PythonScriptPlugin\Content\Python')
import remote_execution as rx
r = rx.RemoteExecution(); r.start()
for _ in range(50):
    if r.remote_nodes: break
    time.sleep(0.1)
r.open_command_connection(r.remote_nodes[0]['node_id'])
res = r.run_command(f'"{sys.argv[1]}"', exec_mode=rx.MODE_EXEC_FILE)
r.stop()
for o in res['output']: print(o['output'], end='')
print('success:', res['success'])
EOF
```

For a one-liner, use `exec_mode=rx.MODE_EXEC_STATEMENT` with the code as the command. Inside the editor, the equivalent is `py "<project>/Scripts/build_<x>.py"` in the Output Log's Python console.

- Scripting fails with "The Editor is currently in a play mode" while the user is in PIE. Wait instead of retrying.
- Remote-exec scripts share one Python global namespace across runs. Reset globals explicitly rather than branching on `"X" in globals()`.
- **API reference:** `Intermediate/PythonStub/unreal.py`. Grep it before guessing a name. A UFUNCTION that returns bool and has an out-param returns the out value on success and `None` on failure in Python.

**Preview layouts without the editor.** `layout.py`, `noise.py`, `town/plan.py` and `town/shape.py` don't import `unreal`:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=Scripts python3 -c "from town import plan; p = plan.make(); print(len(p.buildings))"
```

## Generators (`Scripts/`)

| Entry script | Package | Owns | Level |
|---|---|---|---|
| `build_ship.py` | `ship/` | `/Game/Ship`, `/Game/Player` | `L_ShipInterior` (startup and game-default map) |
| `build_colony.py` | `colony/` | `/Game/Colony` | `L_MarsColony` |
| `build_town.py` | `town/` | `/Game/Town` | `L_BiodiverCity` |
| `build_orbital_window.py` | (single file, older style) | `/Game/OrbitalWindow` | `OrbitalWindow` |

**Generated content is disposable.** Change the generator and rerun it; never hand-edit generated assets. A rerun does the following:
- It reuses existing assets in place (`util.load_or_create`), so references from levels survive.
- It deletes every non-native component on generated Blueprints and adds the generated ones back, so components added by hand are lost.
- It deletes and respawns every actor in the generator's level outliner folders (`FOLDERS` in each `level.py`).

Warn the user before regenerating if they've been hand-authoring under one of these roots.

**Package structure.** Each entry script puts `Scripts/` on `sys.path`, then calls `<pkg>.build.reload_all()` and `<pkg>.build.main()`. `main()` runs named stages through `util.step()`. A failing stage logs its traceback and is added to `util.FAILURES` rather than aborting the run. Check the log for `finished with failures in:`.

**Shared code flows one way: ship → colony → town.**
- `colony` imports `ship.geo`, `ship.util` and `ship.materials`.
- `town` imports those plus `colony.geo` and `colony.noise`.
- `reload_all()` reloads the shared modules first. A new shared import must be added there, or edits to it won't take effect without an editor restart.
- Colony and town materials are instances of the ship kit's masters (`/Game/Ship/Materials/M_ShipSurface`, `M_ShipGlass`). The ship kit must have been built at least once before them.

**Units.** UE works in centimetres. Each `layout.py` (the source of truth for its scene's composition, hero camera included) is in metres and converts through `util.M`. The ship grid is 600 cm cells with the deck at Z=0.

## C++ module (`Source/Spacevolution`)

Dependencies: Core, CoreUObject, Engine (public); EnhancedInput, RenderCore, RHI (private). Plugins: PythonScriptPlugin, GeometryScripting, EnhancedInput, ModelingToolsEditorMode, ModelContextProtocol. The log category is `LogShip`.

**Python ↔ C++ contract.** The generators spawn and configure C++ types by their reflected names: `unreal.Ship`, `ShipModulePlacement`, `ShipLayout`, `ShipCellFace`, `Ocean`, `OceanWave`, `WaveRider`, `TownInstances`, `SpaceEnvironment`, `SpacevolutionGameMode`. Renaming a class, UPROPERTY or enum value breaks the generators, so grep `Scripts/` when you do. Python only sees reflection changes after a rebuild and an editor restart. After setting defaults on a Blueprint CDO from Python, compile the Blueprint *again*. Otherwise spawned instances ignore the new values.

**Ship (`Ship/`).**
- `AShip::Layout` (`FShipLayout`) is the source of truth that gets saved, loaded and edited. Spawned `AShipModule` actors are derived from it by `Rebuild()`.
- Runtime editing must go through `AddModule`, `RemoveModuleAt` and `SetFixture` so the layout stays authoritative.
- Modules and fixtures are `UPrimaryDataAsset` definitions (`ShipPartDefinitions.h`). The Asset Manager scans for them under `/Game/Ship` (see `Config/DefaultGame.ini`).
- Placement is checked against typed connectors on cell faces. Fixtures mount on hardpoint components whose slot types are Chamfer, Wall, Ceiling and Floor.

**Zero-point flight.**
- The ship never moves in the level. `UShipFlightComponent` keeps a pose in a planet-centred space frame (km, double).
- `ASpaceEnvironment` moves the SkyAtmosphere planet and the sun each frame. It also pushes `SpaceOrigin` and `SpaceAxisX/Y/Z` into the cloud and star-backdrop MIDs.
- Any non-ship actor near the origin must have no collision. The 200 km backdrop sphere once launched spawning players into space.

**Ocean and wave rider (`Ocean/`, `WaveRider/`, `Town/`).**
- `AOcean` evaluates Gerstner waves and calm zones on the CPU (`SampleSurface`) and pushes them to the `M_Ocean` MID as `Wave0..7` and `Calm0..15`.
- The WPO HLSL in `Scripts/town/ocean.py` must match `AOcean::Displace` exactly, and `MAX_WAVES`/`MAX_CALM` must match the C++ constants. Change both sides together.
- `AWaveRider` is a physics pawn floating on four spring lift rings.
- `L_BiodiverCity` overrides the GameMode with `BP_WaveRiderGameMode`. Every other map uses the global `BP_ShipGameMode`.

## Rendering gotchas hit in this project

- Any `is_sky` material in the scene stops SkyAtmosphere from drawing sky pixels. That's why the star backdrop is an additive unlit shell that ray-traces the planet in-shader.
- Volumetric cloud materials need `used_with_volumetric_cloud = True`. Without it they render purple garbage, with no compile error.
- Single Layer Water scattering and absorption are per **centimetre**, so scale per-metre values by 0.01. Create the `SingleLayerWaterMaterialOutput` node before switching the shading model.
- `connect_material_expressions(vec_param, "RGBA", ...)` passes a float4, while the default `""` output is a float3.
- Geometry Script `append_buffers_to_mesh` only takes UV layers consecutively from `uv0`. The target mesh also needs `set_num_uv_sets` before `append_mesh`, or UV1 is dropped.

## Screenshots

- Use `unreal.AutomationLibrary.take_high_res_screenshot(..., camera=cam, delay=1.5)`. It's latent, and the image lands in `Saved/Screenshots/WindowsEditor/`. Without the delay, Lumen/TSR noise speckles metals.
- An unfocused editor throttles and never renders the shot. Temporarily set `bThrottleCPUWhenNotForeground` to False (that exact C++ name) on `/Script/UnrealEd.Default__EditorPerformanceSettings`, then restore it afterwards.
- For PIE:
  - `LevelEditorSubsystem.editor_request_begin_play()` / `editor_request_end_play()` start and stop it.
  - `UnrealEditorSubsystem.get_game_world()` gives the game world.
  - `HighResShot` via `execute_console_command` takes gameplay screenshots.
- Slate post-tick callbacks outlive PIE sessions. Give each input-injection test its own state and handle, and never run two at once.
