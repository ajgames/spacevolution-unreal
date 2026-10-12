#!/usr/bin/env python3
"""Game sound effects: make them with the claude-music SFX skill and load them into the editor. Run from WSL.

  python3 Scripts/sfx.py generate Door/DoorOpen --prompt "pneumatic hiss, then servo whir" --duration 4
  python3 Scripts/sfx.py add Drive/SurgeEngage ~/Music/claude-music-output/sfx-....flac [more files...]
  python3 Scripts/sfx.py loop Drive/DriveHumLoop SourceAudio/SFX/Drive/DriveHum_01.wav --start 3 --end 20
  python3 Scripts/sfx.py import [--force]

Each take is saved as SourceAudio/SFX/<Name>_NN.<ext> (NN counts up; nothing is overwritten) and imported to
/Game/Audio/SFX/<Name>_NN by audio_import.py: straight away if the editor is open, otherwise when it next starts.
Put "Loop" in the name of sounds that should loop. Prompts and seeds are logged to SourceAudio/takes.jsonl.

`generate` passes --quality and --seed to the engine and everything else (--prompt, --duration, --batch, --negative,
--guidance-scale, --steps, --no-trim) to its generate command; see the claude-music-sfx skill for what they do.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
PROJECT = SCRIPTS.parent
SOURCE = PROJECT / "SourceAudio"
SFX = SOURCE / "SFX"
TAKES_LOG = SOURCE / "takes.jsonl"
SFX_ENGINE = Path(os.environ.get("CLAUDE_MUSIC_SFX", "~/.claude/skills/claude-music/scripts/sfx_engine.sh")).expanduser()
EXTENSIONS = {".wav", ".flac", ".ogg", ".mp3", ".aif", ".aiff", ".opus"}


def ue_root():
    if os.environ.get("UE_ROOT"):
        return Path(os.environ["UE_ROOT"])
    association = json.loads((PROJECT / "Spacevolution.uproject").read_text())["EngineAssociation"]
    if not association.startswith("{"):
        return Path(f"/mnt/c/Program Files/Epic Games/UE_{association}")
    # A GUID: the engine was registered by path in HKCU\Software\Epic Games\Unreal Engine\Builds.
    query = subprocess.run(["reg.exe", "query", r"HKCU\Software\Epic Games\Unreal Engine\Builds", "/v", association],
                           capture_output=True, text=True).stdout
    match = re.search(r"REG_SZ\s+(.+)", query)
    if not match:
        sys.exit(f"Can't find the engine for EngineAssociation {association}; set UE_ROOT")
    return Path(subprocess.run(["wslpath", "-u", match.group(1).strip()], check=True, capture_output=True,
                               text=True).stdout.strip())


def windows_path(path):
    return subprocess.run(["wslpath", "-w", str(path)], check=True, capture_output=True, text=True).stdout.strip()


def take_paths(name, count):
    """The next `count` free SourceAudio/SFX/<Name>_NN paths, without extension. Name may have folders: Door/DoorOpen."""
    parts = [p for p in name.replace("\\", "/").split("/") if p]
    if not parts or any(p in (".", "..") for p in parts):
        sys.exit(f"Bad sound name {name!r}; use something like Door/DoorOpen")
    parts = [re.sub(r"[^A-Za-z0-9_]", "_", p) for p in parts]
    folder = SFX.joinpath(*parts[:-1])
    folder.mkdir(parents=True, exist_ok=True)
    pattern = re.compile(rf"{re.escape(parts[-1])}_(\d+)\.\w+$", re.IGNORECASE)
    start = max((int(m.group(1)) for f in folder.iterdir() if (m := pattern.match(f.name))), default=0) + 1
    return [folder / f"{parts[-1]}_{n:02d}" for n in range(start, start + count)]


def log_take(path, **info):
    entry = {"file": path.relative_to(SOURCE).as_posix(), "added": datetime.now().isoformat(timespec="seconds"), **info}
    with TAKES_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    print(f"  {path.relative_to(PROJECT)}")


def import_into_editor(force=False):
    python = ue_root() / "Engine/Binaries/ThirdParty/Python3/Win64/python.exe"
    args = [str(python), windows_path(SCRIPTS / "ue_exec.py"), windows_path(SCRIPTS / "audio_import.py")]
    sys.stdout.flush()
    code = subprocess.run(args + (["--force"] if force else [])).returncode
    if code == 2:
        print("The editor isn't open; these will be imported when it next starts.")
    elif code == 3:
        print("The editor is in Play mode; stop it and run `python3 Scripts/sfx.py import` (or restart the editor).")
    elif code:
        sys.exit(f"Import failed (exit {code})")


def cmd_generate(args, engine_args):
    if not SFX_ENGINE.exists():
        sys.exit(f"claude-music SFX engine not found at {SFX_ENGINE} (set CLAUDE_MUSIC_SFX)")
    with tempfile.TemporaryDirectory(prefix="sfx-") as stage:
        command = ["bash", str(SFX_ENGINE), "--format", "wav", "--output-dir", stage]
        if args.quality:
            command += ["--quality", args.quality]
        if args.seed is not None:
            command += ["--seed", str(args.seed)]
        # Progress goes to stderr and passes straight through; the JSON result is on stdout.
        run = subprocess.run(command + ["generate", *engine_args], stdout=subprocess.PIPE, text=True)
        try:
            result = json.loads(run.stdout[run.stdout.index("{"):])
        except ValueError:
            result = {}
        if not result.get("success"):
            sys.exit(run.stdout.strip() or f"SFX engine failed (exit {run.returncode})")

        outputs = sorted(result["outputs"], key=lambda o: o["index"])
        for out, dest in zip(outputs, take_paths(args.name, len(outputs))):
            src = Path(out["path"])
            dest = dest.with_suffix(src.suffix)
            shutil.move(src, dest)
            log_take(dest, prompt=result["params"]["prompt"], seed=out["seed"], duration_sec=out["duration_sec"],
                     quality=result.get("quality"), params=result["params"])
    import_into_editor()


def audio_python():
    """A Python with numpy and soundfile: the claude-music Stable Audio environment's."""
    if os.environ.get("SFX_PYTHON"):
        return os.environ["SFX_PYTHON"]
    config = json.loads((SFX_ENGINE.parent.parent / "config.json").read_text())
    return str(Path(config["stable_audio_dir"]).expanduser() / ".venv" / "bin" / "python")


