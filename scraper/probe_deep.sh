#!/usr/bin/env bash
# Deep probe: Pinnacle esports variants, Leaguepedia batching, other esportsbooks,
# and extracting the Hotspawn permalink rule from the Angular bundle.
set -u
mkdir -p probe research data

UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'

hr() { echo; echo "==================== $* ===================="; }

hr "1. Pinnacle E Sports (sport id 12) variants"
for u in \
  "https://guest.api.arcadia.pinnacle.com/0.1/sports/12/leagues?brandId=0" \
  "https://guest.api.arcadia.pinnacle.com/0.1/sports/12/leagues?brandId=1" \
  "https://guest.api.arcadia.pinnacle.com/0.1/sports/12/leagues?brandId=2" \
  "https://guest.api.arcadia.pinnacle.com/0.1/sports/12/leagues" \
  "https://guest.api.arcadia.pinnacle.com/0.1/sports/12/matchups?brandId=0" \
  "https://guest.api.arcadia.pinnacle.com/0.1/leagues/12/matchups?brandId=0" \
  "https://guest.api.arcadia.pinnacle.com/0.1/sports/12/leagues/0/matchups?brandId=0" \
  ; do
  code=$(curl -sS -o probe/last.txt -w '%{http_code}' --max-time 30 -A "$UA" -H 'Accept: application/json' "$u" 2>/dev/null || echo ERR)
  echo "--- $u -> $code ($(wc -c < probe/last.txt)B)"
  head -c 250 probe/last.txt; echo
done

