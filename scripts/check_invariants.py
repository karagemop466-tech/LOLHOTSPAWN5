#!/usr/bin/env python3
"""Hard publication gate: refuse to ship a board that fills in a value it cannot defend.

The rule this enforces is the project's whole reason for existing:

  * a published probability must have evidence behind it (an external market, or at least
    MIN_MATCHES_RELIABLE rated results for BOTH teams), and must carry a link to that evidence;
  * anything else is blank, has a stated limitation and a stated remedy, and appears on the
    Unresolved page;
  * a fixture whose kickoff has passed never carries a pick (that number would be hindsight);
  * Hotspawn's crowd pick share is never used as a probability.

Exits 1 on any violation, so the refresh workflow fails instead of publishing. Writes a machine
readable summary to data/invariants.json for the record.
"""
import json, os, sys, datetime as dt

DATA = "data"
PICKS = f"{DATA}/picks.json"
OUT = f"{DATA}/invariants.json"
MIN_RELIABLE = 3
TOL_HOURS = 8.0

errors, warnings, notes = [], [], []


def iso(s):
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


def main():
    if not os.path.exists(PICKS):
        print(f"FAIL: {PICKS} missing")
        return 1
    doc = json.load(open(PICKS))
    rows = doc.get("picks") or []
    if not rows:
        errors.append("picks.json has no rows")

    by_method = {"market": 0, "model": 0, "unresolved": 0}
    picked = 0
    share_collisions = 0

    for r in rows:
        rid = r.get("id") or "?"
        tag = f"{rid} {r.get('home')} vs {r.get('away')}"
        for f in ("id", "home", "away", "competition", "start_utc"):
            if not r.get(f):
                errors.append(f"{tag}: missing required field {f}")

        method = r.get("method")
        if method not in by_method:
            errors.append(f"{tag}: unknown method {method!r}")
            continue
        by_method[method] += 1

        ph, pa = r.get("prob_home"), r.get("prob_away")
        pick = r.get("pick")

        if method in ("market", "model"):
            picked += 1
            for name, v in (("prob_home", ph), ("prob_away", pa)):
                if v is None:
                    errors.append(f"{tag}: {method} row has no {name} (blank must mean unresolved)")
                elif not (0.0 < v < 1.0):
                    errors.append(f"{tag}: {name}={v} outside (0,1)")
            if ph is not None and pa is not None and abs((ph + pa) - 1.0) > 1e-3:
                errors.append(f"{tag}: probabilities sum to {ph + pa:.4f}, not 1")
            if pick not in (r.get("home"), r.get("away")):
                errors.append(f"{tag}: pick {pick!r} is not one of the two teams")
            elif ph is not None:
                expect_pick = r["home"] if ph >= 0.5 else r["away"]
                if pick != expect_pick:
                    errors.append(f"{tag}: pick {pick!r} contradicts prob_home={ph}")
            if r.get("pick_prob") is None:
                errors.append(f"{tag}: pick_prob missing")
            elif ph is not None and abs(r["pick_prob"] - max(ph, pa)) > 1e-3:
                errors.append(f"{tag}: pick_prob {r['pick_prob']} != max(prob) {max(ph, pa)}")

            # evidence link that actually resolves to the source of the number
            if method == "market":
                if not (r.get("market_api_url") or r.get("market_url")):
                    errors.append(f"{tag}: market row has no source URL")
                if r.get("market_source") not in ("Pinnacle", "Kalshi", "Bovada"):
                    warnings.append(f"{tag}: unexpected market_source {r.get('market_source')!r}")
                mstart = iso(r.get("market_start_utc"))
                hstart = iso(r.get("start_utc"))
                if mstart and hstart:
                    dh = abs((mstart - hstart).total_seconds()) / 3600.0
                    if dh > TOL_HOURS:
                        errors.append(f"{tag}: market start is {dh:.1f}h from fixture start")
            else:
                lo = min(r.get("home_matches") or 0, r.get("away_matches") or 0)
                if lo < MIN_RELIABLE:
                    errors.append(f"{tag}: model row published with min rated results {lo} "
                                  f"< {MIN_RELIABLE} (this is a prior, not evidence)")
                if r.get("confidence") not in ("low", "medium", "high"):
                    errors.append(f"{tag}: model row confidence {r.get('confidence')!r}")
                for f in ("model_url", "model_url_away"):
                    if not r.get(f):
                        errors.append(f"{tag}: model row missing {f}")
                    elif "lol.fandom.com" not in r[f]:
                        errors.append(f"{tag}: {f} is not a Leaguepedia link: {r[f]}")

            # Hotspawn's crowd share must never equal the published probability
            hsp = r.get("hotspawn_pick_share_home")
            if hsp is not None and ph is not None and abs(float(hsp) / 100.0 - ph) < 1e-6:
                share_collisions += 1

        if method == "unresolved":
            if pick is not None or ph is not None or pa is not None or r.get("pick_prob") is not None:
                errors.append(f"{tag}: unresolved row carries a pick/probability")
            if r.get("unresolved_kind") not in ("stale_fixture", "insufficient_history"):
                errors.append(f"{tag}: unresolved_kind {r.get('unresolved_kind')!r} invalid")
            if len(r.get("unresolved_reason") or "") < 40:
                errors.append(f"{tag}: unresolved row has no substantive limitation text")
            if len(r.get("unresolved_remedy") or "") < 20:
                errors.append(f"{tag}: unresolved row has no remedy text")

        # hindsight rule
        if r.get("is_past_start") and method != "unresolved":
            errors.append(f"{tag}: kickoff already passed but row publishes a {method} number")

    # counters must describe the rows that actually exist
    t = doc.get("totals") or {}
    got = t.get("by_method") or {}
    for k, v in by_method.items():
        if got.get(k) != v:
            errors.append(f"totals.by_method.{k}={got.get(k)} but counted {v}")
    if t.get("with_a_pick") != picked:
        errors.append(f"totals.with_a_pick={t.get('with_a_pick')} but counted {picked}")
    if t.get("matches") != len(rows):
        errors.append(f"totals.matches={t.get('matches')} but {len(rows)} rows")

    if rows and share_collisions > max(3, 0.02 * len(rows)):
        errors.append(f"{share_collisions} rows publish a probability equal to Hotspawn's crowd "
                      f"share; that looks like the crowd number leaking into the model")

    summary = {
        "checked_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rows": len(rows),
        "by_method": by_method,
        "with_a_pick": picked,
        "errors": errors,
        "warnings": warnings,
        "notes": notes,
        "status": "pass" if not errors else "fail",
    }
    os.makedirs(DATA, exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(summary, f, indent=1)

    for w in warnings:
        print(f"WARN: {w}")
    for e in errors:
        print(f"ERROR: {e}")
    print(f"invariants: {len(rows)} rows, {picked} picked "
          f"({by_method['market']} market / {by_method['model']} model), "
          f"{by_method['unresolved']} unresolved -> "
          f"{len(errors)} errors, {len(warnings)} warnings")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
