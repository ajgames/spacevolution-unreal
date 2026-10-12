"""Paths and logging for the colony build scripts. Editor handles and generic helpers come from the ship kit."""
import traceback

import unreal

from ship.util import AT, EAL, EAS, LES, MEL, UES, R, V, V2, load_or_create, try_set  # noqa: F401

ROOT = "/Game/Colony"
M = 100.0  # cm per metre: the layout is authored in metres

FAILURES = []


def log(msg):
    unreal.log(f"[Colony] {msg}")


def step(name, fn, *args):
    log(f"{name}...")
    try:
        return fn(*args)
    except Exception:
        FAILURES.append(name)
        unreal.log_error(f"[Colony] {name} failed:\n{traceback.format_exc()}")
