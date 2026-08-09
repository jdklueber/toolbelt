import subprocess
import sys

import pytest

from helpers import load_command, init_git_repo, COMMANDS_DIR

bulk_git = load_command("bulk_git_cmd", "bulk-git.py")

BULK_GIT_PY = COMMANDS_DIR / "bulk-git.py"


def _cp(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(["git"], returncode, stdout, stderr)


# ---- status_line ----

def test_status_line_contains_name_operation_and_tag():
    line = bulk_git.status_line("repo", "pull", "OK")
    assert "repo" in line
    assert "pull" in line
    assert "[OK]" in line


def test_status_line_appends_message_when_present():
    line = bulk_git.status_line("repo", "status", "FAIL", "boom")
    assert "boom" in line


def test_status_line_omits_message_separator_when_absent():
    line = bulk_git.status_line("repo", "status", "OK", "")
    assert not line.rstrip().endswith("  ")


def test_status_line_colors_every_known_tag():
    for tag, color in bulk_git.TAG_COLORS.items():
        assert color in bulk_git.status_line("r", "op", tag)


# ---- run_status ----

def test_run_status_clean_up_to_date(monkeypatch, tmp_path):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _cp(0, "## main...origin/main\n"))
    name, op, tag, msg = bulk_git.run_status("repo", str(tmp_path))
    assert (name, op, tag, msg) == ("repo", "status", "CLEAN", "up to date")


def test_run_status_no_upstream(monkeypatch, tmp_path):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _cp(0, "## main\n"))
    _, _, tag, msg = bulk_git.run_status("repo", str(tmp_path))
    assert tag == "CLEAN"
    assert msg == "no upstream"


def test_run_status_ahead_and_behind(monkeypatch, tmp_path):
    branch = "## main...origin/main [ahead 2, behind 1]\n"
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _cp(0, branch))
    _, _, tag, msg = bulk_git.run_status("repo", str(tmp_path))
    assert tag == "CLEAN"
    assert "ahead 2" in msg
    assert "behind 1" in msg


def test_run_status_dirty_reports_file_count(monkeypatch, tmp_path):
    stdout = "## main...origin/main\n M file1.txt\n?? file2.txt\n"
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _cp(0, stdout))
    _, _, tag, msg = bulk_git.run_status("repo", str(tmp_path))
    assert tag == "CHANGES"
    assert "2 files" in msg


def test_run_status_single_dirty_file_is_singular(monkeypatch, tmp_path):
    stdout = "## main...origin/main\n M file1.txt\n"
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _cp(0, stdout))
    _, _, tag, msg = bulk_git.run_status("repo", str(tmp_path))
    assert "1 file" in msg
    assert "1 files" not in msg


def test_run_status_directory_missing():
    _, op, tag, msg = bulk_git.run_status("repo", "/does/not/exist")
    assert op == "status"
    assert tag == "FAIL"
    assert msg == "directory not found"


def test_run_status_git_error_uses_last_stderr_line(monkeypatch, tmp_path):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _cp(128, "", "fatal: one\nfatal: real error\n"))
    _, _, tag, msg = bulk_git.run_status("repo", str(tmp_path))
    assert tag == "FAIL"
    assert msg == "fatal: real error"


# ---- run_command ----

def test_run_command_directory_missing():
    _, op, tag, msg = bulk_git.run_command("repo", "/nope", ["fetch"])
    assert op == "fetch"
    assert tag == "FAIL"
    assert msg == "directory not found"


def test_run_command_success(monkeypatch, tmp_path):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _cp(0))
    _, op, tag, msg = bulk_git.run_command("repo", str(tmp_path), ["pull"])
    assert op == "pull"
    assert tag == "OK"
    assert msg == ""


def test_run_command_failure_uses_last_stderr_line(monkeypatch, tmp_path):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _cp(1, "", "line one\nline two\n"))
    _, _, tag, msg = bulk_git.run_command("repo", str(tmp_path), ["push"])
    assert tag == "FAIL"
    assert msg == "line two"


def test_run_command_no_git_args_uses_placeholder_operation():
    _, op, _, _ = bulk_git.run_command("repo", "/nope", [])
    assert op == "?"


# ---- run_clone ----

def test_run_clone_creates_root_and_succeeds(monkeypatch, tmp_path):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _cp(0))
    root = tmp_path / "does" / "not" / "exist-yet"
    name, op, tag, msg = bulk_git.run_clone("repo", "https://example.com/repo.git", str(root))
    assert op == "clone"
    assert tag == "OK"
    assert root.is_dir()


