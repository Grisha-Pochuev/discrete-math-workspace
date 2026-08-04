#!/usr/bin/env bash
set -u
out="${1:-resource-monitor.log}"
interval="${2:-30}"
while true; do
  {
    date -u +%FT%TZ
    grep -E 'MemTotal|MemAvailable|SwapTotal|SwapFree' /proc/meminfo || true
    df -h . || true
    ps -eo pid,ppid,rss,stat,comm,args --sort=-rss | head -30 || true
    if [ -f /sys/fs/cgroup/memory.events ]; then
      cat /sys/fs/cgroup/memory.events || true
    fi
    echo '---'
  } >> "$out" 2>&1
  sleep "$interval"
done
