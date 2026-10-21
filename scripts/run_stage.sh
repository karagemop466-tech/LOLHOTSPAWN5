#!/usr/bin/env bash
# Run one pipeline stage, always recording its outcome into data/collect_log.txt so the
# result is auditable from the repo (Actions logs are not retrievable in this environment).
set -uo pipefail
name="$1"; shift
mkdir -p data
start=$(date -u +%s)
out=$("$@" 2>&1); rc=$?
end=$(date -u +%s)
{
  echo "=== $name @ $(date -u +%Y-%m-%dT%H:%M:%SZ) rc=$rc elapsed=$((end-start))s ==="
  echo "$out" | tail -40
} >> data/collect_log.txt
echo "[$name] rc=$rc elapsed=$((end-start))s"
exit 0
