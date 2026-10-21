#!/usr/bin/env bash
# Collect + analyse: Hotspawn fixtures API (LoL slice) and probe keyless odds sources.
# Runs on a GitHub Actions runner (agent sandbox has no general egress).
set -u
mkdir -p probe research data

UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
API='https://phpstack-1372681-6459848.cloudwaysapps.com/api/v1'

hr() { echo; echo "==================== $* ===================="; }

hr "1. download fixtures"
curl -sS --max-time 180 -A "$UA" -H 'Accept: application/json' \
  "${API}/fixtures" -o probe/fixtures_all.json
echo "bytes: $(wc -c < probe/fixtures_all.json)"

hr "2. week prize widget for LOL"
for q in "?sportAlias=lol" "?sport_alias=lol" "?sport=lol" "?sportAlias=LOL"; do
  echo "--- /week-prizes/widget${q}"
  curl -sS --max-time 30 -A "$UA" "${API}/week-prizes/widget${q}" | head -c 400
  echo
done

hr "3. fixture detail endpoints"
for p in "/fixtures/1081205" "/fixture/1081205" "/fixtures/1081205/picks"; do
  code=$(curl -sS -o probe/last.json -w '%{http_code}' --max-time 30 -A "$UA" "${API}${p}" || echo ERR)
  echo "GET ${API}${p} -> ${code} ($(wc -c < probe/last.json)B)"
  head -c 400 probe/last.json; echo
done

hr "4. python analysis"
python3 - <<'PY'
import json, datetime as dt, collections, os
os.makedirs('data', exist_ok=True)

recs = json.load(open('probe/fixtures_all.json'))
print("total records:", len(recs))

by_sport = collections.Counter(r.get('sport_alias') for r in recs)
print("sport_alias counts:", dict(by_sport))

lol = [r for r in recs if (r.get('sport_alias') or '').lower() == 'lol']
print("lol records:", len(lol))

print("lol statuses:", dict(collections.Counter(r.get('status') for r in lol)))
print("lol tiers:", dict(collections.Counter(r.get('tier') for r in lol)))

def ms(v):
    try: return int(v)
    except Exception: return 0

now_ms = int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)
print("now_ms:", now_ms)

with_time = [r for r in lol if ms(r.get('scheduled_start_time'))]
print("lol with scheduled_start_time:", len(with_time))
mn = min(with_time, key=lambda r: ms(r['scheduled_start_time']))
mx = max(with_time, key=lambda r: ms(r['scheduled_start_time']))
print("earliest:", mn['scheduled_start_time'], mn['competition_name'], mn['participants0_name'], 'vs', mn['participants1_name'])
print("latest  :", mx['scheduled_start_time'], mx['competition_name'], mx['participants0_name'], 'vs', mx['participants1_name'])

# statuses vs time
st_time = collections.Counter()
for r in with_time:
    t = ms(r['scheduled_start_time'])
    rel = 'future' if t > now_ms else 'past'
    st_time[(r.get('status'), rel)] += 1
print("status x past/future:", dict(st_time))

# what is currently pickable: status suggests open + lock in future
future = [r for r in with_time if ms(r['scheduled_start_time']) > now_ms]
print("future lol fixtures:", len(future))
print("future by status:", dict(collections.Counter(r.get('status') for r in future)))

# week bucket by scheduled_start_time
wk = collections.Counter()
for r in future:
    d = dt.datetime.fromtimestamp(ms(r['scheduled_start_time'])/1000, dt.timezone.utc)
    wk[d.strftime('%Y-%m-%d')] += 1
print("future by UTC date:", dict(sorted(wk.items())))

# lock_time coverage
print("future with lock_time:", sum(1 for r in future if ms(r.get('lock_time'))))

# competition list for future
comps = collections.Counter(r.get('competition_name') for r in future)
print("future competitions:", len(comps))
for c, n in comps.most_common(60):
    print(f"   {n:3d}  {c}")

# save compact future slice
def slim(r):
    return {
        'id': r.get('id'),
        'competition_id': r.get('competition_id'),
        'competition_name': r.get('competition_name'),
        'status': r.get('status'),
        'scheduled_start_time': r.get('scheduled_start_time'),
        'lock_time': r.get('lock_time'),
        'tier': r.get('tier'),
        'stage': r.get('stage'),
        'best_of': r.get('best_of'),
        'offered_points': r.get('offered_points'),
        'base_points': r.get('base_points'),
        'total_picks': r.get('total_picks'),
        'p0_id': r.get('participants0_id'),
        'p0_name': r.get('participants0_name'),
        'p0_pct': r.get('participants0_picked_percent'),
        'p1_id': r.get('participants1_id'),
        'p1_name': r.get('participants1_name'),
        'p1_pct': r.get('participants1_picked_percent'),
    }

out = sorted(future, key=lambda r: ms(r.get('scheduled_start_time')))
json.dump([slim(r) for r in out], open('data/hotspawn_lol_future_raw.json','w'), indent=1)
print("wrote data/hotspawn_lol_future_raw.json:", len(out), "records")

print()
print("SAMPLE (first 3 future):")
for r in out[:3]:
    print(json.dumps(r, indent=1))
PY

hr "5. odds source probes"
probe_url() {
  local label="$1"; shift
  local code
  code=$(curl -sS -o probe/last.txt -w '%{http_code}' --max-time 40 -A "$UA" \
     -H 'Accept: application/json' "$@" 2>/dev/null || echo ERR)
  echo "--- ${label} -> ${code} ($(wc -c < probe/last.txt)B)"
  head -c 500 probe/last.txt; echo
}

probe_url "polymarket gamma lol tag" \
  'https://gamma-api.polymarket.com/events?tag_slug=league-of-legends&closed=false&limit=50'
probe_url "polymarket gamma search lol" \
  'https://gamma-api.polymarket.com/public-search?q=League%20of%20Legends&limit_per_type=10'
probe_url "pinnacle guest sports" \
  'https://guest.api.arcadia.pinnacle.com/0.1/sports'
probe_url "pinnacle guest esports leagues" \
  'https://guest.api.arcadia.pinnacle.com/0.1/leagues?all=false'
probe_url "leaguepedia cargo" \
  'https://lol.fandom.com/api.php?action=cargoquery&format=json&tables=ScoreboardGames&fields=ScoreboardGames.Team1,ScoreboardGames.Team2,ScoreboardGames.WinTeam,ScoreboardGames.DateTime_UTC&where=ScoreboardGames.Team1%3D%22Solary%22&limit=5'
probe_url "kalshi lol" \
  'https://api.elections.kalshi.com/trade-api/v2/events?status=open&limit=50'

hr "6. leaguepedia with descriptive UA"
curl -sS --max-time 40 \
  -A 'LOLHOTSPAWN5-PickDesk/1.0 (research; contact: repo owner) curl/8' \
  -H 'Accept: application/json' \
  'https://lol.fandom.com/api.php?action=cargoquery&format=json&tables=ScoreboardGames&fields=ScoreboardGames.Team1,ScoreboardGames.Team2,ScoreboardGames.WinTeam,ScoreboardGames.DateTime_UTC,ScoreboardGames.Tournament&where=ScoreboardGames.Team1%3D%22Solary%22%20OR%20ScoreboardGames.Team2%3D%22Solary%22&order_by=ScoreboardGames.DateTime_UTC%20DESC&limit=5' \
  -o probe/lp.json
echo "status: $?  bytes: $(wc -c < probe/lp.json)"
head -c 1500 probe/lp.json

hr "DONE"
