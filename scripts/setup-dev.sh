#!/usr/bin/env bash
# setup-dev.sh — Sentient AI Framework development environment setup
# Idempotent: safe to run multiple times.
set -euo pipefail

echo "=== Sentient AI Framework — Dev Setup ==="
echo ""

# --- Check Python version ---
python3 -c "
import sys
if sys.version_info < (3, 12):
    print(f'ERROR: Python {sys.version_info.major}.{sys.version_info.minor} found, but >= 3.12 is required.')
    sys.exit(1)
print(f'Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} — OK')
"

# --- Create virtual environment if missing ---
VENV_DIR=".venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment in $VENV_DIR/..."
    python3 -m venv "$VENV_DIR"
    echo "Virtual environment created."
else
    echo "Virtual environment already exists in $VENV_DIR/."
fi

# --- Activate venv ---
source "$VENV_DIR/bin/activate"

# --- Install project in editable mode with dev extras ---
echo "Installing project in editable mode..."
pip install -e ".[dev]" 2>&1 | tail -5

# --- Ensure core dev tools are available ---
echo "Verifying dev tools..."
pip install pytest pytest-asyncio pytest-cov ruff --quiet 2>/dev/null || true

# --- Verify tools work ---
echo ""
echo "--- Verification ---"
python3 -m pytest --version
ruff --version
echo ""

echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Activate the venv in a new shell:  source $VENV_DIR/bin/activate"
echo "  2. Run tests:                        pytest tests/ -v"
echo "  3. Run lint:                          ruff check src/ tests/"
echo "  4. Run tests with coverage:           pytest tests/ --cov=sentient --cov-report=term-missing"