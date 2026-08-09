import sys

from helpers import load_command

hello = load_command("hello_cmd", "hello.py")


def test_hello_prints_greeting(capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["hello.py"])
    hello.main()
    assert capsys.readouterr().out == "Hello, World!\n"


def test_hello_help_flag_suppresses_greeting(capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["hello.py", "--help"])
    hello.main()
    out = capsys.readouterr().out
    assert out.startswith("Usage: toolbelt hello")
    assert "Hello, World!" not in out.splitlines()


def test_hello_short_help_flag(capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["hello.py", "-h"])
    hello.main()
    assert capsys.readouterr().out.startswith("Usage: toolbelt hello")
