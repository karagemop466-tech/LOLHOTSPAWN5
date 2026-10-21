#!/usr/bin/env bash
# Final source probe: Pinnacle E-Sports odds, Kambi(Unibet) esports, Polymarket LoL,
# Hotspawn permalink-rule verification, Leaguepedia OR-batch behaviour.
set -u
mkdir -p probe research data
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
hr() { echo; echo "==================== $* ===================="; }

hr "1. Pinnacle E Sports leagues (no brandId)"
curl -sS --max-time 60 -A "$UA" -H 'Accept: application/json' \
  'https://guest.api.arcadia.pinnacle.com/0.1/sports/12/leagues' -o probe/pin_esports_leagues.json
python3 - <<'PY'
import json
d=json.load(open('probe/pin_esports_leagues.json'))
print("leagues:", len(d))
for lg in d:
    print(f"  {lg.get('id'):>12}  {lg.get('name')}  (group={lg.get('group')}, matchups={lg.get('matchupCount')})")
PY

hr "2. Pinnacle E Sports matchups -> which leagues have LoL"
curl -sS --max-time 90 -A "$UA" -H 'Accept: application/json' \
  'https://guest.api.arcadia.pinnacle.com/0.1/sports/12/matchups?brandId=0' -o probe/pin_esports_matchups.json
echo "bytes: $(wc -c < probe/pin_esports_matchups.json)"
python3 - <<'PY'
import json, datetime as dt, collections
d=json.load(open('probe/pin_esports_matchups.json'))
print("matchups:", len(d))
if d:
    print("keys:", sorted(d[0].keys()))
    print(json.dumps(d[0], indent=1)[:2500])
lg=collections.Counter()
for m in d:
    l=m.get('league') or {}
    lg[(l.get('id'), l.get('name'))]+=1
print("by league:")
for k,v in lg.most_common():
    print("   ", k, v)
PY

hr "3. Pinnacle straight markets for E Sports"
for u in \
 "https://guest.api.arcadia.pinnacle.com/0.1/sports/12/markets/straight?brandId=0" \
 "https://guest.api.arcadia.pinnacle.com/0.1/sports/12/markets/straight" ; do
 code=$(curl -sS -o probe/pin_ml.json -w '%{http_code}' --max-time 60 -A "$UA" -H 'Accept: application/json' "$u" || echo ERR)
 echo "--- $u -> $code ($(wc -c < probe/pin_ml.json)B)"
 head -c 600 probe/pin_ml.json; echo
done
python3 - <<'PY'
import json
try:
    d=json.load(open('probe/pin_ml.json'))
except Exception as e:
    print("no json:", e); raise SystemExit
print("groups:", len(d))
if d:
    print("group keys:", sorted(d[0].keys()))
    g=d[0]
    print(json.dumps(g, indent=1)[:2000])
PY

hr "4. Kambi (Unibet) esports groups"
curl -sS --max-time 60 -A "$UA" -H 'Accept: application/json' \
 'https://eu-offering-api.kambicdn.com/offering/v2018/ub/listView/esports/all/all/all/matches.json?lang=en_GB&market=GB&client_id=2&channel_id=1&useCombined=true' \
 -o probe/kambi.json
echo "bytes: $(wc -c < probe/kambi.json)"
python3 - <<'PY'
import json, collections
d=json.load(open('probe/kambi.json'))
evs=d.get('events',[])
print("events:", len(evs))
paths=collections.Counter()
for e in evs:
    ev=e.get('event',{})
    p=[x.get('name') for x in ev.get('path',[])]
    paths[" / ".join(p)]+=1
for k,v in paths.most_common(40):
    print(f"  {v:4d}  {k}")
print()
print("sample event with betOffers:")
for e in evs[:3]:
    ev=e.get('event',{})
    print(json.dumps({k:v for k,v in ev.items() if k!='path'}, indent=1)[:800])
    for bo in (e.get('betOffers') or [])[:2]:
        print("   OFFER:", json.dumps(bo, indent=1)[:900])
PY

