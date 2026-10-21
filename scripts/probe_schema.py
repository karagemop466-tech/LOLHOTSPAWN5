#!/usr/bin/env python3
"""Discover the real MatchSchedule Cargo schema, then validate field sets via CargoExport."""
import json, re, urllib.parse, urllib.request, urllib.error

UA = ("LOLHOTSPAWN5-pipeline/1.0 (https://github.com/karagemop466-tech/LOLHOTSPAWN5) python-urllib/3.11")


def get(url, timeout=50):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return 0, f"{type(e).__name__}: {e}"


out = {}

# --- schema page
st, html = get("https://lol.fandom.com/wiki/Special:CargoTables/MatchSchedule")
fields = []
if st == 200:
    # rows look like: <td>FieldName</td> ... possibly with links
    for m in re.finditer(r'<td[^>]*>\s*(?:<a[^>]*>)?\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?:</a>)?\s*</td>', html):
        fields.append(m.group(1))
    # dedupe preserving order, drop obvious non-fields
    seen, f2 = set(), []
    for f in fields:
        if f not in seen:
            seen.add(f); f2.append(f)
    fields = f2
out["schema_status"] = st
out["schema_bytes"] = len(html)
out["fields_found"] = fields[:120]
out["fields_count"] = len(fields)

# --- validate candidate field sets
candidates = [
    ["Team1", "Team2", "Winner", "DateTime_UTC"],
    ["Team1", "Team2", "Winner", "DateTime_UTC", "BestOf"],
    ["OverviewPage", "Team1", "Team2", "Winner", "DateTime_UTC", "BestOf"],
    ["OverviewPage", "Team1", "Team2", "Winner", "DateTime_UTC", "BestOf", "MatchId", "Tab"],
    ["Team1", "Team2", "Team1Score", "Team2Score", "Winner", "DateTime_UTC", "BestOf"],
]
tests = []
for c in candidates:
    q = {"tables": "MatchSchedule", "fields": ",".join(c),
         "order_by": "DateTime_UTC DESC", "limit": "5", "format": "json"}
    st2, body = get("https://lol.fandom.com/wiki/Special:CargoExport?" + urllib.parse.urlencode(q))
    ok = body.strip().startswith(("{", "[")) and "Error" not in body[:40]
    tests.append({"fields": c, "status": st2, "ok": ok, "snippet": body[:260]})
out["field_tests"] = tests

# --- with a date filter (the query we actually need)
q = {"tables": "MatchSchedule", "fields": "Team1,Team2,Winner,DateTime_UTC,BestOf",
     "where": "DateTime_UTC >= '2026-09-01'", "order_by": "DateTime_UTC DESC",
     "limit": "20", "format": "json"}
st3, body = get("https://lol.fandom.com/wiki/Special:CargoExport?" + urllib.parse.urlencode(q))
out["dated_query"] = {"status": st3, "bytes": len(body), "snippet": body[:500]}

json.dump(out, open("research/schema_probe.json", "w"), indent=1)
print("schema", st, "fields", len(fields))
for t in tests:
    print("OK " if t["ok"] else "BAD", t["fields"], "|", t["snippet"][:110].replace("\n", " "))
print("dated:", st3, out["dated_query"]["snippet"][:220].replace("\n", " "))
