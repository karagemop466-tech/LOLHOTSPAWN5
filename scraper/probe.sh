#!/usr/bin/env bash
# Discovery probe for play.hotspawn.com data sources.
# Runs on a GitHub Actions runner (the agent sandbox has no general egress).
set -u

UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
mkdir -p probe

hr() { echo; echo "==================== $* ===================="; }

hr "1. lobby HTML"
curl -sSL -A "$UA" --max-time 60 \
  -D probe/headers-lobby.txt \
  'https://play.hotspawn.com/lol-pickems' -o probe/lol-pickems.html
echo "bytes: $(wc -c < probe/lol-pickems.html)"
echo "--- status line ---"; head -1 probe/headers-lobby.txt
echo "--- content-type / server ---"; grep -iE '^(content-type|server|x-)' probe/headers-lobby.txt | head -10

hr "1a. script srcs"
grep -oE 'src="[^"]+\.js[^"]*"' probe/lol-pickems.html | sed 's/src="//;s/"$//' | sort -u | head -60

hr "1b. preload / modulepreload links"
grep -oE '<link[^>]+href="[^"]+\.(js|css)[^"]*"' probe/lol-pickems.html | sed -E 's/.*href="([^"]*)".*/\1/' | sort -u | head -40

hr "1c. api-ish strings in HTML"
grep -oE '"(https?://[^"]*(api|graphql|backend)[^"]*)"' probe/lol-pickems.html | sort -u | head -40

hr "1d. framework markers"
grep -oE '(__NEXT_DATA__|__NUXT__|__remixContext|window\.__[A-Za-z_]+|data-page=|vite|webpack|buildManifest)' \
  probe/lol-pickems.html | sort -u | head -20

hr "1e. count of 'hotspawn.com/matches/' links (server-rendered matches?)"
grep -oE 'hotspawn\.com/matches/[a-z0-9-]+' probe/lol-pickems.html | sort -u | wc -l

hr "1f. any JSON blobs"
grep -oE 'application/(json|ld\+json)' probe/lol-pickems.html | sort | uniq -c

hr "2. candidate API paths on play.hotspawn.com"
for p in \
  "/api/matches" "/api/match" "/api/lobby" "/api/events" "/api/pickems" "/api/fixtures" \
  "/api/v1/matches" "/api/v1/match" "/api/v1/lobby" "/api/v1/events" "/api/v1/fixtures" \
  "/api/week" "/api/matches/lol" "/api/lol/matches" "/api/games/lol/matches" \
  "/api/tournaments" "/api/leaderboard" "/api/user" "/api/me" "/api/config" ; do
  code=$(curl -sS -o probe/resp.txt -w '%{http_code}' --max-time 20 -A "$UA" \
    -H 'Accept: application/json' "https://play.hotspawn.com${p}" 2>/dev/null || echo ERR)
  size=$(wc -c < probe/resp.txt 2>/dev/null || echo 0)
  echo "GET play.hotspawn.com${p} -> ${code} (${size}B)"
  if [ "${code}" = "200" ] && [ "${size}" -gt 60 ]; then
    echo "    preview: $(head -c 400 probe/resp.txt | tr -d '\n')"
  fi
done

hr "3. alternate hosts"
for h in "api.play.hotspawn.com" "api.hotspawn.com" "backend.play.hotspawn.com" \
         "play-api.hotspawn.com" "data.hotspawn.com" "graphql.hotspawn.com" ; do
  code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 12 -A "$UA" "https://${h}/" 2>/dev/null || echo ERR)
  echo "https://${h}/ -> ${code}"
done

hr "4. www.hotspawn.com WP REST API"
code=$(curl -sS -o probe/wp-root.json -w '%{http_code}' --max-time 30 -A "$UA" \
  'https://www.hotspawn.com/wp-json/' 2>/dev/null || echo ERR)
echo "wp-json root -> ${code} ($(wc -c < probe/wp-root.json 2>/dev/null)B)"
head -c 3000 probe/wp-root.json
echo
echo "--- routes mentioning 'match' or 'fixture' ---"
python3 - <<'PY'
import json
try:
    d = json.load(open('probe/wp-root.json'))
except Exception as e:
    print("parse fail:", e); raise SystemExit
routes = d.get('routes', {})
hits = [r for r in routes if any(k in r.lower() for k in ('match','fixture','event','team','tournament','game','pick'))]
for r in sorted(hits)[:80]:
    print(" ", r)
print("total routes:", len(routes), "hits:", len(hits))
PY

hr "5. WP namespaces"
python3 - <<'PY'
import json
try:
    d = json.load(open('probe/wp-root.json'))
except Exception as e:
    print("parse fail:", e); raise SystemExit
ns = set()
for r in d.get('routes', {}):
    if '/' in r and r.startswith('/'):
        ns.add(r.split('/')[1])
print(sorted(ns))
PY

hr "6. robots.txt of both sites"
echo "--- play ---"; curl -sS --max-time 20 -A "$UA" https://play.hotspawn.com/robots.txt
echo "--- www ---";  curl -sS --max-time 20 -A "$UA" https://www.hotspawn.com/robots.txt | head -40

hr "DONE"
