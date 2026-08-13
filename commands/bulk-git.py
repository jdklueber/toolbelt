import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from _common import handle_list, print_help, reset_repo, spinner, wants_help

USAGE = "toolbelt bulk-git <config|config.json|--here> <git-command> [args...]"
DESCRIPTION = "Runs git operations across a set of repos in parallel."
OPTIONS = [
    (
        "config",
        "Filename resolved from $TOOLBELT_CONFIG/repos/<name>.json (.json "
        "extension optional), or an absolute/relative path to an existing "
        "file.",
    ),
    (
        "--here",
        "Operates on all git repos found directly under the current "
        "working directory, instead of a config file. Not valid with "
        "clone.",
    ),
    (
        "--list [config]",
        "List all available repo configs, or list the repos within a "
        "specific config.",
    ),
    (
        "git-command",
        'Git subcommand to run (e.g. status, pull, fetch). "clone" is '
        "only valid with a config file, since it needs URLs.",
    ),
    ("args...", "Additional arguments passed through to the git command."),
    (
        "--reset",
        "Toolbelt subcommand (not git reset): hard-resets each repo to its "
        "remote tracking branch, then prunes untracked files. Clones any "
        "repos that are missing (config mode only). Falls back to main if "
        "the current branch no longer exists on the remote. Fails fast on "
        "local changes unless --force is also passed.",
    ),
    (
        "--force",
        "Used with --reset: discards all uncommitted changes before resetting.",
    ),
]
EXAMPLES = [
    "toolbelt bulk-git --list",
    "toolbelt bulk-git --list writing",
    "toolbelt bulk-git writing status",
    "toolbelt bulk-git writing pull --rebase",
    "toolbelt bulk-git writing clone",
    "toolbelt bulk-git --here fetch",
    "toolbelt bulk-git writing --reset",
    "toolbelt bulk-git writing --reset --force",
]

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BLUE   = "\033[94m"
RESET  = "\033[0m"

TAG_COLORS = {
    "OK": GREEN,
    "CLEAN": GREEN,
    "CHANGES": BLUE,
    "FAIL": RED,
}


def enable_ansi():
    if sys.platform == "win32":
        import ctypes
        k = ctypes.windll.kernel32
        k.SetConsoleMode(k.GetStdHandle(-11), 7)


def status_line(name, operation, tag, message=""):
    color = TAG_COLORS[tag]
    line = f"{CYAN}{name:<40}{RESET} {YELLOW}{operation:<12}{RESET} {color}[{tag}]{RESET}"
    if message:
        line += f"  {message}"
    return line


def run_clone(name, url, root):
    operation = "clone"
    try:
        Path(root).mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            ["git", "clone", url, name],
            cwd=root,
            capture_output=True,
            text=True,
        )
        tag = "OK" if result.returncode == 0 else "FAIL"
        msg = "" if tag == "OK" else (result.stderr.strip().splitlines() or [""])[-1]
        return (name, operation, tag, msg)
    except Exception as e:
        return (name, operation, "FAIL", str(e))


