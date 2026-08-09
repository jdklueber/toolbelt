import json
import os
import subprocess
import sys
from pathlib import Path

from _common import print_help, wants_help

USAGE = "toolbelt git-at <config|config.json> <repo-name> <git-command> [args...]"
DESCRIPTION = (
    "Runs a single git command against one repo from a bulk-git config, "
    "from any working directory."
)
OPTIONS = [
    (
        "config",
        "Resolved from $TOOLBELT_CONFIG/repos/<name>.json (.json extension "
        "optional), or an absolute/relative path to an existing file.",
    ),
    (
        "repo-name",
        "Must match a key in the config's repos list; resolved as "
        "<root>/<repo-name>.",
    ),
    ("git-command", "Git subcommand to run (e.g. status, pull, fetch)."),
    ("args...", "Additional arguments passed through to the git command."),
]


def load_config(source):
    if Path(source).is_absolute() or Path(source).is_file():
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


def main():
    args = sys.argv[1:]
    if wants_help(args):
        print_help(USAGE, DESCRIPTION, OPTIONS)
        return

    if len(args) < 3:
        print(f"Usage: {USAGE}")
        sys.exit(1)

    source, repo_name, *git_args = args

    root, repos = load_config(source)
    names = [name for name, _ in repos]
    if repo_name not in names:
        print(f"Error: repo '{repo_name}' not found in config '{source}'")
        print(f"Available repos: {', '.join(names)}")
        sys.exit(1)

    repo_path = Path(root) / repo_name
    if not repo_path.is_dir():
        print(f"Error: directory not found: {repo_path}")
        sys.exit(1)

    result = subprocess.run(["git", *git_args], cwd=repo_path)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
