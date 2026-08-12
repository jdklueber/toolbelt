import json
import os
import subprocess
import sys

import pytest

from helpers import load_command, init_git_repo, COMMANDS_DIR

sync_all = load_command("sync_all_cmd", "sync-all.py")

SYNC_ALL_PY = COMMANDS_DIR / "sync-all.py"


def _cp(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(["git"], returncode, stdout, stderr)


def _sequence(*results):
    results = list(results)

    def _run(*a, **k):
        return results.pop(0)

    return _run


# ---- status_line ----

def test_status_line_contains_operation_and_tag():
    line = sync_all.status_line("pull", "OK")
    assert "pull" in line
    assert "[OK]" in line


def test_status_line_appends_message_when_present():
    line = sync_all.status_line("pull", "FAIL", "boom")
    assert "boom" in line


def test_status_line_colors_every_known_tag():
    for tag, color in sync_all.TAG_COLORS.items():
        assert color in sync_all.status_line("op", tag)


# ---- check_dirty ----

def test_check_dirty_missing_directory_is_not_blocking():
    name, tag, msg = sync_all.check_dirty("repo", "/does/not/exist")
    assert tag == "MISSING"


def test_check_dirty_clean_repo(monkeypatch, tmp_path):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _cp(0, ""))
    _, tag, msg = sync_all.check_dirty("repo", str(tmp_path))
    assert tag == "CLEAN"


def test_check_dirty_reports_file_count(monkeypatch, tmp_path):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _cp(0, " M file1.txt\n?? file2.txt\n"))
    _, tag, msg = sync_all.check_dirty("repo", str(tmp_path))
    assert tag == "DIRTY"
    assert "2 uncommitted files" in msg


def test_check_dirty_single_file_is_singular(monkeypatch, tmp_path):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _cp(0, " M file1.txt\n"))
    _, _, msg = sync_all.check_dirty("repo", str(tmp_path))
    assert "1 uncommitted file" in msg
    assert "1 uncommitted files" not in msg


def test_check_dirty_git_error_is_fail(monkeypatch, tmp_path):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _cp(128, "", "fatal: one\nfatal: real error\n"))
    _, tag, msg = sync_all.check_dirty("repo", str(tmp_path))
    assert tag == "FAIL"
    assert msg == "fatal: real error"


def test_check_dirty_does_not_request_branch_info(monkeypatch, tmp_path):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return _cp(0, "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    sync_all.check_dirty("repo", str(tmp_path))
    assert "--branch" not in captured["cmd"]


# ---- sync_repo ----

def test_sync_repo_clones_when_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _cp(0))
    root = tmp_path / "missing-root"
    name, steps = sync_all.sync_repo("proj", "https://example.com/proj.git", str(root))
    assert steps == [("clone", "OK", "cloned")]
    assert root.is_dir()


def test_sync_repo_clone_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _cp(1, "", "fatal: repository not found\n"))
    _, steps = sync_all.sync_repo("proj", "bad-url", str(tmp_path))
    assert len(steps) == 1
    op, tag, msg = steps[0]
    assert op == "clone"
    assert tag == "FAIL"
    assert "repository not found" in msg


def test_sync_repo_fetch_failure_skips_pull_push(monkeypatch, tmp_path):
    (tmp_path / "proj").mkdir()
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return _cp(1, "", "fatal: no route to host\n")

    monkeypatch.setattr(subprocess, "run", fake_run)
    _, steps = sync_all.sync_repo("proj", "url", str(tmp_path))
    assert len(steps) == 1
    op, tag, msg = steps[0]
    assert op == "fetch"
    assert tag == "FAIL"
    assert len(calls) == 1


