import itertools
import subprocess
import sys
import textwrap
import threading
import time
from contextlib import contextmanager
from pathlib import Path

WRAP_WIDTH = 75

HELP_FLAGS = ("-h", "--help")

SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


@contextmanager
def spinner(message):
    """Animate `message` with a spinner while a parallel operation runs.

    No-ops when stdout isn't a tty (piped/captured output), so it's safe
    to wrap unconditionally.
    """
    stop = threading.Event()

    def spin():
        for frame in itertools.cycle(SPINNER_FRAMES):
            if stop.is_set():
                break
            sys.stdout.write(f"\r{frame} {message}")
            sys.stdout.flush()
            time.sleep(0.08)

    thread = threading.Thread(target=spin, daemon=True) if sys.stdout.isatty() else None
    if thread:
        thread.start()
    try:
        yield
    finally:
        if thread:
            stop.set()
            thread.join()
            sys.stdout.write("\r" + " " * (len(message) + 2) + "\r")
            sys.stdout.flush()


def wants_help(args):
    return any(a in HELP_FLAGS for a in args)


def print_help(usage, description="", options=None, examples=None):
    print(f"Usage: {usage}")
    if description:
        print()
        for line in textwrap.wrap(description, width=WRAP_WIDTH, break_on_hyphens=False):
            print(line)
    if options:
        print()
        print("Arguments:")
        name_width = max(len(name) for name, _ in options)
        prefix = name_width + 4  # 2 leading spaces + name + 2 separator spaces
        desc_width = WRAP_WIDTH - prefix
        indent = " " * prefix
        for name, desc in options:
            lines = textwrap.wrap(desc, width=desc_width, break_on_hyphens=False) or [""]
            print(f"  {name.ljust(name_width)}  {lines[0]}")
            for line in lines[1:]:
                print(f"{indent}{line}")
    if examples:
        print()
        print("Examples:")
        for example in examples:
            print(f"  {example}")


def reset_repo(repo_path, force=False):
    """Hard-reset a repo to its remote tracking branch, pruning untracked files.

    Returns (ok: bool, message: str).
    Fails fast if the working tree is dirty unless force=True, which discards
    all local changes first. Falls back to main if the current branch no
    longer exists on the remote.
    """
    def git(*args):
        return subprocess.run(
            ["git", *args], cwd=str(repo_path), capture_output=True, text=True
        )

    def last(text):
        return (text.strip().splitlines() or [""])[-1]

    status = git("status", "--porcelain=v1")
    if status.returncode != 0:
        return False, last(status.stderr)
    if status.stdout.strip():
        if not force:
            return False, "uncommitted changes (use --force to discard)"
        git("reset", "--hard", "HEAD")
        git("clean", "-fd")

    fetch = git("fetch", "--prune")
    if fetch.returncode != 0:
        return False, last(fetch.stderr)

    r = git("rev-parse", "--abbrev-ref", "HEAD")
    if r.returncode != 0:
        return False, last(r.stderr)
    branch = r.stdout.strip()

    if branch != "HEAD":
        ls = git("ls-remote", "--heads", "origin", branch)
        if ls.returncode == 0 and ls.stdout.strip():
            target = f"origin/{branch}"
        else:
            co = git("checkout", "main")
            if co.returncode != 0:
                return False, f"branch '{branch}' gone from remote; fallback failed: " + last(co.stderr)
            target = "origin/main"
    else:
        co = git("checkout", "main")
        if co.returncode != 0:
            return False, "detached HEAD; fallback to main failed: " + last(co.stderr)
        target = "origin/main"

    reset = git("reset", "--hard", target)
    if reset.returncode != 0:
        return False, last(reset.stderr)
    git("clean", "-fd")

    return True, f"-> {target}"
