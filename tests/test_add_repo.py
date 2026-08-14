import json

import pytest

from helpers import load_command, init_git_repo, setup_remote_repo

add_repo = load_command("add_repo_cmd", "add-repo.py")


# ---- parse_args ----

def test_parse_args_here():
    repo_path, config = add_repo.parse_args(["--here", "--config", "writing"])
    assert config == "writing"


def test_parse_args_path():
    repo_path, config = add_repo.parse_args(["--path", "/some/repo", "--config", "writing"])
    from pathlib import Path
    assert repo_path == Path("/some/repo")
    assert config == "writing"


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
    url = add_repo.get_remote_url(clone)
    assert url == str(bare)


def test_get_remote_url_no_origin_exits(tmp_path, capsys):
    repo = tmp_path / "repo"
    init_git_repo(repo)
    with pytest.raises(SystemExit):
        add_repo.get_remote_url(repo)
    assert "origin" in capsys.readouterr().out


# ---- load_or_create_config ----

def test_load_or_create_config_loads_existing(tmp_path):
    cfg_path = tmp_path / "conf.json"
    cfg_path.write_text(json.dumps({"root": "/r", "repos": []}))
    config = add_repo.load_or_create_config(cfg_path, tmp_path)
    assert config == {"root": "/r", "repos": []}


def test_load_or_create_config_declines_creation_exits(tmp_path, monkeypatch, capsys):
    cfg_path = tmp_path / "nope.json"
    monkeypatch.setattr("builtins.input", lambda *_: "n")
    with pytest.raises(SystemExit):
        add_repo.load_or_create_config(cfg_path, tmp_path / "repo")
    assert "Aborted" in capsys.readouterr().out


def test_load_or_create_config_creates_with_default_root(tmp_path, monkeypatch):
    cfg_path = tmp_path / "new.json"
    repo_path = tmp_path / "group" / "myrepo"
    answers = iter(["y", ""])
    monkeypatch.setattr("builtins.input", lambda *_: next(answers))
    config = add_repo.load_or_create_config(cfg_path, repo_path)
    assert config == {"root": str(repo_path.parent), "repos": []}


def test_load_or_create_config_creates_with_custom_root(tmp_path, monkeypatch):
    cfg_path = tmp_path / "new.json"
    repo_path = tmp_path / "group" / "myrepo"
    answers = iter(["y", "/custom/root"])
    monkeypatch.setattr("builtins.input", lambda *_: next(answers))
    config = add_repo.load_or_create_config(cfg_path, repo_path)
    assert config == {"root": "/custom/root", "repos": []}


# ---- write_config / round trip ----

def test_write_config_round_trips(tmp_path):
    cfg_path = tmp_path / "conf.json"
    config = {"root": "/r", "repos": [("a", "url-a"), ("b", "url-b")]}
    add_repo.write_config(cfg_path, config)
    loaded = json.loads(cfg_path.read_text())
    assert loaded["root"] == "/r"
    assert loaded["repos"] == [{"a": "url-a"}, {"b": "url-b"}]


# ---- main() end-to-end ----

def test_main_adds_repo_to_existing_config(tmp_path, monkeypatch, capsys):
    root = tmp_path / "root"
    bare, clone_root_dummy = setup_remote_repo(tmp_path)
    repo_path = root / "myrepo"
    repo_path.mkdir(parents=True)
    import subprocess
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
    import subprocess
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
