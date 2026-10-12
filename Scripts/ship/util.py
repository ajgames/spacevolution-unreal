"""Editor handles and small helpers shared by the ship kit build scripts."""
import traceback

import unreal

ROOT = "/Game/Ship"

EAS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
LES = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
UES = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
EAL = unreal.EditorAssetLibrary
MEL = unreal.MaterialEditingLibrary
AT = unreal.AssetToolsHelpers.get_asset_tools()

FAILURES = []


def V(x, y, z):
    return unreal.Vector(float(x), float(y), float(z))


def V2(x, y):
    return unreal.Vector2D(float(x), float(y))


def R(pitch=0.0, yaw=0.0, roll=0.0):
    return unreal.Rotator(roll=roll, pitch=pitch, yaw=yaw)


def log(msg):
    unreal.log(f"[ShipKit] {msg}")


def step(name, fn, *args):
    log(f"{name}...")
    try:
        return fn(*args)
    except Exception:
        FAILURES.append(name)
        unreal.log_error(f"[ShipKit] {name} failed:\n{traceback.format_exc()}")


def split_path(path):
    folder, name = path.rsplit("/", 1)
    return folder, name


def load_or_create(path, cls, factory):
    """Loads an asset, creating it if it doesn't exist. Existing assets are reused so references survive rebuilds."""
    if EAL.does_asset_exist(path):
        return EAL.load_asset(path)
    folder, name = split_path(path)
    return AT.create_asset(name, folder, cls, factory)


def try_set(obj, key, value):
    # Property names drift between engine versions; one bad name shouldn't sink a whole step.
    try:
        obj.set_editor_property(key, value)
    except Exception as e:
        unreal.log_warning(f"[ShipKit] couldn't set {key}: {e}")
