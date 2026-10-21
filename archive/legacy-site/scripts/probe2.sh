#!/usr/bin/env bash
# Diagnostics round 2: find structured data endpoints + confirm robots/ToS posture.
set -uo pipefail
OUT="research/raw2"
mkdir -p "$OUT"
UA="ArenaResearchBot/1.0 (LoL pick research; +https://github.com/karagemop466-tech/LOLHOTSPAWN5) python-requests"
: > "$OUT/status.txt"

get() { # name url [curl args]
  local name="$1" url="$2"; shift 2
  local code
  code=$(curl -sS -L --max-time 40 -A "$UA" -H 'Accept-Language: en-US,en;q=0.9' \
        -o "$OUT/$name.body" -w '%{http_code}' "$@" "$url" 2>"$OUT/$name.err" || echo ERR)
  echo -e "$name\t$code\t$(wc -c < "$OUT/$name.body" 2>/dev/null || echo 0)B\t$url" >> "$OUT/status.txt"
}

API="https://phpstack-1372681-6459848.cloudwaysapps.com/api/v1"
get hs_fixtures           "$API/fixtures"
get hs_fixtures_lol       "$API/fixtures?game=lol"
get hs_fixtures_lol2      "$API/fixtures?game_slug=lol"
get hs_fixtures_pickem    "$API/fixtures?pickem=true"
get hs_tenant             "$API/tenants/slug/hotspawn"
get hs_permalinks         "$API/admin/gamification/fixtures/permalinks"
get hs_weekprizes         "$API/week-prizes/widget"

# Leaguepedia: retry with backoff, polite spacing
for i in 1 2 3; do
  code=$(curl -sS --max-time 40 -A "$UA" -o "$OUT/lp_try$i.body" -w '%{http_code}' \
    'https://lol.fandom.com/api.php?action=cargoquery&format=json&limit=50&tables=MatchSchedule&fields=Team1,Team2,DateTime_UTC,OverviewPage,Tournament,BestOf&where=DateTime_UTC%20%3E%3D%20%222026-10-20%22&order_by=DateTime_UTC%20ASC&origin=*' \
    2>"$OUT/lp_try$i.err" || echo ERR)
  echo -e "lp_try$i\t$code\t$(wc -c < "$OUT/lp_try$i.body")B\tleaguepedia cargoquery" >> "$OUT/status.txt"
  sleep 12
done
get lp_tables 'https://lol.fandom.com/api.php?action=cargoquery&format=json&limit=5&tables=MatchSchedule&fields=Team1'
get lp_scores 'https://lol.fandom.com/api.php?action=cargoquery&format=json&limit=20&tables=ScoreboardGames&fields=Tournament,Team1,Team2,Winner,DateTime_UTC&order_by=DateTime_UTC%20DESC'

# Liquipedia (API terms require identifying UA)
get liquipedia_api 'https://liquipedia.net/leagueoflegends/api.php?action=query&format=json&list=search&srsearch=Prime%20League&srlimit=3'
get liquipedia_page 'https://liquipedia.net/leagueoflegends/EMEA_Masters/2026/Summer'

# bo3.gg structured data
get bo3_api1 'https://api.bo3.gg/api/v1/matches?games=lol&page=1'
get bo3_api2 'https://bo3.gg/api/v1/matches?games=lol'
get bo3_hints 'https://bo3.gg/lol/matches'

# Prediction markets
get pm_events 'https://gamma-api.polymarket.com/events?tag_slug=league-of-legends&closed=false&limit=100'
get pm_events2 'https://gamma-api.polymarket.com/events?tag_slug=esports&closed=false&limit=100'
get pm_sports 'https://gamma-api.polymarket.com/sports'
get kalshi_series 'https://api.elections.kalshi.com/trade-api/v2/series?category=Esports'
get kalshi_events 'https://api.elections.kalshi.com/trade-api/v2/events?series_ticker=KXLOL&status=open&limit=50'

# Robots / terms posture
for site in www.oddsportal.com www.sportsgambler.com esportsbettinglounge.com liquipedia.net gol.gg www.bovada.lv www.midnite.com; do
  code=$(curl -sS -L --max-time 20 -A "$UA" -o "$OUT/robots_$site.txt" -w '%{http_code}' "https://$site/robots.txt" || echo ERR)
  echo -e "robots_$site\t$code" >> "$OUT/status.txt"
done

# Odds pages that returned 200 earlier
get og_oddsportal 'https://www.oddsportal.com/esports/league-of-legends/league-of-legends-emea-masters/'
get og_sportsgambler 'https://www.sportsgambler.com/betting-tips/esports/league-of-legends-predictions/'
get og_ebl 'https://esportsbettinglounge.com/odds/lol/'
get og_golgg 'https://gol.gg/tournament/tournament-matchlist/EMEA%20Masters%20Summer%202026/'

cat "$OUT/status.txt"
echo "=== robots oddsportal ==="; head -40 "$OUT/robots_www.oddsportal.com.txt"
echo "=== robots sportsgambler ==="; head -20 "$OUT/robots_www.sportsgambler.com.txt"
echo "=== robots liquipedia ==="; head -30 "$OUT/robots_liquipedia.net.txt"
echo "=== api samples ==="
for f in hs_fixtures hs_tenant lp_try1 lp_try3 pm_events kalshi_events bo3_api1; do
  echo "--- $f"; head -c 700 "$OUT/$f.body"; echo
done
