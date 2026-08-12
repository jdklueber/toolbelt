# toolbelt

A personal CLI dispatcher for cross-platform productivity scripts. One command to rule them all.

```
toolbelt <command> [args...]
```

## Setup

### 1. Install uv

toolbelt uses [uv](https://docs.astral.sh/uv/) to manage its Python interpreter and dependencies — it's the only thing you need to install globally. See the [installation guide](https://docs.astral.sh/uv/getting-started/installation/) for your platform.

### 2. Clone the repo

```
git clone https://github.com/jdklueber/toolbelt.git
```

### 3. Linux — run the setup script

```bash
bash setup.sh
source ~/.bashrc   # or ~/.zshrc
toolbelt hello
```

`setup.sh` will check for `uv`, prompt for your `TOOLBELT_CONFIG` directory, create it (including a `repos/` subdirectory), add both `TOOLBELT_CONFIG` and the repo to your PATH in your shell RC file, and pre-sync the `uv`-managed environment. That's all you need on Linux.

### 3. Windows — run the setup script

```bat
setup.bat
```

`setup.bat` checks for `uv` and installs it via `winget` if it's missing. It then prints instructions for the two manual steps that require System Properties → Environment Variables:

| Variable | Value |
|---|---|
| `PATH` | append the repo root (e.g. `D:\git\toolbelt`) |
| `TOOLBELT_CONFIG` | your config/secrets directory (e.g. `D:\etc`) |

Open a new terminal after setting those and run `toolbelt hello` to confirm.

## Commands

### `hello`

Smoke test.

```
toolbelt hello
```

### `list`

Print all registered commands and their descriptions.

```
toolbelt list
```

### `doctor`

Health check: prints configured environment variables, pulls the latest toolbelt code, syncs dependencies with `uv`, and runs the test suite.

```
toolbelt doctor
```

Output covers four steps in order:

1. **Environment variables** — shows `TOOLBELT_CONFIG` (highlighted in yellow if unset).
2. **Git pull** — pulls from the remote; reports `[OK]` or `[FAIL]` with the last line of output.
3. **Dependencies** — runs `uv sync` to bring the managed environment up to date.
4. **Tests** — runs `pytest -q` via `sys.executable`; reports pass count or lists failures by name.

### `bulk-git`

Run git operations across multiple repos in parallel.

```
toolbelt bulk-git <config.json|--here> <git-command> [args...]
```

**Clone all repos defined in a config file:**
```
toolbelt bulk-git writing-repos.json clone
```

**Run a git command on all repos in a config file:**
```
toolbelt bulk-git writing-repos.json checkout main
toolbelt bulk-git writing-repos.json pull
```

**Run a git command on all repos under the current directory:**
```
toolbelt bulk-git --here status
toolbelt bulk-git --here fetch --prune
```

#### Config file format

Config files live in `$TOOLBELT_CONFIG/repos/`. Pass just the filename; absolute paths also work.

```json
{
  "root": "/path/to/clone/into",
  "repos": [
    {"my-project": "https://github.com/user/my-project.git"},
    {"other-repo": "https://github.com/user/other-repo.git"}
  ]
}
```

`root` is created automatically on `clone` if it doesn't exist.

**List available configs, or the repos within one:**
```
toolbelt bulk-git --list
toolbelt bulk-git --list writing-repos
```

`status` gets special handling: instead of raw git output, each repo reports `CLEAN`/`CHANGES` plus ahead/behind counts against its upstream (or `no upstream` if it isn't tracking one).

#### Output

```
my-project                               clone        [OK]
other-repo                               clone        [FAIL]  repository not found
```

Exit code is `0` if all repos succeeded, `1` if any failed.

### `git-at`

Run a single git command against one repo from a bulk-git config, from any working directory — no `cd` needed.

```
toolbelt git-at <config> <repo-name> <git-command> [args...]
```

- **config**: resolved the same way as `bulk-git` — filename from `$TOOLBELT_CONFIG/repos/` (`.json` extension optional), or an absolute/relative path to an existing file.
- **repo-name**: must match a key in the config's `repos` list; the repo path is resolved as `<root>/<repo-name>`.
- **--list [config]**: same as `bulk-git --list` — list all available configs, or the repos within one.

stdin/stdout/stderr are passed through directly, so interactive git commands work normally.

```
toolbelt git-at writing my-novel log --oneline -5
toolbelt git-at writing my-novel diff HEAD~1
```

### `sync-all`

Keep every repo in a config up to date in one shot: aborts before touching anything if any repo has uncommitted changes, then clones missing repos and fetch+pull+pushes the rest, in parallel. Pulls use plain merge semantics (`--no-rebase`); repos with no upstream tracking branch or in a detached HEAD state fail the pull step with git's own error message.

```
toolbelt sync-all <config|config.json>
toolbelt sync-all --list [config]
```

Each repo reports a per-step audit trail (`clone`/`fetch`/`pull`/`push`, each tagged `OK`/`WARN`/`BLOCKED`/`CONFLICT`/`FAIL`). If a pull changes a dependency manifest (`package.json`, `uv.lock`, `Cargo.toml`, etc.), that repo gets an extra `deps-changed` `WARN` step naming the changed file(s), as a nudge to re-sync your local environment.

```
toolbelt sync-all writing-repos
```

Exit code is `0` if all repos succeeded, `1` if any failed or a merge conflict occurred.

## Adding a new command

1. Create `commands/<name>.py`. Handle `--help`/`-h` at the top of `main()` using `_common.wants_help` and `_common.print_help` — see any existing command for the pattern.
2. Register it in `commands.json`:
   ```json
   "name": {
     "script": "{TOOLBELT_ROOT}/commands/name.py",
     "args": "",
     "description": "One-line purpose, shown by `toolbelt list`."
   }
   ```

`{TOOLBELT_ROOT}` is substituted at runtime with the absolute path to the repo, so paths work from any working directory.

Need a third-party package? Add it to `[project.dependencies]` in `pyproject.toml` (`uv add <package>` from the repo root) and run `uv lock`. `uv` resolves it into the managed environment automatically the next time `toolbelt` runs — no separate install step for anyone using it.

## Running tests

Dependencies (project and dev, currently just `pytest`) are managed with [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run pytest
```

`toolbelt doctor` also runs the suite (via `sys.executable -m pytest -q`) as part of its health check. Since the `toolbelt`/`toolbelt.bat` entry points launch everything through `uv run`, `sys.executable` is always the `uv`-managed interpreter — `doctor` finds `pytest` whether you invoke it via `uv run` or the bare `toolbelt` command.

## License

MIT License with Commons Clause. Free to use for any purpose, including commercial use on your own machines. Resale or redistribution for profit is not permitted. See [LICENSE](LICENSE).
