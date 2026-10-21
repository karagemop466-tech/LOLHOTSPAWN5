#!/usr/bin/env bash
# One-off reachability probe. Writes raw samples to research/raw/ (git-ignored from the site build).
set -uo pipefail
OUT="research/raw"
mkdir -p "$OUT"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
: > "$OUT/status.txt"

probe() { # name url [extra curl args...]
  local name="$1" url="$2"; shift 2
  local code
  code=$(curl -sS -L --max-time 45 -A "$UA" -o "$OUT/$name.body" -w '%{http_code}' "$@" "$url" 2>"$OUT/$name.err" || echo "ERR")
  local size
  size=$(wc -c < "$OUT/$name.body" 2>/dev/null || echo 0)
  echo -e "$name\t$code\t${size}B\t$url" >> "$OUT/status.txt"
}

# --- Hotspawn (the list we must cover) ---
probe hotspawn_lol "https://play.hotspawn.com/lol-pickems"
probe hotspawn_lobby "https://play.hotspawn.com/lobby"
probe hotspawn_match "https://www.hotspawn.com/matches/galions-vs-solary-em-2026-summer-main-event-1081205"

# --- Official / structured esports data ---
probe lp_schedule "https://lol.fandom.com/api.php?action=cargoquery&format=json&limit=5&tables=MatchSchedule&fields=Team1,Team2,DateTime_UTC,OverviewPage&order_by=DateTime_UTC%20DESC"
probe lp_teams "https://lol.fandom.com/api.php?action=cargoquery&format=json&limit=5&tables=Teams&fields=Name,OverviewPage,Location"
probe liquipedia "https://liquipedia.net/leagueoflegends/api.php?action=query&format=json&list=search&srsearch=Prime%20League&srlimit=3"
probe lolesports "https://esports-api.lolesports.com/persisted/gw/getLeagues?hl=en-US" -H "x-api-key: 0TvQnueqKa5mxJntVWt0w4LpLSSiF19a8wLoPLD4ntCH6SxHBHg"
probe golgg "https://gol.gg/tournament/list/"

# --- Prediction market (external market-implied probabilities) ---
probe polymarket "https://gamma-api.polymarket.com/markets?closed=false&limit=50&tag=esports"
probe polymarket_search "https://gamma-api.polymarket.com/public-search?q=league%20of%20legends&limit_per_type=10"
probe kalshi "https://api.elections.kalshi.com/trade-api/v2/markets?limit=5&series_ticker=KXLOL"

# --- Esports books / odds aggregators ---
probe oddsportal "https://www.oddsportal.com/esports/league-of-legends/"
probe betexplorer "https://www.betexplorer.com/esports/league-of-legends/"
probe egamersworld "https://egamersworld.com/league-of-legends/matches"
probe bo3 "https://bo3.gg/lol/matches"
probe thunderpick "https://thunderpick.io/esports/league-of-legends"
probe pinnacle "https://www.pinnacle.com/en/esports/league-of-legends/matchups/"
probe betway "https://betway.com/esports/league-of-legends"
probe gg_bet "https://gg.bet/en/esports/league-of-legends"
probe unikrn "https://unikrn.com/esports/league-of-legends"
probe betonline "https://www.betonline.ag/sportsbook/esports"
probe bovada "https://www.bovada.lv/sports/esports/league-of-legends"
probe midnite "https://www.midnite.com/esports/league-of-legends"
probe esportsbet "https://www.esportsbets.com/league-of-legends/"
probe dk "https://sportsbook.draftkings.com/leagues/esports/league-of-legends"
probe fanatics "https://sportsbook.fanatics.com/esports/league-of-legends"

echo "--- structure hints ---"
{
  echo "## hotspawn_lol title/scripts"
  grep -oE '<title>[^<]*</title>' "$OUT/hotspawn_lol.body" | head -3
  grep -oE 'src="[^"]+"' "$OUT/hotspawn_lol.body" | sort -u | head -40
  echo
  echo "## hotspawn_lol api-ish strings"
  grep -oE '"/api/[A-Za-z0-9_/?=&.-]+"' "$OUT/hotspawn_lol.body" | sort -u | head -30
  grep -oE 'https://[a-z0-9.-]+/api/[A-Za-z0-9_/?=&.-]+' "$OUT/hotspawn_lol.body" | sort -u | head -30
  echo
  echo "## hotspawn_lol NEXT_DATA?"
  grep -c '__NEXT_DATA__' "$OUT/hotspawn_lol.body" || true
  grep -c '__NUXT__' "$OUT/hotspawn_lol.body" || true
  echo
  echo "## hotspawn match links count"
  grep -oE 'href="[^"]*/matches/[^"]+"' "$OUT/hotspawn_lol.body" | wc -l
  grep -oE 'href="[^"]*/matches/[^"]+"' "$OUT/hotspawn_lol.body" | head -5
  echo
  echo "## polymarket sample"
  head -c 900 "$OUT/polymarket.body" || true
  echo
  echo "## lp_schedule sample"
  head -c 900 "$OUT/lp_schedule.body" || true
  echo
  echo "## liquipedia sample"
  head -c 500 "$OUT/liquipedia.body" || true
  echo
  echo "## lolesports sample"
  head -c 500 "$OUT/lolesports.body" || true
} > "$OUT/hints.txt" 2>&1

cat "$OUT/status.txt"
