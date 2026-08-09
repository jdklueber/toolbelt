import json
import sys

from helpers import load_command, ROOT

list_cmd = load_command("list_cmd", "list.py")


def test_list_includes_all_registered_commands(capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["list.py"])
    list_cmd.main()
    out = capsys.readouterr().out

    commands = json.loads((ROOT / "commands.json").read_text())
    for name in commands:
        assert name in out


def test_list_header(capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["list.py"])
    list_cmd.main()
    out = capsys.readouterr().out
    assert out.splitlines()[0].startswith("Command")
    assert "Purpose" in out.splitlines()[0]


def test_list_sorted_alphabetically(capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["list.py"])
    list_cmd.main()
    out = capsys.readouterr().out

    commands = json.loads((ROOT / "commands.json").read_text())
    lines = out.splitlines()[1:]
    top_level_names = [line.split()[0] for line in lines if line and not line.startswith(" ")]
    assert top_level_names == sorted(commands)


def test_list_help(capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["list.py", "--help"])
    list_cmd.main()
    out = capsys.readouterr().out
    assert out.startswith("Usage: toolbelt list")
    assert "Command" not in out
