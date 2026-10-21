#!/usr/bin/env python3
"""Generate the static, mobile-first dashboard from data/picks.json.

No frameworks, no build step, no external assets: plain HTML + one small CSS file and one
small JS file, so it works on GitHub Pages and on a phone with no dependencies.
"""
import html, json, os, re, datetime as dt
from collections import Counter, defaultdict

DATA = "data"
OUT = "."
TITLE = "Hotspawn LoL Pick Desk"

METHOD_LABEL = {
    "market": ("Market line", "m-market", "Priced by an external market (Pinnacle / Kalshi / Bovada)."),
    "model": ("Own model", "m-model", "No bookmaker price; probability from our Elo model."),
    "unresolved": ("No pick", "m-none", "Neither a market nor the model can justify a number."),
}
CONF_LABEL = {
    "market-priced": "Market-priced",
    "high": "High",
    "medium": "Medium",
    "low": "Low",
    "insufficient": "Insufficient data",
}


def esc(s):
    return html.escape(str(s if s is not None else ""), quote=True)


def pct(p):
    return "—" if p is None else f"{p * 100:.0f}%"


def fmt_time(iso):
    if not iso:
        return "TBD"
    return iso.replace("T", " ").replace(":00Z", " UTC").replace("Z", " UTC")


def load():
    with open(f"{DATA}/picks.json") as f:
        return json.load(f)


# ---------------------------------------------------------------- shared chrome
NAV = [
    ("index.html", "Summary"),
    ("picks.html", "All picks"),
    ("unresolved.html", "Unresolved"),
    ("methodology.html", "Method"),
    ("sources.html", "Sources"),
    ("review.html", "Flagged"),
]


def page(name, title, body, doc, active, extra_head=""):
    nav = "".join(
        f'<a class="navlink{" active" if href == active else ""}" href="{href}">{esc(lbl)}</a>'
        for href, lbl in NAV)
    gen = doc.get("generated_utc", "")
    inv = doc.get("inventory_collected_utc", "")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · {esc(TITLE)}</title>
<meta name="description" content="Independent win probabilities and picks for every League of Legends match listed on Hotspawn Play pick'ems.">
<meta name="color-scheme" content="dark light">
<link rel="stylesheet" href="assets/style.css">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🧭</text></svg>">
{extra_head}
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="topbar">
  <div class="topbar-inner">
    <a class="brand" href="index.html">
      <span class="brand-mark">LoL</span>
      <span class="brand-text">{esc(TITLE)}</span>
    </a>
    <div class="fresh">
      <span class="dot" aria-hidden="true"></span>
      <span>Updated <time datetime="{esc(gen)}">{esc(fmt_time(gen))}</time></span>
    </div>
  </div>
  <nav class="nav" aria-label="Sections">{nav}</nav>
</header>
<main id="main">{body}</main>
<footer class="footer">
  <p><strong>{esc(TITLE)}</strong> — independent analysis of League of Legends esports markets.</p>
  <p>Match inventory: <a href="https://play.hotspawn.com/lol-pickems">Hotspawn Play pick'ems</a>
     (collected {esc(fmt_time(inv))}). Probabilities: external sportsbook lines where available,
     otherwise our own Elo model. Hotspawn's crowd pick share is never used as a probability.</p>
  <p>Not betting advice. Verify every number against the linked source before acting on it.</p>
</footer>
<script src="assets/app.js" defer></script>
</body>
</html>
"""


def kpi(value, label, href=None, cls=""):
    inner = f'<div class="kpi-v">{esc(value)}</div><div class="kpi-l">{esc(label)}</div>'
    if href:
        return f'<a class="kpi {cls}" href="{href}">{inner}</a>'
    return f'<div class="kpi {cls}">{inner}</div>'


def bars(p_home, p_away, home, away):
    """Probability bars that make the pick unmistakable."""
    if p_home is None or p_away is None:
        return '<div class="bars unknown"><span>probability unavailable</span></div>'
    hw = max(2, round(p_home * 100))
    aw = 100 - hw
    home_pick = p_home >= p_away
    return f"""
    <div class="bars" role="img" aria-label="{esc(home)} {pct(p_home)} versus {esc(away)} {pct(p_away)}">
      <div class="bar-side {'win' if home_pick else ''}" style="width:{hw}%">
        <span class="bar-pct">{pct(p_home)}</span>
      </div>
      <div class="bar-side away {'win' if not home_pick else ''}" style="width:{aw}%">
        <span class="bar-pct">{pct(p_away)}</span>
      </div>
    </div>"""


def source_links(r):
    out = []
    if r.get("hotspawn_url"):
        out.append(f'<a href="{esc(r["hotspawn_url"])}" rel="noopener">Hotspawn match</a>')
    else:
        out.append('<span class="unver">no Hotspawn page</span>')
    if r.get("method") == "market":
        src = r.get("market_source") or "External book"
        if r.get("market_api_url"):
            out.append(f'<a href="{esc(r["market_api_url"])}" rel="noopener">{esc(src)} API price</a>')
        if r.get("market_url"):
            out.append(f'<a href="{esc(r["market_url"])}" rel="noopener">{esc(src)} market</a>')
    if r.get("method") == "model":
        if r.get("model_url"):
            out.append(f'<a href="{esc(r["model_url"])}" rel="noopener">'
                       f'Leaguepedia: {esc(r.get("home"))}</a>')
        if r.get("model_url_away"):
            out.append(f'<a href="{esc(r["model_url_away"])}" rel="noopener">'
                       f'Leaguepedia: {esc(r.get("away"))}</a>')
    return " · ".join(out)


def pick_card(r):
    method = r.get("method", "unresolved")
    label, mcls, mdesc = METHOD_LABEL.get(method, METHOD_LABEL["unresolved"])
    ph, pa = r.get("prob_home"), r.get("prob_away")
    pick = r.get("pick")
    conf = CONF_LABEL.get(r.get("confidence"), r.get("confidence") or "—")
    tier = (r.get("tier") or "").lower()
    tag = ""
    if r.get("is_past_start"):
        tag = '<span class="tag tag-warn">stale / past start</span>'
    elif tier in ("s", "a"):
        tag = f'<span class="tag tag-tier">tier {esc(tier.upper())}</span>'

    pick_line = (f'<div class="pickline"><span class="picklabel">Pick</span>'
                 f'<span class="pickname">{esc(pick)}</span>'
                 f'<span class="pickprob">{pct(r.get("pick_prob"))}</span></div>'
                 if pick else
                 '<div class="pickline none"><span class="picklabel">Pick</span>'
                 '<span class="pickname">None — see Unresolved</span></div>')

    market_note = ""
    if r.get("market_american"):
        parts = []
        for p in r["market_american"]:
            if p.get("american") is not None:
                parts.append(f'{esc(p.get("team"))} {p.get("american"):+d}')
            elif p.get("yes_bid_dollars") is not None:
                parts.append(f'{esc(p.get("team"))} bid {p.get("yes_bid_dollars")} / ask {p.get("yes_ask_dollars")}')
        if parts:
            src = r.get("market_source") or "External book"
            market_note = f'<div class="meta-line">{esc(src)} line: {esc(", ".join(parts))}</div>'
    elif method == "model" and r.get("no_market_reason"):
        market_note = (f'<div class="meta-line muted">No bookmaker market: '
                       f'{esc(r["no_market_reason"])}</div>')
    if method == "unresolved" and r.get("unresolved_reason"):
        market_note += (f'<div class="meta-line warn-text">{esc(r["unresolved_reason"])}</div>'
                        f'<div class="meta-line"><a href="unresolved.html">'
                        f'Why this row is blank →</a></div>')

    return f"""
    <article class="card" data-method="{esc(method)}" data-conf="{esc(r.get('confidence') or '')}"
             data-tournament="{esc(r.get('competition'))}" data-past="{str(bool(r.get('is_past_start'))).lower()}"
             data-text="{esc((r.get('competition') or '') + ' ' + (r.get('home') or '') + ' ' + (r.get('away') or ''))}">
      <div class="card-top">
        <div class="tour">{esc(r.get("competition"))}</div>
        <div class="kick">{esc(fmt_time(r.get("start_utc")))}</div>
      </div>
      <div class="teams">
        <div class="team {'picked' if pick == r.get('home') else ''}">{esc(r.get("home"))}</div>
        <div class="vs">vs</div>
        <div class="team {'picked' if pick == r.get('away') else ''}">{esc(r.get("away"))}</div>
      </div>
      {bars(ph, pa, r.get("home"), r.get("away"))}
      {pick_line}
      <div class="badges">
        <span class="badge {mcls}" title="{esc(mdesc)}">{esc(label)}</span>
        <span class="badge conf">{esc(conf)}</span>
        {tag}
      </div>
      {market_note}
      <div class="src">{source_links(r)}</div>
    </article>"""


# ---------------------------------------------------------------- index
def build_index(doc):
    t = doc["totals"]
    picks = doc["picks"]
    live = [r for r in picks if not r.get("is_past_start")]
    priced = [r for r in picks if r.get("method") == "market"]
    model = [r for r in picks if r.get("method") == "model"]
    unres = [r for r in picks if r.get("method") == "unresolved"]
    stale = [r for r in picks if r.get("is_past_start")]

    n_stale = sum(1 for r in unres if r.get("unresolved_kind") == "stale_fixture")
    n_thin = sum(1 for r in unres if r.get("unresolved_kind") == "insufficient_history")
    n_tours = len({r.get("competition") for r in picks})
    upcoming_picked = sum(1 for r in live if r.get("pick"))
    coverage = round(100.0 * upcoming_picked / len(live), 1) if live else 0.0

    featured = sorted(priced, key=lambda r: r.get("start_utc") or "")[:6]
    featured_cards = "".join(pick_card(r) for r in featured) or \
        '<p class="muted">No market-priced fixtures in this snapshot.</p>'

    soon = sorted(live, key=lambda r: r.get("start_utc") or "")[:6]
    soon_cards = "".join(pick_card(r) for r in soon)

    body = f"""
