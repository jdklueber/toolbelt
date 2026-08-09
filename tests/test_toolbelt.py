import json
import subprocess
import sys

import pytest

import toolbelt
from helpers import ROOT

TOOLBELT_PY = ROOT / "toolbelt.py"
TOOLBELT_SH = ROOT / "toolbelt"


def _write_commands_json(tmp_path, commands):
    (tmp_path / "commands.json").write_text(json.dumps(commands))


def _echo_args_script(directory):
    script = directory / "echo_args.py"
    script.write_text("import json, sys\nprint(json.dumps(sys.argv[1:]))\n")
    return script


# ---- main() unit tests, isolated commands.json ----

def test_dispatch_passes_baked_args_before_extra_args(tmp_path, monkeypatch, capfd):
    # toolbelt.main() spawns a real subprocess, whose output lands on the OS
    # file descriptor directly rather than going through sys.stdout — capfd
    # (not capsys) is required to observe it.
    script = _echo_args_script(tmp_path)
    _write_commands_json(tmp_path, {"greet": {"script": str(script), "args": "--baked one"}})
    monkeypatch.setattr(toolbelt, "TOOLBELT_ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["toolbelt.py", "greet", "extra1", "extra2"])

    with pytest.raises(SystemExit) as exc:
        toolbelt.main()

    assert exc.value.code == 0
    assert json.loads(capfd.readouterr().out) == ["--baked", "one", "extra1", "extra2"]


def test_dispatch_substitutes_toolbelt_root_token(tmp_path, monkeypatch, capfd):
    commands_dir = tmp_path / "cmds"
    commands_dir.mkdir()
    _echo_args_script(commands_dir)
    _write_commands_json(tmp_path, {"greet": {"script": "{TOOLBELT_ROOT}/cmds/echo_args.py", "args": ""}})
    monkeypatch.setattr(toolbelt, "TOOLBELT_ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["toolbelt.py", "greet"])

    with pytest.raises(SystemExit):
        toolbelt.main()

    assert json.loads(capfd.readouterr().out) == []


def test_dispatch_uses_same_interpreter_running_toolbelt(tmp_path, monkeypatch, capfd):
    script = tmp_path / "print_exe.py"
    script.write_text("import sys\nprint(sys.executable)\n")
    _write_commands_json(tmp_path, {"x": {"script": str(script), "args": ""}})
    monkeypatch.setattr(toolbelt, "TOOLBELT_ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["toolbelt.py", "x"])

    with pytest.raises(SystemExit):
        toolbelt.main()

    assert capfd.readouterr().out.strip() == sys.executable


def test_unknown_command_exits_1_and_lists_available(tmp_path, monkeypatch, capsys):
    _write_commands_json(tmp_path, {"hello": {"script": "x", "args": ""}, "list": {"script": "y", "args": ""}})
    monkeypatch.setattr(toolbelt, "TOOLBELT_ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["toolbelt.py", "nope"])

    with pytest.raises(SystemExit) as exc:
        toolbelt.main()

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "Unknown command: nope" in out
    assert "hello" in out and "list" in out


def test_no_command_given_prints_usage_and_exits_1(tmp_path, monkeypatch, capsys):
    _write_commands_json(tmp_path, {})
    monkeypatch.setattr(toolbelt, "TOOLBELT_ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["toolbelt.py"])

    with pytest.raises(SystemExit) as exc:
        toolbelt.main()

    assert exc.value.code == 1
    assert "Usage: toolbelt <command>" in capsys.readouterr().out


def test_command_exit_code_propagates(tmp_path, monkeypatch):
    script = tmp_path / "fail.py"
    script.write_text("import sys\nsys.exit(7)\n")
    _write_commands_json(tmp_path, {"x": {"script": str(script), "args": ""}})
    monkeypatch.setattr(toolbelt, "TOOLBELT_ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["toolbelt.py", "x"])

    with pytest.raises(SystemExit) as exc:
        toolbelt.main()

    assert exc.value.code == 7


def test_command_with_no_baked_args_only_forwards_extra_args(tmp_path, monkeypatch, capfd):
    script = _echo_args_script(tmp_path)
    _write_commands_json(tmp_path, {"greet": {"script": str(script)}})  # no "args" key at all
    monkeypatch.setattr(toolbelt, "TOOLBELT_ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["toolbelt.py", "greet", "solo"])

    with pytest.raises(SystemExit):
        toolbelt.main()

    assert json.loads(capfd.readouterr().out) == ["solo"]


# ---- real end-to-end smoke tests against the actual commands.json ----

def test_real_hello_command_end_to_end():
    result = subprocess.run([sys.executable, str(TOOLBELT_PY), "hello"], capture_output=True, text=True)
    assert result.returncode == 0
    assert result.stdout == "Hello, World!\n"


def test_real_list_command_end_to_end():
    result = subprocess.run([sys.executable, str(TOOLBELT_PY), "list"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "hello" in result.stdout


def test_real_unknown_command_end_to_end():
    result = subprocess.run([sys.executable, str(TOOLBELT_PY), "nope"], capture_output=True, text=True)
    assert result.returncode == 1
    assert "Unknown command: nope" in result.stdout


@pytest.mark.skipif(sys.platform == "win32", reason="toolbelt bash wrapper is POSIX-only")
def test_bash_entrypoint_hello():
    result = subprocess.run([str(TOOLBELT_SH), "hello"], capture_output=True, text=True)
    assert result.returncode == 0
    assert result.stdout == "Hello, World!\n"
