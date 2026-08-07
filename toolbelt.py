import json
import subprocess
import sys
from pathlib import Path

TOOLBELT_ROOT = Path(__file__).parent.resolve()


def main():
    if len(sys.argv) < 2:
        print("Usage: toolbelt <command> [args...]")
        sys.exit(1)

    command_name = sys.argv[1]
    extra_args = sys.argv[2:]

    commands_file = TOOLBELT_ROOT / "commands.json"
    with open(commands_file) as f:
        commands = json.load(f)

    if command_name not in commands:
        print(f"Unknown command: {command_name}")
        print(f"Available commands: {', '.join(sorted(commands))}")
        sys.exit(1)

    template = commands[command_name]
    cmd_str = template.replace("{TOOLBELT_ROOT}", str(TOOLBELT_ROOT))
    cmd = cmd_str.split() + extra_args

    result = subprocess.run(cmd)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