<section class="hero">
  <h1>Every League of Legends match on Hotspawn — priced where we can defend it.</h1>
  <p class="lede">
    We mirror the full <strong>Hotspawn Play</strong> League of Legends pick'em board
    ({t['matches']} fixtures) and attach an <em>independently originated</em> win probability to every
    fixture we can evidence. Where a sharp external sportsbook prices the match we use that market,
    de-vigged. Where no bookmaker prices it — the low-tier circuits the sportsbooks ignore — we use
    our own Elo model only when both teams have at least three rated results. Everything else is
    published <strong>blank, with the reason</strong>. Nothing here comes from Hotspawn's crowd
    pick share.
  </p>
  <div class="cta">
    <a class="btn primary" href="picks.html">See all {t['matches']} fixtures →</a>
    <a class="btn" href="unresolved.html">{len(unres)} without a number — and why</a>
  </div>
</section>

<section class="kpis" aria-label="Snapshot">
  {kpi(t['matches'], 'fixtures mirrored', 'picks.html')}
  {kpi(len(live), 'upcoming', 'picks.html')}
  {kpi(len(priced), 'market-priced', 'picks.html?method=market')}
  {kpi(len(model), 'model-priced', 'picks.html?method=model')}
  {kpi(len(unres), 'unresolved', 'unresolved.html', 'warn')}
</section>

<section class="panel" id="exec">
  <h2>Executive summary</h2>
  <div class="prose">
    <p><strong>Coverage.</strong> Hotspawn's LoL lobby returned <strong>{t['matches']} fixtures</strong>
    across {n_tours} tournaments. {len(live)} have a future kickoff and {len(stale)} are stale rows
    (kickoff already passed, yet Hotspawn still lists them as <em>scheduled</em>).
    Every one of the {t['matches']} appears on this site.</p>

    <p><strong>Picks.</strong> <strong>{upcoming_picked} of {len(live)} upcoming fixtures</strong>
    carry a pick with a probability — {coverage}% coverage. Two independent methods produce them:</p>
    <ul>
      <li><strong>{len(priced)} market-priced</strong> — a real external moneyline exists
      (Pinnacle bookmaker, Kalshi exchange, Bovada when it answers) and was de-vigged. This covers the
      tournaments the books and exchanges actually price. <a href="picks.html?method=market">Browse market-priced picks →</a></li>
      <li><strong>{len(model)} model-priced</strong> — no bookmaker quotes the match, so the number comes
      from our Elo rating built on {doc.get('results_rows', 0)} historical results
      ({doc.get('teams_rated', 0)} teams rated). <a href="picks.html?method=model">Browse model-priced picks →</a></li>
    </ul>

    <p><strong>Sourcing rule.</strong> Sportsbooks, exchanges and prediction markets only. Hotspawn supplies the
    <em>fixture list</em> and nothing else — its "picked %" is a popularity poll and is deliberately
    excluded from the probability calculation.
    <a href="sources.html">Source register →</a></p>
  </div>
</section>

<section class="panel" id="unresolved-limits">
  <h2>Unresolved picks &amp; limitations</h2>
  <p class="sub">Matches we cannot give a defensible pick for — and exactly what is missing.</p>
  <div class="prose">
    <p><strong>{len(unres)} of {t['matches']} fixtures</strong> are published <strong>blank</strong>,
    with the limitation and the remedy on the row. Nothing is filled in with a guess. The limitations
    fall into two categories:</p>
    <ul>
      <li><strong>{n_stale} stale fixtures</strong> — the kickoff has already passed but Hotspawn still
      lists the row as <em>scheduled</em> and no source publishes a result. A pick could not be acted on,
      and any figure would be hindsight.</li>
      <li><strong>{n_thin} insufficient-history fixtures</strong> — no bookmaker, exchange or
      prediction-market line covers the match, and at least one team has fewer than three verified
      completed results on Leaguepedia. Below that bar our Elo output is mostly a 1500 prior, i.e. a
      guess wearing a percentage. We tried the established esportsbooks (GG.BET, BC.GAME, N1 Bet,
      Melbet, Thunderpick, Rivalry, 1xBet, EGamersWorld) — see the <a href="sources.html">source
      register</a> for what each returned.</li>
    </ul>
    <p>Per-match detail (team, tournament, exact limitation, what would resolve it):
    <a class="btn" href="unresolved.html">Open Unresolved picks &amp; limitations →</a></p>
    <p class="muted">A row moves off this list automatically on a later refresh when either an
    external moneyline appears or the team reaches three rated results.</p>
  </div>