def test_sync_repo_pull_conflict_skips_push(monkeypatch, tmp_path):
    (tmp_path / "proj").mkdir()
    monkeypatch.setattr(subprocess, "run", _sequence(
        _cp(0),                                     # fetch
        _cp(0, "abc123\n"),                          # rev-parse HEAD (old)
        _cp(1, "", "error: merge conflict\n"),       # pull
        _cp(0, "UU file.txt\n"),                     # status (unmerged check)
    ))
    _, steps = sync_all.sync_repo("proj", "url", str(tmp_path))
    assert [op for op, _, _ in steps] == ["fetch", "pull"]
    op, tag, msg = steps[-1]
    assert op == "pull"
    assert tag == "CONFLICT"
    assert "resolve manually" in msg


def test_sync_repo_pull_failure_without_conflict_marker(monkeypatch, tmp_path):
    (tmp_path / "proj").mkdir()
    monkeypatch.setattr(subprocess, "run", _sequence(
        _cp(0),                                            # fetch
        _cp(0, "abc123\n"),                                 # rev-parse HEAD (old)
        _cp(1, "", "fatal: not something to merge\n"),     # pull
        _cp(0, ""),                                         # status (no unmerged markers)
    ))
    _, steps = sync_all.sync_repo("proj", "url", str(tmp_path))
    op, tag, msg = steps[-1]
    assert op == "pull"
    assert tag == "CONFLICT"
    assert msg == "fatal: not something to merge"


def test_sync_repo_pull_ok_push_fails(monkeypatch, tmp_path):
    (tmp_path / "proj").mkdir()
    monkeypatch.setattr(subprocess, "run", _sequence(
        _cp(0),                              # fetch
        _cp(0, "abc123\n"),                   # rev-parse HEAD (old)
        _cp(0),                              # pull
        _cp(0, "abc123\n"),                   # rev-parse HEAD (new, unchanged)
        _cp(1, "", "! [rejected]\n"),        # push
    ))
    _, steps = sync_all.sync_repo("proj", "url", str(tmp_path))
    op, tag, msg = steps[-1]
    assert op == "push"
    assert tag == "FAIL"
    assert "[rejected]" in msg


def test_sync_repo_pull_and_push_ok(monkeypatch, tmp_path):
    (tmp_path / "proj").mkdir()
    monkeypatch.setattr(subprocess, "run", _sequence(
        _cp(0),                        # fetch
        _cp(0, "abc123\n"),             # rev-parse HEAD (old)
        _cp(0, "Already up to date."),  # pull
        _cp(0, "abc123\n"),             # rev-parse HEAD (new, unchanged)
        _cp(0),                        # push
    ))
    _, steps = sync_all.sync_repo("proj", "url", str(tmp_path))
    assert [op for op, tag, _ in steps] == ["fetch", "pull", "push"]
    assert all(tag == "OK" for _, tag, _ in steps)


def test_sync_repo_flags_dependency_file_changes(monkeypatch, tmp_path):
    (tmp_path / "proj").mkdir()
    monkeypatch.setattr(subprocess, "run", _sequence(
        _cp(0),                                  # fetch
        _cp(0, "old-sha\n"),                       # rev-parse HEAD (old)
        _cp(0, "Updating old-sha..new-sha"),       # pull
        _cp(0, "new-sha\n"),                       # rev-parse HEAD (new)
        _cp(0, "src/app.py\nuv.lock\n"),           # diff --name-only
        _cp(0),                                  # push
    ))
    _, steps = sync_all.sync_repo("proj", "url", str(tmp_path))
    assert [op for op, _, _ in steps] == ["fetch", "pull", "deps-changed", "push"]
    op, tag, msg = steps[2]
    assert tag == "WARN"
    assert "uv.lock" in msg
    assert "src/app.py" not in msg


def test_sync_repo_no_deps_changed_step_when_head_unchanged(monkeypatch, tmp_path):
    (tmp_path / "proj").mkdir()
    monkeypatch.setattr(subprocess, "run", _sequence(
        _cp(0),                        # fetch
        _cp(0, "abc123\n"),             # rev-parse HEAD (old)
        _cp(0, "Already up to date."),  # pull
        _cp(0, "abc123\n"),             # rev-parse HEAD (new, unchanged)
        _cp(0),                        # push
    ))
    _, steps = sync_all.sync_repo("proj", "url", str(tmp_path))
    assert "deps-changed" not in [op for op, _, _ in steps]


