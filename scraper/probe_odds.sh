#!/usr/bin/env bash
# Probe keyless external odds / esportsbook sources + verify Hotspawn permalinks.
# Runs on a GitHub Actions runner.
set -u
mkdir -p probe research data

UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
LP_UA='LOLHOTSPAWN5-PickDesk/1.0 (research; https://github.com/karagemop466-tech/LOLHOTSPAWN5)'
API='https://phpstack-1372681-6459848.cloudwaysapps.com/api/v1'

hr() { echo; echo "==================== $* ===================="; }

hr "1. Pinnacle guest API: find esports sport id"
curl -sS --max-time 60 -A "$UA" -H 'Accept: application/json' \
  'https://guest.api.arcadia.pinnacle.com/0.1/sports?brandId=0' -o probe/pin_sports.json
echo "bytes: $(wc -c < probe/pin_sports.json)"
python3 - <<'PY'
import json
d = json.load(open('probe/pin_sports.json'))
print("sports:", len(d))
for s in d:
    n = (s.get('name') or '').lower()
    if any(k in n for k in ('esport','league of legend','lol','dota','counter','e-sport','lol')):
        print("  HIT", s.get('id'), s.get('name'), "matchupCount=", s.get('matchupCount'), "SE=", s.get('matchupCountSE'))
print("--- first 40 ids/names ---")
for s in d[:60]:
    print("  ", s.get('id'), s.get('name'), s.get('matchupCount'), s.get('matchupCountSE'))
PY

