"""Builds the arrival: a level where the player starts aboard the ship high over the ocean, flies down to
BiodiverCity, lands at its spaceport, walks out down the boarding ramp and rides off on the PWC-01.

Run inside Unreal Editor 5.8 after the ship kit (build_ship.py) and the town (build_town.py):
    Output Log -> Python:  py "<project>/Scripts/build_arrival.py"

Safe to re-run: /Game/Arrival is regenerated in place and the level rebuilt. The town is streamed in, so rebuilding
the town updates this level too.
"""
import importlib

import unreal

import colony.geo
import ship.geo
import ship.level
import ship.modules
import ship.util
import town.geo
import town.layout
import town.shape
import town.spaceport

from . import util, hull, level


def reload_all():
    for m in (ship.util, ship.geo, ship.modules, ship.level, colony.geo, town.layout, town.shape, town.geo, town.spaceport,
              util, hull, level):
        importlib.reload(m)


def main():
    util.FAILURES.clear()
    with unreal.ScopedSlowTask(3, "Building the arrival") as task:
        task.make_dialog(False)

        task.enter_progress_frame(1, "Level")
        util.step("open level", level.open_level)

        task.enter_progress_frame(1, "Hull")
        hull_mesh = util.step("hull", hull.build)

        task.enter_progress_frame(1, "Populate")
        if hull_mesh:
            util.step("populate", level.build, hull_mesh)

    if util.FAILURES:
        unreal.log_error(f"[Arrival] finished with failures in: {', '.join(util.FAILURES)}")
    else:
        util.log("done")
