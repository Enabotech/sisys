#!/bin/bash
# Continuous regression script - runs two parallel pytest regressions in a loop
# Usage: ./scripts/continuous_regression.sh
#
# Stop: 按 Ctrl+C 或 q 键中断

set -e

BASE_DIR="/tmp/tmp_pytest_continuous"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_DIR="${BASE_DIR}_${TIMESTAMP}"

mkdir -p "$LOG_DIR"

ROUND=0
echo "========================================" > "$LOG_DIR/continuous.log"
echo "Continuous Regression Started at $(date)" >> "$LOG_DIR/continuous.log"
echo "========================================" >> "$LOG_DIR/continuous.log"

stop_flag=0

cleanup() {
    echo ""
    echo ""
    echo "🛑 Stopping continuous regression..."
    stop_flag=1
    # Send SIGTERM to child processes if still running
    [[ -n "$PID1" ]] && kill -TERM $PID1 2>/dev/null || true
    [[ -n "$PID2" ]] && kill -TERM $PID2 2>/dev/null || true
    [[ -n "$PID3" ]] && kill -TERM $PID3 2>/dev/null || true
}
trap cleanup SIGINT SIGTERM

echo "=========================================="
echo "   Continuous Regression Runner"
echo "=========================================="
echo "3个回归同时并行运行（各2进程）"
echo "中断: Ctrl+C"
echo "日志: $LOG_DIR/run*.log"
echo "状态: $LOG_DIR/continuous.log"
echo "=========================================="
echo ""

while [[ $stop_flag -eq 0 ]]; do
    ROUND=$((ROUND + 1))
    echo "[$(date)] ===== Round $ROUND started =====" | tee -a "$LOG_DIR/continuous.log"

    poetry run pytest tests/acceptance tests/unit -n 1 -v > "$LOG_DIR/run1.log" 2>&1 &
    PID1=$!

    poetry run pytest tests/unit tests/integration/ tests/acceptance -n 2 -v > "$LOG_DIR/run2.log" 2>&1 &
    PID2=$!

    poetry run pytest tests/integration tests/unit tests/acceptance -n 1 -v > "$LOG_DIR/run3.log" 2>&1 &
    PID3=$!

    # Wait for both to complete
    wait $PID1
    STATUS1=$?
    wait $PID2
    STATUS2=$?
    wait $PID3
    STATUS3=$?

    # Check if we should stop after this round
    if [[ $stop_flag -eq 1 ]]; then
        echo "[$(date)] ⏹️ Stopping after Round $ROUND completed"
        break
    fi

    # Extract results
    RESULT1=$(grep -E "(passed|failed|skipped)" "$LOG_DIR/run1.log" | tail -1)
    RESULT2=$(grep -E "(passed|failed|skipped)" "$LOG_DIR/run2.log" | tail -1)
    RESULT3=$(grep -E "(passed|failed|skipped)" "$LOG_DIR/run3.log" | tail -1)

    echo -e "[$(date)] Round $ROUND:\nRun1=$STATUS1 ($RESULT1)\nRun2=$STATUS2 ($RESULT2)\nRun3=$STATUS3 ($RESULT3)" | tee -a "$LOG_DIR/continuous.log"

    # Check for failures
    if echo "$RESULT1" | grep -q "failed" || echo "$RESULT2" | grep -q "failed" || echo "$RESULT3" | grep -q "failed"; then
        echo "[$(date)] ⚠️ FAILURE detected in Round $ROUND!" | tee -a "$LOG_DIR/continuous.log"
        echo "--- Run1 failure details ---" >> "$LOG_DIR/continuous.log"
        grep -A5 "FAILED" "$LOG_DIR/run1.log" >> "$LOG_DIR/continuous.log" 2>/dev/null || echo "No FAILED found" >> "$LOG_DIR/continuous.log"
        echo "--- Run2 failure details ---" >> "$LOG_DIR/continuous.log"
        grep -A5 "FAILED" "$LOG_DIR/run2.log" >> "$LOG_DIR/continuous.log" 2>/dev/null || echo "No FAILED found" >> "$LOG_DIR/continuous.log"
        echo "--- Run3 failure details ---" >> "$LOG_DIR/continuous.log"
        grep -A5 "FAILED" "$LOG_DIR/run3.log" >> "$LOG_DIR/continuous.log" 2>/dev/null || echo "No FAILED found" >> "$LOG_DIR/continuous.log"
    else
        echo "[$(date)] ✅ Round $ROUND passed" >> "$LOG_DIR/continuous.log"
    fi

    echo "" >> "$LOG_DIR/continuous.log"

    # Small delay between rounds
    sleep 2
done

echo "=========================================="
echo "   Continuous Regression Stopped"
echo "=========================================="
