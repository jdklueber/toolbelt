import json
import subprocess
import sys

import pytest

from helpers import load_command, init_git_repo, setup_remote_repo, COMMANDS_DIR

git_at = load_command("git_at_cmd", "git-at.py")

GIT_AT_PY = COMMANDS_DIR / "git-at.py"


# ---- load_config ----

def test_load_config_absolute_path(tmp_path):
    cfg = tmp_path / "conf.json"
    cfg.write_text('{"root": "/r", "repos": [{"a": "url-a"}]}')
    root, repos = git_at.load_config(str(cfg))
    assert root == "/r"
    assert repos == [("a", "url-a")]


def test_load_config_relative_existing_file(tmp_path, monkeypatch):
    cfg = tmp_path / "conf.json"
    cfg.write_text('{"root": "/r", "repos": []}')
    monkeypatch.chdir(tmp_path)
    root, repos = git_at.load_config("conf.json")
    assert root == "/r"
    assert repos == []


def test_load_config_bare_name_via_toolbelt_config(tmp_path, monkeypatch):
    repos_dir = tmp_path / "repos"
    repos_dir.mkdir()
    (repos_dir / "writing.json").write_text('{"root": "/w", "repos": [{"x": "y"}]}')
    monkeypatch.setenv("TOOLBELT_CONFIG", str(tmp_path))
    root, repos = git_at.load_config("writing")
    assert root == "/w"
    assert repos == [("x", "y")]


def test_load_config_missing_toolbelt_config_exits(monkeypatch, capsys):
    monkeypatch.delenv("TOOLBELT_CONFIG", raising=False)
    with pytest.raises(SystemExit) as exc:
        git_at.load_config("writing")
    assert exc.value.code == 1
    assert "TOOLBELT_CONFIG" in capsys.readouterr().out


def test_load_config_file_not_found_exits(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TOOLBELT_CONFIG", str(tmp_path))
    (tmp_path / "repos").mkdir()
    with pytest.raises(SystemExit) as exc:
        git_at.load_config("missing")
    assert exc.value.code == 1
    assert "config file not found" in capsys.readouterr().out


# ---- main() end-to-end (real git, real subprocess) ----

def test_main_runs_git_command_against_resolved_repo(tmp_path):
    root = tmp_path / "root"
    init_git_repo(root / "myrepo")
    cfg = tmp_path / "conf.json"
    cfg.write_text(json.dumps({"root": str(root), "repos": [{"myrepo": "url"}]}))

    result = subprocess.run(
        [sys.executable, str(GIT_AT_PY), str(cfg), "myrepo", "log", "--oneline"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "init" in result.stdout


def test_main_passthrough_exit_code(tmp_path):
    root = tmp_path / "root"
    init_git_repo(root / "myrepo")
    cfg = tmp_path / "conf.json"
    cfg.write_text(json.dumps({"root": str(root), "repos": [{"myrepo": "url"}]}))

    result = subprocess.run(
        [sys.executable, str(GIT_AT_PY), str(cfg), "myrepo", "this-is-not-a-git-command"],
        capture_output=True, text=True,
    )
    assert result.returncode != 0


def test_main_unknown_repo(tmp_path):
    cfg = tmp_path / "conf.json"
    cfg.write_text(json.dumps({"root": str(tmp_path), "repos": [{"a": "url"}]}))
    result = subprocess.run(
        [sys.executable, str(GIT_AT_PY), str(cfg), "b", "status"],
        capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "repo 'b' not found" in result.stdout
    assert "Available repos: a" in result.stdout


def test_main_directory_not_found(tmp_path):
    cfg = tmp_path / "conf.json"
    cfg.write_text(json.dumps({"root": str(tmp_path / "nope"), "repos": [{"a": "url"}]}))
    result = subprocess.run(
        [sys.executable, str(GIT_AT_PY), str(cfg), "a", "status"],
        capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "directory not found" in result.stdout


def test_main_too_few_args_prints_usage():
    result = subprocess.run(
        [sys.executable, str(GIT_AT_PY), "conf", "repo"], capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "Usage:" in result.stdout


def test_main_reset_clean_repo(tmp_path):
    _, clone = setup_remote_repo(tmp_path)
    cfg = tmp_path / "conf.json"
    cfg.write_text(json.dumps({"root": str(clone.parent), "repos": [{"clone": "url"}]}))
    result = subprocess.run(
        [sys.executable, str(GIT_AT_PY), str(cfg), "clone", "--reset"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "origin/main" in result.stdout


def test_main_reset_dirty_without_force_fails(tmp_path):
    _, clone = setup_remote_repo(tmp_path)
    (clone / "dirty.txt").write_text("x\n")
    cfg = tmp_path / "conf.json"
    cfg.write_text(json.dumps({"root": str(clone.parent), "repos": [{"clone": "url"}]}))
    result = subprocess.run(
        [sys.executable, str(GIT_AT_PY), str(cfg), "clone", "--reset"],
        capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "--force" in result.stdout


def test_main_reset_dirty_with_force_succeeds(tmp_path):
    _, clone = setup_remote_repo(tmp_path)
    (clone / "dirty.txt").write_text("x\n")
    cfg = tmp_path / "conf.json"
    cfg.write_text(json.dumps({"root": str(clone.parent), "repos": [{"clone": "url"}]}))
    result = subprocess.run(
        [sys.executable, str(GIT_AT_PY), str(cfg), "clone", "reset", "--force"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert not (clone / "dirty.txt").exists()


def test_main_help_flag():
    result = subprocess.run(
        [sys.executable, str(GIT_AT_PY), "--help"], capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "Usage: toolbelt git-at" in result.stdout
