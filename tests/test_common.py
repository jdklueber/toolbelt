import _common


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
