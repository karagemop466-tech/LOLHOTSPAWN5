#!/usr/bin/env python3
"""Render the static site (GitHub Pages) from the collected data.

Pages
  index.html         landing page + executive summary with links into the site
  picks.html         every HotSpawn LoL match with both win probabilities and the pick
  unresolved.html    the matches we could not resolve from an external line, and why
  review.html        everything flagged for manual review
  sources.html       the source register with official links
  methodology.html   how every number is produced
"""
from __future__ import annotations

import datetime
import html
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import REPO_ROOT, utcnow  # noqa: E402

NAV = [
    ("index.html", "Overview"),
    ("picks.html", "All picks"),
    ("unresolved.html", "Unresolved"),
    ("review.html", "Flagged"),
    ("sources.html", "Sources"),
    ("methodology.html", "Methodology"),
]

CONFIDENCE_LABEL = {
    "market": ("market", "External series line"),
    "market-map": ("market-map", "External map price only"),
    "model": ("model", "Our own line"),
    "default": ("default", "Default 50% - unverified"),
}


def load(rel: str, default):
    path = os.path.join(REPO_ROOT, rel)
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def e(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def fmt_time(value) -> str:
    if not value:
        return "unknown"
    try:
        parsed = datetime.datetime.strptime(str(value), "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return str(value)
    return parsed.strftime("%a %d %b %H:%M UTC")


def fmt_utc(value) -> str:
    if not value:
        return "unknown"
    try:
        parsed = datetime.datetime.strptime(str(value), "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return str(value)
    return parsed.strftime("%Y-%m-%d %H:%M UTC")


def pct(value) -> str:
    if value is None:
        return "-"
    return f"{round(float(value) * 100)}%"


def head(title: str, description: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="description" content="{e(description)}">
<meta name="theme-color" content="#0f1420">
<title>{e(title)}</title>
<link rel="stylesheet" href="assets/styles.css">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><text y='26' font-size='26'>&#127918;</text></svg>">
</head>
<body>
<header class="site">
  <div class="wrap site-head">
    <div class="brand">HotSpawn <span>LoL</span> picks<small>league of legends pick'em - win probabilities</small></div>
    <div class="stamp" id="stamp"></div>
  </div>
  <div class="wrap">
    <nav class="site-nav">
      {"".join(f'<a href="{href}">{label}</a>' for href, label in NAV)}
    </nav>
  </div>
</header>
<main class="wrap">
"""


def footer(stamp: dict) -> str:
    return f"""</main>
<footer class="site">
  <div class="wrap">
    <p><b>How to read this site.</b> Every match listed on HotSpawn's League of Legends pick'em board gets a pick and a
    win probability for both teams. Probabilities come from external betting lines (Kalshi, Polymarket, Pinnacle, Bovada)
    or, where no book prices the match, from our own line fitted on Leaguepedia results.
    HotSpawn's own "X% picked" figures are never used as a probability signal.</p>
    <p class="small">Last refreshed: {e(fmt_utc(stamp.get("generated_at")))} &middot; inventory {e(stamp.get("fixtures"))} matches
    &middot; external lines {e(stamp.get("quotes"))} quotes
    &middot; site built {e(fmt_utc(stamp.get("built_at")))}</p>
    <p class="small">Sources are listed on the <a href="sources.html">Sources</a> page, the method on
    <a href="methodology.html">Methodology</a>. Nothing here is betting advice.</p>
  </div>
</footer>
<script src="assets/app.js"></script>
</body>
</html>
"""


def nav_html(current: str) -> str:
    out = []
    for href, label in NAV:
        cls = ' class="active"' if href == current else ""
        out.append(f'<a href="{href}"{cls}>{label}</a>')
    return "".join(out)


def stamp_block(stamp: dict) -> str:
    return (f'updated <b>{e(fmt_utc(stamp.get("generated_at")))}</b><br>'
            f'{e(stamp.get("fixtures"))} matches &middot; {e(stamp.get("covered"))} with an external line')


# --------------------------------------------------------------------------- #
# pick card
# --------------------------------------------------------------------------- #
def pick_card(pick: dict) -> str:
    conf, conf_label = CONFIDENCE_LABEL.get(pick.get("confidence"), ("default", "Unknown"))
    team_a, team_b = pick["team_a"], pick["team_b"]
    winner = pick.get("pick")

    def team_block(team: dict, other: dict) -> str:
        is_win = team["name"] == winner
        prob = team.get("prob")
        width = 0 if prob is None else max(2, min(100, round(float(prob) * 100)))
        return (f'<div class="team {"win" if is_win else "lose"}">'
                f'<span class="bar"><i style="width:{width}%"></i></span>'
                f'<span class="nm">{e(team["name"])}</span>'
                f'<span class="pc">{pct(prob)}</span></div>')

    sources = []
    for row in pick.get("market_sources") or []:
        label = f'{row.get("source")} ({row.get("scope")})'
        sources.append(f'<a href="{e(row.get("source_url"))}" target="_blank" rel="noopener">{e(label)}</a>')
    for side in ("team_a", "team_b"):
        team = pick.get(side) or {}
        if team.get("source_url"):
            sources.append(f'<a href="{e(team.get("source_url"))}" target="_blank" rel="noopener">'
                           f'Leaguepedia: {e(team.get("name"))}</a>')
    if pick.get("hotspawn_url"):
        sources.append(f'<a href="{e(pick.get("hotspawn_url"))}" target="_blank" rel="noopener">HotSpawn match page</a>')
    else:
        sources.append(f'<a href="{e(pick.get("hotspawn_lobby"))}" target="_blank" rel="noopener">HotSpawn board</a>')
    if not pick.get("market_sources"):
        sources.append('<span class="chip flag">no external line for this fixture</span>')

    chips = [f'<span class="chip {conf}">{e(conf_label)}</span>',
             f'<span class="chip pick">Pick: {e(winner)} ({pct(pick.get("pick_prob"))})</span>']
    if pick.get("tier"):
        chips.append(f'<span class="chip">Tier {e(str(pick.get("tier")).upper())}</span>')
    if pick.get("offered_points"):
        chips.append(f'<span class="chip">{e(pick.get("offered_points"))} pts</span>')
    flags = "".join(f'<span class="chip flag">{e(flag)}</span>' for flag in pick.get("flags") or [])

    search_blob = " ".join([
        str(pick.get("tournament") or ""), team_a.get("name") or "", team_b.get("name") or "",
        str(pick.get("tier") or ""), conf_label,
    ]).lower()

    return f"""<article class="pick {conf}" data-pick="{e(search_blob)}" data-conf="{e(pick.get('confidence'))}" data-tour="{e(pick.get('tournament'))}">
  <div class="top">
    <span class="tour">{e(pick.get('tournament'))}</span>
    <span class="when">locks {e(fmt_time(pick.get('lock_time')))}</span>
  </div>
  <div class="teams">
    {team_block(team_a, team_b)}
    {team_block(team_b, team_a)}
  </div>
  <div class="meta">{''.join(chips)}{flags}</div>
  <div class="srcs">{''.join(sources)}</div>
</article>"""


def render_picks_list(picks: list[dict]) -> str:
    return f'<div class="picks">{"".join(pick_card(p) for p in picks)}</div>'


# --------------------------------------------------------------------------- #
# pages
# --------------------------------------------------------------------------- #
def page_index(ctx: dict) -> str:
    picks = ctx["picks"]
    summary = ctx["summary"]
    stamp = ctx["stamp"]
    upcoming = sorted(picks, key=lambda p: (p.get("lock_time") or "9999"))[:8]
    rows = []
    for pick in upcoming:
        conf, conf_label = CONFIDENCE_LABEL.get(pick.get("confidence"), ("default", ""))
        rows.append(
            f"<tr><td>{e(pick.get('tournament'))}</td>"
            f"<td>{e(pick['team_a']['name'])} <b>{pct(pick['team_a']['prob'])}</b> vs "
            f"{e(pick['team_b']['name'])} <b>{pct(pick['team_b']['prob'])}</b></td>"
            f"<td class='nowrap'>{e(pick.get('pick'))}</td>"
            f"<td><span class='chip {conf}'>{e(conf_label)}</span></td>"
            f"<td class='nowrap small'>{e(fmt_time(pick.get('lock_time')))}</td></tr>")

    coverage = ctx["coverage_rows"]
    coverage_html = "".join(
        f"<tr><td>{e(row['tournament'])}</td><td class='num'>{row['total']}</td>"
        f"<td class='num'>{row['market']}</td><td class='num'>{row['model']}</td>"
        f"<td class='num'>{row['default']}</td></tr>" for row in coverage)

    unresolved = summary.get("unresolved", 0)
    body = f"""
<section class="hero">
  <h1>League of Legends pick'em picks for every HotSpawn match</h1>
  <p class="lede">A pick and a win probability for both teams on <b>every</b> League of Legends match on
  HotSpawn's pick'em board - with the source behind each number, and an explicit section for the matches
  that no bookmaker prices.</p>
</section>

<div class="cards">
  <div class="card"><div class="n">{e(summary.get('fixtures', 0))}</div><div class="l">matches on the board</div></div>
  <div class="card ok"><div class="n">{e(summary.get('with_series_market', 0))}</div><div class="l">external series line</div></div>
  <div class="card info"><div class="n">{e(summary.get('with_map_market_only', 0))}</div><div class="l">external map price only</div></div>
  <div class="card warn"><div class="n">{e(unresolved)}</div><div class="l">need our own line</div></div>
</div>

<h2>Where to find the picks</h2>
<div class="cta">
  <a class="primary" href="picks.html"><strong>All picks &rarr;</strong>
    <span>Every match with both win probabilities, the pick, the source link and any flag. Searchable and filterable, built for a phone.</span></a>
  <a href="unresolved.html"><strong>Unresolved picks &amp; limitations &rarr;</strong>
    <span>The {e(unresolved)} matches that no bookmaker prices: what we did about them and exactly why they stay limited.</span></a>
  <a href="review.html"><strong>Flagged for review &rarr;</strong>
    <span>Everything we could not confirm against an official source, with links for manual checking.</span></a>
  <a href="sources.html"><strong>Sources &rarr;</strong>
    <span>Every source used, what it is allowed to supply and whether it answered on the last refresh.</span></a>
  <a href="methodology.html"><strong>Methodology &rarr;</strong>
    <span>How a probability is derived, de-vigged, converted and labelled.</span></a>
</div>

<h2>Next matches to lock</h2>
<div class="table-wrap">
<table>
<thead><tr><th>Tournament</th><th>Match and probabilities</th><th>Pick</th><th>Basis</th><th>Locks</th></tr></thead>
<tbody>{''.join(rows)}</tbody>
</table>
</div>

<h2>Coverage by tournament</h2>
<div class="table-wrap">
<table>
<thead><tr><th>Tournament</th><th>Matches</th><th>External line</th><th>Our line</th><th>Unverified 50%</th></tr></thead>
<tbody>{coverage_html}</tbody>
</table>
</div>

<div class="note">
<b>Read this before you use a number.</b> A percentage here means one of four things, and the badge says which:
a <span class="chip market">external series line</span> is a de-vigged price from a licensed book or prediction market;
a <span class="chip market-map">external map price only</span> is a price for a single game, not the series;
a <span class="chip model">our own line</span> is our Elo model fitted on Leaguepedia results;
a <span class="chip default">unverified</span> means we found no price and no result history for at least one team,
so the probability is a flat 50% and is flagged as unverified on the <a href="review.html">Flagged for review</a> page.
</div>

<div class="note ok">
<b>Automation.</b> The board is re-collected every 4 hours by a scheduled GitHub Actions run
(<code>.github/workflows/refresh.yml</code>): the HotSpawn inventory, the external lines, the reference results,
the picks and this site are all rebuilt and committed automatically.
</div>
"""
    return body


def page_picks(ctx: dict) -> str:
    picks = ctx["picks"]
    summary = ctx["summary"]
    tournaments = sorted({p.get("tournament") for p in picks if p.get("tournament")})
    options = "".join(f'<option value="{e(t)}">{e(t)}</option>' for t in tournaments)
    body = f"""
<section class="hero">
  <h1>All picks</h1>
  <p class="lede">{e(summary.get('fixtures', 0))} League of Legends matches currently on HotSpawn's pick'em board.
  Each card shows the probability for both teams, the pick, the source that backs it and any flag.</p>
</section>
<div class="filters">
  <input id="q" type="search" placeholder="Search team or tournament" aria-label="Search team or tournament">
  <select id="conf" aria-label="Filter by basis">
    <option value="">All bases</option>
    <option value="market">External series line</option>
    <option value="market-map">External map price only</option>
    <option value="model">Our own line</option>
    <option value="default">Default 50% (unverified)</option>
  </select>
  <select id="tour" aria-label="Filter by tournament"><option value="">All tournaments</option>{options}</select>
  <span class="count" id="count"></span>
</div>
{render_picks_list(picks)}
"""
    return body


def page_unresolved(ctx: dict) -> str:
    picks = ctx["picks"]
    unresolved = [p for p in picks if p.get("unresolved")]
    by_tournament: dict[str, list[dict]] = {}
    for pick in unresolved:
        by_tournament.setdefault(pick.get("tournament") or "unknown", []).append(pick)

    summary_rows = "".join(
        f"<tr><td>{e(name)}</td><td class='num'>{len(items)}</td>"
        f"<td>{e(reason)}</td></tr>"
        for (name, items), reason in sorted(
            ((k, v), limit_reason(v)) for k, v in by_tournament.items()))

    cards = []
    for pick in sorted(unresolved, key=lambda p: (p.get("tournament") or "", p.get("lock_time") or "")):
        cards.append(pick_card(pick))

    body = f"""
<section class="hero">
  <h1>Unresolved picks and their limitations</h1>
  <p class="lede">{e(len(unresolved))} of {e(len(picks))} matches on the HotSpawn League of Legends board are not covered
  by a published series price from the sources we can read. They are listed here in full, with the line we generated
  ourselves and the reason each one stays limited.</p>
</section>

<div class="note">
<b>Why this section exists.</b> Most of these matches are low-tier regional leagues. No sportsbook prices them,
prediction markets do not list them, and the match history needed to model them is thin or missing. Rather than
leaving them out - or publishing a number we cannot defend - we give every one of them a pick, label the basis
honestly, and record the limitation here.
</div>

<h2>Where the unresolved matches are</h2>
<div class="table-wrap">
<table>
<thead><tr><th>Tournament</th><th>Matches</th><th>Limitation</th></tr></thead>
<tbody>{summary_rows}</tbody>
</table>
</div>

<h2>The limitations, in full</h2>
<ul class="tight">
  <li><b>No market price exists.</b> The match is in a league no bookmaker prices, so there is no external
      line to de-vig. Our line is a model, not a market, and is labelled
      <span class="chip model">our own line</span>.</li>
  <li><b>Only a single-map price exists.</b> Kalshi publishes a price for one game of the match, not the series.
      We show the map price and flag it; the series format (best-of-N) is only converted when it is verified
      from a source, never guessed.</li>
  <li><b>No verified match history.</b> Leaguepedia does not publish results for at least one of the two teams,
      so our model has nothing to fit. Those rows carry a flat 50% and are flagged as unverified on the
      <a href="review.html">Flagged for review</a> page.</li>
  <li><b>Team-name ambiguity.</b> A few orgs have several entries on Leaguepedia (for example regional
      sister teams). Where the mapping is ambiguous we flag the row instead of silently choosing one.</li>
</ul>

<h2>Every unresolved match</h2>
<div class="filters">
  <input id="q" type="search" placeholder="Search team or tournament" aria-label="Search team or tournament">
  <select id="conf" aria-label="Filter by basis">
    <option value="">All bases</option>
    <option value="market-map">External map price only</option>
    <option value="model">Our own line</option>
    <option value="default">Default 50% (unverified)</option>
  </select>
  <span class="count" id="count"></span>
</div>
<div class="picks">{''.join(cards)}</div>
"""
    return body


def limit_reason(items: list[dict]) -> str:
    reasons = set()
    for item in items:
        for flag in item.get("flags") or []:
            reasons.add(flag)
    if any("no external betting line" in r for r in reasons):
        return "no market price published for this league; own line used"
    if any("single-map price" in r for r in reasons):
        return "only a single-map price is published"
    if any("no verified match history" in r for r in reasons):
        return "no verified match history for at least one team"
    return "see per-match flags"


def page_review(ctx: dict) -> str:
    picks = ctx["picks"]
    register = ctx["register"]
    resolution = ctx["resolution"]
    stamp = ctx["stamp"]

    unverified = [p for p in picks if p.get("confidence") == "default"]
    map_only = [p for p in picks if p.get("confidence") == "market-map"]
    model_rows = [p for p in picks if p.get("confidence") == "model"]
    unresolved_teams = sorted({p["team_a"]["name"] for p in unverified} |
                               {p["team_b"]["name"] for p in unverified})
    blocked = [s for s in register.get("sources", []) if s.get("status") != "live"]

    def rows(items, key_fn):
        out = []
        for item in items:
            out.append("<tr>" + "".join(f"<td>{cell}</td>" for cell in key_fn(item)) + "</tr>")
        return "".join(out)

    unverified_rows = rows(unverified, lambda p: [
        e(p.get("tournament")), e(p["team_a"]["name"]), e(p["team_b"]["name"]),
        e(pct(p.get("pick_prob"))), e(p.get("pick")),
        f'<a href="{e(p.get("hotspawn_lobby"))}" target="_blank" rel="noopener">HotSpawn board</a>'])
    map_rows = rows(map_only, lambda p: [
        e(p.get("tournament")), e(p["team_a"]["name"]), e(p["team_b"]["name"]),
        e(p.get("market", {}).get("source")),
        f'<a href="{e(p.get("market", {}).get("source_url"))}" target="_blank" rel="noopener">source</a>'])
    model_rows_html = rows(model_rows, lambda p: [
        e(p.get("tournament")), e(p["team_a"]["name"]), e(p["team_b"]["name"]),
        e(p.get("model", {}).get("prob_a")),
        e(p.get("team_a", {}).get("rating")), e(p.get("team_a", {}).get("games")),
        e(p.get("team_b", {}).get("rating")), e(p.get("team_b", {}).get("games"))])
    blocked_rows = "".join(
        f"<tr><td>{e(s.get('name'))}</td><td>{e(s.get('status'))}</td>"
        f"<td><a href=\"{e(s.get('url'))}\" target=\"_blank\" rel=\"noopener\">link</a></td>"
        f"<td>{e(s.get('role'))}</td></tr>" for s in blocked)

    unresolved_tournaments = resolution.get("unresolved_tournaments") or []
    unresolved_tournament_list = "".join(f"<li>{e(t)}</li>" for t in unresolved_tournaments) or "<li>none</li>"

    body = f"""
<section class="hero">
  <h1>Flagged for review</h1>
  <p class="lede">Everything this project could not confirm against a source, left blank or explicitly flagged.
  Nothing on this page is presented as verified. Last refresh: {e(fmt_utc(stamp.get('generated_at')))}.</p>
</section>

<h2>Rows with no verifiable probability</h2>
<p class="small muted">No external line and no verified match history for at least one team. The published probability
for these rows is a flat 50%, which is a default and not a forecast.</p>
<div class="table-wrap">
<table>
<thead><tr><th>Tournament</th><th>Team A</th><th>Team B</th><th>Pick probability</th><th>Pick</th><th>Source</th></tr></thead>
<tbody>{unverified_rows or '<tr><td colspan="6">none</td></tr>'}</tbody>
</table>
</div>
<p class="small muted">Teams in the rows above with no verified history:
{e(", ".join(unresolved_teams) if unresolved_teams else "none")}.</p>

<h2>Rows priced from a single map only</h2>
<p class="small muted">The only published price is for one game of the match, so the number is a map price. The series
format is only converted when a source states it.</p>
<div class="table-wrap">
<table>
<thead><tr><th>Tournament</th><th>Team A</th><th>Team B</th><th>Source</th><th>Link</th></tr></thead>
<tbody>{map_rows or '<tr><td colspan="5">none</td></tr>'}</tbody>
</table>
</div>

<h2>Rows priced by our own model</h2>
<p class="small muted">These have no external line. The rating and the number of rated games behind each side are shown
so they can be checked against Leaguepedia.</p>
<div class="table-wrap">
<table>
<thead><tr><th>Tournament</th><th>Team A</th><th>Team B</th><th>Model P(A)</th><th>Rating A</th><th>Games A</th><th>Rating B</th><th>Games B</th></tr></thead>
<tbody>{model_rows_html or '<tr><td colspan="8">none</td></tr>'}</tbody>
</table>
</div>

<h2>Sources that did not answer</h2>
<div class="table-wrap">
<table>
<thead><tr><th>Source</th><th>Status</th><th>Link</th><th>Role</th></tr></thead>
<tbody>{blocked_rows or '<tr><td colspan="4">none</td></tr>'}</tbody>
</table>
</div>

<h2>Tournaments with no wiki page</h2>
<p class="small muted">These HotSpawn tournaments could not be mapped to a Leaguepedia page, so no team history was
collected for them.</p>
<ul class="tight">{unresolved_tournament_list}</ul>

<div class="note">
<b>How to review this page.</b> Every row above carries the exact source link that produced it. Open the link, check
the number, and if it does not match, open an issue on the repository - the collector re-reads the source on the next
scheduled run, so a corrected source fixes the row without a code change.
</div>
"""
    return body


def page_sources(ctx: dict) -> str:
    register = ctx["register"]
    health = ctx["health"]
    rows = []
    for source in register.get("sources", []):
        status = health.get(source.get("id"))
        live = "answered on the last refresh" if status is None else status
        rows.append(
            f"<tr><td>{e(source.get('name'))}<br><span class='tiny muted'>{e(source.get('kind'))}</span></td>"
            f"<td>{e(source.get('role'))}</td>"
            f"<td><span class='chip {'market' if source.get('status') == 'live' else 'flag'}'>{e(source.get('status'))}</span>"
            f"<br><span class='tiny muted'>{e(live)}</span></td>"
            f"<td><a href=\"{e(source.get('url'))}\" target=\"_blank\" rel=\"noopener\">open</a></td></tr>")
    body = f"""
<section class="hero">
  <h1>Sources</h1>
  <p class="lede">Every source this project reads, what it is allowed to supply and whether it answered on the last
  refresh. All of them are external to HotSpawn, except the two HotSpawn pages that are used for the fixture list only.</p>
</section>
<div class="table-wrap">
<table>
<thead><tr><th>Source</th><th>What it supplies here</th><th>Status</th><th>Link</th></tr></thead>
<tbody>{''.join(rows)}</tbody>
</table>
</div>

<h2>What is deliberately not used</h2>
<ul class="tight">
  <li><b>HotSpawn crowd percentages.</b> The "X% picked" figures on the HotSpawn board are ownership data, not a
      forecast. They are not collected and never enter the probability model.</li>
  <li><b>HotSpawn results.</b> For the same reason the historical results on HotSpawn are not used to fit the model.</li>
  <li><b>Unconfirmed values.</b> Where a source does not publish a number, the cell is left blank and the row is flagged
      rather than filled in with an estimate.</li>
</ul>
"""
    return body


def page_methodology(ctx: dict) -> str:
    stamp = ctx["stamp"]
    body = f"""
<section class="hero">
  <h1>Methodology</h1>
  <p class="lede">How every probability on this site is produced, in the order the steps run.</p>
</section>

<h2>1. The match list</h2>
<p>HotSpawn's League of Legends pick'em board is read from its own public surfaces: the pick'em lobby page and the
fixtures API it calls. That gives the full inventory - match id, tournament, tier, points, lock time and the
per-match permalink HotSpawn publishes. HotSpawn's "X% picked" figures are not collected.</p>

<h2>2. The external lines</h2>
<p>Four independent external sources are read for every refresh:</p>
<ul class="tight">
  <li><b>Kalshi</b> - the <code>KXLOLGAME</code> series, a price for a single game of a match.</li>
  <li><b>Polymarket</b> - match-winner markets, which price the series and name the best-of format in the title.</li>
  <li><b>Pinnacle</b> - the public E Sports guest board: period 0 is the series moneyline, period 1 the map moneyline.</li>
  <li><b>Bovada</b> - the esports events feed, moneyline per market period.</li>
</ul>
<p>A quote is matched to a fixture only when both team names match (normalised, with the filler words
"esports", "gaming", "team", "academy" removed) with a score of 0.8 or better, and the pairing has to be
consistent in both directions. Every matched quote keeps its own URL.</p>

<h2>3. De-vigging</h2>
<p>Book prices contain a margin. Two-sided prices are turned back into a probability with
<code>p = (1/decimal) / ((1/decimalA) + (1/decimalB))</code>. The size of the margin (the overround) is stored and shown
on the row, so the size of the adjustment is auditable.</p>

<h2>4. Series versus map</h2>
<p>A price for one game is not a price for the series. When only a map price exists, it is labelled
<span class="chip market-map">external map price only</span> and flagged. It is converted to a series probability only
when the best-of format is verified from a source (Polymarket market titles state it), using
<code>P(BO3) = p&sup3; + 3p&sup2;(1-p)</code> and the equivalent for other lengths. Nothing is converted on a guess.</p>

<h2>5. Our own line</h2>
<p>Matches no book prices are modelled from verified results taken from Leaguepedia - the tournament match lists and
the team "Match History" pages, both read through the wiki's public API. Each result is a series with a date and a
winner. Ratings are fitted with a standard Elo scheme:</p>
<ul class="tight">
  <li>every team starts at 1500;</li>
  <li>results are processed oldest to newest with K = 32 and no home advantage;</li>
  <li>a rating is shrunk toward 1500 when a team has few games:
      <code>r' = (r&middot;n + 1500&middot;8) / (n + 8)</code>;</li>
  <li>the win probability is <code>p(A) = 1 / (1 + 10^(-(rA - rB)/400))</code>.</li>
</ul>
<p>The rating, the number of rated games and the wiki page behind every team are stored on the row so the number can
be re-derived by hand.</p>

<h2>6. When there is nothing to fit</h2>
<p>If neither an external line nor a verified result history exists for a match, the probability is left at a flat
50%, the row is labelled <span class="chip default">unverified</span> and it is listed on the
<a href="unresolved.html">Unresolved</a> and <a href="review.html">Flagged for review</a> pages. No number is invented
to fill the gap.</p>

<h2>7. Refresh cycle</h2>
<p>A scheduled GitHub Actions job runs every four hours
(<code>.github/workflows/refresh.yml</code>) and rebuilds the inventory, the lines, the reference data, the picks and
this site. Last build: {e(fmt_utc(stamp.get("built_at")))}.</p>
"""
    return body


def build_context() -> dict:
    picks_doc = load("data/picks.json", {"picks": [], "summary": {}})
    inventory = load("data/hotspawn_matches.json", {"matches": [], "counts": {}})
    odds = load("data/odds.json", {"quotes": [], "sources": {}})
    register = load("data/source_register.json", {"sources": []})
    resolution = load("data/reference_resolution.json", {})
    strength = load("data/team_strength.json", {"teams": {}})

    picks = picks_doc.get("picks", [])
    summary = dict(picks_doc.get("summary") or {})

    coverage: dict[str, dict] = {}
    for pick in picks:
        key = pick.get("tournament") or "unknown"
        row = coverage.setdefault(key, {"tournament": key, "total": 0, "market": 0, "model": 0, "default": 0})
        row["total"] += 1
        conf = pick.get("confidence")
        if conf in ("market", "market-map"):
            row["market"] += 1
        elif conf == "model":
            row["model"] += 1
        else:
            row["default"] += 1
    coverage_rows = sorted(coverage.values(), key=lambda r: (-r["total"], r["tournament"]))

    health = {}
    for source_id, doc in (("hotspawn-lobby", "evidence/source_health_hotspawn.json"),
                           ("kalshi", "evidence/source_health_odds.json"),
                           ("polymarket", "evidence/source_health_odds.json"),
                           ("pinnacle", "evidence/source_health_odds.json"),
                           ("bovada", "evidence/source_health_odds.json"),
                           ("leaguepedia", "evidence/source_health_reference.json")):
        doc_data = load(doc, {})
        requests = doc_data.get("requests") or []
        failures = [r for r in requests if r.get("status") is None or (r.get("status") or 0) >= 400]
        if requests:
            health[source_id] = (f"{len(requests) - len(failures)}/{len(requests)} requests answered"
                                 + (f", {len(failures)} failed" if failures else ""))

    stamp = {
        "generated_at": picks_doc.get("generated_at"),
        "built_at": utcnow(),
        "fixtures": summary.get("fixtures", len(inventory.get("matches", []))),
        "covered": summary.get("with_series_market", 0) + summary.get("with_map_market_only", 0),
        "quotes": len(odds.get("quotes", [])),
    }

    return {
        "picks": picks,
        "summary": summary,
        "inventory": inventory,
        "odds": odds,
        "register": register,
        "resolution": resolution,
        "strength": strength,
        "coverage_rows": coverage_rows,
        "health": health,
        "stamp": stamp,
    }


def main() -> int:
    ctx = build_context()
    pages = {
        "index.html": page_index,
        "picks.html": page_picks,
        "unresolved.html": page_unresolved,
        "review.html": page_review,
        "sources.html": page_sources,
        "methodology.html": page_methodology,
    }
    for filename, renderer in pages.items():
        title = dict(NAV)[filename]
        html_text = head(f"{title} - HotSpawn LoL picks",
                         "League of Legends pick'em picks and win probabilities for every HotSpawn match.")
        html_text += renderer(ctx)
        html_text += footer(ctx["stamp"])
        path = os.path.join(REPO_ROOT, filename)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(html_text)
        print(f"wrote {filename} ({len(html_text)} bytes)")
    print("summary:", ctx["summary"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