def cmd_loop(args):
    src = Path(args.file).expanduser()
    if not src.is_file():
        sys.exit(f"No such file: {src}")
    dest = take_paths(args.name, 1)[0].with_suffix(".wav")
    command = [audio_python(), "-I", str(SCRIPTS / "sfx_loop.py"), str(src), str(dest), "--start", str(args.start),
               "--crossfade", str(args.crossfade)] + (["--end", str(args.end)] if args.end is not None else [])
    run = subprocess.run(command, stdout=subprocess.PIPE, text=True)
    if run.returncode:
        sys.exit(run.returncode)
    log_take(dest, loop_of=str(src), start=args.start, end=args.end, crossfade=args.crossfade,
             duration_sec=float(run.stdout.strip()))
    import_into_editor()


def cmd_add(args):
    files = [Path(f).expanduser() for f in args.files]
    for f in files:
        if not f.is_file() or f.suffix.lower() not in EXTENSIONS:
            sys.exit(f"Not an importable audio file: {f}")
    for src, dest in zip(files, take_paths(args.name, len(files))):
        dest = dest.with_suffix(src.suffix.lower())
        shutil.copy2(src, dest)
        log_take(dest, source=str(src))
    import_into_editor()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", allow_abbrev=False, help="Generate takes with Stable Audio Open and import them")
    gen.add_argument("name", help="Sound name, optionally in folders: Door/DoorOpen, Ambience/EngineRoomLoop")
    gen.add_argument("--quality", choices=["draft", "standard", "max"])
    gen.add_argument("--seed", type=int)

    add = sub.add_parser("add", help="Copy existing audio files in as takes and import them")
    add.add_argument("name")
    add.add_argument("files", nargs="+")

    loop = sub.add_parser("loop", help="Make a seamless loop from a stretch of a file and import it")
    loop.add_argument("name", help="Include Loop in it, e.g. Drive/DriveHumLoop, so the asset is set to loop")
    loop.add_argument("file")
    loop.add_argument("--start", type=float, default=0.0, help="Seconds to skip, e.g. a fade-in")
    loop.add_argument("--end", type=float, help="Where the loop ends, before any fade-out")
    loop.add_argument("--crossfade", type=float, default=1.5)

    imp = sub.add_parser("import", help="Import anything new in SourceAudio into the open editor")
    imp.add_argument("--force", action="store_true", help="Reimport everything")

    args, extra = parser.parse_known_args()
    if args.command == "generate":
        cmd_generate(args, extra)
    elif extra:
        parser.error(f"unrecognized arguments: {' '.join(extra)}")
    elif args.command == "add":
        cmd_add(args)
    elif args.command == "loop":
        cmd_loop(args)
    else:
        import_into_editor(args.force)


if __name__ == "__main__":
    main()