# ---- load_config ----

def test_load_config_bare_name_resolved_via_toolbelt_config(tmp_path, monkeypatch):
    repos_dir = tmp_path / "repos"
    repos_dir.mkdir()
    (repos_dir / "writing.json").write_text('{"root": "/w", "repos": [{"x": "y"}]}')
    monkeypatch.setenv("TOOLBELT_CONFIG", str(tmp_path))
    root, repos = sync_all.load_config("writing")
    assert root == "/w"
    assert repos == [("x", "y")]


def test_load_config_missing_toolbelt_config_exits(monkeypatch, capsys):
    monkeypatch.delenv("TOOLBELT_CONFIG", raising=False)
    with pytest.raises(SystemExit) as exc:
        sync_all.load_config("writing")
    assert exc.value.code == 1
    assert "TOOLBELT_CONFIG" in capsys.readouterr().out


# ---- main() end-to-end (real git, real subprocess) ----

def _seed_bare_remote(tmp_path, repo_name):
    bare = tmp_path / f"{repo_name}.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)

    seed = tmp_path / f"_seed_{repo_name}"
    init_git_repo(seed)
    subprocess.run(["git", "-C", str(seed), "branch", "-M", "main"], check=True)
    subprocess.run(["git", "-C", str(seed), "remote", "add", "origin", str(bare)], check=True)
    subprocess.run(["git", "-C", str(seed), "push", "-q", "-u", "origin", "main"], check=True)
    subprocess.run(["git", "-C", str(bare), "symbolic-ref", "HEAD", "refs/heads/main"], check=True)
    return bare


def _clone(bare, dest):
    subprocess.run(["git", "clone", "-q", str(bare), str(dest)], check=True)
    subprocess.run(["git", "-C", str(dest), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(dest), "config", "user.name", "Test"], check=True)


def _write_config(path, root, repos):
    path.write_text(json.dumps({"root": str(root), "repos": [{n: u} for n, u in repos]}))