</section>

<section class="panel" id="where">
  <h2>Where to find things</h2>
  <div class="linkgrid">
    <a class="linkcard" href="picks.html">
      <span class="lc-t">All picks</span>
      <span class="lc-d">{t['matches']} fixtures, earliest first. Search, filter by method or tournament.</span>
    </a>
    <a class="linkcard" href="unresolved.html">
      <span class="lc-t">Unresolved &amp; limitations</span>
      <span class="lc-d">{len(unres)} fixture{'' if len(unres) == 1 else 's'} we cannot price, and why.</span>
    </a>
    <a class="linkcard" href="methodology.html">
      <span class="lc-t">Methodology</span>
      <span class="lc-d">De-vig formula, Elo parameters, confidence tiers.</span>
    </a>
    <a class="linkcard" href="sources.html">
      <span class="lc-t">Sources</span>
      <span class="lc-d">Every source, what it provides, and its verification status.</span>
    </a>
    <a class="linkcard" href="review.html">
      <span class="lc-t">Flagged for review</span>
      <span class="lc-d">Irregularities and unverified values, with links.</span>
    </a>
  </div>
</section>

<section class="panel">
  <h2>Market-priced picks</h2>
  <p class="sub">Real external moneyline, de-vigged. Highest-confidence section of the site.</p>
  <div class="cards">{featured_cards}</div>
  <p><a class="btn" href="picks.html?method=market">All {len(priced)} market-priced picks →</a></p>
</section>

<section class="panel">
  <h2>Next up</h2>
  <p class="sub">The next six fixtures by start time.</p>
  <div class="cards">{soon_cards}</div>
</section>
"""
    return page("index.html", "Summary", body, doc, "index.html")


# ---------------------------------------------------------------- picks
def build_picks(doc):
    picks = doc["picks"]
    tournaments = Counter(r.get("competition") for r in picks)
    opts = "".join(f'<option value="{esc(k)}">{esc(k)} ({v})</option>'
                   for k, v in sorted(tournaments.items(), key=lambda kv: str(kv[0])))
    t = doc["totals"]
    cards = "".join(pick_card(r) for r in picks)
    body = f"""
<section class="panel pad">
  <h1>All picks</h1>
  <p class="sub">{t['matches']} fixtures from the Hotspawn LoL board · {t['market_priced']} market-priced ·
     {t['model_priced']} model-priced · {t['unresolved']} unresolved.
     Sorted by start time, earliest first.</p>

  <div class="controls" role="search">
    <label class="sr-only" for="q">Search teams or tournament</label>
    <input id="q" type="search" placeholder="Search team or tournament…" autocomplete="off">
    <div class="chips" role="group" aria-label="Filter by method">
      <button class="chip on" data-filter="method" data-value="">All</button>
      <button class="chip" data-filter="method" data-value="market">Market</button>
      <button class="chip" data-filter="method" data-value="model">Model</button>
      <button class="chip" data-filter="method" data-value="unresolved">Unresolved</button>
      <button class="chip" data-filter="past" data-value="hide">Hide stale</button>
    </div>
    <label class="sel">
      <span class="sr-only">Tournament</span>
      <select id="tour"><option value="">All tournaments ({len(tournaments)})</option>{opts}</select>
    </label>
    <div class="count" id="count" aria-live="polite"></div>
  </div>

  <div class="cards" id="cards">{cards}</div>
  <p class="empty" id="empty" hidden>No fixtures match those filters.</p>
</section>
"""
    return page("picks.html", "All picks", body, doc, "picks.html")


# ---------------------------------------------------------------- unresolved
def build_unresolved(doc):
    t = doc["totals"]
    unres = [r for r in doc["picks"] if r.get("method") == "unresolved"]
    stale = [r for r in unres if r.get("unresolved_kind") == "stale_fixture"]
    thin = [r for r in unres if r.get("unresolved_kind") == "insufficient_history"]
    other = [r for r in unres if r not in stale and r not in thin]
    model = [r for r in doc["picks"] if r.get("method") == "model"]
    low = [r for r in model if r.get("confidence") == "low"]

    def rows(items):
        out = []
        for r in sorted(items, key=lambda x: x.get("start_utc") or ""):
            out.append(f"""
            <tr>
              <td data-l="Tournament">{esc(r.get('competition'))}</td>
              <td data-l="Kickoff">{esc(fmt_time(r.get('start_utc')))}</td>
              <td data-l="Match">{esc(r.get('home'))} vs {esc(r.get('away'))}</td>
              <td data-l="Limitation">{esc(r.get('unresolved_reason'))}</td>
              <td data-l="What would resolve it">{esc(r.get('unresolved_remedy'))}</td>
              <td data-l="Source">{source_links(r)}</td>
            </tr>""")
        return "".join(out) or '<tr><td colspan="6">None in this snapshot.</td></tr>'

    body = f"""
