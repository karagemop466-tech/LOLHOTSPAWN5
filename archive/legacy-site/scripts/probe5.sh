#!/usr/bin/env bash
# Probe 5: Leaguepedia CargoExport bulk results (independent of Hotspawn).
set -uo pipefail
OUT="research/raw5"; mkdir -p "$OUT"
UA="ArenaResearchBot/1.0 (+https://github.com/karagemop466-tech/LOLHOTSPAWN5)"
: > "$OUT/status.txt"
get() { local name="$1" url="$2"; shift 2
  local code; code=$(curl -sS -L --max-time 120 -A "$UA" -o "$OUT/$name.body" -w '%{http_code}' "$@" "$url" 2>"$OUT/$name.err" || echo ERR)
  echo -e "$name\t$code\t$(wc -c < "$OUT/$name.body" 2>/dev/null || echo 0)B\t$url" >> "$OUT/status.txt"; }

E="https://lol.fandom.com/wiki/Special:CargoExport"
Q1='tables=MatchSchedule&fields=OverviewPage%2CTeam1%2CTeam2%2CWinner%2CDateTime_UTC%2CBestOf&where=DateTime_UTC%20%3E%3D%20%222025-10-01%22&order_by=DateTime_UTC&limit=500&format=json'
get lp_ms_500 "$E?$Q1"
Q2='tables=MatchSchedule&fields=OverviewPage%2CTeam1%2CTeam2%2CWinner%2CDateTime_UTC%2CBestOf&where=DateTime_UTC%20%3E%3D%20%222025-10-01%22&order_by=DateTime_UTC&limit=500&offset=500&format=json'
get lp_ms_500b "$E?$Q2"
Q3='tables=MatchSchedule&fields=OverviewPage%2CTeam1%2CTeam2%2CWinner%2CDateTime_UTC&where=Team1%3D%22Solary%22%20OR%20Team2%3D%22Solary%22&order_by=DateTime_UTC&limit=50&format=json'
get lp_solary "$E?$Q3"
Q4='tables=ScoreboardGames&fields=OverviewPage%2CTeam1%2CTeam2%2CWinner%2CDateTime_UTC&where=DateTime_UTC%20%3E%3D%20%222026-10-01%22&order_by=DateTime_UTC&limit=500&format=json'
get lp_sg "$E?$Q4"
Q5='tables=MatchSchedule&fields=OverviewPage%2CTeam1%2CTeam2%2CWinner%2CDateTime_UTC&where=OverviewPage%20LIKE%20%22%25Komplettligaen%25%22&limit=200&format=json'
get lp_komplett "$E?$Q5"

get lp_api_retry 'https://lol.fandom.com/api.php?action=cargoquery&format=json&tables=MatchSchedule&fields=Team1%2CTeam2%2CWinner%2CDateTime_UTC%2COverviewPage&limit=5'

cat "$OUT/status.txt"
echo "=== lp_ms_500 head ==="; head -c 700 "$OUT/lp_ms_500.body"; echo
echo "=== lp_ms_500b head ==="; head -c 400 "$OUT/lp_ms_500b.body"; echo
echo "=== lp_solary head ==="; head -c 500 "$OUT/lp_solary.body"; echo
echo "=== lp_komplett head ==="; head -c 500 "$OUT/lp_komplett.body"; echo
