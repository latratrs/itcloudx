#!/bin/bash
START=$(date +%s)
echo "Claude job started..."
echo "----------------------"
claude --dangerously-skip-permissions "$@"
END=$(date +%s)
RUNTIME=$((END-START))
echo "----------------------"
echo "Claude finished."
echo "Runtime: ${RUNTIME}s"
echo "I finished command latest run"