hr "5. Hotspawn permalink rule verification"
python3 - <<'PY'
import json, re, urllib.request, urllib.error, datetime as dt
UA={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'}
api='https://phpstack-1372681-6459848.cloudwaysapps.com/api/v1/fixtures'
req=urllib.request.Request(api, headers=UA)
fx=json.loads(urllib.request.urlopen(req, timeout=180).read().decode())
lol=[r for r in fx if (r.get('sport_alias') or '')=='lol']
print("lol fixtures:", len(lol))

html=open('probe/lobby.html', encoding='utf-8', errors='replace').read()
links=set(re.findall(r'https://www\.hotspawn\.com/matches/([a-z0-9-]+?)-(\d{6,8})', html))
print("SSR permalinks found:", len(links))
byid={}
for slug, i in links:
    byid.setdefault(i, set()).add(slug)

def slug(s):
    s = (s or '').strip().lower()
    s = re.sub(r'[^a-z0-9]+', '-', s)
    return s.strip('-')

ok=miss=0
examples=[]
for r in lol:
    fid=str(r.get('id'))
    if fid not in byid: continue
    t1=slug(r.get('participants0_name')); t2=slug(r.get('participants1_name')); c=slug(r.get('competition_name'))
    guess=f"{t1}-vs-{t2}-{c}-{fid}"
    if guess in byid[fid]:
        ok+=1
    else:
        miss+=1
        if len(examples)<15:
            examples.append((fid, guess, list(byid[fid])))
print(f"permalink rule matched {ok}, missed {miss}")
for fid,g,actual in examples:
    print("  MISMATCH id", fid)
    print("    guess :", g)
    print("    actual:", actual)
PY

hr "6. Leaguepedia OR-equality batch behaviour"
python3 - <<'PY'
import json, urllib.request, urllib.parse, time
UA={'User-Agent':'LOLHOTSPAWN5-PickDesk/1.0 (research; https://github.com/karagemop466-tech/LOLHOTSPAWN5)'}
def cargo(where, fields, order_by=None, limit=500, offset=0, table='ScoreboardGames'):
    p={'action':'cargoquery','format':'json','tables':table,'fields':fields,'where':where,
       'limit':str(limit),'offset':str(offset)}
    if order_by: p['order_by']=order_by
    url='https://lol.fandom.com/api.php?'+urllib.parse.urlencode(p)
    for a in range(6):
        try:
            r=urllib.request.Request(url, headers=UA)
            j=json.loads(urllib.request.urlopen(r, timeout=60).read().decode())
            if 'error' in j:
                time.sleep(4*(a+1)); continue
            return j.get('cargoquery',[])
        except Exception:
            time.sleep(4*(a+1))
    return []
def q(s): return s.replace('"','\\"')
teams=["Solary","Galions","AceGaming","Hannover Esports e.V.","El Menzah Esports"]
where=" OR ".join([f'ScoreboardGames.Team1="{q(t)}"', f'ScoreboardGames.Team2="{q(t)}"'] if False else
                  [x for t in teams for x in (f'ScoreboardGames.Team1="{q(t)}"', f'ScoreboardGames.Team2="{q(t)}"')])
rows=cargo(where, 'ScoreboardGames.Team1,ScoreboardGames.Team2,ScoreboardGames.WinTeam,ScoreboardGames.DateTime_UTC,ScoreboardGames.Tournament',
           order_by='ScoreboardGames.DateTime_UTC DESC', limit=25)
print("rows:", len(rows))
for r in rows[:15]:
    print("   ", r['title'])
time.sleep(3)
print()
print("--- Tournaments table (raw name probe) ---")
for t in ["Prime League 2nd Division 2026 Fall","PRM 2nd Division 26-27 Fall","Worlds 2026 Main Event"]:
    rows=cargo(f'Tournaments.Name="{q(t)}"','Tournaments.Name,Tournaments.OverviewPage,Tournaments.DateStartFuzzy',
               table='Tournaments', limit=5)
    print(f"  {t!r} -> {len(rows)}", rows[:2])
    time.sleep(3)
PY

hr "DONE"
