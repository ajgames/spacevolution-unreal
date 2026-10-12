"""Builds the Mars colony greybox: terrain, rock formations, domes and towers, and the low-sun dusty sky.

Run inside Unreal Editor 5.8 (Python Editor Script Plugin + Geometry Script):
    Output Log -> Python:  py "<project>/Scripts/build_colony.py"

Safe to re-run: assets under /Game/Colony are regenerated in place and the level is rebuilt. Building
materials are instances of the ship kit's masters, so the ship kit must have been built once.
"""
import importlib

import unreal

import ship.geo
import ship.materials
import ship.util

from . import util, layout, noise, geo, terrain, rocks, structures, materials, level


def reload_all():
    # The ship modules first: the colony modules import names from them.
    for m in (ship.util, ship.geo, ship.materials,
              util, layout, noise, geo, terrain, rocks, structures, materials, level):
        importlib.reload(m)


def main():
    util.FAILURES.clear()
    with unreal.ScopedSlowTask(6, "Building Mars colony") as task:
        task.make_dialog(False)

        # Open the level first, so baking doesn't replace meshes the open level is still using.
        task.enter_progress_frame(1, "Level")
        util.step("open level", level.open_level)

        task.enter_progress_frame(1, "Materials")
        mats = util.step("materials", materials.build_all)

        task.enter_progress_frame(1, "Terrain")
        ground = util.step("terrain", terrain.build, mats) if mats else None

        task.enter_progress_frame(1, "Rocks")
        rock_meshes = util.step("rocks", rocks.build, mats) if mats else None

        task.enter_progress_frame(1, "Colony")
        kit = util.step("structures", structures.build, mats) if mats else None

        task.enter_progress_frame(1, "Populate")
        if ground and rock_meshes and kit:
            util.step("populate", level.build, ground, rock_meshes, kit, mats["Clouds"])

    if util.FAILURES:
        unreal.log_error(f"[Colony] finished with failures in: {', '.join(util.FAILURES)}")
    else:
        util.log("done")
