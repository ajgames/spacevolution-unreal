"""Paths and logging for the arrival build scripts. Editor handles and generic helpers come from the ship kit."""
import traceback

import unreal

from ship.util import AT, EAL, EAS, LES, MEL, UES, R, V, V2, load_or_create, try_set  # noqa: F401

ROOT = "/Game/Arrival"
M = 100.0

FAILURES = []


def log(msg):
    unreal.log(f"[Arrival] {msg}")


def step(name, fn, *args):
    log(f"{name}...")
    try:
        return fn(*args)
    except Exception:
        FAILURES.append(name)
        unreal.log_error(f"[Arrival] {name} failed:\n{traceback.format_exc()}")
