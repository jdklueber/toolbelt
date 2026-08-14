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


def setup_remote_repo(tmp_path, subdir=None):
    """Creates a bare remote repo and a clean clone with an initial commit on main.

    Returns (bare_path, clone_path) as Path objects.

    subdir: optional subdirectory name under tmp_path to namespace this repo,
    useful when calling this helper multiple times for the same tmp_path.
    """
    import subprocess

    base = tmp_path / subdir if subdir else tmp_path

    bare = base / "remote.git"
    bare.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "--bare", "-q", str(bare)], check=True)

    seed = base / "_seed"
    seed.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(seed)], check=True)
    subprocess.run(["git", "-C", str(seed), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(seed), "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", str(seed), "checkout", "-b", "main"], check=True, capture_output=True)
    (seed / "README.md").write_text("hi\n")
    subprocess.run(["git", "-C", str(seed), "add", "."], check=True)
    subprocess.run(["git", "-C", str(seed), "commit", "-q", "-m", "init"], check=True)
    subprocess.run(["git", "-C", str(seed), "remote", "add", "origin", str(bare)], check=True)
    subprocess.run(["git", "-C", str(seed), "push", "-q", "-u", "origin", "main"], check=True)
    # Point the bare repo's HEAD at main so clones check out the right branch.
    subprocess.run(["git", "-C", str(bare), "symbolic-ref", "HEAD", "refs/heads/main"], check=True)

    clone = base / "clone"
    subprocess.run(["git", "clone", "-q", str(bare), str(clone)], check=True)
    subprocess.run(["git", "-C", str(clone), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(clone), "config", "user.name", "Test"], check=True)

    return bare, clone


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
