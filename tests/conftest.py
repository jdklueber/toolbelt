import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMMANDS_DIR = ROOT / "commands"

# Let tests `import toolbelt` (repo root) and `import _common` (commands/,
# matching how each command script imports it via its own script directory).
for _p in (str(ROOT), str(COMMANDS_DIR), str(Path(__file__).resolve().parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
