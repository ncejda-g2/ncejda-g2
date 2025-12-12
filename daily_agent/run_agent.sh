#!/bin/bash
# Wrapper script to run the autonomous agent
# This ensures environment variables are loaded correctly

set -e

# Navigate to project root
cd "$(dirname "$0")/.."

# Load environment variables from .env if it exists
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Run the agent
python3 daily_agent/agent.py