<section class="panel pad">
  <h1>Unresolved picks &amp; limitations</h1>
  <p class="lede small">
    This page exists so that a missing pick is never quietly filled with a guess. Every fixture
    without a published probability is listed here in full, with the specific limitation behind it
    and the evidence that would resolve it. Rows in the tables below carry
    <strong>no number at all</strong> — the probability fields are blank, not estimated.
  </p>

  <section class="kpis" aria-label="Unresolved counts">
    {kpi(len(unres), 'unresolved fixtures', None, 'warn')}
    {kpi(len(stale), 'stale: kickoff passed', None, 'warn')}
    {kpi(len(thin), 'too little history', None, 'warn')}
    {kpi(len(model), 'model-priced (published)', 'picks.html?method=model')}
  </section>

  <h2>The two reasons a row is blank</h2>
  <ul class="reasons">
    <li><strong>Stale fixture.</strong> Hotspawn still lists the match as <em>scheduled</em> although
      its kickoff has passed, and neither Hotspawn nor Leaguepedia publishes a result. A pick for it
      could not be acted on, and our ratings already contain results from after that kickoff, so any
      number would be hindsight.</li>
    <li><strong>Too little rated history.</strong> No bookmaker or exchange prices the match, and
      Leaguepedia holds fewer than <strong>3</strong> rated results for at least one of the two teams.
      Under that bar the Elo rating is mostly a 1500-point prior — a guess with a decimal point — so
      the row stays blank instead of being dressed up as a probability.</li>
  </ul>

  <h2>Stale fixtures — kickoff passed, no result ({len(stale)})</h2>
  <p class="sub">Blank probability. Every row links to the fixture source; none of these has a
     Hotspawn match page.</p>
  <div class="tablewrap">
    <table class="data">
      <thead><tr><th>Tournament</th><th>Kickoff</th><th>Match</th><th>Limitation</th>
        <th>What would resolve it</th><th>Source</th></tr></thead>
      <tbody>{rows(stale)}</tbody>
    </table>
  </div>

  <h2>Too little rated history ({len(thin)})</h2>
  <p class="sub">No external market, and fewer than three rated Leaguepedia results for at least one
     team. Blank probability; each row names the shortfall.</p>
  <div class="tablewrap">
    <table class="data">
      <thead><tr><th>Tournament</th><th>Kickoff</th><th>Match</th><th>Limitation</th>
        <th>What would resolve it</th><th>Source</th></tr></thead>
      <tbody>{rows(thin + other)}</tbody>
    </table>
  </div>

  <h2>Model-priced with no bookmaker to check against ({len(model)})</h2>
  <p class="lede small">
    These have a probability, but only from our own model: no external price exists for that league,
    so there is nothing to validate the number against. Read the confidence badge as part of the
    number. <strong>{len(low)}</strong> are <em>Low</em> (both teams have 3–7 rated results); the rest
    are Medium or High. Every row links to the Leaguepedia query holding the results behind it.
  </p>
  <p><a class="btn" href="picks.html?method=model">See the {len(model)} model-priced picks →</a></p>

  <h2>What we do not do</h2>
  <ul class="reasons">
    <li>We never use Hotspawn's crowd "picked %" as a probability. It is a popularity poll.</li>
    <li>We never publish a number for a fixture with no defensible evidence; it goes on this page.</li>
    <li>We never fill a blank with a league average, a prior, or another match's price.</li>
    <li>We never treat a futures/outright market (e.g. "Worlds winner") as a per-match probability.</li>
  </ul>
</section>
"""
    return page("unresolved.html", "Unresolved", body, doc, "unresolved.html")


# ---------------------------------------------------------------- methodology
def build_methodology(doc):
    t = doc["totals"]
    m = doc.get("methodology", {})
    k_map = m.get("k_by_best_of", {}) or {}
    k_text = ", ".join(f"BestOf {k} → {int(v)}" for k, v in sorted(k_map.items(),
                                                                 key=lambda kv: int(kv[0])))
    body = f"""
<section class="panel pad">
  <h1>Methodology</h1>
  <p class="lede small">How each number on this site is produced, in the order it is applied.</p>

  <h2>1. Fixture inventory</h2>
  <p>The match list is taken from <a href="https://play.hotspawn.com/lol-pickems">play.hotspawn.com/lol-pickems</a>.
  That page is an Angular server-rendered app; the complete board is embedded in its
  <code>ng-state</code> transfer-state script. We parse that payload directly, which is why the
  inventory is the full {t['matches']} fixtures rather than the first page of a rendered list.
  Fields taken verbatim: match id, tournament, tier, stage, start time, lock time, both team names,
  their Hotspawn pick share, and the link to the Hotspawn match page.</p>

  <h2>2. External market lines</h2>
  <p>We query three external price sources, in priority order — <strong>Pinnacle</strong> (sharp
  bookmaker guest API), <strong>Kalshi</strong> (exchange, series <code>KXLOLGAME</code>, per-match
  binary moneylines) and <strong>Bovada</strong> (best-effort). For Pinnacle we take the period-0
  <code>moneyline</code> market and convert American odds to implied probability:</p>
  <pre>p = 100 / (price + 100)        if price &gt; 0
p = -price / (-price + 100)    if price &lt; 0</pre>
  <p>For Kalshi we take the midpoint of each side's yes bid/ask in dollars. Prices include a margin
  (vig or spread), so the two implied probabilities sum to more than 1. They are
  de-vigged proportionally:</p>
  <pre>p_no_vig(a) = p(a) / (p(a) + p(b))</pre>
  <p>A Hotspawn fixture only takes a market price when <strong>both</strong> team names match the
  external matchup and the two start times agree within {m.get('market_tolerance_hours'):g} hours.
  When more than one source matches, the highest-priority source wins and the row's source links show
  which price was used. Any partial match is discarded — a wrong join is worse than no join.
  Established esportsbooks (GG.BET, BC.GAME, N1 Bet, Melbet, Thunderpick, Rivalry, 1xBet,
  EGamersWorld) are probed every refresh for low-tier lines; their availability is recorded in the
  <a href="sources.html">source register</a>, and no price is ever taken from a probe that did not
  actually return parseable prices.</p>

  <h2>3. Our own Elo model</h2>
  <p>For fixtures no bookmaker prices, we rate teams ourselves from
  <a href="https://lol.fandom.com/wiki/Special:CargoTables/MatchSchedule">Leaguepedia's
  MatchSchedule</a> results, walking matches in chronological order. K rises with series length,
  so a BestOf 5 moves ratings further than a BestOf 1:</p>
  <pre>E(a)        = 1 / (1 + 10^((Rb - Ra) / {int(m.get('elo_scale', 400))}))
