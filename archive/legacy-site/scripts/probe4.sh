#!/usr/bin/env bash
# Probe 4: find a bulk results feed for low-tier leagues + verify source URLs.
set -uo pipefail
OUT="research/raw4"; mkdir -p "$OUT"
UA="ArenaResearchBot/1.0 (+https://github.com/karagemop466-tech/LOLHOTSPAWN5)"
: > "$OUT/status.txt"
get() { local name="$1" url="$2"; shift 2
  local code; code=$(curl -sS -L --max-time 45 -A "$UA" -o "$OUT/$name.body" -w '%{http_code}' "$@" "$url" 2>"$OUT/$name.err" || echo ERR)
  echo -e "$name\t$code\t$(wc -c < "$OUT/$name.body" 2>/dev/null || echo 0)B\t$url" >> "$OUT/status.txt"; }

B="https://api.bo3.gg/api/v1"
get bo3_filter1 "$B/matches?page=1&limit=25&filter%5Bdiscipline_id%5D=3"
get bo3_filter2 "$B/matches?page=1&limit=25&filter%5BdisciplineIds%5D=3"
get bo3_filter3 "$B/matches?page=1&limit=25&discipline=3"
get bo3_filter4 "$B/matches?page=1&limit=25&disciplines=3"
get bo3_filter5 "$B/tournaments?page=1&limit=25&filter%5Bdiscipline_id%5D=3"
get bo3_filter6 "$B/matches?page=1&limit=25&filter%5Bgame%5D=lol"

# Leaguepedia alternative endpoint (Cargo export) - polite single calls
get lp_export 'https://lol.fandom.com/wiki/Special:CargoExport?tables=MatchSchedule&fields=Team1%2CTeam2%2CWinner%2CTournament%2CDateTime_UTC&limit=50&format=json&where=DateTime_UTC%20%3E%20%222026-10-01%22'
get lp_api_small 'https://lol.fandom.com/api.php?action=cargoquery&format=json&tables=MatchSchedule&fields=Team1%2CTeam2%2CWinner&limit=3'
sleep 20
get lp_export2 'https://lol.fandom.com/wiki/Special:CargoExport?tables=Tournaments&fields=Name%2CYear&limit=20&format=json'
get lp_rest 'https://lol.fandom.com/api.php?action=query&format=json&list=recentchanges&rclimit=2'

# Hotspawn competition-level fixtures
H="https://phpstack-1372681-6459848.cloudwaysapps.com/api/v1"
get hs_comp_fixtures "$H/competitions/34812/fixtures"
get hs_fixtures_comp "$H/fixtures?competition_id=34812"
get hs_fixtures_status "$H/fixtures?sport_alias=lol&status=all&tenantId=1"
get hs_competitions "$H/competitions?sport_alias=lol"

# Verify the exact URLs we will publish as source links
get v_pinnacle 'https://guest.api.arcadia.pinnacle.com/0.1/matchups/1638906945/markets/related/straight'
get v_kalshi 'https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXLOLGAME&status=open&limit=5'
get v_kalshi_page 'https://kalshi.com/markets/kxlolgame'
get v_lolesports 'https://lolesports.com/en-US/'
get v_golgg 'https://gol.gg/tournament/list/'
get v_liquipedia 'https://liquipedia.net/leagueoflegends/Portal:Tournaments'
get v_polymarket 'https://polymarket.com/sports/league-of-legends/games'

cat "$OUT/status.txt"
echo "=== bo3 variants (first result title/slug) ==="
python3 - <<'PY'
import json,glob
for f in sorted(glob.glob('research/raw4/bo3_filter*.body')):
    try:
        d=json.load(open(f)); r=(d.get('results') or [{}])[0]
        print(f, '| total', (d.get('total') or {}).get('count'), '| first:', r.get('slug'), '| disc', r.get('discipline_id'))
    except Exception as e: print(f,'ERR',e)
PY
echo "=== lp export ==="; head -c 400 "$OUT/lp_export.body"; echo
echo "=== lp export2 ==="; head -c 300 "$OUT/lp_export2.body"; echo
echo "=== hs comp ==="; head -c 400 "$OUT/hs_comp_fixtures.body"; echo
