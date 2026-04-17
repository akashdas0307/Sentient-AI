#!/usr/bin/env bash
# run_tests_safe.sh — Resource-constrained test runner
#
# Prevents test runs from consuming all system RAM and causing freezes.
# The key problem: pytest collects ALL tests → imports ALL of sentient →
# loads chromadb (~500MB) + sentence_transformers (~1GB) + litellm (~200MB).
#
# SOLUTION: Run tests per-directory in SEPARATE processes. Each subprocess
# only loads what that directory's tests need, keeping peak RAM low.
#
# Usage:
#   bash scripts/run_tests_safe.sh                    # quick check (no coverage)
#   bash scripts/run_tests_safe.sh --cov              # per-module coverage
#   bash scripts/run_tests_safe.sh --cov sentient.api # single module coverage
#   bash scripts/run_tests_safe.sh tests/unit/core/   # specific directory
set -euo pipefail

MAX_RAM_PCT=60
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# Activate venv
source .venv/bin/activate 2>/dev/null || true

# ── Resource check ──────────────────────────────────────────────────
check_resources() {
    local total_kb avail_kb avail_pct
    total_kb=$(awk '/MemTotal/ {print $2}' /proc/meminfo)
    avail_kb=$(awk '/MemAvailable/ {print $2}' /proc/meminfo)
    avail_pct=$((avail_kb * 100 / total_kb))

    echo "RAM: ${avail_pct}% available ($((avail_kb/1024))MB of $((total_kb/1024))MB)"

    if [ "$avail_pct" -lt 25 ]; then
        echo "ERROR: Only ${avail_pct}% RAM available. Refusing to run tests."
        echo "Free up memory or close other applications."
        exit 1
    fi
}

# ── Set per-process memory limit ────────────────────────────────────
set_memory_limit() {
    local avail_kb limit_kb
    avail_kb=$(awk '/MemAvailable/ {print $2}' /proc/meminfo)
    # Allow MAX_RAM_PCT% of available RAM for this process
    limit_kb=$((avail_kb * MAX_RAM_PCT / 100))
    # Python often needs more virtual memory than RSS, so set a generous
    # virtual limit (2x the RAM limit) but rely on the RSS check above
    # for the real guard
    ulimit -v $((limit_kb * 2)) 2>/dev/null || true
}

# ── Run a single test directory in isolation ────────────────────────
run_dir() {
    local dir="$1"
    shift
    echo "── Testing: $dir ──"
    python -m pytest "$dir" -x -q --tb=short --ignore=tests/wetware "$@"
    local rc=$?
    if [ $rc -ne 0 ]; then
        echo "FAILED: $dir (exit $rc)"
        return $rc
    fi
    echo "PASSED: $dir"
    return 0
}

# ── Quick run: each directory in separate subprocess ────────────────
run_quick() {
    echo "=== Quick test run (per-directory isolation) ==="
    check_resources

    local dirs=(tests/unit/core tests/unit/api tests/unit/persona tests/unit/sleep tests/unit/prajna tests/unit/test_main.py tests/integration)
    local failed=0
    local passed=0
    local total=0

    for dir in "${dirs[@]}"; do
        if [ ! -e "$dir" ]; then
            continue
        fi
        total=$((total + 1))
        check_resources  # Re-check before each directory
        if run_dir "$dir"; then
            passed=$((passed + 1))
        else
            failed=$((failed + 1))
            # Continue to next directory instead of stopping
        fi
    done

    echo ""
    echo "=== Results: $passed/$total directories passed, $failed failed ==="
    return $failed
}

# ── Coverage: per-module in separate subprocess ──────────────────────
run_cov_module() {
    local module="$1"
    shift || true
    echo "=== Coverage for $module ==="
    check_resources
    # Find test directories that test this module
    local test_dirs=""
    case "$module" in
        sentient.core)       test_dirs="tests/unit/core/" ;;
        sentient.api)        test_dirs="tests/unit/api/" ;;
        sentient.persona)    test_dirs="tests/unit/persona/" ;;
        sentient.sleep)      test_dirs="tests/unit/sleep/" ;;
        sentient.prajna)     test_dirs="tests/unit/prajna/" ;;
        sentient.health)     test_dirs="tests/unit/core/" ;;  # health tests are in core
        sentient.memory)     test_dirs="tests/unit/core/" ;;  # memory tests are in core
        sentient.thalamus)   test_dirs="tests/unit/core/" ;;  # some thalamus tests
        sentient.brainstem)  test_dirs="tests/unit/core/" ;;  # some brainstem tests
        sentient.main)       test_dirs="tests/unit/test_main.py" ;;
        *)                   test_dirs="tests/unit/" ;;
    esac

    python -m pytest $test_dirs -x -q --tb=short --ignore=tests/wetware \
        "--cov=$module" --cov-report=term-missing "$@"
}

run_cov_all() {
    echo "=== Full coverage (per-module, isolated) ==="
    check_resources
    local modules=(
        "sentient.core"
        "sentient.api"
        "sentient.persona"
        "sentient.sleep"
        "sentient.prajna"
    )

    local total_failed=0
    for mod in "${modules[@]}"; do
        check_resources
        if run_cov_module "$mod"; then
            echo "OK: $mod"
        else
            echo "FAIL: $mod"
            total_failed=$((total_failed + 1))
        fi
    done

    echo "=== Coverage complete, $total_failed module(s) had failures ==="
    return $total_failed
}

# ── Main ─────────────────────────────────────────────────────────────
case "${1:-quick}" in
    --cov)
        shift || true
        if [ -n "${1:-}" ]; then
            run_cov_module "$@"
        else
            run_cov_all "$@"
        fi
        ;;
    quick|*)
        # If a specific test path is given, run just that
        if [ -e "${1:-}" ] 2>/dev/null; then
            check_resources
            run_dir "$@"
        else
            run_quick "$@"
        fi
        ;;
esac