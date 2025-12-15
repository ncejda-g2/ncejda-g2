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

echo "=================================================="
echo "Daily Agent Run Completed: $(date)"
echo "Exit Code: $EXIT_CODE"
echo "=================================================="

exit $EXIT_CODE