def test_main_aborts_when_any_repo_dirty(tmp_path):
    init_git_repo(tmp_path / "repo-clean")
    init_git_repo(tmp_path / "repo-dirty")
    (tmp_path / "repo-dirty" / "scratch.txt").write_text("wip\n")

    config = tmp_path / "conf.json"
    _write_config(config, tmp_path, [("repo-clean", "unused"), ("repo-dirty", "unused")])

    result = subprocess.run(
        [sys.executable, str(SYNC_ALL_PY), str(config)], capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "repo-dirty" in result.stdout
    assert "uncommitted" in result.stdout
    assert "repo-clean" not in result.stdout


def test_main_autoclones_missing_repo(tmp_path):
    bare = _seed_bare_remote(tmp_path, "proj")
    work = tmp_path / "work"
    config = tmp_path / "conf.json"
    _write_config(config, work, [("proj", str(bare))])

    result = subprocess.run(
        [sys.executable, str(SYNC_ALL_PY), str(config)], capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "[OK]" in result.stdout
    assert "cloned" in result.stdout
    assert (work / "proj" / "README.md").is_file()


def test_main_pull_and_push_success(tmp_path):
    bare = _seed_bare_remote(tmp_path, "proj")

    device_a = tmp_path / "deviceA" / "proj"
    _clone(bare, device_a)

    device_b_root = tmp_path / "deviceB"
    _clone(bare, device_b_root / "proj")

    (device_a / "new.txt").write_text("from A\n")
    subprocess.run(["git", "-C", str(device_a), "add", "."], check=True)
    subprocess.run(["git", "-C", str(device_a), "commit", "-q", "-m", "add new"], check=True)
    subprocess.run(["git", "-C", str(device_a), "push", "-q"], check=True)

    config = tmp_path / "conf.json"
    _write_config(config, device_b_root, [("proj", str(bare))])

    result = subprocess.run(
        [sys.executable, str(SYNC_ALL_PY), str(config)], capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "[OK]" in result.stdout
    assert (device_b_root / "proj" / "new.txt").is_file()


def test_main_conflict_skips_push(tmp_path):
    bare = _seed_bare_remote(tmp_path, "proj")

    device_a = tmp_path / "deviceA" / "proj"
    _clone(bare, device_a)

    device_b_root = tmp_path / "deviceB"
    device_b = device_b_root / "proj"
    _clone(bare, device_b)

    (device_a / "README.md").write_text("from A\n")
    subprocess.run(["git", "-C", str(device_a), "add", "."], check=True)
    subprocess.run(["git", "-C", str(device_a), "commit", "-q", "-m", "edit from A"], check=True)
    subprocess.run(["git", "-C", str(device_a), "push", "-q"], check=True)

    (device_b / "README.md").write_text("from B\n")
    subprocess.run(["git", "-C", str(device_b), "add", "."], check=True)
    subprocess.run(["git", "-C", str(device_b), "commit", "-q", "-m", "edit from B"], check=True)

    before = subprocess.run(
        ["git", "-C", str(bare), "rev-parse", "main"], capture_output=True, text=True, check=True,
    ).stdout.strip()

    config = tmp_path / "conf.json"
    _write_config(config, device_b_root, [("proj", str(bare))])

    result = subprocess.run(
        [sys.executable, str(SYNC_ALL_PY), str(config)], capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "[CONFLICT]" in result.stdout
    assert "resolve manually" in result.stdout

    after = subprocess.run(
        ["git", "-C", str(bare), "rev-parse", "main"], capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert after == before


def test_main_push_rejected_reported_not_crashed(tmp_path):
    bare = _seed_bare_remote(tmp_path, "proj")
    device_root = tmp_path / "device"
    device = device_root / "proj"
    _clone(bare, device)

    subprocess.run(
        ["git", "-C", str(device), "remote", "set-url", "--push", "origin", str(tmp_path / "nonexistent.git")],
        check=True,
    )

    config = tmp_path / "conf.json"
    _write_config(config, device_root, [("proj", str(bare))])

    result = subprocess.run(
        [sys.executable, str(SYNC_ALL_PY), str(config)], capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "[FAIL]" in result.stdout
    assert "Traceback" not in result.stdout
    assert "Traceback" not in result.stderr


def test_main_help_flag():
    result = subprocess.run(
        [sys.executable, str(SYNC_ALL_PY), "--help"], capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "Usage: toolbelt sync-all" in result.stdout


def test_main_list_passthrough(tmp_path):
    repos_dir = tmp_path / "repos"
    repos_dir.mkdir()
    (repos_dir / "writing.json").write_text(json.dumps({"root": "/w", "repos": [{"x": "y"}]}))
    env = os.environ.copy()
    env["TOOLBELT_CONFIG"] = str(tmp_path)

    result = subprocess.run(
        [sys.executable, str(SYNC_ALL_PY), "--list", "writing"],
        capture_output=True, text=True, env=env,
    )
    assert result.returncode == 0
    assert "x" in result.stdout


def test_main_too_few_args_prints_usage():
    result = subprocess.run(
        [sys.executable, str(SYNC_ALL_PY)], capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "Usage:" in result.stdout


def test_main_missing_toolbelt_config_exits():
    env = os.environ.copy()
    env.pop("TOOLBELT_CONFIG", None)

    result = subprocess.run(
        [sys.executable, str(SYNC_ALL_PY), "writing"], capture_output=True, text=True, env=env,
    )
    assert result.returncode == 1
    assert "TOOLBELT_CONFIG" in result.stdout
