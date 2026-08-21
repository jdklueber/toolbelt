import json
import subprocess

import pytest

from helpers import load_command, init_git_repo, setup_remote_repo

repo_config = load_command("repo_config_cmd", "repo-config.py")


# ---- resolve_config_path ----

def test_resolve_config_path_absolute(tmp_path):
    cfg = tmp_path / "conf.json"
    assert repo_config.resolve_config_path(str(cfg)) == cfg


def test_resolve_config_path_bare_name(tmp_path, monkeypatch):
    monkeypatch.setenv("TOOLBELT_CONFIG", str(tmp_path))
    result = repo_config.resolve_config_path("writing")
    assert result == tmp_path / "repos" / "writing.json"


def test_resolve_config_path_missing_toolbelt_config_exits(monkeypatch, capsys):
    monkeypatch.delenv("TOOLBELT_CONFIG", raising=False)
    with pytest.raises(SystemExit):
        repo_config.resolve_config_path("writing")
    assert "TOOLBELT_CONFIG" in capsys.readouterr().out


# ---- write_config / round trip ----

def test_write_config_round_trips(tmp_path):
    cfg_path = tmp_path / "conf.json"
    config = {"root": "/r", "repos": [("a", "url-a"), ("b", "url-b")]}
    repo_config.write_config(cfg_path, config)
    loaded = json.loads(cfg_path.read_text())
    assert loaded["root"] == "/r"
    assert loaded["repos"] == [{"a": "url-a"}, {"b": "url-b"}]


# ---- get_remote_url ----

def test_get_remote_url_reads_origin(tmp_path):
    bare, clone = setup_remote_repo(tmp_path)
    url, err = repo_config.get_remote_url(clone)
    assert url == str(bare)
    assert err is None


def test_get_remote_url_no_origin_returns_error(tmp_path):
    repo = tmp_path / "repo"
    init_git_repo(repo)
    url, err = repo_config.get_remote_url(repo)
    assert url is None
    assert "origin" in err


# ---- find_git_repos ----

def test_find_git_repos_finds_immediate_children(tmp_path):
    bare1, _ = setup_remote_repo(tmp_path, subdir="r1")
    bare2, _ = setup_remote_repo(tmp_path, subdir="r2")
    base = tmp_path / "base"
    base.mkdir()
    subprocess.run(["git", "clone", "-q", str(bare1), str(base / "repo1")], check=True)
    subprocess.run(["git", "clone", "-q", str(bare2), str(base / "repo2")], check=True)
    found = repo_config.find_git_repos(base)
    names = {p.name for p in found}
    assert names == {"repo1", "repo2"}


