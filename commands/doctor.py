import os
import re
import subprocess
import sys
from pathlib import Path

from _common import print_help, wants_help

TOOLBELT_ROOT = Path(__file__).resolve().parent.parent

USAGE = "toolbelt doctor"
DESCRIPTION = (
    "Health check: prints configured environment variables, pulls the "
    "latest toolbelt code, and runs the test suite."
)

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"

ENV_VARS = [
    "TOOLBELT_CONFIG",
]


def enable_ansi():
    if sys.platform == "win32":
        import ctypes
        k = ctypes.windll.kernel32
        k.SetConsoleMode(k.GetStdHandle(-11), 7)


def last_line(text):
    lines = [line for line in text.strip().splitlines() if line.strip()]
    return lines[-1] if lines else ""


def print_env_vars():
    print("Environment variables:")
    name_width = max(len(name) for name in ENV_VARS)
    for name in ENV_VARS:
        value = os.environ.get(name)
        if value:
            print(f"  {name.ljust(name_width)}  {value}")
        else:
            print(f"  {name.ljust(name_width)}  {YELLOW}not set{RESET}")
    print()


def git_pull():
    print("Git pull:")
    result = subprocess.run(
        ["git", "pull"],
        cwd=TOOLBELT_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print(f"  {GREEN}[OK]{RESET}  {last_line(result.stdout)}")
    else:
        print(f"  {RED}[FAIL]{RESET}  {last_line(result.stderr)}")
    print()


def run_tests():
    print("Tests:")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q"],
            cwd=TOOLBELT_ROOT,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as e:
        print(f"  {YELLOW}Could not run pytest: {e}{RESET}")
        return

    output = result.stdout + result.stderr

    if "No module named pytest" in output:
        print(f"  {YELLOW}pytest is not installed — skipping.{RESET}")
        return

    if result.returncode == 5:
        print(f"  {YELLOW}No tests found.{RESET}")
        return

    if result.returncode == 0:
        match = re.search(r"(\d+) passed", output)
        count = match.group(1) if match else "0"
        print(f"  {GREEN}[OK]{RESET}  {count} passed")
        return

    failures = re.findall(r"^FAILED (\S+)", output, re.MULTILINE)
    if failures:
        print(f"  {RED}[FAIL]{RESET}  {len(failures)} failing:")
        for name in failures:
            print(f"    - {name}")
    else:
        print(f"  {RED}[FAIL]{RESET}  {last_line(output)}")


def main():
    enable_ansi()
    if wants_help(sys.argv[1:]):
        print_help(USAGE, DESCRIPTION)
        return

    print_env_vars()
    git_pull()
    run_tests()


if __name__ == "__main__":
    main()