hr "2. Extract permalink rule from play.hotspawn.com bundle"
curl -sSL --max-time 60 -A "$UA" 'https://play.hotspawn.com/lol-pickems' -o probe/lobby.html
JS=$(grep -oE 'src="[^"]*main-[A-Z0-9]+\.js"' probe/lobby.html | head -1 | sed 's/src="//;s/"$//')
echo "main js: $JS"
if [ -n "$JS" ]; then
  case "$JS" in
    http*) FULL="$JS";;
    /*)    FULL="https://play.hotspawn.com${JS}";;
    *)     FULL="https://play.hotspawn.com/${JS}";;
  esac
  echo "full: $FULL"
  curl -sSL --max-time 90 -A "$UA" "$FULL" -o probe/main.js
  echo "bundle bytes: $(wc -c < probe/main.js)"
  echo "--- occurrences of 'matches' ---"
  grep -oE '.{160}hotspawn\.com/matches.{120}' probe/main.js | head -20
  echo "--- occurrences of '/matches/' string literal ---"
  grep -oE '.{120}["'"'"']/matches/.{80}' probe/main.js | head -20
  echo "--- slugify-ish helpers ---"
  grep -oE '.{80}(slugify|permalink|toSlug|slug).{200}' probe/main.js | head -10
fi

hr "3. Leaguepedia: test batched IN query + rate limit behaviour"
python3 - <<'PY'
import json, urllib.request, urllib.parse, time, sys

UA = {'User-Agent': 'LOLHOTSPAWN5-PickDesk/1.0 (research; https://github.com/karagemop466-tech/LOLHOTSPAWN5)'}

def cargo(where, fields, limit=500, offset=0, table='ScoreboardGames'):
    q = urllib.parse.urlencode({
        'action': 'cargoquery', 'format': 'json', 'tables': table,
        'fields': fields, 'where': where, 'limit': str(limit), 'offset': str(offset),
    })
    url = 'https://lol.fandom.com/api.php?' + q
    for attempt in range(5):
        try:
            r = urllib.request.Request(url, headers=UA)
            body = urllib.request.urlopen(r, timeout=60).read().decode('utf-8', 'replace')
            j = json.loads(body)
            if 'error' in j:
                wait = 5 * (attempt + 1)
                print(f"   api error {j['error'].get('code')}, sleeping {wait}s")
                time.sleep(wait)
                continue
            return j.get('cargoquery', [])
        except Exception as e:
            print(f"   exc {e}, sleeping {5*(attempt+1)}s")
            time.sleep(5 * (attempt + 1))
    return []

def esc(s):
    return s.replace('"', '\\"')

teams = ["Solary", "Galions", "Ascent Gaming", "NTNUI Kometkameratene", "Solid Gaming",
         "DMG Esports Norway", "AceGaming", "Phong Vũ Buffalo", "El Menzah Esports",
         "Anyone's Legend", "T1", "Gen.G"]
inlist = ",".join('"%s"' % esc(t) for t in teams)
where = f'ScoreboardGames.Team1 IN ({inlist}) OR ScoreboardGames.Team2 IN ({inlist})'
fields = 'ScoreboardGames.Team1,ScoreboardGames.Team2,ScoreboardGames.WinTeam,ScoreboardGames.DateTime_UTC,ScoreboardGames.Tournament'
t0 = time.time()
rows = cargo(where, fields, limit=50)
print(f"IN query rows: {len(rows)} in {time.time()-t0:.1f}s")
for r in rows[:8]:
    print("   ", r['title'])

time.sleep(3)

print()
print("--- count query ---")
q = urllib.parse.urlencode({
    'action':'cargoquery','format':'json','tables':'ScoreboardGames',
    'fields':'COUNT(*)=cnt','where':'ScoreboardGames.DateTime_UTC >= "2026-01-01"','limit':'1'})
try:
    r = urllib.request.Request('https://lol.fandom.com/api.php?'+q, headers=UA)
    print(json.loads(urllib.request.urlopen(r, timeout=60).read().decode())[:400])
except Exception as e:
    print("count err", e)

time.sleep(3)

print()
print("--- Tournaments table fuzzy lookup ---")
for name in ["Prime League", "PRM", "Tunisian", "Komplettligaen", "Worlds 2026", "Arabian League"]:
    q = urllib.parse.urlencode({
        'action':'cargoquery','format':'json','tables':'Tournaments',
        'fields':'Tournaments.Name,Tournaments.OverviewPage,Tournaments.DateStartFuzzy',
        'where':f'Tournaments.Name LIKE "%{name}%"','order_by':'Tournaments.DateStartFuzzy DESC','limit':'8'})
    try:
        r = urllib.request.Request('https://lol.fandom.com/api.php?'+q, headers=UA)
        d = json.loads(urllib.request.urlopen(r, timeout=60).read().decode())
        rows = d.get('cargoquery', [])
        print(f"  '{name}': {len(rows)}")
        for x in rows[:8]:
            print("      ", x['title'])
    except Exception as e:
        print(f"  '{name}': ERR {e}")
    time.sleep(3)
PY

hr "4. Other esportsbook / odds endpoints"
probe_url() {
  local label="$1"; shift
  local code
  code=$(curl -sS -o probe/last.txt -w '%{http_code}' --max-time 30 -A "$UA" \
     -H 'Accept: application/json' "$@" 2>/dev/null || echo ERR)
  echo "--- ${label} -> ${code} ($(wc -c < probe/last.txt)B)"
  head -c 300 probe/last.txt; echo
}
probe_url "kambi unibet lol" 'https://eu-offering-api.kambicdn.com/offering/v2018/ub/listView/esports/all/all/all/matches.json?lang=en_GB&market=GB&client_id=2&channel_id=1&useCombined=true&ncid=1'
probe_url "kambi betfinder" 'https://eu-offering-api.kambicdn.com/offering/v2018/ub/listView/league_of_legends.json?lang=en_GB&market=GB&client_id=2&channel_id=1&useCombined=true'
probe_url "betexplorer esports lol" 'https://www.betexplorer.com/esports/league-of-legends/'
probe_url "oddsportal next data" 'https://www.oddsportal.com/esports/league-of-legends/'
probe_url "ggbet graphql" 'https://ggbet.com/api/v1/esports/live/matches'
probe_url "thunderpick api" 'https://api.thunderpick.io/graphql'
probe_url "stake sportsbook" 'https://api.stake.com/graphql'
probe_url "luckbox" 'https://api.luckbox.com/api/v1/matches'
probe_url "esportsbet" 'https://esportsbet.com/api/matches'
probe_url "sharkscope" 'https://www.egb.com/api/matches'
probe_url "elo none" 'https://api.lolesports.com/persisted/gw/getSchedule?hl=en-US&sport=lol'

hr "DONE"
