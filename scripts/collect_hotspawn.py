#!/usr/bin/env python3
"""Collect the complete League of Legends pick'ems inventory from Hotspawn Play.

Method (reverse-engineered, verified against live HTML on 2026-10-21):
  https://play.hotspawn.com/lol-pickems is an Angular SSR app. The full match list is
  embedded in `<script id="ng-state" type="application/json">` (Angular transfer state),
  under the top-level entry whose `b` value is a list of match records.

Nothing is invented: every field written here is copied verbatim from that payload.
`picked_percent` is the Hotspawn *crowd pick share*. It is NOT a probability and is never
used as one downstream (see METHODOLOGY.md).
"""
import json, os, re, sys, hashlib, datetime as dt, urllib.request, urllib.error

URL = "https://play.hotspawn.com/lol-pickems"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
DATA = "data"
RAW = "data/raw"


def fetch(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9", "Cache-Control": "no-cache",
    })
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def extract_transfer_state(html):
    m = re.search(r'<script[^>]*id="ng-state"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        raise SystemExit("ng-state transfer state not found - Hotspawn layout changed")
    return json.loads(m.group(1))


def pick(payload, predicate):
    """Find the single top-level entry whose `b` satisfies predicate."""
    for key, val in payload.items():
        if not isinstance(val, dict):
            continue
        b = val.get("b")
        if predicate(b):
            return b
    return None


def is_match_list(b):
    return isinstance(b, list) and len(b) > 0 and isinstance(b[0], dict) \
        and "participants0_name" in b[0]


def is_permalinks(b):
    return isinstance(b, dict) and "permalinks" in b


def iso(ms):
    if ms in (None, "", 0):
        return None
    try:
        return dt.datetime.fromtimestamp(int(ms) / 1000, dt.timezone.utc) \
            .strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return None


def norm(rec, permalinks):
    mid = str(rec.get("id"))
    return {
        "id": mid,
        "competition_id": rec.get("competition_id"),
        "competition": rec.get("competition_name"),
        "sport": rec.get("sport_name"),
        "sport_alias": rec.get("sport_alias"),
        "status": rec.get("status"),
        "start_utc": iso(rec.get("scheduled_start_time")),
        "start_epoch_ms": rec.get("scheduled_start_time"),
        "lock_utc": iso(rec.get("lock_time")),
        "lock_offset_sec": rec.get("lock_offset_sec"),
        "tier": rec.get("tier"),
        "stage": rec.get("stage"),
        "best_of": rec.get("best_of"),
        "offered_points": rec.get("offered_points"),
        "total_picks": rec.get("total_picks"),
        "home": {
            "id": str(rec.get("participants0_id")),
            "name": rec.get("participants0_name"),
            "hotspawn_pick_share": rec.get("participants0_picked_percent"),
            "score": rec.get("participants0_score"),
        },
        "away": {
            "id": str(rec.get("participants1_id")),
            "name": rec.get("participants1_name"),
            "hotspawn_pick_share": rec.get("participants1_picked_percent"),
            "score": rec.get("participants1_score"),
        },
        "hotspawn_url": permalinks.get(mid),
    }


def main():
    # `--html PATH` replays a saved snapshot (used for offline parser verification).
    if len(sys.argv) > 2 and sys.argv[1] == "--html":
        html = open(sys.argv[2], encoding="utf-8").read()
        print(f"replaying saved snapshot {sys.argv[2]}", file=sys.stderr)
    else:
        html = fetch(URL)
    os.makedirs(RAW, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    payload = extract_transfer_state(html)
    matches_raw = pick(payload, is_match_list)
    if matches_raw is None:
        raise SystemExit("no match list entry in transfer state")
    permalinks = (pick(payload, is_permalinks) or {}).get("permalinks", {})

    matches = [norm(m, permalinks) for m in matches_raw]
    lol = [m for m in matches if (m.get("sport_alias") or "").lower() == "lol"]
    # the /lol-pickems page should be LoL-only; keep all rows but record any mismatch
    non_lol = [m for m in matches if (m.get("sport_alias") or "").lower() != "lol"]

    matches.sort(key=lambda m: (m.get("start_utc") or "9999", m.get("id")))

    with open(f"{RAW}/hotspawn_lol_pickems_{stamp}.html", "w") as f:
        f.write(html)
    with open(f"{RAW}/hotspawn_transfer_state_{stamp}.json", "w") as f:
        json.dump(payload, f)

    doc = {
        "source": URL,
        "source_name": "Hotspawn Play - League of Legends Pick'ems",
        "collected_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "html_sha256": hashlib.sha256(html.encode()).hexdigest(),
        "html_bytes": len(html),
        "match_count": len(matches),
        "lol_match_count": len(lol),
        "non_lol_rows": [{"id": m["id"], "sport": m["sport"]} for m in non_lol],
        "matches_with_hotspawn_page": sum(1 for m in matches if m["hotspawn_url"]),
        "matches_without_hotspawn_page": sum(1 for m in matches if not m["hotspawn_url"]),
        "matches": matches,
    }
    os.makedirs(DATA, exist_ok=True)
    with open(f"{DATA}/hotspawn_matches.json", "w") as f:
        json.dump(doc, f, indent=1)

    # keep the raw payload dir from growing without bound
    raws = sorted(os.listdir(RAW))
    for old in raws[:-8]:
        os.remove(os.path.join(RAW, old))

    print(f"collected {len(matches)} matches "
          f"(lol_alias={len(lol)}, without_hotspawn_page="
          f"{doc['matches_without_hotspawn_page']})", file=sys.stderr)
    print(json.dumps({k: doc[k] for k in
                      ("collected_utc", "match_count", "matches_with_hotspawn_page",
                       "matches_without_hotspawn_page")}, indent=1))


if __name__ == "__main__":
    main()