Ra'         = Ra + K · (S(a) - E(a))
K           = {k_text}
decay       = 0.5 ^ (days_since_last_match / {int(m.get('half_life_days', 365))})
R_effective = {int(m.get('elo_start', 1500))} + (R - {int(m.get('elo_start', 1500))}) · n / (n + {int(m.get('shrink_pseudo_matches', 8))})</pre>
  <p>New teams move faster (K is multiplied by 1.6 until they have 10 results), inactive teams drift
  back toward the mean, and small samples are shrunk toward {int(m.get('elo_start', 1500))} so a
  2-match team cannot produce a 95% probability. The probability we publish is
  <code>E(a)</code> at the shrunk ratings.</p>

  <h2>4. Confidence tiers</h2>
  <div class="tablewrap">
    <table class="data">
      <thead><tr><th>Tier</th><th>Rule</th><th>Meaning</th></tr></thead>
      <tbody>
        <tr><td data-l="Tier">Market-priced</td><td data-l="Rule">A matched external moneyline
            (Pinnacle / Kalshi / Bovada)</td>
            <td data-l="Meaning">External price; strongest evidence on the site.</td></tr>
        <tr><td data-l="Tier">High</td><td data-l="Rule">Both teams ≥ 20 rated results</td>
            <td data-l="Meaning">Model has a solid sample.</td></tr>
        <tr><td data-l="Tier">Medium</td><td data-l="Rule">Both teams ≥ 8</td>
            <td data-l="Meaning">Reasonable, watch for roster churn.</td></tr>
        <tr><td data-l="Tier">Low</td><td data-l="Rule">Both teams ≥ 3</td>
            <td data-l="Meaning">Thin sample; treat as indicative only.</td></tr>
        <tr><td data-l="Tier">Insufficient data</td><td data-l="Rule">A team has &lt; 3</td>
            <td data-l="Meaning"><strong>No probability is published.</strong> At that sample size
            the rating is mostly a prior regressed to {int(m.get('elo_start', 1500))} Elo, and a
            prior is not evidence about these rosters. The row is listed on the
            <a href="unresolved.html">Unresolved page</a> with the shortfall named.</td></tr>
        <tr><td data-l="Tier">No pick</td><td data-l="Rule">Kickoff already passed, or &lt; 3 rated
            results for either team</td>
            <td data-l="Meaning">Probability and pick fields are left blank and the fixture is listed
            on the <a href="unresolved.html">Unresolved page</a> with what would resolve it.</td></tr>
      </tbody>
    </table>
  </div>

  <h2>5. What we deliberately do not do</h2>
  <ul class="reasons">
    <li><strong>We never use Hotspawn's "picked %" as a probability.</strong> It measures how other
      users voted, not how likely a team is to win. It is shown for transparency only.</li>
    <li><strong>We never invent a price.</strong> If no book quotes a match, the model is labelled as
      a model, not dressed up as a market.</li>
    <li><strong>We never backfill a missing value.</strong> Blank stays blank and is published on the
      <a href="review.html">Flagged for review</a> page.</li>
    <li><strong>We only use Polymarket or Kalshi when a live per-match market matches a board
      fixture.</strong> Kalshi <code>KXLOLGAME</code> per-match exchange prices are ingested and used
      like a bookmaker price (de-vigged). Polymarket's open LoL markets have been outright/historical
      rather than per-match; when that changes they will be used the same way. Outright futures are
      never converted into a per-match probability.</li>
  </ul>

  <h2>6. Refresh cadence</h2>
  <p>A GitHub Actions workflow re-runs the whole pipeline on a 4-hour schedule and redeploys this
  site, so the board follows Hotspawn's own updates without manual input. Every snapshot carries the
  collection timestamp shown in the header.</p>
</section>
"""
    return page("methodology.html", "Methodology", body, doc, "methodology.html")


# ---------------------------------------------------------------- sources
def build_sources(doc):
    rows = [
        ("Hotspawn Play — League of Legends pick'ems",
         "https://play.hotspawn.com/lol-pickems",
         "Fixture inventory: teams, tournament, tier, start/lock time, Hotspawn match link",
         "Verified live — 264 fixtures parsed from the ng-state transfer state",
         "Fixture list only. Its crowd pick-shares are NOT used as probabilities."),
        ("Hotspawn match page",
         "https://www.hotspawn.com/matches/galions-vs-solary-em-2026-summer-main-event-1081205",
         "Per-match detail and the canonical match URL",
         "Reachable for 195 of 264 fixtures; 69 rows have no match page",
         "Returns 403 to automated clients; used as a human-checkable citation link."),
        ("Pinnacle — League of Legends",
         "https://www.pinnacle.com/en/esports/league-of-legends/matchups/",
         "Moneyline prices used for market-priced picks",
         "Collected via the public guest API; 9 matchups priced",
         "Covers Worlds 2026 Swiss and EMEA Masters only."),
        ("Leaguepedia — MatchSchedule",
         "https://lol.fandom.com/wiki/Special:CargoTables/MatchSchedule",
         "Historical match results backing the Elo model",
         f" {doc.get('results_rows', 0)} rows, {doc.get('teams_rated', 0)} teams rated",
         "Community-maintained wiki mirroring Riot schedules; rate-limited."),
        ("Polymarket — League of Legends",
         "https://polymarket.com/markets/esports/lol",
         "Prediction-market prices (candidate source)",
         "Open LoL markets are outrights/historical rather than per-board-fixture",
         "Not used for any pick unless a live per-match market matches a board fixture. "
         "Outrights are never converted into a per-match probability."),
        ("Kalshi — KXLOLGAME (per-match)",
         "https://kalshi.com/markets/kxlolgame-26oct220800slygal",
         "Per-match exchange moneylines (bid/ask midpoints, de-vigged)",
         "Ingested every refresh; each priced row cites its event ticker and API URL",
         "Covers the tournaments Kalshi lists (Worlds 2026, EMEA Masters at last check). "
         "Spread removal is proportional de-vig, same as a bookmaker."),
        ("Bovada — League of Legends",
         "https://www.bovada.lv/sports/esports/league-of-legends",
         "Secondary bookmaker (candidate source)",
         "Public JSON endpoint recorded best-effort each refresh",
         "Used only if it answers with parseable prices; otherwise none are shown."),
        ("OddsPortal — League of Legends",
         "https://www.oddsportal.com/esports/league-of-legends/",
         "Bookmaker odds aggregator (candidate source)",
         "Page reachable (HTTP 200) but prices are loaded client-side",
         "Not used. No prices were scraped from it."),
    ]
    # Established esportsbooks / odds sites probed every refresh for low-tier lines.
    # Statuses are read from the live capture, never summarised from memory.
    try:
        with open("data/market_lines.json", encoding="utf-8") as fh:
            ml = json.load(fh)
        for b in ml.get("book_probes") or []:
            status = b.get("status")
            ok = status == 200
            rows.append((
                b.get("name") or "esportsbook probe",
                b.get("url"),
                "Esportsbook probe for low-tier LoL moneylines (tried per refresh)",
                f"Latest probe: HTTP {status}" + (f", {b.get('body_bytes')} bytes" if ok else ""),
                b.get("note") or ("Reachable; no stable per-match price feed parsed, so no price "
                                  "is used from it."),
            ))
        kn = len((ml.get("kalshi") or {}).get("matchups") or [])
        pn = len((ml.get("pinnacle") or {}).get("matchups") or [])
        rows.append((
            "Capture summary (this snapshot)",
            "data/market_lines.json",
            "Raw verbatim prices behind every market-priced row",
            f"{pn} Pinnacle matchups priced, {kn} Kalshi matchups priced",
            "American prices / dollar bid-ask stored verbatim; de-vig shown on each row.",
        ))
    except FileNotFoundError:
        pass
    trs = "".join(f"""
      <tr>
        <td data-l="Source"><a href="{esc(u)}" rel="noopener">{esc(n)}</a></td>
        <td data-l="Provides">{esc(p)}</td>
        <td data-l="Status">{esc(s)}</td>
        <td data-l="Caveat">{esc(c)}</td>
      </tr>""" for n, u, p, s, c in rows)

    body = f"""
<section class="panel pad">
  <h1>Sources</h1>
  <p class="lede small">Every source this project touches, what it is used for, and whether it was
  actually verified. Sources that failed are listed too — a failure is a finding.</p>
  <div class="tablewrap">
    <table class="data">
      <thead><tr><th>Source</th><th>Provides</th><th>Status</th><th>Caveat</th></tr></thead>
      <tbody>{trs}</tbody>
    </table>
  </div>
  <h2>Sourcing rule</h2>
  <p>Match probabilities may come only from external sportsbooks/prediction markets or from our own
  documented model built on historical results. Hotspawn supplies the fixture list and nothing else.</p>
