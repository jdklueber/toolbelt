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

`setup.sh` will check for `uv`, prompt for your `TOOLBELT_CONFIG` directory, create it, add both `TOOLBELT_CONFIG` and the repo to your PATH in your shell RC file, and pre-sync the `uv`-managed environment. That's all you need on Linux.

### 3. Windows — manual setup

Add two entries via System Properties → Environment Variables:

| Variable | Value |
|---|---|
| `PATH` | append `D:\git\toolbelt` (or wherever you cloned) |
| `TOOLBELT_CONFIG` | `D:\etc` (or wherever you want config/secrets to live) |

Open a new terminal and run `toolbelt hello` to confirm.

## Commands

### `hello`

Smoke test.

```
toolbelt hello
```

### `bulk-git`

Run git operations across multiple repos in parallel, with colored per-repo output.

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

#### Output

```
my-project                               clone        [OK]
other-repo                               clone        [FAIL]  repository not found
```

Exit code is `0` if all repos succeeded, `1` if any failed.

## Adding a new command

1. Create `commands/<name>.py`.
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
