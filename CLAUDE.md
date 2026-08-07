# Toolbelt

A personal cross-platform CLI dispatcher. Commands are registered in `commands.json` and invoked via a single `toolbelt <command>` entry point.

## Architecture

```
toolbelt/
  toolbelt.py       # dispatcher — reads commands.json, resolves paths, runs the command
  toolbelt.bat      # Windows PATH entry point; calls toolbelt.py with %~dp0 so no hardcoded paths
  commands.json     # command registry: name → shell command template
  commands/         # one script per command
```

### How dispatch works

`toolbelt.py` reads `commands.json`, looks up the command name, substitutes `{TOOLBELT_ROOT}` with the absolute path of the repo root (derived from `__file__`), splits the result into a list, appends any extra CLI args, and runs it via `subprocess.run`.

### Adding a new command

1. Create `commands/<name>.py`.
2. Add an entry to `commands.json`:
   ```json
   "name": "python {TOOLBELT_ROOT}/commands/name.py"
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

### `hello`
Smoke-test command. Prints "Hello, World!".

### `bulk-git`
Runs git operations across a set of repos in parallel.

```
toolbelt bulk-git <config.json|--here> <git-command> [args...]
```

- **config.json**: filename resolved from `$TOOLBELT_CONFIG/repos/<name>.json`. Absolute paths also accepted.
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

Output: one colored status line per repo — `[OK]` in green, `[FAIL]` in red with the last line of stderr appended.
