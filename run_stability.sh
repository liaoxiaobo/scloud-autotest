#!/bin/bash
# 阶段五：5轮稳定性验证

cd /Users/qichh/py_workspaces/claude_code_0514/playwright-sugon/playwright-sugon
mkdir -p sugon_web/logs

for i in 1 2 3 4 5; do
    echo "========== 阶段五 第${i}轮开始 $(date '+%H:%M:%S') =========="
    LOG_FILE="sugon_web/logs/test_tm_session_create_round${i}.log"
    .venv/bin/pytest sugon_web/testcase/network/test_tm_session_create.py -v --tb=short \
        --log-file="$LOG_FILE" --log-file-level=DEBUG \
        > /tmp/pytest_round${i}.out 2>&1
    EXIT_CODE=$?
    echo "========== 第${i}轮结束 $(date '+%H:%M:%S') 退出码: $EXIT_CODE =========="
    tail -5 /tmp/pytest_round${i}.out
    echo ""
done

echo "全部5轮执行完毕"
