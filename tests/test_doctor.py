import subprocess
import sys

from helpers import load_command

doctor = load_command("doctor_cmd", "doctor.py")


def _fake_run(returncode=0, stdout="", stderr=""):
    def run(*args, **kwargs):
        return subprocess.CompletedProcess(args, returncode, stdout, stderr)
    return run


# ---- last_line ----

def test_last_line_empty_string():
    assert doctor.last_line("") == ""


def test_last_line_single_line():
    assert doctor.last_line("only one line") == "only one line"


def test_last_line_skips_trailing_blank_lines():
    assert doctor.last_line("first\n\n   \nsecond\n\n") == "second"


# ---- print_env_vars ----

def test_print_env_vars_set(capsys, monkeypatch):
    monkeypatch.setenv("TOOLBELT_CONFIG", "/some/path")
    doctor.print_env_vars()
    out = capsys.readouterr().out
    assert "/some/path" in out
    assert "not set" not in out


def test_print_env_vars_unset(capsys, monkeypatch):
    monkeypatch.delenv("TOOLBELT_CONFIG", raising=False)
    doctor.print_env_vars()
    assert "not set" in capsys.readouterr().out


# ---- git_pull ----

def test_git_pull_ok(capsys, monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_run(0, "Already up to date.\n", ""))
    doctor.git_pull()
    out = capsys.readouterr().out
    assert "[OK]" in out
    assert "Already up to date." in out


def test_git_pull_fail(capsys, monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_run(1, "", "fatal: not a git repository\n"))
    doctor.git_pull()
    out = capsys.readouterr().out
    assert "[FAIL]" in out
    assert "fatal: not a git repository" in out


# ---- uv_sync ----

def test_uv_sync_ok(capsys, monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_run(0, "", "Resolved 12 packages in 3ms\nChecked 5 packages in 0.24ms\n"))
    doctor.uv_sync()
    out = capsys.readouterr().out
    assert "[OK]" in out
    assert "Checked 5 packages in 0.24ms" in out


def test_uv_sync_fail(capsys, monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_run(1, "", "error: failed to fetch package\n"))
    doctor.uv_sync()
    out = capsys.readouterr().out
    assert "[FAIL]" in out
    assert "error: failed to fetch package" in out


def test_uv_sync_not_found(capsys, monkeypatch):
    def raise_fnf(*a, **k):
        raise FileNotFoundError("no such file")
    monkeypatch.setattr(subprocess, "run", raise_fnf)
    doctor.uv_sync()
    assert "uv not found" in capsys.readouterr().out


# ---- run_tests ----

def test_run_tests_pytest_not_installed(capsys, monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_run(1, "", "No module named pytest"))
    doctor.run_tests()
    assert "pytest is not installed" in capsys.readouterr().out


def test_run_tests_no_tests_found(capsys, monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_run(5, "no tests ran", ""))
    doctor.run_tests()
    assert "No tests found." in capsys.readouterr().out


def test_run_tests_all_passed(capsys, monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_run(0, "5 passed in 0.12s\n", ""))
    doctor.run_tests()
    out = capsys.readouterr().out
    assert "[OK]" in out
    assert "5 passed" in out


def test_run_tests_reports_failing_test_names(capsys, monkeypatch):
    stdout = "FAILED tests/test_a.py::test_x\nFAILED tests/test_b.py::test_y\n2 failed\n"
    monkeypatch.setattr(subprocess, "run", _fake_run(1, stdout, ""))
    doctor.run_tests()
    out = capsys.readouterr().out
    assert "[FAIL]" in out
    assert "2 failing:" in out
    assert "tests/test_a.py::test_x" in out
    assert "tests/test_b.py::test_y" in out


def test_run_tests_generic_failure_falls_back_to_last_line(capsys, monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_run(2, "", "some internal pytest error\n"))
    doctor.run_tests()
    out = capsys.readouterr().out
    assert "[FAIL]" in out
    assert "some internal pytest error" in out


def test_run_tests_pytest_not_runnable(capsys, monkeypatch):
    def raise_fnf(*a, **k):
        raise FileNotFoundError("no such file")
    monkeypatch.setattr(subprocess, "run", raise_fnf)
    doctor.run_tests()
    assert "Could not run pytest" in capsys.readouterr().out


# ---- main / --help ----

def test_doctor_help(capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["doctor.py", "--help"])
    doctor.main()
    out = capsys.readouterr().out
    assert out.startswith("Usage: toolbelt doctor")
    assert "Environment variables:" not in out
    assert "Dependencies:" not in out
