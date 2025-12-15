#!/bin/bash

# Daily Agent Runner Script
# This script is designed to be run from cron with proper environment setup

# Set up logging
LOG_DIR="/Users/ncejda/github/ncejda-g2/logs"
LOG_FILE="$LOG_DIR/daily_agent_$(date +\%Y\%m\%d).log"

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Redirect all output to log file
exec >> "$LOG_FILE" 2>&1

echo "=================================================="
echo "Daily Agent Run Started: $(date)"
echo "=================================================="

# Change to project directory
cd /Users/ncejda/github/ncejda-g2 || {
    echo "ERROR: Failed to change to project directory"
    exit 1
}

# Initialize conda for bash (needed for cron environment)
eval "$(/Users/ncejda/miniconda3/bin/conda shell.bash hook)"

# Run the agent
echo "Executing daily_agent/agent.py..."
/Users/ncejda/miniconda3/bin/python3 daily_agent/agent.py

# Capture exit code
EXIT_CODE=$?

# If agent succeeded, commit and push changes
if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo "Committing and pushing changes to GitHub..."

    # Extract day number from README for commit message
    DAY=$(grep -oP "Days running.*: \K\d+" README.md || echo "X")

    git add .
    git commit -m "🤖 Day ${DAY} - Autonomous README update"
    git push origin main
    git log --oneline -1

    PUSH_EXIT=$?
    echo "Git push exit code: $PUSH_EXIT"
else
    echo "Agent failed, skipping git operations"
fi

echo "=================================================="
echo "Daily Agent Run Completed: $(date)"
echo "Exit Code: $EXIT_CODE"
echo "=================================================="

exit $EXIT_CODE
