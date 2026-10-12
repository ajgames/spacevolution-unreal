"""Entry point: py "<project>/Scripts/build_colony.py" from the editor's Python console."""
import importlib
import os
import sys

import unreal

SCRIPTS = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()), "Scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import colony.build  # noqa: E402

importlib.reload(colony.build)
colony.build.reload_all()
colony.build.main()
