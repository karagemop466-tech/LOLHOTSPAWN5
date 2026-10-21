#!/usr/bin/env bash
# Probe the discovered Hotspawn backend API:
#   https://phpstack-1372681-6459848.cloudwaysapps.com/api/v1/fixtures
# Runs on a GitHub Actions runner (agent sandbox has no general egress).
set -u

API='https://phpstack-1372681-6459848.cloudwaysapps.com/api/v1'
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
mkdir -p probe

hr() { echo; echo "==================== $* ===================="; }

get() {  # get <label> <url>
  local label="$1" url="$2"; shift 2
  local code
  code=$(curl -sS -o probe/last.json -w '%{http_code}' --max-time 45 \
    -A "$UA" -H 'Accept: application/json' -H 'Origin: https://play.hotspawn.com' \
    -H 'Referer: https://play.hotspawn.com/' "$@" "$url" 2>/dev/null || echo ERR)
  local size; size=$(wc -c < probe/last.json 2>/dev/null || echo 0)
  echo "--- ${label}"
  echo "    GET ${url}  -> ${code} (${size}B)"
  if [ "${code}" = "200" ] && [ "${size}" -gt 20 ]; then
    cp "probe/last.json" "probe/$(echo "${label}" | tr -c 'A-Za-z0-9' '_').json"
    echo "    preview: $(head -c 600 probe/last.json | tr -d '\n')"
  fi
}

hr "A. tenant"
get tenant "${API}/tenants/slug/hotspawn"

hr "B. fixtures (bare)"
get fixtures_bare "${API}/fixtures"

hr "C. fixtures (pagination variants)"
get f_page1 "${API}/fixtures?page=1"
get f_per_page "${API}/fixtures?per_page=5"
get f_limit "${API}/fixtures?limit=5"
get f_limit500 "${API}/fixtures?limit=500"

hr "D. fixtures (filters)"
get f_game_lol "${API}/fixtures?game=lol"
get f_game_lol2 "${API}/fixtures?game=League%20of%20Legends"
get f_gameid2 "${API}/fixtures?game_id=2"
get f_gameid1 "${API}/fixtures?game_id=1"
get f_upcoming "${API}/fixtures?status=upcoming"
get f_open "${API}/fixtures?status=open"
get f_live "${API}/fixtures?status=live"

hr "E. week prizes + permalinks (shape hints)"
get weekprizes "${API}/week-prizes/widget"
get permalinks "${API}/admin/gamification/fixtures/permalinks"

hr "F. structural analysis of the best fixtures response"
python3 - <<'PY'
import json, glob, os

best = None
for path in sorted(glob.glob('probe/*.json')):
    name = os.path.basename(path)[:-5]
    if not name.startswith(('f_', 'fixtures')):
        continue
    try:
        d = json.load(open(path))
    except Exception as e:
        print(f"{name}: not json ({e})")
        continue
    if isinstance(d, (list, dict)):
        best = (name, d, path)
        break

if not best:
    print("no json fixtures response found")
    raise SystemExit

name, d, path = best
print(f"analysing {path}")
print("top-level type:", type(d).__name__)
if isinstance(d, dict):
    print("top-level keys:", list(d.keys()))
    for k, v in d.items():
        t = type(v).__name__
        n = len(v) if isinstance(v, (list, dict, str)) else v
        print(f"   {k}: {t} (len={n})")
    # find the list of fixtures
    cand = None
    for k, v in d.items():
        if isinstance(v, list) and v and isinstance(v[0], dict):
            cand = v
            print("   -> using key:", k)
            break
else:
    cand = d

if cand:
    print("record count:", len(cand))
    print("record keys:", sorted(cand[0].keys()))
    print()
    print("FIRST RECORD (pretty):")
    print(json.dumps(cand[0], indent=2)[:4000])
    print()
    print("SECOND RECORD (pretty):")
    if len(cand) > 1:
        print(json.dumps(cand[1], indent=2)[:2000])
PY

hr "DONE"
