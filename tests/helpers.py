import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMMANDS_DIR = ROOT / "commands"


def load_command(module_name, filename):
    """Load a commands/*.py script as an importable module.

    Needed for bulk-git.py / git-at.py since a hyphenated filename can't be
    `import`-ed directly.
    """
    spec = importlib.util.spec_from_file_location(module_name, COMMANDS_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def init_git_repo(path, with_commit=True):
    import subprocess

    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Test"], check=True)
    if with_commit:
        (path / "README.md").write_text("hi\n")
        subprocess.run(["git", "-C", str(path), "add", "."], check=True)
        subprocess.run(["git", "-C", str(path), "commit", "-q", "-m", "init"], check=True)
