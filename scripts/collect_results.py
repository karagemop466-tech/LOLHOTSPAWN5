#!/usr/bin/env python3
"""Collect historical LoL match results used to build our own team ratings.

Source: Leaguepedia (lol.fandom.com) - the community-maintained League of Legends esports wiki
that mirrors official Riot schedules and results. Public, no API key required.

Access path matters: `api.php?action=cargoquery` is aggressively rate-limited from cloud IPs
(verified: every request returned {"code":"ratelimited"}), while the `Special:CargoExport`
endpoint serves the same Cargo tables without that limit. CargoExport also returns raw column
names with spaces (e.g. "DateTime UTC"), which is normalised here.

Only completed matches (non-empty Winner) are kept. Nothing is invented.
"""
import json, os, sys, time, datetime as dt, urllib.parse, urllib.request, urllib.error

EXPORT = "https://lol.fandom.com/wiki/Special:CargoExport"
UA = ("LOLHOTSPAWN5-pipeline/1.0 (https://github.com/karagemop466-tech/LOLHOTSPAWN5) "
      "python-urllib/3.11")
FIELDS = ["OverviewPage", "Team1", "Team2", "Winner", "DateTime_UTC", "BestOf",
          "MatchId", "Tab"]
DATA = "data"
OUT = f"{DATA}/match_results.json"


def export(params, tries=4):
    url = EXPORT + "?" + urllib.parse.urlencode(params)
    delay = 2
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=60) as r:
                body = r.read().decode("utf-8", "replace")
            if not body.strip():
                return []
            doc = json.loads(body)
            return doc if isinstance(doc, list) else []
        except (urllib.error.HTTPError, json.JSONDecodeError, TimeoutError) as e:
            code = getattr(e, "code", None)
            if a < tries - 1 and (code in (None, 429, 500, 502, 503)):
                time.sleep(delay)
                delay = min(delay * 2, 15)
                continue
            print(f"  export failed: {e}", file=sys.stderr)
            return None
        except Exception as e:
            print(f"  export failed: {e}", file=sys.stderr)
            return None
    return None


def get(rec, *names):
    for n in names:
        if n in rec and rec[n] not in (None, ""):
            return rec[n]
    return None


def main():
    os.makedirs(DATA, exist_ok=True)
    # Three-year window: low-tier ERL rosters (PRM 2nd/3rd Division and similar) change
    # slowly at the org level, and earlier seasons are what lift thin teams over the
    # MIN_MATCHES_RELIABLE bar with *verified* results rather than a prior. The Elo pass
    # already applies a 365-day half-life, so old rows decay instead of dominating.
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1095)).strftime("%Y-%m-%d")

    rows, offset, page = [], 0, 500
    while len(rows) < 24000:
        params = {
            "tables": "MatchSchedule",
            "fields": ",".join(FIELDS),
            "where": f"DateTime_UTC >= '{since}'",
            "order_by": "DateTime_UTC DESC",
            "limit": str(page),
            "offset": str(offset),
            "format": "json",
        }
        batch = export(params)
        if batch is None:
            print(f"  offset={offset} failed, stopping with {len(rows)} rows", file=sys.stderr)
            break
        if not batch:
            break
        rows.extend(batch)
        print(f"  offset={offset} got {len(batch)} total={len(rows)}", file=sys.stderr)
        offset += page
        if len(batch) < page:
            break
        time.sleep(1)

    clean, seen = [], set()
    for r in rows:
        t1 = get(r, "Team1")
        t2 = get(r, "Team2")
        w = get(r, "Winner")
        d = get(r, "DateTime UTC", "DateTime_UTC")
        # Older rows can carry numeric team IDs instead of names; those cannot be
        # attributed to a team, so they are skipped rather than mixed into ratings.
        if t1 is not None and not isinstance(t1, str):
            t1 = str(t1)
        if t2 is not None and not isinstance(t2, str):
            t2 = str(t2)
        if t1:
            t1 = t1.strip()
        if t2:
            t2 = t2.strip()
        if not (t1 and t2 and d):
            continue
        if t1.isdigit() or t2.isdigit() or t1 == t2:
            continue
        if not w or t1 == "TBD" or t2 == "TBD":
            continue  # not played yet - cannot inform a rating
        mid = get(r, "MatchId") or f"{t1}|{t2}|{d}"
        if isinstance(mid, (int, float)):
            mid = str(mid)
        if mid in seen:
            continue
        seen.add(mid)
        clean.append({
            "d": d,
            "t1": t1,
            "t2": t2,
            "w": w,
            "bo": get(r, "BestOf"),
            "page": get(r, "OverviewPage"),
            "mid": mid,
        })

    if not clean:
        raise SystemExit("no completed matches returned - refusing to overwrite data")

    teams = sorted({r["t1"] for r in clean} | {r["t2"] for r in clean})
    doc = {
        "source": "https://lol.fandom.com/wiki/Special:CargoTables/MatchSchedule",
        "source_endpoint": EXPORT,
        "source_name": "Leaguepedia (League of Legends esports wiki) - MatchSchedule table",
        "collected_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window_since": since,
        "row_count": len(clean),
        "team_count": len(teams),
        "earliest": min(r["d"] for r in clean),
        "latest": max(r["d"] for r in clean),
        "rows_with_winner": sum(1 for r in clean if r["w"]),
        "results": clean,
    }
    with open(OUT, "w") as f:
        json.dump(doc, f, separators=(",", ":"))
    print(json.dumps({k: doc[k] for k in
                      ("row_count", "team_count", "earliest", "latest",
                       "rows_with_winner")}, indent=1))


if __name__ == "__main__":
    main()