hr "2. Pinnacle: leagues for candidate esports sport ids"
python3 - <<'PY'
import json, urllib.request, ssl
UA={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'}
d=json.load(open('probe/pin_sports.json'))
cands=[s['id'] for s in d if (s.get('matchupCountSE') or 0)>0 or (s.get('name') or '').lower() in ('esports','e-sports','league of legends')]
if not cands:
    cands=[s['id'] for s in d]
print("candidate sport ids:", cands[:15])
for sid in cands[:12]:
    for path in (f"https://guest.api.arcadia.pinnacle.com/0.1/sports/{sid}/leagues?brandId=0",
                 f"https://guest.api.arcadia.pinnacle.com/0.1/leagues?sportId={sid}&brandId=0"):
        try:
            req=urllib.request.Request(path, headers=UA)
            body=urllib.request.urlopen(req, timeout=40).read().decode('utf-8','replace')
            j=json.loads(body)
            if isinstance(j,list) and j:
                print(f"OK {path} -> {len(j)} leagues")
                for lg in j[:25]:
                    print("    ", lg.get('id'), lg.get('name'), 'eventCount=', lg.get('eventCount'))
                break
        except Exception as e:
            print(f"ERR {path} -> {e}")
PY

hr "3. Hotspawn permalink verification"
python3 - <<'PY'
import json, urllib.request, urllib.error, re, datetime as dt
UA={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'}
def slug(s):
    s=re.sub(r'[^a-zA-Z0-9]+','-',(s or '').strip().lower()).strip('-')
    return s
def head(url):
    req=urllib.request.Request(url, headers=UA, method='GET')
    try:
        r=urllib.request.urlopen(req, timeout=40)
        return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:
        return 'ERR:'+type(e).__name__

tests=[]
for t in ["https://www.hotspawn.com/matches/galions-vs-solary-em-2026-summer-main-event-1081205",
          "https://www.hotspawn.com/matches/ascent-gaming-vs-ntnui-kometkameratene-komplettligaen-2026-autumn-1071214"]:
    tests.append((t, head(t)))
for u,s in tests:
    print(s, u)

# try constructed URL for a fixture id NOT in the SSR html (pick one deep-future)
print("--- constructed for a far-future fixture ---")
print(head("https://www.hotspawn.com/matches/acegaming-vs-hannover-esports-ev-prm-2nd-division-26-27-fall-1"))
PY

hr "4. Other keyless odds endpoints"
probe_url() {
  local label="$1"; shift
  local code
  code=$(curl -sS -o probe/last.txt -w '%{http_code}' --max-time 35 -A "$UA" \
     -H 'Accept: application/json' "$@" 2>/dev/null || echo ERR)
  echo "--- ${label} -> ${code} ($(wc -c < probe/last.txt)B)"
  head -c 400 probe/last.txt; echo
}
probe_url "pinnacle guest matchups direct (sport 29)" 'https://guest.api.arcadia.pinnacle.com/0.1/sports/29/leagues?brandId=0'
probe_url "pinnacle guest all leagues v2" 'https://guest.api.arcadia.pinnacle.com/0.1/leagues?brandId=0'
probe_url "draftkings lol" 'https://sportsbook.draftkings.com/sites/US-SB/api/v5/eventgroups/88670846?format=json'
probe_url "draftkings esports leagues" 'https://sportsbook.draftkings.com/sites/US-SB/api/v2/leagues?format=json'
probe_url "ggbet api" 'https://api.ggbet.com/api/v1/esports/matches'
probe_url "1xbet esports feed" 'https://1xbet.com/service-api/LineFeed/Get1x2_VZip?sports=40&count=50&lng=en'
probe_url "unibet esports" 'https://www.unibet.com/sportsbook-feeds/views/filter/esports'
probe_url "betexplorer lol" 'https://www.betexplorer.com/league-of-legends/'
probe_url "oddsportal lol" 'https://www.oddsportal.com/esports/league-of-legends/'
probe_url "liquipedia api" 'https://liquipedia.net/leagueoflegends/api.php?action=query&format=json&meta=siteinfo'
probe_url "gol.gg" 'https://gol.gg/tournament/list/'
probe_url "pandascore" 'https://api.pandascore.co/lol/matches'
probe_url "abios" 'https://api.abiosgaming.com/v2/matches'

hr "5. Leaguepedia: build a check for a low-tier team"
for T in "AceGaming" "NTNUI Kometkameratene" "Phong Vũ Buffalo" "El Menzah Esports"; do
  TQ=$(python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))" "$T")
  curl -sS --max-time 40 -A "$LP_UA" -H 'Accept: application/json' \
    "https://lol.fandom.com/api.php?action=cargoquery&format=json&tables=ScoreboardGames&fields=ScoreboardGames.Team1,ScoreboardGames.Team2,ScoreboardGames.WinTeam,ScoreboardGames.DateTime_UTC,ScoreboardGames.Tournament&where=ScoreboardGames.Team1%3D%22${TQ}%22%20OR%20ScoreboardGames.Team2%3D%22${TQ}%22&order_by=ScoreboardGames.DateTime_UTC%20DESC&limit=3" \
    -o probe/lp_$RANDOM.json 2>/dev/null
  echo "--- $T"
  ls -t probe/lp_*.json 2>/dev/null | head -1 | xargs -r head -c 600
  echo
done

hr "6. Leaguepedia: tournament coverage check for our tournaments"
python3 - <<'PY'
import json, urllib.request, urllib.parse, datetime as dt
UA={'User-Agent':'LOLHOTSPAWN5-PickDesk/1.0 (research; https://github.com/karagemop466-tech/LOLHOTSPAWN5)'}
tours=["PRM 3rd Division 26-27 Fall","PRM 2nd Division 26-27 Fall","Tunisian Super League 2026",
       "RIVALS LEAGUE Season 2","4 Nations 2026 Halloween Heist","Komplettligaen 2026 Autumn",
       "Worlds 2026 Main Event","Arabian League 2nd Division 2026 Summer"]
for t in tours:
    q=urllib.parse.urlencode({
      'action':'cargoquery','format':'json','tables':'ScoreboardGames',
      'fields':'ScoreboardGames.Team1,ScoreboardGames.Team2,ScoreboardGames.WinTeam,ScoreboardGames.DateTime_UTC',
      'where':f'ScoreboardGames.Tournament="{t}"','order_by':'ScoreboardGames.DateTime_UTC DESC','limit':'5'})
    try:
        r=urllib.request.Request("https://lol.fandom.com/api.php?"+q, headers=UA)
        d=json.loads(urllib.request.urlopen(r,timeout=45).read().decode())
        rows=d.get('cargoquery',[])
        print(f"{t!r}: {len(rows)} rows")
        for x in rows[:3]:
            print("   ", x['title'])
    except Exception as e:
        print(f"{t!r}: ERR {e}")
PY

hr "DONE"
