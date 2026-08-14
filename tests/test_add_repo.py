import json
import subprocess

import pytest

from helpers import load_command, init_git_repo, setup_remote_repo

add_repo = load_command("add_repo_cmd", "add-repo.py")


# ---- parse_args ----

def test_parse_args_here():
    repo_path, config, scan_mode = add_repo.parse_args(["--here", "--config", "writing"])
    assert config == "writing"
    assert scan_mode is True


def test_parse_args_path():
    from pathlib import Path
    repo_path, config, scan_mode = add_repo.parse_args(["--path", "/some/repo", "--config", "writing"])
    assert repo_path == Path("/some/repo")
    assert config == "writing"
    assert scan_mode is False


def test_parse_args_missing_here_or_path_exits(capsys):
    with pytest.raises(SystemExit) as exc:
        add_repo.parse_args(["--config", "writing"])
    assert exc.value.code == 1
    assert "--here or --path" in capsys.readouterr().out


def test_parse_args_missing_config_exits(capsys):
    with pytest.raises(SystemExit) as exc:
        add_repo.parse_args(["--here"])
    assert exc.value.code == 1
    assert "--config is required" in capsys.readouterr().out


def test_parse_args_unrecognized_arg_exits(capsys):
    with pytest.raises(SystemExit):
        add_repo.parse_args(["--here", "--config", "writing", "--bogus"])
    assert "unrecognized" in capsys.readouterr().out


# ---- resolve_config_path ----

def test_resolve_config_path_absolute(tmp_path):
    cfg = tmp_path / "conf.json"
    assert add_repo.resolve_config_path(str(cfg)) == cfg


def test_resolve_config_path_bare_name(tmp_path, monkeypatch):
    monkeypatch.setenv("TOOLBELT_CONFIG", str(tmp_path))
    result = add_repo.resolve_config_path("writing")
    assert result == tmp_path / "repos" / "writing.json"


def test_resolve_config_path_missing_toolbelt_config_exits(monkeypatch, capsys):
    monkeypatch.delenv("TOOLBELT_CONFIG", raising=False)
    with pytest.raises(SystemExit):
        add_repo.resolve_config_path("writing")
    assert "TOOLBELT_CONFIG" in capsys.readouterr().out


# ---- get_remote_url ----

def test_get_remote_url_reads_origin(tmp_path):
    bare, clone = setup_remote_repo(tmp_path)
    url, err = add_repo.get_remote_url(clone)
    assert url == str(bare)
    assert err is None


def test_get_remote_url_no_origin_returns_error(tmp_path):
    repo = tmp_path / "repo"
    init_git_repo(repo)
    url, err = add_repo.get_remote_url(repo)
    assert url is None
    assert "origin" in err


# ---- load_or_create_config ----

def test_load_or_create_config_loads_existing(tmp_path):
    cfg_path = tmp_path / "conf.json"
    cfg_path.write_text(json.dumps({"root": "/r", "repos": []}))
    config = add_repo.load_or_create_config(cfg_path, str(tmp_path))
    assert config == {"root": "/r", "repos": []}


def test_load_or_create_config_declines_creation_exits(tmp_path, monkeypatch, capsys):
    cfg_path = tmp_path / "nope.json"
    monkeypatch.setattr("builtins.input", lambda *_: "n")
    with pytest.raises(SystemExit):
        add_repo.load_or_create_config(cfg_path, str(tmp_path))
    assert "Aborted" in capsys.readouterr().out


def test_load_or_create_config_creates_with_default_root(tmp_path, monkeypatch):
    cfg_path = tmp_path / "new.json"
    default_root = str(tmp_path / "group")
    answers = iter(["y", ""])
    monkeypatch.setattr("builtins.input", lambda *_: next(answers))
    config = add_repo.load_or_create_config(cfg_path, default_root)
    assert config == {"root": default_root, "repos": []}


def test_load_or_create_config_creates_with_custom_root(tmp_path, monkeypatch):
    cfg_path = tmp_path / "new.json"
    answers = iter(["y", "/custom/root"])
    monkeypatch.setattr("builtins.input", lambda *_: next(answers))
    config = add_repo.load_or_create_config(cfg_path, str(tmp_path))
    assert config == {"root": "/custom/root", "repos": []}


