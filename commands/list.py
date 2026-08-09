import json
import sys
import textwrap
from pathlib import Path

from _common import print_help, wants_help

TOOLBELT_ROOT = Path(__file__).resolve().parent.parent
WRAP_WIDTH = 75

USAGE = "toolbelt list"
DESCRIPTION = "Lists every toolbelt command and its purpose, as a plain wrapped table."


def main():
    if wants_help(sys.argv[1:]):
        print_help(USAGE, DESCRIPTION)
        return

    commands_file = TOOLBELT_ROOT / "commands.json"
    with open(commands_file) as f:
        commands = json.load(f)

    rows = sorted(
        (name, entry.get("description", "")) for name, entry in commands.items()
    )

    name_width = max(len("Command"), *(len(n) for n, _ in rows))
    indent = " " * (name_width + 1)

    print(f"{'Command'.ljust(name_width)} Purpose")
    for name, desc in rows:
        lines = textwrap.wrap(desc, width=WRAP_WIDTH, break_on_hyphens=False) or [""]
        print(f"{name.ljust(name_width)} {lines[0]}")
        for line in lines[1:]:
            print(f"{indent}{line}")


if __name__ == "__main__":
    main()
