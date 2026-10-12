"""Import <project>/SourceAudio into /Game/Audio as Sound Waves. Runs inside the editor.

Folders are mirrored: SourceAudio/SFX/Door/DoorOpen_01.wav becomes /Game/Audio/SFX/Door/DoorOpen_01. New files are
imported and changed files reimported (asset settings are kept). Anything with "loop" in its name is set to loop.

SourceAudio/.imported.json remembers what has been imported, so deleting an unwanted take in the Content Browser
sticks; pass --force to reimport everything. Assets are never deleted when their source file goes away.

Runs at editor startup (StartupScripts in Config/DefaultEngine.ini) and from Scripts/sfx.py in WSL.
"""
import json
import os
import re
import sys

import unreal

EXTENSIONS = {".wav", ".flac", ".ogg", ".mp3", ".aif", ".aiff", ".opus"}
MOUNT = "/Game/Audio"
PROJECT = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
SOURCE = os.path.join(PROJECT, "SourceAudio")
STATE = os.path.join(SOURCE, ".imported.json")


def log(msg):
    unreal.log(f"[Audio] {msg}")


def asset_name(text):
    return re.sub(r"[^A-Za-z0-9_]", "_", text)


def _load_state():
    try:
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _sources():
    """(relative path, absolute path, destination folder, asset name) for every importable file."""
    for root, dirs, files in os.walk(SOURCE):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        rel_dir = os.path.relpath(root, SOURCE)
        parts = [] if rel_dir == "." else [asset_name(p) for p in rel_dir.split(os.sep)]
        for filename in sorted(files):
            stem, ext = os.path.splitext(filename)
            if ext.lower() in EXTENSIONS:
                rel = "/".join(parts + [filename])
                yield rel, os.path.join(root, filename), "/".join([MOUNT] + parts), asset_name(stem)


def _signature(path):
    st = os.stat(path)
    return [round(st.st_mtime, 3), st.st_size]


def sync(force=False):
    """Import new and changed files. Returns the imported asset paths."""
    if not os.path.isdir(SOURCE):
        return []
    state = _load_state()
    todo = [s for s in _sources() if force or state.get(s[0]) != _signature(s[1])]
    if not todo:
        return []

    tasks = []
    for _, path, folder, name in todo:
        task = unreal.AssetImportTask()
        task.set_editor_property("filename", path)
        task.set_editor_property("destination_path", folder)
        task.set_editor_property("destination_name", name)
        task.set_editor_property("replace_existing", True)
        task.set_editor_property("automated", True)
        task.set_editor_property("save", True)
        tasks.append(task)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)

    imported = []
    for task, (rel, path, folder, name) in zip(tasks, todo):
        wave = next((o for o in task.get_objects() if isinstance(o, unreal.SoundWave)), None)
        if wave is None:
            unreal.log_warning(f"[Audio] Could not import {path}")
            continue
        if "loop" in name.lower() and not wave.get_editor_property("looping"):
            wave.set_editor_property("looping", True)
            unreal.EditorAssetLibrary.save_loaded_asset(wave)
        state[rel] = _signature(path)
        imported.append(f"{folder}/{name}")
        log(f"{folder}/{name}  {wave.get_editor_property('duration'):.2f}s"
            f"{'  loop' if wave.get_editor_property('looping') else ''}")

    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=1, sort_keys=True)
    log(f"Imported {len(imported)} of {len(todo)} sound(s) from SourceAudio")
    return imported


def on_editor_startup():
    """StartupScripts hook. Commandlets (cooking, packaging) run startup scripts too; never import during those."""
    if "-run=" not in unreal.SystemLibrary.get_command_line().lower():
        sync()


if __name__ == "__main__":
    if not sync(force="--force" in sys.argv[1:]):
        log("No new sounds imported")