# ---- find_git_repos ----

def test_find_git_repos_finds_immediate_children(tmp_path):
    bare1, clone1 = setup_remote_repo(tmp_path, subdir="r1")
    bare2, clone2 = setup_remote_repo(tmp_path, subdir="r2")
    base = tmp_path / "base"
    base.mkdir()
    subprocess.run(["git", "clone", "-q", str(bare1), str(base / "repo1")], check=True)
    subprocess.run(["git", "clone", "-q", str(bare2), str(base / "repo2")], check=True)
    found = add_repo.find_git_repos(base)
    names = {p.name for p in found}
    assert names == {"repo1", "repo2"}


def test_find_git_repos_finds_nested_repos(tmp_path):
    bare, clone = setup_remote_repo(tmp_path)
    base = tmp_path / "base"
    nested = base / "level1" / "level2"
    nested.mkdir(parents=True)
    subprocess.run(["git", "clone", "-q", str(bare), str(nested / "deep_repo")], check=True)
    found = add_repo.find_git_repos(base)
    assert len(found) == 1
    assert found[0].name == "deep_repo"


def test_find_git_repos_does_not_recurse_into_repos(tmp_path):
    bare, clone = setup_remote_repo(tmp_path)
    base = tmp_path / "base"
    repo = base / "repo"
    repo.mkdir(parents=True)
    subprocess.run(["git", "clone", "-q", str(bare), str(repo)], check=True)
    # add a subdirectory inside the repo that looks like another repo
    inner = repo / "inner"
    inner.mkdir()
    init_git_repo(inner)
    found = add_repo.find_git_repos(base)
    assert len(found) == 1
    assert found[0].name == "repo"