def test_find_git_repos_empty_dir(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    assert repo_config.find_git_repos(base) == []


# ---- cmd_list ----

def test_cmd_list_all_configs(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TOOLBELT_CONFIG", str(tmp_path))
    repos_dir = tmp_path / "repos"
    repos_dir.mkdir()
    (repos_dir / "writing.json").write_text(json.dumps({"root": "/w", "repos": []}))
    (repos_dir / "work.json").write_text(json.dumps({"root": "/x", "repos": []}))

    repo_config.cmd_list([])
    out = capsys.readouterr().out
    assert "writing" in out
    assert "work" in out


def test_cmd_list_no_configs(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TOOLBELT_CONFIG", str(tmp_path))
    (tmp_path / "repos").mkdir()

    repo_config.cmd_list([])
    assert "No repo configs found." in capsys.readouterr().out


def test_cmd_list_repos_in_config(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TOOLBELT_CONFIG", str(tmp_path))
    repos_dir = tmp_path / "repos"
    repos_dir.mkdir()
    (repos_dir / "writing.json").write_text(
        json.dumps({"root": "/w", "repos": [{"arryn": "url-a"}, {"tully": "url-b"}]})
    )

    repo_config.cmd_list(["writing"])
    out = capsys.readouterr().out
    assert "arryn" in out
    assert "tully" in out


# ---- cmd_create ----

def test_cmd_create_makes_new_config(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TOOLBELT_CONFIG", str(tmp_path))
    repo_config.cmd_create(["writing", "--root", "/home/jason/git/writing"])

    cfg_path = tmp_path / "repos" / "writing.json"
    loaded = json.loads(cfg_path.read_text())
    assert loaded == {"root": "/home/jason/git/writing", "repos": []}
    assert "Created 'writing'" in capsys.readouterr().out


def test_cmd_create_missing_root_exits(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TOOLBELT_CONFIG", str(tmp_path))
    with pytest.raises(SystemExit):
        repo_config.cmd_create(["writing"])
    assert "--root is required" in capsys.readouterr().out


def test_cmd_create_already_exists_exits(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TOOLBELT_CONFIG", str(tmp_path))
    repos_dir = tmp_path / "repos"
    repos_dir.mkdir()
    (repos_dir / "writing.json").write_text(json.dumps({"root": "/w", "repos": []}))

    with pytest.raises(SystemExit):
        repo_config.cmd_create(["writing", "--root", "/w"])
    assert "already exists" in capsys.readouterr().out


# ---- cmd_add ----

def test_cmd_add_path_adds_repo(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TOOLBELT_CONFIG", str(tmp_path))
    root = tmp_path / "root"
    bare, _ = setup_remote_repo(tmp_path)
    repo_path = root / "myrepo"
    repo_path.mkdir(parents=True)
    subprocess.run(["git", "clone", "-q", str(bare), str(repo_path)], check=True)

    repos_dir = tmp_path / "repos"
    repos_dir.mkdir()
    (repos_dir / "writing.json").write_text(json.dumps({"root": str(root), "repos": []}))

    repo_config.cmd_add(["writing", "--path", str(repo_path)])

    out = capsys.readouterr().out
    assert "Added 'myrepo'" in out
    loaded = json.loads((repos_dir / "writing.json").read_text())
    assert loaded["repos"] == [{"myrepo": str(bare)}]


def test_cmd_add_missing_config_exits(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TOOLBELT_CONFIG", str(tmp_path))
    (tmp_path / "repos").mkdir()
    repo_path = tmp_path / "somerepo"
    init_git_repo(repo_path)

    with pytest.raises(SystemExit):
        repo_config.cmd_add(["writing", "--path", str(repo_path)])
    out = capsys.readouterr().out
    assert "not found" in out
    assert "create" in out


def test_cmd_add_here_adds_multiple_repos(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TOOLBELT_CONFIG", str(tmp_path))
    bare1, _ = setup_remote_repo(tmp_path, subdir="bare1")
    bare2, _ = setup_remote_repo(tmp_path, subdir="bare2")
    base = tmp_path / "base"
    base.mkdir()
    subprocess.run(["git", "clone", "-q", str(bare1), str(base / "repo1")], check=True)
    subprocess.run(["git", "clone", "-q", str(bare2), str(base / "repo2")], check=True)

    repos_dir = tmp_path / "repos"
    repos_dir.mkdir()
    (repos_dir / "writing.json").write_text(json.dumps({"root": str(base), "repos": []}))

    monkeypatch.chdir(base)
    repo_config.cmd_add(["writing", "--here"])

    out = capsys.readouterr().out
    assert "Added 'repo1'" in out
    assert "Added 'repo2'" in out
    loaded = json.loads((repos_dir / "writing.json").read_text())
    assert len(loaded["repos"]) == 2


def test_cmd_add_duplicate_name_exits(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TOOLBELT_CONFIG", str(tmp_path))
    root = tmp_path / "root"
    bare, _ = setup_remote_repo(tmp_path)
    repo_path = root / "myrepo"
    repo_path.mkdir(parents=True)
    subprocess.run(["git", "clone", "-q", str(bare), str(repo_path)], check=True)

    repos_dir = tmp_path / "repos"
    repos_dir.mkdir()
    (repos_dir / "writing.json").write_text(
        json.dumps({"root": str(root), "repos": [{"myrepo": "old-url"}]})
    )

    with pytest.raises(SystemExit):
        repo_config.cmd_add(["writing", "--path", str(repo_path)])
    assert "already exists" in capsys.readouterr().out


def test_cmd_add_name_url_adds_entry_directly(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TOOLBELT_CONFIG", str(tmp_path))
    repos_dir = tmp_path / "repos"
    repos_dir.mkdir()
    (repos_dir / "writing.json").write_text(json.dumps({"root": "/w", "repos": []}))

    repo_config.cmd_add(["writing", "--name", "arryn", "--url", "https://example.com/arryn.git"])

    out = capsys.readouterr().out
    assert "Added 'arryn' -> https://example.com/arryn.git" in out
    loaded = json.loads((repos_dir / "writing.json").read_text())
    assert loaded["repos"] == [{"arryn": "https://example.com/arryn.git"}]


def test_cmd_add_name_url_duplicate_exits(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TOOLBELT_CONFIG", str(tmp_path))
    repos_dir = tmp_path / "repos"
    repos_dir.mkdir()
    (repos_dir / "writing.json").write_text(
        json.dumps({"root": "/w", "repos": [{"arryn": "old-url"}]})
    )

    with pytest.raises(SystemExit):
        repo_config.cmd_add(["writing", "--name", "arryn", "--url", "new-url"])
    assert "already exists" in capsys.readouterr().out


def test_cmd_add_name_without_url_exits(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TOOLBELT_CONFIG", str(tmp_path))
    with pytest.raises(SystemExit):
        repo_config.cmd_add(["writing", "--name", "arryn"])
    assert "together" in capsys.readouterr().out


def test_cmd_add_name_url_with_path_exits(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TOOLBELT_CONFIG", str(tmp_path))
    with pytest.raises(SystemExit):
        repo_config.cmd_add(
            ["writing", "--path", "/some/repo", "--name", "arryn", "--url", "u"]
        )
    assert "mutually exclusive" in capsys.readouterr().out


def test_cmd_add_no_mode_exits(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TOOLBELT_CONFIG", str(tmp_path))
    with pytest.raises(SystemExit):
        repo_config.cmd_add(["writing"])
    assert "is required" in capsys.readouterr().out


# ---- cmd_remove ----

def test_cmd_remove_removes_repo(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TOOLBELT_CONFIG", str(tmp_path))
    repos_dir = tmp_path / "repos"
    repos_dir.mkdir()
    (repos_dir / "writing.json").write_text(
        json.dumps({"root": "/w", "repos": [{"arryn": "url-a"}, {"tully": "url-b"}]})
    )

    repo_config.cmd_remove(["writing", "arryn"])

    out = capsys.readouterr().out
    assert "Removed 'arryn'" in out
    loaded = json.loads((repos_dir / "writing.json").read_text())
    assert loaded["repos"] == [{"tully": "url-b"}]


def test_cmd_remove_missing_repo_exits(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TOOLBELT_CONFIG", str(tmp_path))
    repos_dir = tmp_path / "repos"
    repos_dir.mkdir()
    (repos_dir / "writing.json").write_text(json.dumps({"root": "/w", "repos": []}))

    with pytest.raises(SystemExit):
        repo_config.cmd_remove(["writing", "arryn"])
    assert "not found" in capsys.readouterr().out


# ---- cmd_set_url ----

def test_cmd_set_url_updates_url(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TOOLBELT_CONFIG", str(tmp_path))
    repos_dir = tmp_path / "repos"
    repos_dir.mkdir()
    (repos_dir / "writing.json").write_text(
        json.dumps({"root": "/w", "repos": [{"arryn": "old-url"}]})
    )

    repo_config.cmd_set_url(["writing", "arryn", "new-url"])

    out = capsys.readouterr().out
    assert "Set 'arryn'" in out
    loaded = json.loads((repos_dir / "writing.json").read_text())
    assert loaded["repos"] == [{"arryn": "new-url"}]


def test_cmd_set_url_missing_repo_exits(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TOOLBELT_CONFIG", str(tmp_path))
    repos_dir = tmp_path / "repos"
    repos_dir.mkdir()
    (repos_dir / "writing.json").write_text(json.dumps({"root": "/w", "repos": []}))

    with pytest.raises(SystemExit):
        repo_config.cmd_set_url(["writing", "arryn", "new-url"])
    assert "not found" in capsys.readouterr().out


# ---- cmd_delete ----

def test_cmd_delete_with_force_deletes(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TOOLBELT_CONFIG", str(tmp_path))
    repos_dir = tmp_path / "repos"
    repos_dir.mkdir()
    cfg_path = repos_dir / "writing.json"
    cfg_path.write_text(json.dumps({"root": "/w", "repos": []}))

    repo_config.cmd_delete(["writing", "--force"])

    assert "Deleted 'writing'" in capsys.readouterr().out
    assert not cfg_path.is_file()


def test_cmd_delete_declines_without_force(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TOOLBELT_CONFIG", str(tmp_path))
    repos_dir = tmp_path / "repos"
    repos_dir.mkdir()
    cfg_path = repos_dir / "writing.json"
    cfg_path.write_text(json.dumps({"root": "/w", "repos": []}))

    monkeypatch.setattr("builtins.input", lambda *_: "n")
    with pytest.raises(SystemExit):
        repo_config.cmd_delete(["writing"])
    assert "Aborted" in capsys.readouterr().out
    assert cfg_path.is_file()


def test_cmd_delete_missing_config_exits(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TOOLBELT_CONFIG", str(tmp_path))
    (tmp_path / "repos").mkdir()

    with pytest.raises(SystemExit):
        repo_config.cmd_delete(["writing", "--force"])
    assert "not found" in capsys.readouterr().out


# ---- main() dispatch ----

def test_main_help_flag(capsys, monkeypatch):
    monkeypatch.setattr("sys.argv", ["repo-config", "--help"])
    repo_config.main()
    assert "Usage: toolbelt repo-config" in capsys.readouterr().out


def test_main_no_args_prints_usage(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["repo-config"])
    with pytest.raises(SystemExit):
        repo_config.main()
    assert "Usage:" in capsys.readouterr().out


def test_main_unknown_subcommand_prints_usage(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["repo-config", "bogus"])
    with pytest.raises(SystemExit):
        repo_config.main()
    assert "Usage:" in capsys.readouterr().out


def test_main_dispatches_to_list(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TOOLBELT_CONFIG", str(tmp_path))
    (tmp_path / "repos").mkdir()
    monkeypatch.setattr("sys.argv", ["repo-config", "list"])
    repo_config.main()
    assert "No repo configs found." in capsys.readouterr().out
