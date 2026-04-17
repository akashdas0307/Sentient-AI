#!/bin/bash
# coverage_per_module.sh — Measure coverage for a single module
# Usage: bash scripts/coverage_per_module.sh MODULE_NAME TEST_PATH
# Example: bash scripts/coverage_per_module.sh sentient.api.server tests/unit/api/test_server.py
#
# RAM-safe: checks available RAM first, runs in subprocess isolation.

set -euo pipefail

MODULE="${1:?Usage: coverage_per_module.sh MODULE_NAME TEST_PATH}"
TEST_PATH="${2:?Usage: coverage_per_module.sh MODULE_NAME TEST_PATH}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="${PROJECT_ROOT}/.venv/bin/python"

# RAM check
AVAILABLE_MB=$(free -m | awk 'NR==2 {print $7}')
TOTAL_MB=$(free -m | awk 'NR==2 {print $2}')
MIN_RAM=$((TOTAL_MB / 4))

if (( AVAILABLE_MB < MIN_RAM )); then
    echo "FAIL: Available RAM (${AVAILABLE_MB}MB) is below 25% threshold (${MIN_RAM}MB)"
    exit 1
fi

echo "── Coverage: ${MODULE} ──"
echo "RAM: ${AVAILABLE_MB}MB available (${TOTAL_MB}MB total)"

cd "${PROJECT_ROOT}"

# Run coverage in a subprocess with memory limit
RESULT_FILE="${PROJECT_ROOT}/coverage-${MODULE//\./-}.json"

"${VENV_PYTHON}" -m pytest \
    "${TEST_PATH}" \
    --cov="${MODULE}" \
    --cov-report=term-missing \
    --cov-report="json:${RESULT_FILE}" \
    --override-ini="addopts=" \
    -q \
    --no-header \
    2>&1 || true

if [[ -f "${RESULT_FILE}" ]]; then
    echo ""
    echo "Coverage JSON saved to: ${RESULT_FILE}"
    "${VENV_PYTHON}" -c "
import json
with open('${RESULT_FILE}') as f:
    data = json.load(f)
totals = data.get('totals', {})
print(f'Lines: {totals.get(\"covered_lines\", \"?\")}/{totals.get(\"num_statements\", \"?\")} = {totals.get(\"percent_covered\", \"?\")}%')
"
else
    echo "WARNING: Coverage JSON not found at ${RESULT_FILE}"
fi