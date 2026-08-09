# Toolbelt

A personal cross-platform CLI dispatcher. Commands are registered in `commands.json` and invoked via a single `toolbelt <command>` entry point.

## Architecture

```
toolbelt/
  toolbelt.py       # dispatcher — reads commands.json, resolves paths, runs the command
  toolbelt.bat      # Windows PATH entry point; calls toolbelt.py with %~dp0 so no hardcoded paths
  commands.json     # command registry: name → {script, args}
  commands/         # one script per command
```

### How dispatch works

Every command is a Python script — `toolbelt.py` always invokes it with `sys.executable`, the same interpreter that is currently running `toolbelt.py` itself. This is what makes the dispatcher work identically whether the platform entry point launched it as `python` (Windows) or `python3` (Linux): there's no `python`/`python3` guessing anywhere in `commands.json`.

For each command, `commands.json` holds two separate strings:
- `script`: path to the command's script, with `{TOOLBELT_ROOT}` substituted for the repo root (derived from `__file__`). Kept as a single, unsplit token — safe even if the path contains spaces.
- `args`: optional baked-in arguments, whitespace-split and prepended before any extra CLI args.

`toolbelt.py` builds `[sys.executable, script] + baked_args + extra_args` and runs it via `subprocess.run`. Keeping `sys.executable` as its own list element (rather than interpolating it into a string that later gets `.split()`) avoids breaking on interpreter paths with spaces, e.g. Windows' default `C:\Program Files\Python311\python.exe`.

If a command needs to launch something that isn't Python (a JVM, a binary, etc.), write a Python wrapper script in `commands/` that shells out to it — don't add a non-Python entry to `commands.json`.

### `--help` / `-h`

Every command supports `--help`/`-h` and prints its usage, description, and parameters instead of running. This is implemented via `commands/_common.py` (a shared helper, not itself a registered command — scripts in the same directory can `import _common` directly since Python puts a script's own directory on `sys.path`):

- `wants_help(args)`: checks the command's `sys.argv[1:]` for `-h`/`--help`.
- `print_help(usage, description="", options=None)`: prints the usage line, then the description, then an `Options:` list — all wrapped at 75 characters (`break_on_hyphens=False`, so tokens like `<repo-name>` don't get split), matching the style of `toolbelt list`.

### Adding a new command

1. Create `commands/<name>.py`.
2. Handle `--help`/`-h` at the top of `main()` using `_common.wants_help` / `_common.print_help` (see any existing command for the pattern).
3. Add an entry to `commands.json`:
   ```json
   "name": {
     "script": "{TOOLBELT_ROOT}/commands/name.py",
     "args": "",
     "description": "One-line purpose, shown by `toolbelt list`."
   }
   ```
That's it. No changes to the dispatcher needed.

## Environment variables

| Variable | Purpose |
|---|---|
| `TOOLBELT_CONFIG` | Path to the config/secrets directory (e.g. `D:/etc` on Windows). Never inside this repo. Commands that need config files resolve paths relative to this. |

`TOOLBELT_CONFIG` must be set as a permanent system environment variable. Commands that need it will fail fast with a clear error if it is missing.

## Platform notes

- **Windows**: `toolbelt.bat` is the entry point. Add the repo root to `PATH` manually.
- **Linux**: `toolbelt` (no extension, bash) is the entry point. Run `bash setup.sh` after cloning — it prompts for `TOOLBELT_CONFIG`, creates the directory, and writes both env vars to the shell RC file. `setup.sh` is idempotent; re-running it skips lines already present.

## Existing commands

### `list`
Lists every toolbelt command and its purpose (from each entry's `description` in `commands.json`) as a plain, wrapped table — no borders.

### `hello`
Smoke-test command. Prints "Hello, World!".

### `bulk-git`
Runs git operations across a set of repos in parallel.

```
toolbelt bulk-git <config|config.json|--here> <git-command> [args...]
```

- **config**: filename resolved from `$TOOLBELT_CONFIG/repos/<name>.json` — the `.json` extension is optional (`writing` and `writing.json` both work). Absolute/relative paths to an existing file are also accepted as-is.
- **--here**: operates on all git repos found directly under the current working directory.
- `clone` is only valid with a config file (needs URLs). All other git subcommands work with both sources.

Config file format (`$TOOLBELT_CONFIG/repos/*.json`):
```json
{
  "root": "/path/to/clone/into",
  "repos": [
    {"repo-name": "https://github.com/user/repo.git"}
  ]
}
```

### `git-at`
Runs a single git command against one repo from a bulk-git config, from any working directory — no `cd` needed.

```
toolbelt git-at <config|config.json> <repo-name> <git-command> [args...]
```

- **config**: resolved the same way as `bulk-git` (`$TOOLBELT_CONFIG/repos/<name>.json`, `.json` optional, or an absolute/relative path to an existing file).
- **repo-name**: must match a key in the config's `repos` list; the repo path is resolved as `<root>/<repo-name>`.
- Output and exit code are passed through directly (stdin/stdout/stderr inherited), so interactive git commands work normally.

Output: one colored status line per repo — `[OK]` in green, `[FAIL]` in red with the last line of stderr appended.
