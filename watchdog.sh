#!/bin/bash
# Watchdog: tự restart agent-hub nếu không response
if ! curl -sf http://localhost:7777/api/agents > /dev/null 2>&1; then
  pkill -f "agent-hub/server.py" 2>/dev/null
  sleep 1
  cd /home/nathan-ubutu/.openclaw/workspace/agent-hub
  nohup python3 server.py >> /tmp/agent-hub.log 2>&1 &
  echo "[$(date)] Agent Hub restarted" >> /tmp/agent-hub-watchdog.log
fi
