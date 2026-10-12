"""Run a Python script inside the open Spacevolution editor via Python Remote Execution.

Must run under the engine's Windows Python (Engine/Binaries/ThirdParty/Python3/Win64/python.exe), which is how
Scripts/sfx.py calls it:  python.exe ue_exec.py <script.py> [args...]

Exit codes: 0 ran, 1 the script failed, 2 no Spacevolution editor found, 3 the editor is in Play mode.
"""
import os
import sys
import time

ENGINE = os.path.abspath(os.path.join(os.path.dirname(sys.executable), *[os.pardir] * 4))
sys.path.insert(0, os.path.join(ENGINE, "Plugins", "Experimental", "PythonScriptPlugin", "Content", "Python"))
import remote_execution as rx  # noqa: E402

PROJECT = "Spacevolution"


def main():
    script, args = os.path.abspath(sys.argv[1]), sys.argv[2:]
    code = (
        "import runpy, sys, unreal\n"
        "if unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor():\n"
        "    raise RuntimeError('PIE_ACTIVE')\n"
        f"sys.argv = {[script] + args!r}\n"
        f"runpy.run_path({script!r}, run_name='__main__')\n"
    )
    remote = rx.RemoteExecution()
    remote.start()
    try:
        deadline = time.time() + 10
        node = None
        while node is None and time.time() < deadline:
            node = next((n for n in remote.remote_nodes if n.get("project_name") == PROJECT), None)
            time.sleep(0.2)
        if node is None:
            return 2
        remote.open_command_connection(node["node_id"])
        result = remote.run_command(code, unattended=True, exec_mode=rx.MODE_EXEC_FILE, raise_on_failure=False)
        for out in result.get("output", []):
            text = out.get("output", "").rstrip()
            if text:
                print(text if out.get("type") == "Info" else f"[{out.get('type')}] {text}")
        if result.get("success"):
            return 0
        if "PIE_ACTIVE" in str(result.get("result")):
            return 3
        print(result.get("result"))
        return 1
    finally:
        remote.stop()


if __name__ == "__main__":
    sys.exit(main())