def run_command(name, repo_path, git_args):
    operation = git_args[0] if git_args else "?"
    try:
        if not Path(repo_path).is_dir():
            return (name, operation, "FAIL", "directory not found")
        result = subprocess.run(
            ["git", *git_args],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
        tag = "OK" if result.returncode == 0 else "FAIL"
        msg = "" if tag == "OK" else (result.stderr.strip().splitlines() or [""])[-1]
        return (name, operation, tag, msg)
    except Exception as e:
        return (name, operation, "FAIL", str(e))


def run_reset(name, repo_path, force, clone_url=None, clone_root=None):
    operation = "reset"
    try:
        if not Path(repo_path).is_dir():
            if clone_url and clone_root:
                return run_clone(name, clone_url, clone_root)
            return (name, operation, "FAIL", "directory not found")
        ok, msg = reset_repo(repo_path, force)
        return (name, operation, "OK" if ok else "FAIL", msg)
    except Exception as e:
        return (name, operation, "FAIL", str(e))


def run_status(name, repo_path):
    operation = "status"
    try:
        if not Path(repo_path).is_dir():
            return (name, operation, "FAIL", "directory not found")
        result = subprocess.run(
            ["git", "status", "--porcelain=v1", "--branch"],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            msg = (result.stderr.strip().splitlines() or [""])[-1]
            return (name, operation, "FAIL", msg)

        lines = result.stdout.splitlines()
        branch_line = lines[0] if lines else ""
        file_count = len(lines) - 1 if lines else 0
        clean = file_count == 0

        no_upstream = "..." not in branch_line
        ahead_match = re.search(r"ahead (\d+)", branch_line)
        behind_match = re.search(r"behind (\d+)", branch_line)
        ahead = int(ahead_match.group(1)) if ahead_match else 0
        behind = int(behind_match.group(1)) if behind_match else 0

        parts = []
        if not clean:
            parts.append(f"{file_count} file{'s' if file_count != 1 else ''}")
        if no_upstream:
            parts.append("no upstream")
        elif ahead == 0 and behind == 0:
            parts.append("up to date")
        else:
            sync = []
            if ahead:
                sync.append(f"ahead {ahead}")
            if behind:
                sync.append(f"behind {behind}")
            parts.append(", ".join(sync))

        tag = "CLEAN" if clean else "CHANGES"
        return (name, operation, tag, " | ".join(parts))
    except Exception as e:
        return (name, operation, "FAIL", str(e))


def load_config(source):
    has_path_hint = "/" in source or "\\" in source or source.endswith(".json")
    if Path(source).is_absolute() or (has_path_hint and Path(source).is_file()):
        config_path = Path(source)
    else:
        config_dir = os.environ.get("TOOLBELT_CONFIG")
        if not config_dir:
            print("Error: TOOLBELT_CONFIG environment variable is not set")
            sys.exit(1)
        filename = source if source.endswith(".json") else f"{source}.json"
        config_path = Path(config_dir) / "repos" / filename

    with open(config_path) as f:
        config = json.load(f)

    root = config["root"]
    repos = [(list(r.keys())[0], list(r.values())[0]) for r in config["repos"]]
    return root, repos


def gather_here():
    cwd = Path.cwd()
    repos = [
        (d.name, str(d))
        for d in sorted(cwd.iterdir())
        if d.is_dir() and (d / ".git").exists()
    ]
    if not repos:
        print("No git repositories found in current directory")
        sys.exit(1)
    return repos


def main():
    enable_ansi()

    args = sys.argv[1:]
    if wants_help(args):
        print_help(USAGE, DESCRIPTION, OPTIONS, EXAMPLES)
        return
    if handle_list(args):
        return

    if len(args) < 2:
        print(f"Usage: {USAGE}")
        sys.exit(1)

    source   = args[0]
    git_args = args[1:]
    operation = git_args[0]

    if source == "--here":
        if operation == "clone":
            print("Error: --here cannot be used with clone (no URLs available)")
            sys.exit(1)
        repos = gather_here()
        root = None
    else:
        root, repos = load_config(source)

    futures = {}
    with spinner(f"Running '{' '.join(git_args)}' across {len(repos)} repos..."):
        with ThreadPoolExecutor() as executor:
            for name, url_or_path in repos:
                if operation == "clone":
                    f = executor.submit(run_clone, name, url_or_path, root)
                elif git_args == ["status"]:
                    repo_path = url_or_path if source == "--here" else str(Path(root) / name)
                    f = executor.submit(run_status, name, repo_path)
                elif operation == "--reset":
                    force = "--force" in git_args
                    if source == "--here":
                        f = executor.submit(run_reset, name, url_or_path, force)
                    else:
                        repo_path = str(Path(root) / name)
                        f = executor.submit(run_reset, name, repo_path, force, url_or_path, root)
                else:
                    repo_path = url_or_path if source == "--here" else str(Path(root) / name)
                    f = executor.submit(run_command, name, repo_path, git_args)
                futures[f] = name

            results = [future.result() for future in as_completed(futures)]

    all_ok = True
    for name, op, tag, msg in results:
        print(status_line(name, op, tag, msg))
        if tag == "FAIL":
            all_ok = False

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
