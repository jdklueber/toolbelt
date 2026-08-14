import json
import os
import subprocess
import sys
from pathlib import Path

from _common import print_help, wants_help

USAGE = "toolbelt add-repo (--here | --path <path>) --config <config|config.json>"
DESCRIPTION = (
    "Adds git repositories to a bulk-git config. With --here, scans all "
    "subdirectories of the current working directory for git repos and adds "
    "them all. With --path, adds a single repo. Each repo is keyed by its "
    "directory name and points at its 'origin' remote URL."
)
OPTIONS = [
    (
        "--here",
        "Scan subdirectories of the current working directory for git repos "
        "and add them all to the config.",
    ),
    ("--path <path>", "Use the given directory as the repo to add (single repo)."),
    (
        "--config <name|path>",
        "Resolved from $TOOLBELT_CONFIG/repos/<name>.json (.json extension "
        "optional), or an absolute/relative path to a file. If the config "
        "doesn't exist yet, you'll be prompted to create it.",
    ),
]
EXAMPLES = [
    "toolbelt add-repo --here --config writing",
    "toolbelt add-repo --path /home/jason/git/writing/arryn --config writing",
]


def parse_args(args):
    repo_path = None
    config = None
    scan_mode = False
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--here":
            repo_path = Path.cwd()
            scan_mode = True
            i += 1
        elif arg == "--path":
            if i + 1 >= len(args):
                print("Error: --path requires a value")
                sys.exit(1)
            repo_path = Path(args[i + 1])
            scan_mode = False
            i += 2
        elif arg == "--config":
            if i + 1 >= len(args):
                print("Error: --config requires a value")
                sys.exit(1)
            config = args[i + 1]
            i += 2
        else:
            print(f"Error: unrecognized argument '{arg}'")
            sys.exit(1)

    if repo_path is None:
        print("Error: either --here or --path is required")
        sys.exit(1)
    if config is None:
        print("Error: --config is required")
        sys.exit(1)

    return repo_path, config, scan_mode


def resolve_config_path(source):
    has_path_hint = "/" in source or "\\" in source or source.endswith(".json")
    if Path(source).is_absolute() or (has_path_hint and Path(source).is_file()):
        return Path(source)

    config_dir = os.environ.get("TOOLBELT_CONFIG")
    if not config_dir:
        print("Error: TOOLBELT_CONFIG environment variable is not set")
        sys.exit(1)
    filename = source if source.endswith(".json") else f"{source}.json"
    return Path(config_dir) / "repos" / filename


def get_remote_url(repo_path):
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        msg = (result.stderr.strip().splitlines() or [""])[-1]
        return None, f"could not read 'origin' remote: {msg}"
    return result.stdout.strip(), None


def load_or_create_config(config_path, default_root):
    if config_path.is_file():
        with open(config_path) as f:
            return json.load(f)

    print(f"Config '{config_path}' does not exist.")
    answer = input("Create it? [y/N] ").strip().lower()
    if answer not in ("y", "yes"):
        print("Aborted.")
        sys.exit(1)

    root = input(f"Root directory [{default_root}]: ").strip() or default_root
    return {"root": root, "repos": []}


def write_config(config_path, config):
    config_path.parent.mkdir(parents=True, exist_ok=True)
    entry_lines = [
        "    " + json.dumps({name: url}) for name, url in config["repos"]
    ]
    text = "{\n"
    text += f'  "root": {json.dumps(config["root"])},\n'
    text += '  "repos": [\n'
    text += ",\n".join(entry_lines)
    text += "\n  ]\n}\n"
    config_path.write_text(text)


def find_git_repos(base_path):
    repos = []
    try:
        children = sorted(base_path.iterdir())
    except PermissionError:
        return repos
    for child in children:
        if not child.is_dir():
            continue
        if (child / ".git").exists():
            repos.append(child)
        else:
            repos.extend(find_git_repos(child))
    return repos


def main():
    args = sys.argv[1:]
    if wants_help(args):
        print_help(USAGE, DESCRIPTION, OPTIONS, EXAMPLES)
        return

    repo_path, config_source, scan_mode = parse_args(args)

    if scan_mode:
        found = find_git_repos(repo_path)
        if not found:
            print(f"No git repositories found under {repo_path}")
            sys.exit(1)

        config_path = resolve_config_path(config_source)
        config = load_or_create_config(config_path, str(repo_path.resolve()))

        repos = [(list(r.keys())[0], list(r.values())[0]) for r in config["repos"]]
        existing_names = {n for n, _ in repos}

        added = []
        skipped = []
        failed = []

        for rp in found:
            name = rp.resolve().name
            if name in existing_names:
                skipped.append(name)
                continue
            url, err = get_remote_url(rp)
            if err:
                failed.append((name, err))
                continue
            repos.append((name, url))
            existing_names.add(name)
            added.append((name, url))

        config["repos"] = repos
        if added:
            write_config(config_path, config)

        for name, url in added:
            print(f"Added '{name}' -> {url}")
        for name in skipped:
            print(f"Skipped '{name}' (already in config)")
        for name, err in failed:
            print(f"Failed '{name}': {err}")

        print(
            f"\n{len(added)} added, {len(skipped)} skipped, {len(failed)} failed"
            f" -> {config_path}"
        )

    else:
        if not (repo_path / ".git").exists():
            print(f"Error: not a git repository: {repo_path}")
            sys.exit(1)

        name = repo_path.resolve().name
        url, err = get_remote_url(repo_path)
        if err:
            print(f"Error: {err}")
            sys.exit(1)

        config_path = resolve_config_path(config_source)
        config = load_or_create_config(config_path, str(repo_path.resolve().parent))

        repos = [(list(r.keys())[0], list(r.values())[0]) for r in config["repos"]]
        existing_names = [n for n, _ in repos]
        if name in existing_names:
            print(f"Error: repo '{name}' already exists in config '{config_path}'")
            sys.exit(1)

        expected_path = Path(config["root"]) / name
        if repo_path.resolve() != expected_path.resolve():
            print(
                f"Warning: '{name}' is at {repo_path.resolve()}, but other "
                f"toolbelt commands will look for it at {expected_path} "
                f"(config root '{config['root']}')."
            )

        repos.append((name, url))
        config["repos"] = repos
        write_config(config_path, config)

        print(f"Added '{name}' -> {url} to {config_path}")


if __name__ == "__main__":
    main()
