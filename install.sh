#!/usr/bin/env bash
set -euo pipefail

# Simple installer for NeOak from source.
# Prefers pipx if available, otherwise installs with pip --user.

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

have_cmd() { command -v "$1" >/dev/null 2>&1; }

if have_cmd pipx; then
  echo "Installing with pipx (isolated venv)..."
  pipx install "$PROJECT_DIR" --force
  echo "Done. Run: neoak"
  exit 0
fi

if have_cmd python3; then
  echo "Installing with pip (user install)..."
  python3 -m pip install --user "$PROJECT_DIR"
  echo "Done. If 'neoak' is not found, add ~/.local/bin to your PATH."
  echo "  For bash:  echo 'export PATH=\$HOME/.local/bin:\$PATH' >> ~/.bashrc && source ~/.bashrc"
  echo "  For zsh:   echo 'export PATH=\$HOME/.local/bin:\$PATH' >> ~/.zshrc && source ~/.zshrc"
  exit 0
fi

echo "Error: python3 not found on PATH. Please install Python 3.9+ and retry."
exit 1

