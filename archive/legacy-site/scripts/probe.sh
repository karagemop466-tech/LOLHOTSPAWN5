#!/usr/bin/env bash
# Diagnostic probe. Writes findings to probe/ and publishes annotations.
set -uo pipefail
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
mkdir -p probe
OUT=probe/fetch.log
: > "$OUT"

echo "== HOTSPAWN PAGE ==" >> "$OUT"
code=$(curl -sS --compressed -A "$UA" -H "Accept-Language: en-US,en;q=0.9" \
  --max-time 45 -w '%{http_code}' -o probe/lol-pickems.html \
  https://play.hotspawn.com/lol-pickems || echo 000)
echo "status=$code bytes=$(wc -c < probe/lol-pickems.html 2>/dev/null || echo 0)" >> "$OUT"

echo "== FRAMEWORK MARKERS ==" >> "$OUT"
echo "next_data=$(grep -c '__NEXT_DATA__' probe/lol-pickems.html || true)" >> "$OUT"
echo "nuxt=$(grep -c '__NUXT__' probe/lol-pickems.html || true)" >> "$OUT"
echo "react_root=$(grep -c 'id=\"root\"' probe/lol-pickems.html || true)" >> "$OUT"

echo "== SCRIPT SRCS ==" >> "$OUT"
grep -oE '<script[^>]+src="[^"]+"' probe/lol-pickems.html 2>/dev/null | head -20 >> "$OUT"

echo "== API PATH LITERALS ==" >> "$OUT"
grep -oE '"/api/[a-zA-Z0-9_/.?=-]*"' probe/lol-pickems.html 2>/dev/null | sort -u | head -40 >> "$OUT"

echo "== ENDPOINT PROBES ==" >> "$OUT"
for p in /api/lol-pickems /api/lol/pickems /api/games/lol /api/v1/lol-pickems /api/pickems/lol /api/tournaments /api/matches/lol /lol-pickems/data /lol-pickems.json /api/health; do
  printf '%-26s ' "$p" >> "$OUT"
  curl -sS -o /dev/null -w '%{http_code} %{size_download}b %{content_type}\n' -A "$UA" --max-time 20 "https://play.hotspawn.com$p" >> "$OUT" 2>&1 || echo "ERR" >> "$OUT"
done

echo "== EXTERNAL SOURCE REACHABILITY ==" >> "$OUT"
for u in https://lol.fandom.com/api.php https://oracleselixir.com https://www.oddsportal.com https://polymarket.com https://gamma-api.polymarket.com/events?limit=1 https://gg.bet https://www.esportbet.com https://www.betway.com https://liquipedia.net/leagueoflegends/ https://www.leagueoflegends.com https://lolesports.com https://www.hotspawn.com/matches https://gol.gg https://www.bayes-esports.com; do
  printf '%-56s ' "$u" >> "$OUT"
  curl -sS -o /dev/null -w '%{http_code} %{size_download}b\n' -A "$UA" --max-time 20 "$u" >> "$OUT" 2>&1 || echo ERR >> "$OUT"
done

echo "== HTML HEAD ==" >> "$OUT"
head -c 1200 probe/lol-pickems.html >> "$OUT" 2>/dev/null

# Surface a compact summary as annotations (readable via gh run view)
n=$(grep -c 'Who will win' probe/lol-pickems.html || true)
echo "::notice::hotspawn status=$code bytes=$(wc -c < probe/lol-pickems.html) whoWillWin=$n"
grep -E '^(https://[^ ]* 2[0-9][0-9] )' "$OUT" | while read -r line; do echo "::notice::REACH $line"; done
echo "probe done"
