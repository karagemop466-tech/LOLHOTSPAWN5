#!/usr/bin/env bash
# Probe 3: exact endpoints needed by the pipeline.
set -uo pipefail
OUT="research/raw3"; mkdir -p "$OUT"
UA="ArenaResearchBot/1.0 (+https://github.com/karagemop466-tech/LOLHOTSPAWN5)"
: > "$OUT/status.txt"
get() { local name="$1" url="$2"; shift 2
  local code; code=$(curl -sS -L --max-time 40 -A "$UA" -o "$OUT/$name.body" -w '%{http_code}' "$@" "$url" 2>"$OUT/$name.err" || echo ERR)
  echo -e "$name\t$code\t$(wc -c < "$OUT/$name.body" 2>/dev/null || echo 0)B\t$url" >> "$OUT/status.txt"; }

P="https://guest.api.arcadia.pinnacle.com/0.1"
K="https://api.elections.kalshi.com/trade-api/v2"
get pin_leagues     "$P/sports/12/leagues"
get pin_matchups    "$P/sports/12/matchups"
get pin_lol_league  "$P/leagues/9587/matchups"
get pin_markets     "$P/matchups/1638906945/markets/related/straight"

get kal_series      "$K/series/KXLOLGAME"
get kal_game_mkts   "$K/markets?series_ticker=KXLOLGAME&status=open&limit=1000"
get kal_lol_mkts    "$K/markets?series_ticker=KXLOL&status=open&limit=1000"
get kal_events      "$K/events?series_ticker=KXLOLGAME&status=open&limit=200"

get bo3_disciplines 'https://api.bo3.gg/api/v1/disciplines'
get bo3_d2          'https://api.bo3.gg/api/v1/matches?discipline_id=2&page=1'
get bo3_d3          'https://api.bo3.gg/api/v1/matches?discipline_id=3&page=1'
get bo3_gameslug    'https://api.bo3.gg/api/v1/matches?game_slug=lol&page=1'
get bo3_upcoming    'https://api.bo3.gg/api/v1/matches?status=upcoming&page=1&limit=100'
get bo3_tournaments 'https://api.bo3.gg/api/v1/tournaments?page=1&limit=100'

get pm_lol_sorted   'https://gamma-api.polymarket.com/events?tag_slug=league-of-legends&closed=false&limit=100&order=startDate&ascending=false'
get pm_esports_sorted 'https://gamma-api.polymarket.com/events?tag_slug=esports&closed=false&limit=100&order=startDate&ascending=false'

cat "$OUT/status.txt"
echo "=== pin_markets ==="; head -c 1200 "$OUT/pin_markets.body"; echo
echo "=== kal_game_mkts ==="; head -c 800 "$OUT/kal_game_mkts.body"; echo
echo "=== kal_events ==="; head -c 500 "$OUT/kal_events.body"; echo
echo "=== bo3_disciplines ==="; head -c 600 "$OUT/bo3_disciplines.body"; echo
echo "=== bo3_d2 first ==="; head -c 400 "$OUT/bo3_d2.body"; echo
echo "=== pm_lol_sorted titles ==="; python3 - <<'PY'
import json
try:
    d=json.load(open('research/raw3/pm_lol_sorted.body'))
    for e in d[:20]: print(e.get('startDate','')[:16], e.get('title','')[:80])
except Exception as ex: print('err',ex)
PY
