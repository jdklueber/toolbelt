import json
import subprocess
import sys
import textwrap
from pathlib import Path

TOOLBELT_ROOT = Path(__file__).parent.resolve()
WRAP_WIDTH = 75


def print_help(commands):
    print("Usage: toolbelt <command> [args...]")
    print()
    for line in textwrap.wrap(
        "A personal CLI dispatcher. Runs registered commands via a single entry "
        "point, with automatic dependency management via uv.",
        width=WRAP_WIDTH,
        break_on_hyphens=False,
    ):
        print(line)
    if commands:
        print()
        print("Commands:")
        name_width = max(len(name) for name in commands)
        indent = " " * (name_width + 4)
        for name in sorted(commands):
            desc = commands[name].get("description", "")
            lines = textwrap.wrap(desc, width=WRAP_WIDTH, break_on_hyphens=False) or [""]
            print(f"  {name.ljust(name_width)}  {lines[0]}")
            for line in lines[1:]:
                print(f"{indent}{line}")
    print()
    print("Options:")
    print("  -h, --help  Show this help message and exit.")
    print()
    print("Run 'toolbelt <command> --help' for help on a specific command.")


def main():
    commands_file = TOOLBELT_ROOT / "commands.json"
    with open(commands_file) as f:
        commands = json.load(f)

    if len(sys.argv) < 2:
        print_help(commands)
        sys.exit(1)

    if sys.argv[1] in ("-h", "--help"):
        print_help(commands)
        sys.exit(0)

    command_name = sys.argv[1]
    extra_args = sys.argv[2:]

    if command_name not in commands:
        print(f"Unknown command: {command_name}")
        print(f"Available commands: {', '.join(sorted(commands))}")
        sys.exit(1)

    entry = commands[command_name]
    script = entry["script"].replace("{TOOLBELT_ROOT}", str(TOOLBELT_ROOT))
    baked_args = entry.get("args", "").split()
    cmd = [sys.executable, script] + baked_args + extra_args

    result = subprocess.run(cmd)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
