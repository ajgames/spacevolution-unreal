"""Builds BiodiverCity: a procedural lily-pad island town after BIG's masterplan for Penang, an ocean of rideable
waves round it, and the PWC-01 hover jet-ski to ride them.

Run inside Unreal Editor 5.8 (Python Editor Script Plugin + Geometry Script):
    Output Log -> Python:  py "<project>/Scripts/build_town.py"

Safe to re-run: assets under /Game/Town are regenerated in place and the level is rebuilt. Hard finishes are
instances of the ship kit's surface master, so the ship kit must have been built once.
"""
import importlib

import unreal

import colony.geo
import colony.noise
import ship.geo
import ship.materials
import ship.util

from . import util, layout, shape, plan, geo, materials, terrain, kit, bridges, ocean, rider, level


def reload_all():
    # Shared modules first: the town modules import names from them.
    for m in (ship.util, ship.geo, ship.materials, colony.noise, colony.geo,
              util, layout, shape, plan, geo, materials, terrain, kit, bridges, ocean, rider, level):
        importlib.reload(m)


def main():
    util.FAILURES.clear()
    with unreal.ScopedSlowTask(9, "Building BiodiverCity") as task:
        task.make_dialog(False)

        # Open the level first, so baking doesn't replace meshes the open level is still using.
        task.enter_progress_frame(1, "Level")
        util.step("open level", level.open_level)

        task.enter_progress_frame(1, "Materials")
        mats = util.step("materials", materials.build_all)

        task.enter_progress_frame(1, "Plan")
        town = util.step("plan", plan.make)
        if town:
            util.log(f"plan: {len(town.buildings)} buildings, {len(town.trees)} trees, {len(town.bridges)} bridges")

        task.enter_progress_frame(1, "Terrain")
        ground = util.step("terrain", terrain.build, mats) if mats else None

        task.enter_progress_frame(1, "Kit")
        meshes = util.step("kit", kit.build, mats) if mats else None

        task.enter_progress_frame(1, "Bridges")
        bridge_mesh = util.step("bridges", bridges.build, town, mats) if mats and town else None

        task.enter_progress_frame(1, "Ocean")
        water = util.step("ocean", ocean.build)

        task.enter_progress_frame(1, "Wave rider")
        riders = util.step("wave rider", rider.build, mats) if mats else None

        task.enter_progress_frame(1, "Populate")
        if all((town, ground, meshes, bridge_mesh, water, riders)):
            util.step("populate", level.build, town, ground, meshes, mats, bridge_mesh, water, riders)

    if util.FAILURES:
        unreal.log_error(f"[Town] finished with failures in: {', '.join(util.FAILURES)}")
    else:
        util.log("done")
