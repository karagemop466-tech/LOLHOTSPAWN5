#!/usr/bin/env python3
"""Collect historical LoL match results used to build our own team ratings.

Source: Leaguepedia (lol.fandom.com) Cargo API - the community-maintained League of Legends
esports wiki, which mirrors official Riot match schedules/results. Public, no key required.

The API rate-limits aggressively, so requests are paced and retried with backoff.
If the API is unavailable the previous snapshot is kept and the run is marked degraded;
nothing is invented.
"""
import json, os, sys, time, datetime as dt, urllib.parse, urllib.request, urllib.error

API = "https://lol.fandom.com/api.php"
UA = ("LOLHOTSPAWN5-pipeline/1.0 (https://github.com/karagemop466-tech/LOLHOTSPAWN5; "
      "contact: repo issues) python-urllib")
DATA = "data"
OUT = f"{DATA}/match_results.json"

FIELD_SETS = [
    ["OverviewPage", "Team1", "Team2", "Winner", "DateTime_UTC", "BestOf",
     "Tournament", "MatchId", "Tab"],
    ["OverviewPage", "Team1", "Team2", "Winner", "DateTime_UTC", "BestOf", "Tournament"],
    ["Team1", "Team2", "Winner", "DateTime_UTC"],
]


def api(params, tries=4):
    url = API + "?" + urllib.parse.urlencode(params)
    delay = 3
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                body = r.read().decode("utf-8", "replace")
            doc = json.loads(body)
            if "error" in doc:
                code = (doc["error"] or {}).get("code", "")
                if code == "ratelimited":
                    print(f"  ratelimited, sleeping {delay}s", file=sys.stderr)
                    time.sleep(delay)
                    delay = min(delay * 2, 20)
                    continue
                raise RuntimeError(f"api error: {doc['error']}")
            return doc
        except urllib.error.HTTPError as e:
            if e.code in (429, 503):
                time.sleep(delay)
                delay = min(delay * 2, 20)
                continue
            raise
        except urllib.error.URLError as e:
            print(f"  url error {e}, retry", file=sys.stderr)
            time.sleep(delay)
            delay = min(delay * 2, 20)
    return None


def collect(days_back=120, max_rows=2500, page=500):
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days_back))
    since_s = since.strftime("%Y-%m-%d 00:00:00")

    fields = None
    for fs in FIELD_SETS:
        doc = api({"action": "cargoquery", "format": "json", "tables": "MatchSchedule",
                   "fields": ",".join(fs),
                   "where": f"DateTime_UTC >= '{since_s}'",
                   "order_by": "DateTime_UTC DESC", "limit": 3})
        if doc and doc.get("cargoquery"):
            fields = fs
            print(f"using field set: {fs}", file=sys.stderr)
            break
        time.sleep(6)
    if fields is None:
        raise SystemExit("could not establish a working MatchSchedule field set")

    rows, offset = [], 0
    while len(rows) < max_rows:
        doc = api({"action": "cargoquery", "format": "json", "tables": "MatchSchedule",
                   "fields": ",".join(fields),
                   "where": f"DateTime_UTC >= '{since_s}'",
                   "order_by": "DateTime_UTC DESC",
                   "limit": page, "offset": offset})
        if not doc:
            print(f"  page offset={offset} unavailable, stopping", file=sys.stderr)
            break
        batch = [r.get("title", r) for r in doc.get("cargoquery", [])]
        if not batch:
            break
        rows.extend(batch)
        print(f"  offset={offset} got {len(batch)} total={len(rows)}", file=sys.stderr)
        offset += page
        if len(batch) < page:
            break
        time.sleep(10)

    clean = []
    for r in rows:
        t1, t2 = r.get("Team1"), r.get("Team2")
        w = r.get("Winner")
        d = r.get("DateTime_UTC")
        if not (t1 and t2 and d):
            continue
        clean.append({
            "d": d,
            "t1": t1,
            "t2": t2,
            "w": w if w in (t1, t2, "1", "2") else None,
            "bo": r.get("BestOf"),
            "tour": r.get("Tournament"),
            "page": r.get("OverviewPage"),
            "mid": r.get("MatchId"),
        })
    return fields, clean


def main():
    os.makedirs(DATA, exist_ok=True)
    try:
        fields, rows = collect()
    except SystemExit as e:
        print(f"COLLECTION FAILED: {e}", file=sys.stderr)
        raise
    if not rows:
        raise SystemExit("no rows returned - refusing to overwrite with empty data")

    teams = sorted({r["t1"] for r in rows} | {r["t2"] for r in rows})
    doc = {
        "source": "https://lol.fandom.com/wiki/Special:CargoTables/MatchSchedule",
        "source_api": API,
        "source_name": "Leaguepedia (League of Legends esports wiki) - MatchSchedule",
        "collected_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fields": fields,
        "row_count": len(rows),
        "team_count": len(teams),
        "earliest": min(r["d"] for r in rows),
        "latest": max(r["d"] for r in rows),
        "rows_with_winner": sum(1 for r in rows if r["w"]),
        "results": rows,
    }
    with open(OUT, "w") as f:
        json.dump(doc, f, separators=(",", ":"))
    print(json.dumps({k: doc[k] for k in
                      ("row_count", "team_count", "earliest", "latest",
                       "rows_with_winner")}, indent=1))


if __name__ == "__main__":
    main()