def test_find_git_repos_empty_dir(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    assert add_repo.find_git_repos(base) == []


# ---- write_config / round trip ----

def test_write_config_round_trips(tmp_path):
    cfg_path = tmp_path / "conf.json"
    config = {"root": "/r", "repos": [("a", "url-a"), ("b", "url-b")]}
    add_repo.write_config(cfg_path, config)
    loaded = json.loads(cfg_path.read_text())
    assert loaded["root"] == "/r"
    assert loaded["repos"] == [{"a": "url-a"}, {"b": "url-b"}]


# ---- main() end-to-end: --path (single repo) ----

def test_main_adds_repo_to_existing_config(tmp_path, monkeypatch, capsys):
    root = tmp_path / "root"
    bare, clone_root_dummy = setup_remote_repo(tmp_path)
    repo_path = root / "myrepo"
    repo_path.mkdir(parents=True)
    subprocess.run(["git", "clone", "-q", str(bare), str(repo_path)], check=True)

    cfg_path = tmp_path / "conf.json"
    cfg_path.write_text(json.dumps({"root": str(root), "repos": []}))

    monkeypatch.setattr("sys.argv", ["add-repo", "--path", str(repo_path), "--config", str(cfg_path)])
    add_repo.main()

    out = capsys.readouterr().out
    assert "Added 'myrepo'" in out
    loaded = json.loads(cfg_path.read_text())
    assert loaded["repos"] == [{"myrepo": str(bare)}]


def test_main_warns_when_location_mismatched(tmp_path, monkeypatch, capsys):
    bare, clone = setup_remote_repo(tmp_path)
    repo_path = tmp_path / "elsewhere" / "myrepo"
    repo_path.parent.mkdir()
    clone.rename(repo_path)

    cfg_path = tmp_path / "conf.json"
    cfg_path.write_text(json.dumps({"root": str(tmp_path / "expected_root"), "repos": []}))

    monkeypatch.setattr("sys.argv", ["add-repo", "--path", str(repo_path), "--config", str(cfg_path)])
    add_repo.main()

    out = capsys.readouterr().out
    assert "Warning" in out
    assert "Added 'myrepo'" in out


def test_main_duplicate_name_exits(tmp_path, monkeypatch, capsys):
    root = tmp_path / "root"
    bare, clone = setup_remote_repo(tmp_path)
    repo_path = root / "myrepo"
    repo_path.mkdir(parents=True)
    subprocess.run(["git", "clone", "-q", str(bare), str(repo_path)], check=True)

    cfg_path = tmp_path / "conf.json"
    cfg_path.write_text(json.dumps({"root": str(root), "repos": [{"myrepo": "old-url"}]}))

    monkeypatch.setattr("sys.argv", ["add-repo", "--path", str(repo_path), "--config", str(cfg_path)])
    with pytest.raises(SystemExit):
        add_repo.main()
    assert "already exists" in capsys.readouterr().out


def test_main_not_a_git_repo_exits(tmp_path, monkeypatch, capsys):
    repo_path = tmp_path / "notrepo"
    repo_path.mkdir()
    cfg_path = tmp_path / "conf.json"

    monkeypatch.setattr("sys.argv", ["add-repo", "--path", str(repo_path), "--config", str(cfg_path)])
    with pytest.raises(SystemExit):
        add_repo.main()
    assert "not a git repository" in capsys.readouterr().out


# ---- main() end-to-end: --here (scan mode) ----

def test_main_here_adds_multiple_repos(tmp_path, monkeypatch, capsys):
    bare1, _ = setup_remote_repo(tmp_path, subdir="bare1")
    bare2, _ = setup_remote_repo(tmp_path, subdir="bare2")
    base = tmp_path / "base"
    base.mkdir()
    subprocess.run(["git", "clone", "-q", str(bare1), str(base / "repo1")], check=True)
    subprocess.run(["git", "clone", "-q", str(bare2), str(base / "repo2")], check=True)

    cfg_path = tmp_path / "conf.json"
    cfg_path.write_text(json.dumps({"root": str(base), "repos": []}))

    monkeypatch.chdir(base)
    monkeypatch.setattr("sys.argv", ["add-repo", "--here", "--config", str(cfg_path)])
    add_repo.main()

    out = capsys.readouterr().out
    assert "Added 'repo1'" in out
    assert "Added 'repo2'" in out
    assert "2 added" in out
    loaded = json.loads(cfg_path.read_text())
    assert len(loaded["repos"]) == 2


def test_main_here_skips_duplicates(tmp_path, monkeypatch, capsys):
    bare, _ = setup_remote_repo(tmp_path)
    base = tmp_path / "base"
    base.mkdir()
    subprocess.run(["git", "clone", "-q", str(bare), str(base / "repo1")], check=True)

    cfg_path = tmp_path / "conf.json"
    cfg_path.write_text(json.dumps({"root": str(base), "repos": [{"repo1": "old-url"}]}))

    monkeypatch.chdir(base)
    monkeypatch.setattr("sys.argv", ["add-repo", "--here", "--config", str(cfg_path)])
    add_repo.main()

    out = capsys.readouterr().out
    assert "Skipped 'repo1'" in out
    assert "0 added, 1 skipped" in out


def test_main_here_no_repos_exits(tmp_path, monkeypatch, capsys):
    base = tmp_path / "base"
    base.mkdir()
    cfg_path = tmp_path / "conf.json"

    monkeypatch.chdir(base)
    monkeypatch.setattr("sys.argv", ["add-repo", "--here", "--config", str(cfg_path)])
    with pytest.raises(SystemExit):
        add_repo.main()
    assert "No git repositories found" in capsys.readouterr().out


def test_main_here_reports_failed_repos(tmp_path, monkeypatch, capsys):
    base = tmp_path / "base"
    base.mkdir()
    # repo with no origin remote
    no_origin = base / "no_origin"
    init_git_repo(no_origin)

    cfg_path = tmp_path / "conf.json"
    cfg_path.write_text(json.dumps({"root": str(base), "repos": []}))

    monkeypatch.chdir(base)
    monkeypatch.setattr("sys.argv", ["add-repo", "--here", "--config", str(cfg_path)])
    add_repo.main()

    out = capsys.readouterr().out
    assert "Failed 'no_origin'" in out
    assert "0 added" in out
