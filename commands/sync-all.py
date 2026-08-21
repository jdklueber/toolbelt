import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from _common import print_help, spinner, wants_help

USAGE = "toolbelt sync-all <config|config.json>"
DESCRIPTION = (
    "Syncs every repo in a config: aborts before touching anything if any "
    "repo has uncommitted changes, then clones missing repos and "
    "fetch+pull+pushes the rest, in parallel. Pulls use plain merge "
    "semantics (no rebase). Repos with no upstream tracking branch or in "
    "a detached HEAD state will fail the pull step with git's own error "
    "message."
)
OPTIONS = [
    (
        "config",
        "Resolved from $TOOLBELT_CONFIG/repos/<name>.json (.json extension "
        "optional), or an absolute/relative path to an existing file.",
    ),
]
EXAMPLES = [
    "toolbelt sync-all writing",
]

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BLUE   = "\033[94m"
RESET  = "\033[0m"

TAG_COLORS = {
    "OK": GREEN,
    "WARN": YELLOW,
    "BLOCKED": RED,
    "CONFLICT": RED,
    "FAIL": RED,
}

FAILING_TAGS = ("CONFLICT", "FAIL")

UNMERGED_PREFIXES = ("UU", "AA", "DD", "AU", "UA", "DU", "UD")

DEPENDENCY_FILES = {
    "package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "requirements.txt", "Pipfile", "Pipfile.lock", "pyproject.toml",
    "uv.lock", "poetry.lock", "Gemfile", "Gemfile.lock",
    "go.mod", "go.sum", "Cargo.toml", "Cargo.lock", "composer.json", "composer.lock",
}


def enable_ansi():
    if sys.platform == "win32":
        import ctypes
        k = ctypes.windll.kernel32
        k.SetConsoleMode(k.GetStdHandle(-11), 7)


def status_line(operation, tag, message=""):
    color = TAG_COLORS[tag]
    line = f"{YELLOW}{operation:<12}{RESET} {color}[{tag}]{RESET}"
    if message:
        line += f"  {message}"
    return line


def load_config(source):
    if Path(source).is_absolute() or (source.endswith(".json") and Path(source).is_file()):
        config_path = Path(source)
    else:
        config_dir = os.environ.get("TOOLBELT_CONFIG")
        if not config_dir:
            print("Error: TOOLBELT_CONFIG environment variable is not set")
            sys.exit(1)
        filename = source if source.endswith(".json") else f"{source}.json"
        config_path = Path(config_dir) / "repos" / filename

    if not config_path.is_file():
        print(f"Error: config file not found: {config_path}")
        sys.exit(1)

    with open(config_path) as f:
        config = json.load(f)

    root = config["root"]
    repos = [(list(r.keys())[0], list(r.values())[0]) for r in config["repos"]]
    return root, repos