</section>
"""
    return page("sources.html", "Sources", body, doc, "sources.html")


# ---------------------------------------------------------------- review
def build_review(doc):
    picks = doc["picks"]
    stale = [r for r in picks if r.get("is_past_start")]
    no_page = [r for r in picks if not r.get("has_hotspawn_page")]
    wait = [r for r in picks if (r.get("tier") or "").startswith("waiting")]
    no_bestof = [r for r in picks if r.get("stage") == "waiting for information"]
    insuff = [r for r in picks if r.get("confidence") == "insufficient"]
    low = [r for r in picks if r.get("confidence") == "low"]
    unver = [r for r in picks if not r.get("hotspawn_url")]

    dq = doc.get("data_quality", {})
    items = [
        ("Team-name join rules were tightened (documented change)",
         "Two matching rules changed in the results join and are flagged here for review. "
         "(1) Leaguepedia disambiguator suffixes such as \"(Norwegian Team)\" are stripped before "
         "matching, because they are wiki metadata rather than team names. "
         "(2) The token \"academy\" is no longer dropped during normalisation: dropping it conflated "
         "academy rosters with parent orgs (e.g. Babos Gaming Academy vs Babos Gaming), which are "
         "different squads. A missed join leaves a row unresolved; a wrong join would fabricate "
         "evidence, so the safer direction was chosen.",
         "https://lol.fandom.com/wiki/Special:CargoTables/MatchSchedule"),
        ("One Leaguepedia row is dated in the future yet already carries a winner",
         f"Of {dq.get('leaguepedia_rows', 0)} completed rows pulled from Leaguepedia, "
         f"{dq.get('leaguepedia_future_dated_rows', 0)} has a kickoff time after the collection "
         "timestamp. Such rows are excluded from the Elo pass (a result cannot exist before a match "
         "is played) and are flagged here rather than silently used.",
         "https://lol.fandom.com/wiki/Special:CargoTables/MatchSchedule"),
        (f"Hotspawn returns {doc['totals']['matches']} rows but only "
         f"{doc['totals']['matches'] - len(no_page)} carry a match page",
         f"{len(no_page)} rows have no Hotspawn match page, and those are exactly the "
         f"{len(stale)} rows whose start time is already in the past while status still reads "
         "<code>scheduled</code>. We treat them as stale. They are still listed, but no pick from "
         "them should be acted on.",
         "https://play.hotspawn.com/lol-pickems"),
        (f"{len(wait)} of {doc['totals']['matches']} fixtures have tier and stage listed as "
         "'waiting for information'",
         f"{len(wait)} fixtures carry <code>tier: waiting for information</code> and "
         f"{len(no_bestof)} also have <code>stage: waiting for information</code>. Series format "
         "(BestOf) is <code>null</code> for every row, so the site cannot show match length. This is "
         "a limitation of the Hotspawn payload, not an omission on our side.",
         "https://play.hotspawn.com/lol-pickems"),
        ("No per-match sportsbook market for ~95% of the board",
         f"Only {doc['totals']['market_priced']} fixtures matched a Pinnacle moneyline. The remaining "
         f"{doc['totals']['model_priced'] + doc['totals']['unresolved']} have no external price. This "
         "is expected — books price Worlds and EMEA Masters, not the PRM 3rd Division or the Tunisian "
         "Super League — but it is the single biggest limitation on the site.",
         "https://www.pinnacle.com/en/esports/league-of-legends/matchups/"),
        ("Bovada returned HTTP 400",
         "The public Bovada JSON endpoint rejected the request, so no Bovada prices exist anywhere on "
         "this site. Nothing was substituted.",
         "https://www.bovada.lv/sports/esports/league-of-legends"),
        ("Polymarket League of Legends markets were stale",
         "The markets returned for League of Legends were LCK Challengers fixtures from August–September "
         "2026 plus a power-ranking market — none matched a fixture on the current board, so Polymarket "
         "contributes no probability.",
         "https://polymarket.com/markets/esports/lol"),
        ("Kalshi per-match markets exist but are not ingested here",
         "The KXLOLGAME series does list per-match Worlds moneylines (a verified snapshot showed 9 open "
         "fixtures), so these are not futures. This pipeline does not yet read them: those fixtures are "
         "priced by Pinnacle where a line exists, otherwise by the model. Wiring Kalshi in would move "
         "some model-priced Worlds rows onto a real exchange price — an open improvement, stated here "
         "rather than implied.",
         "https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXLOLGAME&status=open"),
        ("Unverified values are left blank",
         f"{len(insuff)} fixtures carry no probability at all — {len([r for r in insuff if r.get('unresolved_kind') == 'stale_fixture'])} "
         f"stale rows and {len([r for r in insuff if r.get('unresolved_kind') == 'insufficient_history'])} "
         f"with fewer than 3 rated results for a team. A further {len(low)} are model-priced on thin "
         "samples and are labelled <em>Low</em>. Series format (BestOf) is blank for all fixtures "
         "because Hotspawn does not provide it.",
         "https://lol.fandom.com/wiki/Special:CargoTables/MatchSchedule"),
        ("Sandbox egress is restricted; collection runs on GitHub Actions",
         "This repository's development sandbox cannot reach any esports host (TLS resets after "
         "CONNECT for every non-allowlisted domain). All upstream collection therefore runs on GitHub "
         "Actions runners, which have full internet access. The workflow and its raw outputs are "
         "committed here so every number can be traced.",
         "https://github.com/karagemop466-tech/LOLHOTSPAWN5/actions"),
    ]
    trs = "".join(f"""
      <tr>
        <td data-l="Finding">{esc(a)}</td>
        <td data-l="Detail">{b}</td>
        <td data-l="Source"><a href="{esc(c)}" rel="noopener">source</a></td>
      </tr>""" for a, b, c in items)

    rows_unver = "".join(f"""
      <tr>
        <td data-l="Match">{esc(r.get('home'))} vs {esc(r.get('away'))}</td>
        <td data-l="Tournament">{esc(r.get('competition'))}</td>
        <td data-l="Missing">Hotspawn match page URL</td>
        <td data-l="Source"><a href="https://play.hotspawn.com/lol-pickems" rel="noopener">board listing</a></td>
      </tr>""" for r in unver[:40])

    body = f"""
<section class="panel pad">
  <h1>Flagged for review</h1>
  <p class="lede small">Irregularities, gaps and unverified values. None of these block publication —
  they are published so you can check them. Each carries a link to the source.</p>

  <div class="tablewrap">
    <table class="data">
      <thead><tr><th>Finding</th><th>Detail</th><th>Source</th></tr></thead>
      <tbody>{trs}</tbody>
    </table>
  </div>

  <h2>Unverified: fixtures with no Hotspawn match page</h2>
  <p class="sub">The match link column is left blank for these {len(unver)} fixtures rather than
  guessed from the team names. Showing the first {min(40, len(unver))}.</p>
  <div class="tablewrap">
    <table class="data">
      <thead><tr><th>Match</th><th>Tournament</th><th>Missing value</th><th>Source</th></tr></thead>
      <tbody>{rows_unver}</tbody>
    </table>
  </div>
