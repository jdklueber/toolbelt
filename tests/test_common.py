import subprocess
import sys
from pathlib import Path

import _common
from helpers import setup_remote_repo


def test_wants_help_short_flag():
    assert _common.wants_help(["-h"]) is True


def test_wants_help_long_flag():
    assert _common.wants_help(["--help"]) is True


def test_wants_help_flag_mixed_with_other_args():
    assert _common.wants_help(["foo", "--help", "bar"]) is True


def test_wants_help_false_when_absent():
    assert _common.wants_help(["foo", "bar"]) is False


def test_wants_help_false_when_empty():
    assert _common.wants_help([]) is False


def test_print_help_usage_only(capsys):
    _common.print_help("toolbelt hello")
    assert capsys.readouterr().out == "Usage: toolbelt hello\n"


def test_print_help_with_description(capsys):
    _common.print_help("toolbelt hello", "Prints a greeting.")
    assert capsys.readouterr().out == "Usage: toolbelt hello\n\nPrints a greeting.\n"


def test_print_help_wraps_long_description(capsys):
    long_desc = ("word " * 40).strip()
    _common.print_help("toolbelt hello", long_desc)
    out = capsys.readouterr().out
    for line in out.splitlines():
        assert len(line) <= _common.WRAP_WIDTH


def test_print_help_does_not_break_on_hyphens(capsys):
    desc = ("See the <repo-name> argument for details. " * 4).strip()
    _common.print_help("toolbelt x", desc)
    out = capsys.readouterr().out
    assert "repo-\n" not in out
    assert "<repo-name>" in out


def test_print_help_with_options(capsys):
    options = [("config", "The config file."), ("--here", "Use cwd repos.")]
    _common.print_help("toolbelt bulk-git", "desc", options)
    out = capsys.readouterr().out
    assert "Arguments:" in out
    assert "config" in out
    assert "The config file." in out
    assert "--here" in out
    assert "Use cwd repos." in out


def test_print_help_no_options_section_when_none_given(capsys):
    _common.print_help("toolbelt hello", "desc")
    assert "Arguments:" not in capsys.readouterr().out


def test_print_help_options_wrap_with_aligned_indent(capsys):
    options = [
        ("a", "short"),
        ("much-longer-name", "a description long enough that it wraps onto a second continuation line for sure"),
    ]
    _common.print_help("usage", "", options)
    lines = capsys.readouterr().out.splitlines()

    name_width = len("much-longer-name")
    indent = " " * (name_width + 4)

    continuation_lines = [
        line for line in lines
        if line.startswith(indent) and line[len(indent):len(indent) + 1] != " "
    ]
    assert continuation_lines, "expected at least one wrapped continuation line"


# ---- reset_repo ----

def test_reset_repo_clean_repo_resets_to_remote(tmp_path):
    _, clone = setup_remote_repo(tmp_path)
    ok, msg = _common.reset_repo(clone)
    assert ok
    assert "origin/main" in msg


def test_reset_repo_dirty_without_force_fails(tmp_path):
    _, clone = setup_remote_repo(tmp_path)
    (clone / "dirty.txt").write_text("dirty\n")
    ok, msg = _common.reset_repo(clone)
    assert not ok
    assert "--force" in msg


def test_reset_repo_dirty_with_force_discards_and_resets(tmp_path):
    _, clone = setup_remote_repo(tmp_path)
    (clone / "dirty.txt").write_text("dirty\n")
    ok, msg = _common.reset_repo(clone, force=True)
    assert ok
    assert not (clone / "dirty.txt").exists()
    assert "origin/main" in msg


def test_reset_repo_staged_changes_without_force_fails(tmp_path):
    _, clone = setup_remote_repo(tmp_path)
    (clone / "staged.txt").write_text("staged\n")
    subprocess.run(["git", "-C", str(clone), "add", "staged.txt"], check=True)
    ok, msg = _common.reset_repo(clone)
    assert not ok
    assert "--force" in msg


def test_reset_repo_staged_changes_with_force_discards_and_resets(tmp_path):
    _, clone = setup_remote_repo(tmp_path)
    (clone / "staged.txt").write_text("staged\n")
    subprocess.run(["git", "-C", str(clone), "add", "staged.txt"], check=True)
    ok, msg = _common.reset_repo(clone, force=True)
    assert ok
    assert not (clone / "staged.txt").exists()


def test_reset_repo_falls_back_to_main_when_branch_gone(tmp_path):
    bare, clone = setup_remote_repo(tmp_path)
    # Push a feature branch then delete it from remote
    subprocess.run(["git", "-C", str(clone), "checkout", "-b", "feature"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(clone), "push", "-q", "origin", "feature"], check=True)
    subprocess.run(["git", "-C", str(clone), "push", "-q", "origin", "--delete", "feature"], check=True)
    # Now on feature branch whose remote no longer exists
    ok, msg = _common.reset_repo(clone)
    assert ok
    assert "origin/main" in msg
    branch = subprocess.run(
        ["git", "-C", str(clone), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True,
    ).stdout.strip()
    assert branch == "main"


def test_reset_repo_prunes_untracked_files_after_reset(tmp_path):
    _, clone = setup_remote_repo(tmp_path)
    (clone / "leftover.txt").write_text("leftover\n")
    ok, msg = _common.reset_repo(clone, force=True)
    assert ok
    assert not (clone / "leftover.txt").exists()