def check_dirty(name, repo_path):
    if not Path(repo_path).is_dir():
        return (name, "MISSING", "")

    try:
        result = subprocess.run(
            ["git", "status", "--porcelain=v1"],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
    except Exception as e:
        return (name, "FAIL", str(e))

    if result.returncode != 0:
        msg = (result.stderr.strip().splitlines() or [""])[-1]
        return (name, "FAIL", msg)

    lines = [line for line in result.stdout.splitlines() if line]
    if not lines:
        return (name, "CLEAN", "")

    n = len(lines)
    return (name, "DIRTY", f"{n} uncommitted file{'s' if n != 1 else ''}")


def rev_parse_head(repo_path):
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo_path, capture_output=True, text=True,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def changed_dependency_files(repo_path, old_head, new_head):
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", old_head, new_head],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
    except Exception:
        return []
    if result.returncode != 0:
        return []
    changed = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return [f for f in changed if Path(f).name in DEPENDENCY_FILES]


def sync_repo(name, url, root):
    repo_path = str(Path(root) / name)
    steps = []

    if not Path(repo_path).is_dir():
        try:
            Path(root).mkdir(parents=True, exist_ok=True)
            result = subprocess.run(
                ["git", "clone", url, name],
                cwd=root,
                capture_output=True,
                text=True,
            )
        except Exception as e:
            steps.append(("clone", "FAIL", str(e)))
            return (name, steps)
        if result.returncode != 0:
            msg = (result.stderr.strip().splitlines() or [""])[-1]
            steps.append(("clone", "FAIL", msg))
            return (name, steps)
        steps.append(("clone", "OK", "cloned"))
        return (name, steps)

    try:
        fetch = subprocess.run(
            ["git", "fetch"], cwd=repo_path, capture_output=True, text=True,
        )
    except Exception as e:
        steps.append(("fetch", "FAIL", str(e)))
        return (name, steps)
    if fetch.returncode != 0:
        msg = (fetch.stderr.strip().splitlines() or [""])[-1]
        steps.append(("fetch", "FAIL", msg))
        return (name, steps)
    steps.append(("fetch", "OK", (fetch.stderr.strip().splitlines() or [""])[-1]))

    old_head = rev_parse_head(repo_path)

    try:
        pull = subprocess.run(
            ["git", "pull", "--no-rebase"], cwd=repo_path, capture_output=True, text=True,
        )
    except Exception as e:
        steps.append(("pull", "CONFLICT", str(e)))
        return (name, steps)
    if pull.returncode != 0:
        status = subprocess.run(
            ["git", "status", "--porcelain=v1"],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
        unmerged = any(
            line.startswith(p) for line in status.stdout.splitlines() for p in UNMERGED_PREFIXES
        )
        if unmerged:
            msg = "conflict — resolve manually"
        else:
            msg = (pull.stderr.strip().splitlines() or [""])[-1]
        steps.append(("pull", "CONFLICT", msg))
        return (name, steps)
    steps.append(("pull", "OK", (pull.stdout.strip().splitlines() or [""])[-1]))

    new_head = rev_parse_head(repo_path)
    if old_head and new_head and old_head != new_head:
        deps = changed_dependency_files(repo_path, old_head, new_head)
        if deps:
            steps.append(("deps-changed", "WARN", ", ".join(deps)))

    try:
        push = subprocess.run(
            ["git", "push"], cwd=repo_path, capture_output=True, text=True,
        )
    except Exception as e:
        steps.append(("push", "FAIL", str(e)))
        return (name, steps)
    if push.returncode != 0:
        msg = (push.stderr.strip().splitlines() or [""])[-1]
        steps.append(("push", "FAIL", msg))
        return (name, steps)
    steps.append(("push", "OK", (push.stderr.strip().splitlines() or [""])[-1]))

    return (name, steps)


def main():
    enable_ansi()

    args = sys.argv[1:]
    if wants_help(args):
        print_help(USAGE, DESCRIPTION, OPTIONS, EXAMPLES)
        return

    if len(args) < 1:
        print(f"Usage: {USAGE}")
        sys.exit(1)

    source = args[0]
    root, repos = load_config(source)

    with spinner(f"Checking {len(repos)} repos for uncommitted changes..."):
        with ThreadPoolExecutor() as executor:
            futures = {
                executor.submit(check_dirty, name, str(Path(root) / name)): name
                for name, _ in repos
            }
            checks = [future.result() for future in as_completed(futures)]

    blockers = sorted(
        (name, tag, msg) for name, tag, msg in checks if tag in ("DIRTY", "FAIL")
    )
    if blockers:
        print("Sync aborted — the following repos need attention first:")
        for name, tag, msg in blockers:
            print(f"{CYAN}{name}{RESET}  {status_line('status', 'BLOCKED', msg)}")
        sys.exit(1)

    with spinner(f"Syncing {len(repos)} repos..."):
        with ThreadPoolExecutor() as executor:
            futures = {
                executor.submit(sync_repo, name, url, root): name
                for name, url in repos
            }
            results = {name: steps for name, steps in (f.result() for f in as_completed(futures))}

    all_ok = True
    for name, _ in repos:
        steps = results[name]
        print(f"{CYAN}{name}{RESET}")
        for op, tag, msg in steps:
            print(f"  {status_line(op, tag, msg)}")
        if any(tag in FAILING_TAGS for _, tag, _ in steps):
            all_ok = False

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