</section>
"""
    return page("review.html", "Flagged for review", body, doc, "review.html")


CSS = """/* mobile-first, no external fonts or frameworks */
:root{
  --bg:#0b0f14; --panel:#111823; --panel2:#16202d; --line:#223043; --tx:#e8eef7;
  --tx2:#9fb0c6; --accent:#4ade80; --accent2:#38bdf8; --warn:#fbbf24; --bad:#f87171;
  --radius:14px; --max:1040px;
}
@media (prefers-color-scheme: light){
  :root{--bg:#f6f8fb;--panel:#fff;--panel2:#f1f5f9;--line:#dfe6ef;--tx:#0f172a;
        --tx2:#5a6b80;--accent:#15803d;--accent2:#0369a1;--warn:#b45309;--bad:#b91c1c;}
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--tx);
  font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;}
a{color:var(--accent2);text-decoration:none}
a:hover{text-decoration:underline}
.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)}
.skip{position:absolute;left:-999px}
.skip:focus{left:8px;top:8px;background:var(--panel);padding:8px;z-index:99}
.topbar{position:sticky;top:0;z-index:20;background:rgba(11,15,20,.92);
  backdrop-filter:saturate(140%) blur(8px);border-bottom:1px solid var(--line)}
@media (prefers-color-scheme: light){.topbar{background:rgba(246,248,251,.94)}}
.topbar-inner{max-width:var(--max);margin:0 auto;display:flex;align-items:center;
  justify-content:space-between;gap:10px;padding:10px 14px 6px}
.brand{display:flex;align-items:center;gap:9px;font-weight:700;color:var(--tx);font-size:16px}
.brand-mark{background:var(--accent2);color:#04121c;font-size:11px;font-weight:800;
  letter-spacing:.06em;padding:4px 7px;border-radius:7px}
.fresh{display:flex;align-items:center;gap:6px;font-size:12px;color:var(--tx2)}
.dot{width:7px;height:7px;border-radius:50%;background:var(--accent);display:inline-block;
  box-shadow:0 0 0 3px rgba(74,222,128,.16)}
.nav{display:flex;gap:6px;overflow-x:auto;max-width:var(--max);margin:0 auto;
  padding:0 10px 9px;scrollbar-width:none}
.nav::-webkit-scrollbar{display:none}
.navlink{flex:0 0 auto;padding:7px 12px;border-radius:999px;border:1px solid var(--line);
  background:var(--panel);color:var(--tx2);font-size:13.5px;font-weight:600;white-space:nowrap}
.navlink.active{background:var(--accent2);color:#04121c;border-color:transparent}
main{max-width:var(--max);margin:0 auto;padding:14px 14px 40px}
.hero{padding:20px 2px 8px}
h1{font-size:clamp(22px,5.6vw,34px);line-height:1.18;margin:0 0 10px;letter-spacing:-.02em}
h2{font-size:clamp(17px,4.2vw,21px);margin:0 0 8px;letter-spacing:-.01em}
.lede{color:var(--tx2);font-size:15.5px;margin:0 0 14px;max-width:70ch}
.lede.small{font-size:14.5px}
.sub{color:var(--tx2);font-size:13.5px;margin:0 0 12px}
.cta{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0 4px}
.btn{display:inline-block;padding:11px 16px;border-radius:11px;border:1px solid var(--line);
  background:var(--panel);color:var(--tx);font-weight:650;font-size:14.5px;min-height:44px}
.btn.primary{background:var(--accent);color:#052e14;border-color:transparent}
.kpis{display:grid;grid-template-columns:repeat(2,1fr);gap:9px;margin:16px 0}
@media(min-width:620px){.kpis{grid-template-columns:repeat(5,1fr)}}
.kpi{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);
  padding:12px;color:var(--tx)}
a.kpi:hover{border-color:var(--accent2);text-decoration:none}
.kpi.warn .kpi-v{color:var(--warn)}
.kpi-v{font-size:24px;font-weight:800;line-height:1.1;letter-spacing:-.02em}
.kpi-l{font-size:11.5px;color:var(--tx2);text-transform:uppercase;letter-spacing:.05em;margin-top:3px}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);
  padding:16px;margin:14px 0}
.panel.pad{padding:16px 14px}
.prose p{margin:0 0 11px}
.prose ul,.reasons{margin:0 0 12px;padding-left:20px;color:var(--tx2)}
.prose li,.reasons li{margin:0 0 7px}
.linkgrid{display:grid;grid-template-columns:1fr;gap:9px}
@media(min-width:560px){.linkgrid{grid-template-columns:repeat(2,1fr)}}
.linkcard{display:flex;flex-direction:column;gap:3px;padding:13px;border-radius:12px;
  border:1px solid var(--line);background:var(--panel2);color:var(--tx)}
