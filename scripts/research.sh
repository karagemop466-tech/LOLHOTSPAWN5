#!/usr/bin/env bash
set -uo pipefail
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
mkdir -p research/samples
R=research/samples
log(){ echo "$*" | tee -a research/probe2.log; }

log "=== HOTSPAWN FIXTURES API ==="
for u in \
 "https://phpstack-1372681-6459848.cloudwaysapps.com/api/v1/fixtures?sport_alias=lol&tenantId=1" \
 "https://phpstack-1372681-6459848.cloudwaysapps.com/api/v1/fixtures?sportAlias=lol&tenantId=1" ; do
  code=$(curl -sS --compressed -A "$UA" -H "Accept: application/json" --max-time 40 -w '%{http_code}' -o "$R/fixtures_$(echo "$u"|md5sum|cut -c1-6).json" "$u")
  log "  $code  $u"
done

log "=== PINNACLE ARCADIA ==="
PK="CmX2KcMrXuFmNg6YFbmTxE0y9CIrOi0R"
for s in 12 16 17; do
  code=$(curl -sS --compressed -A "$UA" --max-time 40 \
    -H "X-API-Key: $PK" -H "Accept: application/json" \
    -H "X-Device-UUID: 00000000-0000-0000-0000-000000000000" \
    -w '%{http_code}' -o "$R/pin_sport$s.json" \
    "https://guest.api.arcadia.pinnacle.com/0.1/sports/$s/matchups")
  log "  sport=$s $code bytes=$(wc -c < "$R/pin_sport$s.json")"
done
code=$(curl -sS --compressed -A "$UA" --max-time 40 -H "X-API-Key: $PK" -H "Accept: application/json" \
  -w '%{http_code}' -o "$R/pin_sports.json" "https://guest.api.arcadia.pinnacle.com/0.1/sports")
log "  sports-list $code bytes=$(wc -c < "$R/pin_sports.json")"

log "=== LEAGUEPEDIA CARGO ==="
LP='https://lol.fandom.com/api.php?action=cargoquery&format=json&limit=3&tables=MatchSchedule&fields=Team1,Team2,DateTime_UTC,OverviewPage,Winner'
code=$(curl -sS --compressed -A "$UA" -w '%{http_code}' -o "$R/lp_test.json" "$LP")
log "  $code bytes=$(wc -c < "$R/lp_test.json")"
head -c 400 "$R/lp_test.json" >> research/probe2.log; echo >> research/probe2.log

log "=== POLYMARKET LOL ==="
for u in "https://gamma-api.polymarket.com/events?limit=20&closed=false&tag_slug=league-of-legends" \
         "https://gamma-api.polymarket.com/markets?limit=20&closed=false&tag_slug=league-of-legends" ; do
  code=$(curl -sS --compressed -A "$UA" --max-time 40 -w '%{http_code}' -o "$R/pm_$(echo "$u"|md5sum|cut -c1-6).json" "$u")
  log "  $code bytes=$(wc -c < "$R/pm_$(echo "$u"|md5sum|cut -c1-6).json")  $u"
done

log "=== KALSHI LOL ==="
code=$(curl -sS --compressed -A "$UA" --max-time 40 -w '%{http_code}' -o "$R/kalshi_lol.json" \
  "https://api.elections.kalshi.com/trade-api/v2/markets?limit=50&series_ticker=KXLOL")
log "  $code bytes=$(wc -c < "$R/kalshi_lol.json")"

log "=== BOVADA LOL ==="
code=$(curl -sS --compressed -A "$UA" --max-time 40 -w '%{http_code}' -o "$R/bovada.html" \
  "https://www.bovada.lv/sports/esports/league-of-legends")
log "  $code bytes=$(wc -c < "$R/bovada.html")"

log "=== ODDS PORTAL LOL ==="
code=$(curl -sS --compressed -A "$UA" --max-time 40 -w '%{http_code}' -o "$R/oddsportal.html" \
  "https://www.oddsportal.com/esports/league-of-legends/")
log "  $code bytes=$(wc -c < "$R/oddsportal.html")"

# trim anything large so the repo stays light
python3 - <<'PY'
import os,glob
for f in glob.glob('research/samples/*'):
    s=os.path.getsize(f)
    if s>250_000 and not f.endswith('.log'):
        os.remove(f); print('removed large',f,s)
PY
ls -la "$R" >> research/probe2.log
