import json
import os
import subprocess
import sys
from pathlib import Path

from _common import print_help, wants_help

USAGE = "toolbelt repo-config <list|create|add|remove|set-url|delete> ..."
DESCRIPTION = (
    "CRUD operations on bulk-git repo configs. A config is a JSON file "
    "listing a root directory and a set of named repos, used by bulk-git, "
    "git-at, and sync-all."
)
OPTIONS = [
    (
        "list [config]",
        "List all available configs, or the repos within a specific config.",
    ),
    (
        "create <config> --root <path>",
        "Create a new, empty config.",
    ),
    (
        "add <config> --here",
        "Add every git repo found by scanning subdirectories of the "
        "current working directory.",
    ),
    (
        "add <config> --path <path>",
        "Add a single local repo, reading its name and origin URL from "
        "disk.",
    ),
    (
        "add <config> --name <name> --url <url>",
        "Add an entry directly, without needing a local clone. --name "
        "and --url must be given together.",
    ),
    (
        "remove <config> <repo-name>",
        "Remove a repo from a config.",
    ),
    (
        "set-url <config> <repo-name> <url>",
        "Change the remote URL recorded for a repo in a config.",
    ),
    (
        "delete <config> [--force]",
        "Delete a config file entirely. Prompts for confirmation unless "
        "--force is given.",
    ),
]
EXAMPLES = [
    "toolbelt repo-config list",
    "toolbelt repo-config list writing",
    "toolbelt repo-config create writing --root /home/jason/git/writing",
    "toolbelt repo-config add writing --here",
    "toolbelt repo-config add writing --path /home/jason/git/writing/arryn",
    "toolbelt repo-config add writing --name arryn --url https://github.com/user/arryn.git",
    "toolbelt repo-config remove writing arryn",
    "toolbelt repo-config set-url writing arryn https://github.com/user/arryn.git",
    "toolbelt repo-config delete writing",
]


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


def load_config(config_path):
    if not config_path.is_file():
        print(f"Error: config '{config_path}' not found")
        sys.exit(1)
    with open(config_path) as f:
        return json.load(f)


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


def cmd_list(args):
    config_dir = os.environ.get("TOOLBELT_CONFIG")
    if not config_dir:
        print("Error: TOOLBELT_CONFIG environment variable is not set")
        sys.exit(1)
    repos_dir = Path(config_dir) / "repos"

    if not args:
        configs = sorted(p.stem for p in repos_dir.glob("*.json"))
        if not configs:
            print("No repo configs found.")
        else:
            for name in configs:
                print(f"  {name}")
        return

    config_path = resolve_config_path(args[0])
    config = load_config(config_path)
    for r in config["repos"]:
        print(f"  {list(r.keys())[0]}")


def cmd_create(args):
    if not args:
        print("Error: config name is required")
        sys.exit(1)
    name = args[0]
    root = None
    i = 1
    while i < len(args):
        if args[i] == "--root":
            if i + 1 >= len(args):
                print("Error: --root requires a value")
                sys.exit(1)
            root = args[i + 1]
            i += 2
        else:
            print(f"Error: unrecognized argument '{args[i]}'")
            sys.exit(1)
    if root is None:
        print("Error: --root is required")
        sys.exit(1)

    config_path = resolve_config_path(name)
    if config_path.is_file():
        print(f"Error: config '{name}' already exists at {config_path}")
        sys.exit(1)

    write_config(config_path, {"root": root, "repos": []})
    print(f"Created '{name}' -> {config_path}")