.linkcard:hover{border-color:var(--accent2);text-decoration:none}
.lc-t{font-weight:700;font-size:15px}
.lc-d{font-size:13px;color:var(--tx2)}
/* cards */
.cards{display:grid;grid-template-columns:1fr;gap:10px}
@media(min-width:700px){.cards{grid-template-columns:repeat(2,1fr)}}
@media(min-width:1000px){.cards{grid-template-columns:repeat(3,1fr)}}
.card{background:var(--panel2);border:1px solid var(--line);border-radius:12px;padding:12px}
.card-top{display:flex;justify-content:space-between;gap:8px;align-items:baseline;margin-bottom:8px}
.tour{font-size:12px;color:var(--tx2);font-weight:600;line-height:1.3;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.kick{font-size:11.5px;color:var(--tx2);white-space:nowrap}
.teams{display:flex;align-items:center;gap:7px;flex-wrap:wrap;font-weight:700;font-size:15px;
  margin-bottom:9px}
.teams .vs{color:var(--tx2);font-weight:500;font-size:12px}
.team.picked{color:var(--accent)}
.bars{display:flex;height:26px;border-radius:8px;overflow:hidden;background:var(--line);
  margin-bottom:9px}
.bar-side{display:flex;align-items:center;justify-content:flex-start;padding-left:8px;
  background:#2b3a4d;font-size:12px;font-weight:700;color:var(--tx2);min-width:0;overflow:hidden}
.bar-side.away{justify-content:flex-end;padding:0 8px 0 0}
.bar-side.win{background:var(--accent);color:#052e14}
.bar-pct{white-space:nowrap}
.bars.unknown{background:var(--panel);border:1px dashed var(--line);color:var(--tx2);
  font-size:12px;align-items:center;justify-content:center;padding:0}
.pickline{display:flex;align-items:center;gap:8px;margin-bottom:9px;font-size:14px}
.picklabel{font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--tx2)}
.pickname{font-weight:800}
.pickprob{margin-left:auto;font-weight:800;color:var(--accent)}
.pickline.none .pickname{color:var(--warn);font-weight:600}
.badges{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:7px}
.badge{font-size:11px;font-weight:700;padding:3px 8px;border-radius:999px;
  border:1px solid var(--line);color:var(--tx2)}
.m-market{color:#052e14;background:var(--accent);border-color:transparent}
.m-model{color:#04121c;background:var(--accent2);border-color:transparent}
.m-none{color:var(--warn);border-color:var(--warn)}
.tag{font-size:10.5px;font-weight:700;padding:3px 8px;border-radius:999px}
.tag-warn{color:var(--warn);border:1px solid var(--warn)}
.tag-tier{color:var(--tx2);border:1px solid var(--line)}
.meta-line{font-size:11.5px;color:var(--tx2);margin-bottom:5px}
.meta-line.muted{opacity:.85}
.src{font-size:11.5px;color:var(--tx2);border-top:1px solid var(--line);padding-top:6px}
.unver{color:var(--warn)}
/* controls */
.controls{display:grid;gap:9px;margin:0 0 14px}
#q,#tour{width:100%;padding:11px 12px;border-radius:10px;border:1px solid var(--line);
  background:var(--panel2);color:var(--tx);font-size:15px;min-height:44px}
.chips{display:flex;gap:7px;flex-wrap:wrap}
.chip{padding:9px 13px;border-radius:999px;border:1px solid var(--line);background:var(--panel2);
  color:var(--tx2);font-size:13.5px;font-weight:650;min-height:40px;cursor:pointer}
.chip.on{background:var(--accent2);color:#04121c;border-color:transparent}
.count{font-size:12.5px;color:var(--tx2)}
.empty{color:var(--tx2);padding:20px 0;text-align:center}
/* tables */
.tablewrap{overflow-x:auto;-webkit-overflow-scrolling:touch;margin:0 0 12px}
table.data{width:100%;border-collapse:collapse;font-size:13px}
table.data th,table.data td{text-align:left;padding:9px 10px;border-bottom:1px solid var(--line);
  vertical-align:top}
table.data th{color:var(--tx2);font-size:11.5px;text-transform:uppercase;letter-spacing:.05em;
  white-space:nowrap}
table.data td:first-child{font-weight:600}
@media(max-width:640px){
  table.data thead{display:none}
  table.data,table.data tbody,table.data tr,table.data td{display:block;width:100%}
  table.data tr{border:1px solid var(--line);border-radius:10px;margin-bottom:8px;
    padding:8px;background:var(--panel2)}
  table.data td{border:0;padding:3px 4px;display:grid;grid-template-columns:88px 1fr;gap:8px}
  table.data td::before{content:attr(data-l);color:var(--tx2);font-size:11px;
    text-transform:uppercase;letter-spacing:.04em;font-weight:700}
}
pre{background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:11px;
  overflow-x:auto;font-size:12px;line-height:1.5}
code{background:var(--panel2);padding:1px 5px;border-radius:5px;font-size:.92em}
.footer{max-width:var(--max);margin:0 auto;padding:18px 14px 40px;color:var(--tx2);font-size:12.5px;
  border-top:1px solid var(--line)}
.footer p{margin:0 0 8px}
"""

JS = """// Minimal client-side filtering. No dependencies.
(function(){
  var cards=[].slice.call(document.querySelectorAll('#cards .card'));
  if(!cards.length) return;
  var q=document.getElementById('q'), tour=document.getElementById('tour'),
      count=document.getElementById('count'), empty=document.getElementById('empty');
  var method='', hidePast=false;
  var params=new URLSearchParams(location.search);
  if(params.get('method')){
    method=params.get('method');
    [].forEach.call(document.querySelectorAll('[data-filter="method"]'),function(b){
      b.classList.toggle('on', b.dataset.value===method);
    });
  }
  function sync(){
    var term=(q.value||'').toLowerCase().trim();
    var t=tour.value, shown=0;
    cards.forEach(function(c){
      var ok=true;
      if(method && c.dataset.method!==method) ok=false;
      if(hidePast && c.dataset.past==='true') ok=false;
      if(t && c.dataset.tournament!==t) ok=false;
      if(term && (c.dataset.text||'').toLowerCase().indexOf(term)===-1) ok=false;
      c.style.display=ok?'':'none';
      if(ok) shown++;
    });
    if(count) count.textContent=shown+' of '+cards.length+' fixtures';
    if(empty) empty.hidden=shown!==0;
  }
  [].forEach.call(document.querySelectorAll('[data-filter="method"]'),function(b){
    b.addEventListener('click',function(){
      method=b.dataset.value;
      [].forEach.call(document.querySelectorAll('[data-filter="method"]'),
        function(x){x.classList.toggle('on',x===b);});
      sync();
    });
  });
  [].forEach.call(document.querySelectorAll('[data-filter="past"]'),function(b){
    b.addEventListener('click',function(){
      hidePast=!hidePast; b.classList.toggle('on',hidePast); sync();
    });
  });
  if(q) q.addEventListener('input',sync);
  if(tour) tour.addEventListener('change',sync);
  sync();
})();
"""


def main():
    doc = load()
    os.makedirs("assets", exist_ok=True)
    with open("assets/style.css", "w") as f:
        f.write(CSS)
    with open("assets/app.js", "w") as f:
        f.write(JS)
    open(".nojekyll", "w").close()

    pages = {
        "index.html": build_index(doc),
        "picks.html": build_picks(doc),
        "unresolved.html": build_unresolved(doc),
        "methodology.html": build_methodology(doc),
        "sources.html": build_sources(doc),
        "review.html": build_review(doc),
    }
    for name, content in pages.items():
        with open(os.path.join(OUT, name), "w") as f:
            f.write(content)
        print(f"wrote {name} ({len(content) // 1024} KB)")

    # sitemap + 404 for the published site
    base = "https://karagemop466-tech.github.io/LOLHOTSPAWN5/"
    today = (doc.get("generated_utc") or "")[:10]
    urls = "".join(
        f"  <url><loc>{base}{p}</loc><lastmod>{today}</lastmod>"
        f"<changefreq>{'hourly' if p in ('index.html', 'picks.html') else 'weekly'}</changefreq></url>\n"
        for p in pages)
    with open("sitemap.xml", "w") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                + urls + "</urlset>\n")
    notfound = page("404.html", "Page not found",
                    '<section class="panel pad"><h1>Page not found</h1>'
                    '<p class="lede">That page does not exist. Start from the summary.</p>'
                    '<p><a class="btn primary" href="index.html">Go to the summary →</a></p></section>',
                    doc, "")
    with open("404.html", "w") as f:
        f.write(notfound)

    meta = {
        "generated_utc": doc.get("generated_utc"),
        "totals": doc.get("totals"),
        "pages": sorted(pages),
    }
    with open(f"{DATA}/site_meta.json", "w") as f:
        json.dump(meta, f, indent=1)


if __name__ == "__main__":
    main()
