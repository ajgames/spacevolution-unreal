"""Builds the modular ship kit and the interior mock-up level.

Run inside Unreal Editor 5.8 (Python Editor Script Plugin + Geometry Script, Spacevolution C++ module built):
    Output Log -> Python:  py "<project>/Scripts/build_ship.py"

Safe to re-run: assets are regenerated in place under /Game/Ship and /Game/Player, and the level is rebuilt.
"""
import importlib

import unreal

from . import util, geo, materials, audio, profile, fixtures, modules, blueprints, player, level


def reload_all():
    for m in (util, geo, materials, audio, profile, fixtures, modules, blueprints, player, level):
        importlib.reload(m)


def main(build_level=True):
    util.FAILURES.clear()
    with unreal.ScopedSlowTask(6, "Building ship kit") as task:
        task.make_dialog(False)

        task.enter_progress_frame(1, "Materials")
        mats = util.step("materials", materials.build_all)

        task.enter_progress_frame(1, "Fixtures")
        fixture_defs = util.step("fixtures", blueprints.build_fixtures, [f() for f in fixtures.ALL], mats)

        task.enter_progress_frame(1, "Modules")
        full, half = modules.ribs()
        kit = [modules.entry(full, half), modules.corridor(full, half), modules.observation_end(full, half)]
        module_defs = util.step("modules", blueprints.build_modules, kit, [full, half], mats, fixture_defs)

        task.enter_progress_frame(1, "Player")
        util.step("player", player.build)

        task.enter_progress_frame(1, "Level")
        if build_level and module_defs and fixture_defs:
            util.step("level", level.build, module_defs, fixture_defs)

    if util.FAILURES:
        unreal.log_error(f"[ShipKit] finished with failures in: {', '.join(util.FAILURES)}")
    else:
        util.log("done")
    return module_defs, fixture_defs
