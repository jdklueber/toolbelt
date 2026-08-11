import json
import os
import sys
import textwrap
from pathlib import Path

WRAP_WIDTH = 75

HELP_FLAGS = ("-h", "--help")


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


def handle_list(args):
    """Handle --list [config]. Returns True and exits if --list is present."""
    if "--list" not in args:
        return False

    config_dir = os.environ.get("TOOLBELT_CONFIG")
    if not config_dir:
        print("Error: TOOLBELT_CONFIG environment variable is not set")
        sys.exit(1)

    repos_dir = Path(config_dir) / "repos"
    idx = args.index("--list")
    next_arg = args[idx + 1] if idx + 1 < len(args) else None
    config_name = next_arg if next_arg and not next_arg.startswith("-") else None

    if config_name is None:
        configs = sorted(p.stem for p in repos_dir.glob("*.json"))
        if not configs:
            print("No repo configs found.")
        else:
            for name in configs:
                print(f"  {name}")
    else:
        filename = config_name if config_name.endswith(".json") else f"{config_name}.json"
        config_path = repos_dir / filename
        if not config_path.is_file():
            print(f"Error: config '{config_name}' not found in {repos_dir}")
            sys.exit(1)
        with open(config_path) as f:
            config = json.load(f)
        repos = [list(r.keys())[0] for r in config["repos"]]
        for name in repos:
            print(f"  {name}")

    return True