def cmd_add(args):
    if not args:
        print("Error: config name is required")
        sys.exit(1)
    name = args[0]
    rest = args[1:]

    repo_path = None
    scan_mode = False
    manual_name = None
    manual_url = None
    i = 0
    while i < len(rest):
        arg = rest[i]
        if arg == "--here":
            repo_path = Path.cwd()
            scan_mode = True
            i += 1
        elif arg == "--path":
            if i + 1 >= len(rest):
                print("Error: --path requires a value")
                sys.exit(1)
            repo_path = Path(rest[i + 1])
            scan_mode = False
            i += 2
        elif arg == "--name":
            if i + 1 >= len(rest):
                print("Error: --name requires a value")
                sys.exit(1)
            manual_name = rest[i + 1]
            i += 2
        elif arg == "--url":
            if i + 1 >= len(rest):
                print("Error: --url requires a value")
                sys.exit(1)
            manual_url = rest[i + 1]
            i += 2
        else:
            print(f"Error: unrecognized argument '{arg}'")
            sys.exit(1)

    manual_mode = manual_name is not None or manual_url is not None
    modes_given = sum([repo_path is not None, manual_mode])
    if modes_given == 0:
        print("Error: one of --here, --path, or --name/--url is required")
        sys.exit(1)
    if modes_given > 1:
        print("Error: --here, --path, and --name/--url are mutually exclusive")
        sys.exit(1)
    if manual_mode and (manual_name is None or manual_url is None):
        print("Error: --name and --url must be given together")
        sys.exit(1)

    config_path = resolve_config_path(name)
    if not config_path.is_file():
        print(f"Error: config '{name}' not found. Run 'repo-config create' first.")
        sys.exit(1)
    config = load_config(config_path)
    repos = [(list(r.keys())[0], list(r.values())[0]) for r in config["repos"]]

    if manual_mode:
        existing_names = [n for n, _ in repos]
        if manual_name in existing_names:
            print(f"Error: repo '{manual_name}' already exists in config '{config_path}'")
            sys.exit(1)
        repos.append((manual_name, manual_url))
        config["repos"] = repos
        write_config(config_path, config)
        print(f"Added '{manual_name}' -> {manual_url} to {config_path}")
    elif scan_mode:
        found = find_git_repos(repo_path)
        if not found:
            print(f"No git repositories found under {repo_path}")
            sys.exit(1)

        existing_names = {n for n, _ in repos}
        added, skipped, failed = [], [], []
        for rp in found:
            rname = rp.resolve().name
            if rname in existing_names:
                skipped.append(rname)
                continue
            url, err = get_remote_url(rp)
            if err:
                failed.append((rname, err))
                continue
            repos.append((rname, url))
            existing_names.add(rname)
            added.append((rname, url))

        config["repos"] = repos
        if added:
            write_config(config_path, config)

        for rname, url in added:
            print(f"Added '{rname}' -> {url}")
        for rname in skipped:
            print(f"Skipped '{rname}' (already in config)")
        for rname, err in failed:
            print(f"Failed '{rname}': {err}")
        print(
            f"\n{len(added)} added, {len(skipped)} skipped, {len(failed)} failed"
            f" -> {config_path}"
        )
    else:
        if not (repo_path / ".git").exists():
            print(f"Error: not a git repository: {repo_path}")
            sys.exit(1)

        rname = repo_path.resolve().name
        url, err = get_remote_url(repo_path)
        if err:
            print(f"Error: {err}")
            sys.exit(1)

        existing_names = [n for n, _ in repos]
        if rname in existing_names:
            print(f"Error: repo '{rname}' already exists in config '{config_path}'")
            sys.exit(1)

        expected_path = Path(config["root"]) / rname
        if repo_path.resolve() != expected_path.resolve():
            print(
                f"Warning: '{rname}' is at {repo_path.resolve()}, but other "
                f"toolbelt commands will look for it at {expected_path} "
                f"(config root '{config['root']}')."
            )

        repos.append((rname, url))
        config["repos"] = repos
        write_config(config_path, config)
        print(f"Added '{rname}' -> {url} to {config_path}")


def cmd_remove(args):
    if len(args) < 2:
        print("Error: usage: repo-config remove <config> <repo-name>")
        sys.exit(1)
    name, repo_name = args[0], args[1]

    config_path = resolve_config_path(name)
    config = load_config(config_path)
    repos = [(list(r.keys())[0], list(r.values())[0]) for r in config["repos"]]

    remaining = [(n, u) for n, u in repos if n != repo_name]
    if len(remaining) == len(repos):
        print(f"Error: repo '{repo_name}' not found in config '{name}'")
        sys.exit(1)

    config["repos"] = remaining
    write_config(config_path, config)
    print(f"Removed '{repo_name}' from {config_path}")


def cmd_set_url(args):
    if len(args) < 3:
        print("Error: usage: repo-config set-url <config> <repo-name> <url>")
        sys.exit(1)
    name, repo_name, url = args[0], args[1], args[2]

    config_path = resolve_config_path(name)
    config = load_config(config_path)
    repos = [(list(r.keys())[0], list(r.values())[0]) for r in config["repos"]]

    for idx, (n, _) in enumerate(repos):
        if n == repo_name:
            repos[idx] = (n, url)
            config["repos"] = repos
            write_config(config_path, config)
            print(f"Set '{repo_name}' -> {url} in {config_path}")
            return

    print(f"Error: repo '{repo_name}' not found in config '{name}'")
    sys.exit(1)


def cmd_delete(args):
    if not args:
        print("Error: config name is required")
        sys.exit(1)
    name = args[0]
    force = "--force" in args[1:]

    config_path = resolve_config_path(name)
    if not config_path.is_file():
        print(f"Error: config '{name}' not found")
        sys.exit(1)

    if not force:
        answer = input(f"Delete config '{name}' ({config_path})? [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            print("Aborted.")
            sys.exit(1)

    config_path.unlink()
    print(f"Deleted '{name}' ({config_path})")


SUBCOMMANDS = {
    "list": cmd_list,
    "create": cmd_create,
    "add": cmd_add,
    "remove": cmd_remove,
    "set-url": cmd_set_url,
    "delete": cmd_delete,
}


def main():
    args = sys.argv[1:]
    if wants_help(args):
        print_help(USAGE, DESCRIPTION, OPTIONS, EXAMPLES)
        return

    if not args or args[0] not in SUBCOMMANDS:
        print(f"Usage: {USAGE}")
        sys.exit(1)

    SUBCOMMANDS[args[0]](args[1:])


if __name__ == "__main__":
    main()
