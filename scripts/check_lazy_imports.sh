#!/bin/bash
# check_lazy_imports.sh - Verify lazy import policy by measuring RSS delta on import

set -euo pipefail

VENV_PYTHON="/home/akashdas/Desktop/Sentient-AI/.venv/bin/python"
THRESHOLD_MB=400
THRESHOLD_BYTES=$((THRESHOLD_MB * 1024 * 1024))

# Check available RAM (need > 25% free)
AVAILABLE_MB=$(free -m | awk 'NR==2 {print $7}')
TOTAL_MB=$(free -m | awk 'NR==2 {print $2}')
MIN_REQUIRED=$((TOTAL_MB / 4))

if (( AVAILABLE_MB < MIN_REQUIRED )); then
    echo "FAIL: Available RAM (${AVAILABLE_MB} MB) is below 25% threshold (${MIN_REQUIRED} MB)"
    exit 1
fi

echo "RAM check passed: ${AVAILABLE_MB} MB available (> 25% of ${TOTAL_MB} MB total)"

# Create a temporary Python script to measure RSS delta using tracemalloc
MEASURE_SCRIPT=$(mktemp)
cat > "$MEASURE_SCRIPT" << 'MEASURE_EOF'
import subprocess
import sys
import os

# Get baseline RSS
def get_rss_kb():
    with open('/proc/self/status', 'r') as f:
        for line in f:
            if line.startswith('VmRSS:'):
                return int(line.split()[1])  # in kB
    return None

# Measure baseline
rss_before = get_rss_kb()

# Import sentient.main
sys.path.insert(0, '/home/akashdas/Desktop/Sentient-AI/src')
import sentient.main

# Measure after import
rss_after = get_rss_kb()

rss_delta_kb = rss_after - rss_before
rss_delta_mb = rss_delta_kb / 1024
threshold_mb = 400

print(f"RSS before: {rss_before} kB ({rss_before / 1024:.1f} MB)")
print(f"RSS after:  {rss_after} kB ({rss_after / 1024:.1f} MB)")
print(f"Delta:      {rss_delta_kb} kB ({rss_delta_mb:.1f} MB)")
print(f"Threshold:  {threshold_mb} MB")

if rss_delta_kb * 1024 > threshold_mb * 1024 * 1024:
    print(f"FAIL: RSS delta ({rss_delta_mb:.1f} MB) exceeds threshold ({threshold_mb} MB)")
    sys.exit(1)
else:
    print(f"PASS: RSS delta ({rss_delta_mb:.1f} MB) is within threshold ({threshold_mb} MB)")
    sys.exit(0)
MEASURE_EOF

# Run the measurement script using the venv python
"$VENV_PYTHON" "$MEASURE_SCRIPT"
RESULT=$?

# Cleanup
rm -f "$MEASURE_SCRIPT"

exit $RESULT