def test_run_clone_failure_reports_stderr(monkeypatch, tmp_path):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _cp(1, "", "fatal: repository not found\n"))
    _, _, tag, msg = bulk_git.run_clone("repo", "bad-url", str(tmp_path))
    assert tag == "FAIL"
    assert "repository not found" in msg


# ---- load_config ----

def test_load_config_absolute_path(tmp_path):
    cfg = tmp_path / "myconf.json"
    cfg.write_text('{"root": "/x", "repos": [{"a": "url-a"}, {"b": "url-b"}]}')
    root, repos = bulk_git.load_config(str(cfg))
    assert root == "/x"
    assert repos == [("a", "url-a"), ("b", "url-b")]


def test_load_config_relative_path_with_slash_hint(tmp_path, monkeypatch):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "myconf.json").write_text('{"root": "/x", "repos": []}')
    monkeypatch.chdir(tmp_path)
    root, repos = bulk_git.load_config("sub/myconf.json")
    assert root == "/x"
    assert repos == []


def test_load_config_bare_name_resolved_via_toolbelt_config(tmp_path, monkeypatch):
    repos_dir = tmp_path / "repos"
    repos_dir.mkdir()
    (repos_dir / "writing.json").write_text('{"root": "/w", "repos": [{"x": "y"}]}')
    monkeypatch.setenv("TOOLBELT_CONFIG", str(tmp_path))
    root, repos = bulk_git.load_config("writing")
    assert root == "/w"
    assert repos == [("x", "y")]


def test_load_config_bare_name_with_json_extension(tmp_path, monkeypatch):
    repos_dir = tmp_path / "repos"
    repos_dir.mkdir()
    (repos_dir / "writing.json").write_text('{"root": "/w", "repos": []}')
    monkeypatch.setenv("TOOLBELT_CONFIG", str(tmp_path))
    root, _ = bulk_git.load_config("writing.json")
    assert root == "/w"


def test_load_config_missing_toolbelt_config_exits(monkeypatch, capsys):
    monkeypatch.delenv("TOOLBELT_CONFIG", raising=False)
    with pytest.raises(SystemExit) as exc:
        bulk_git.load_config("writing")
    assert exc.value.code == 1
    assert "TOOLBELT_CONFIG" in capsys.readouterr().out


# ---- gather_here ----

def test_gather_here_finds_only_git_repos_sorted(tmp_path, monkeypatch):
    (tmp_path / "repo-b" / ".git").mkdir(parents=True)
    (tmp_path / "repo-a" / ".git").mkdir(parents=True)
    (tmp_path / "not-a-repo").mkdir()
    (tmp_path / "file.txt").write_text("x")
    monkeypatch.chdir(tmp_path)
    repos = bulk_git.gather_here()
    assert [name for name, _ in repos] == ["repo-a", "repo-b"]


def test_gather_here_no_repos_exits(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as exc:
        bulk_git.gather_here()
    assert exc.value.code == 1
    assert "No git repositories found" in capsys.readouterr().out


# ---- main() end-to-end (real git, real subprocess) ----

def test_main_here_status_clean_repo(tmp_path):
    init_git_repo(tmp_path / "proj")
    result = subprocess.run(
        [sys.executable, str(BULK_GIT_PY), "--here", "status"],
        cwd=tmp_path, capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "[CLEAN]" in result.stdout
    assert "proj" in result.stdout


def test_main_here_clone_is_rejected(tmp_path):
    result = subprocess.run(
        [sys.executable, str(BULK_GIT_PY), "--here", "clone"],
        cwd=tmp_path, capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "cannot be used with clone" in result.stdout


def test_main_here_no_repos_found(tmp_path):
    result = subprocess.run(
        [sys.executable, str(BULK_GIT_PY), "--here", "status"],
        cwd=tmp_path, capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "No git repositories found" in result.stdout


def test_main_too_few_args_prints_usage():
    result = subprocess.run(
        [sys.executable, str(BULK_GIT_PY), "onlyone"], capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "Usage:" in result.stdout


def test_main_help_flag():
    result = subprocess.run(
        [sys.executable, str(BULK_GIT_PY), "--help"], capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "Usage: toolbelt bulk-git" in result.stdout
