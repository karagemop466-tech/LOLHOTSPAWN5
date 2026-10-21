#!/usr/bin/env python3
"""Find a working path to historical LoL results (rate-limit hunt). Report only."""
import json, time, urllib.parse, urllib.request, urllib.error

UA = ("LOLHOTSPAWN5-pipeline/1.0 (https://github.com/karagemop466-tech/LOLHOTSPAWN5) "
      "python-urllib/3.11")
RIOT_KEY = "0TvQnueqKa5mxJntVWt0w4LpLSSiF19a8wLoPLD"
OUT = []


def get(url, headers=None, timeout=50):
    h = {"User-Agent": UA, "Accept": "*/*"}
    if headers:
        h.update(headers)
    try:
        req = urllib.request.Request(url, headers=h)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", "replace")
        except Exception:
            body = ""
        return e.code, body
    except Exception as e:
        return 0, f"{type(e).__name__}: {e}"


def note(tag, status, body):
    snippet = body[:320].replace("\n", " ")
    OUT.append({"probe": tag, "status": status, "bytes": len(body), "snippet": snippet,
                "looks_json": body.strip().startswith(("{", "["))})


# 1. Special:CargoExport - a different code path from api.php cargoquery
q = {
    "tables": "MatchSchedule",
    "fields": "Team1,Team2,Winner,DateTime_UTC,BestOf,Tournament",
    "where": "DateTime_UTC >= '2026-09-01'",
    "order_by": "DateTime_UTC DESC",
    "limit": "50",
    "format": "json",
}
note("cargoexport", *get("https://lol.fandom.com/wiki/Special:CargoExport?"
                         + urllib.parse.urlencode(q)))

# 2. api.php cargoquery with maxlag and small limit
q2 = dict(q)
q2.update({"action": "cargoquery", "format": "json", "limit": "5"})
q2.pop("where", None)
note("api_maxlag", *get("https://lol.fandom.com/api.php?"
                        + urllib.parse.urlencode(q2), {"Accept": "application/json"}))

# 3. Plain MediaWiki query (different rate-limit bucket entirely)
note("mw_query", *get("https://lol.fandom.com/api.php?"
                      + urllib.parse.urlencode({"action": "query", "format": "json",
                                                "list": "allpages", "aplimit": "2"})))

# 4. Riot official esports API with the public web key
note("riot_leagues", *get("https://esports-api.lolesports.com/persisted/gw/getLeagues?hl=en-US",
                          {"x-api-key": RIOT_KEY, "Accept": "application/json"}))
note("riot_schedule", *get("https://esports-api.lolesports.com/persisted/gw/getSchedule?hl=en-US",
                           {"x-api-key": RIOT_KEY, "Accept": "application/json"}))

# 5. gol.gg - a results-bearing HTML source
note("golgg_list", *get("https://gol.gg/tournament/list/"))
note("golgg_teamrank", *get("https://gol.gg/teams/list/season-S16/split-Summer/tournament-ALL/"
                            "page-1/"))

# 6. bo3.gg - guess a JSON API
note("bo3_api", *get("https://bo3.gg/api/v1/lol/matches?page=1"))

report = {"probes": OUT}
with open("research/results_sources.json", "w") as f:
    json.dump(report, f, indent=1)

lines = ["# Historical-results source probes", ""]
for p in OUT:
    lines.append(f"## {p['probe']} — HTTP {p['status']} ({p['bytes']} bytes, "
                 f"json={p['looks_json']})")
    lines.append("```")
    lines.append(p["snippet"])
    lines.append("```")
    lines.append("")
open("research/results_sources.md", "w").write("\n".join(lines))
print("\n".join(f"{p['probe']:16s} {p['status']} {p['bytes']}B json={p['looks_json']}"
                for p in OUT))
