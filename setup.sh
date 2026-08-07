#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Colors ────────────────────────────────────────────────────────────────────
GREEN="\033[92m"
YELLOW="\033[93m"
CYAN="\033[96m"
RESET="\033[0m"

ok()   { echo -e "${GREEN}  [OK]${RESET}  $*"; }
info() { echo -e "${CYAN}  -->  ${RESET}$*"; }
warn() { echo -e "${YELLOW}  [!]  ${RESET}$*"; }

# ── Sanity checks ─────────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo "Error: python3 not found. Install Python 3 and try again."
    exit 1
fi

# ── Detect shell RC file ───────────────────────────────────────────────────────
case "$SHELL" in
    */zsh)  RC_FILE="$HOME/.zshrc" ;;
    */bash) RC_FILE="$HOME/.bashrc" ;;
    *)      RC_FILE="$HOME/.bashrc" ;;
esac

echo ""
echo "  toolbelt setup"
echo "  ────────────────────────────────────────"
echo ""

# ── Config directory ───────────────────────────────────────────────────────────
echo "  Where should toolbelt store its configuration?"
echo "  (Credentials and config files live here, outside the repo)"
echo ""
read -rp "  TOOLBELT_CONFIG [${HOME}/.config/toolbelt]: " config_dir
config_dir="${config_dir:-${HOME}/.config/toolbelt}"
echo ""

mkdir -p "$config_dir/repos"
ok "Config directory ready: $config_dir"

# ── Write to RC file ───────────────────────────────────────────────────────────
add_to_rc() {
    local marker="$1"
    local line="$2"
    if grep -qF "$marker" "$RC_FILE" 2>/dev/null; then
        warn "Already in $RC_FILE: $line"
    else
        echo "$line" >> "$RC_FILE"
        ok "Added to $RC_FILE: $line"
    fi
}

add_to_rc "TOOLBELT_CONFIG"  "export TOOLBELT_CONFIG=\"$config_dir\""
add_to_rc "toolbelt"         "export PATH=\"$SCRIPT_DIR:\$PATH\""

# ── Make entry point executable ────────────────────────────────────────────────
chmod +x "$SCRIPT_DIR/toolbelt"
ok "toolbelt marked executable"

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "  ────────────────────────────────────────"
info "Run:  source $RC_FILE"
info "Then: toolbelt hello"
echo ""
