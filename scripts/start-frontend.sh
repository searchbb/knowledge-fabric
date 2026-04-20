#!/bin/bash
export NVM_DIR="/Users/mac/.nvm"
export PATH="/Users/mac/.nvm/versions/node/v22.17.0/bin:/Users/mac/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export HOME="/Users/mac"

LOGF="/Users/mac/Downloads/code/knowledge-fabric/logs/fe-debug.log"
echo "=== launched $(date) ===" >> "$LOGF"
echo "PORT3000=$(lsof -ti:3000)" >> "$LOGF"
\
  exec /Users/mac/.nvm/versions/node/v22.17.0/bin/npm run dev >> "$LOGF" 2>&1
echo "FAILED cd/npm exit=$?" >> "$LOGF"
