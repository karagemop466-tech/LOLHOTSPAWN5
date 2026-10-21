#!/usr/bin/env python3
"""
Dev-time page generator for the GitHub Pages dashboard.

Writes the eight static HTML pages in the repository root. The pages are plain
static files (no build step at deploy time) - this script only exists so the
shared shell/navigation stays identical across pages.

    python3 scripts/build_pages.py
"""

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

NAV = [
    ("index.html", "Summary"),
    ("picks.html", "All Picks"),
    ("markets.html", "Market Lines"),
    ("model.html", "Originated Lines"),
    ("unresolved.html", "Unresolved"),
    ("methodology.html", "Methodology"),
    ("sources.html", "Sources"),
    ("flagged.html", "Flagged"),
]

SHELL = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="stylesheet" href="assets/style.css">
</head>
<body>
<a class="skip" href="#content">Skip to content</a>

<header class="site-header">
  <div class="header-inner">
    <a class="brand" href="index.html">
      <span class="brand-mark">HS</span>
      <span class="brand-text">
        <span class="brand-title">Hotspawn LoL Pick Desk</span>
        <span class="brand-sub">League of Legends Pick'em lines</span>
      </span>
    </a>
    <span class="stamp">Data updated<br><b id="updated">&mdash;</b></span>
  </div>
  <nav class="site-nav" id="mainnav" aria-label="Main">
    <ul>
{navitems}
    </ul>
  </nav>
</header>

<main id="content" class="wrap">
{body}
</main>

<footer class="site-footer">
  <div class="wrap">
    <p><b>Hotspawn LoL Pick Desk</b> &mdash; independent research dashboard.
       Not affiliated with, endorsed by, or operated by Hotspawn.</p>
    <p>Match board: <a href="{lobby}" target="_blank" rel="noopener noreferrer">play.hotspawn.com/lol-pickems</a>.
       Data is regenerated automatically every 6 hours by GitHub Actions.
       Nothing on this site is gambling advice.</p>
    <p>Every table row on this site links to the official source it was derived from.
       Values that could not be confirmed from an official source are left blank and
       flagged on the <a href="flagged.html">Flagged for Review</a> page.</p>
  </div>
</footer>

<script src="assets/app.js"></script>
</body>
</html>
"""

LOBBY = "https://play.hotspawn.com/lol-pickems"
API = "https://phpstack-1372681-6459848.cloudwaysapps.com/api/v1/fixtures"
PINNACLE = "https://www.pinnacle.com/en/esports/"
UNIBET = "https://www.unibet.com/sportsbook-feeds/views/filter/esports"
POLY = "https://polymarket.com/"
LEAGUEPEDIA = "https://lol.fandom.com/api.php?action=help&modules=cargoquery"

TOOLBAR = """
  <div class="toolbar">
    <input type="search" id="search" placeholder="Search team, tournament, evidence…" aria-label="Search picks">
    <select id="tournament-filter" aria-label="Filter by tournament">
      <option value="">All tournaments</option>
    </select>
    <div class="viewtoggle" role="group" aria-label="View mode">
      <button type="button" data-view="cards" aria-pressed="true">Cards</button>
      <button type="button" data-view="table" aria-pressed="false">Table</button>
    </div>
  </div>
  <p class="small muted" id="result-count">&nbsp;</p>
"""


def nav_html(current):
    out = []
    for href, label in NAV:
        cur = ' aria-current="page"' if href == current else ""
        out.append(f'      <li><a href="{href}"{cur}>{label}</a></li>')
    return "\n".join(out)


def page(filename, title, desc, body):
    return SHELL.format(
        title=title, desc=desc, navitems=nav_html(filename), body=body, lobby=LOBBY
    )


# --------------------------------------------------------------------------- #
# Page bodies
# --------------------------------------------------------------------------- #

INDEX = """
  <h1 class="page-title">Executive summary</h1>
  <p class="lede">Independent win probabilities for <b>every</b> League of Legends match listed on the
     <a href="{lobby}" target="_blank" rel="noopener noreferrer">Hotspawn Pick'em board</a>,
     regenerated automatically every 6 hours.</p>

  <h2 class="section">Where to find the picks</h2>
  <div class="grid c2">
    <a class="navcard" href="picks.html">
      <h3>All picks <span class="badge tier"><span data-count="total">&mdash;</span> fixtures</span></h3>
      <p>The complete, searchable board. Team-by-team win probability, the pick, how the line was
         produced, and an official source link on every row.</p>
      <span class="go">Open all picks &rarr;</span>
    </a>
    <a class="navcard good" href="markets.html">
      <h3>Market lines <span class="badge market"><span data-count="market">&mdash;</span></span></h3>
      <p>Fixtures priced by an outside esportsbook or prediction market (Pinnacle, Unibet,
         Polymarket). Strongest evidence tier.</p>
      <span class="go">Open market lines &rarr;</span>
    </a>
    <a class="navcard" href="model.html">
      <h3>Originated lines <span class="badge model"><span data-count="model">&mdash;</span></span></h3>
      <p>Fixtures with no betting market, where we originate our own line from official Leaguepedia
         match history using a documented Elo + recent-form model.</p>
      <span class="go">Open originated lines &rarr;</span>
    </a>
    <a class="navcard warn" href="unresolved.html">
      <h3>Unresolved <span class="badge unresolved"><span data-count="unresolved">&mdash;</span></span></h3>
      <p>Fixtures we could <b>not</b> resolve from any outside source, the 50/50 nominal picks we
         publish for them, and a precise statement of the limitations.</p>
      <span class="go">Open unresolved &amp; limitations &rarr;</span>
    </a>
  </div>

  <div class="grid c2">
    <a class="navcard neutral" href="methodology.html">
      <h3>Methodology</h3>
      <p>Exactly how each probability is produced, in what order sources are trusted, and how the
         model is built.</p>
      <span class="go">Read methodology &rarr;</span>
    </a>
    <a class="navcard neutral" href="sources.html">
      <h3>Sources &amp; verification</h3>
      <p>Every external source used, what it provides, and the verification performed against it.</p>
      <span class="go">Open sources &rarr;</span>
    </a>
  </div>

  <h2 class="section">Coverage right now</h2>
  <div id="summary"><p class="muted">Loading coverage statistics…</p></div>

  <h2 class="section">What this site does</h2>
  <div class="note good">
    <p><b>1. It lists every scheduled League of Legends Pick'em on Hotspawn</b> &mdash; not just the
       high-profile ones. The board is read directly from Hotspawn's own fixture API.</p>
    <p><b>2. It prices each match from outside esports betting markets first</b> &mdash; Pinnacle,
       Unibet (Kambi) and Polymarket. Prices are de-vigged into probabilities.</p>
    <p><b>3. Where no market exists, it originates its own line</b> from official Leaguepedia match
       history using a documented Elo + recent-form model with sample-size shrinkage.</p>
    <p><b>4. Where neither is possible, it says so.</b> Those matches get a nominal 50/50 pick and a
       row on the <a href="unresolved.html">Unresolved</a> page with the limitation stated.</p>
  </div>

  <h2 class="section">What this site does <i>not</i> do</h2>
  <div class="note warn">
    <p><b>Hotspawn's own crowd pick percentages are never used as a probability input.</b> The
       "X% picked" figures shown on the Hotspawn lobby are the crowd's picks, not a line. They are
       recorded on this site for context and clearly labelled, but they never feed a number.</p>
    <p><b>No value is invented.</b> If a number cannot be traced to an official source it is left
       blank and flagged on the <a href="flagged.html">Flagged for Review</a> page.</p>
  </div>

  <h2 class="section">Unresolved picks &mdash; the limitation in one paragraph</h2>
  <div class="note warn">
    <p>Most fixtures on the Hotspawn LoL board are <b>Tier&nbsp;C/D amateur and regional circuits</b>
       (PRM 3rd Division, Tunisian Super League, RIVALS LEAGUE, Komplettligaen, Arabian regional
       leagues and similar). No commercial bookmaker and no prediction market prices these fixtures,
       and many of the teams have no completed match recorded in Leaguepedia &mdash; rosters in these
       circuits turn over constantly and results are frequently unreported. For those matches we
       publish a <b>nominal 50/50 pick</b> so the board is complete, and we label it
       <span class="badge unresolved">Unresolved</span> so it is never confused with a real edge.
       See the <a href="unresolved.html">Unresolved page</a> for the full list and the detailed
       limitations.</p>
    <p><a href="unresolved.html">Read the full unresolved section &amp; limitations &rarr;</a></p>
  </div>

  <h2 class="section">How often is this updated?</h2>
  <p>A GitHub Actions workflow re-runs the whole pipeline <b>every 6 hours</b> (and on demand),
     re-reads the Hotspawn board, re-pulls every market and the Leaguepedia history, and republishes
     <code>data/picks.json</code>. The timestamp at the top of this page is the collection time.
     No manual input is required.</p>

  <h2 class="section">Flagged for review</h2>
  <p>Items we could not fully verify &mdash; reconstructed match permalinks, thin-history model
     lines, single-book lines and stale board entries &mdash; are published with their source links on the
     <a href="flagged.html">Flagged for Review</a> page.</p>
""".format(lobby=LOBBY)


PICKS = """
  <h1 class="page-title">All picks</h1>
  <p class="lede">Every scheduled League of Legends Pick'em fixture on the Hotspawn board, with an
     independent win probability for each team. Filter, search, or switch to table view.</p>
""" + TOOLBAR + """
  <div id="list"><p class="loading">Loading picks…</p></div>
"""


def list_page(filename, title, lede, method=None, open_only=False, extra=""):
    attrs = []
    if method:
        attrs.append(f'data-method="{method}"')
    if open_only:
        attrs.append('data-open-only="1"')
    body = f"""
  <h1 class="page-title">{title}</h1>
  <p class="lede">{lede}</p>
{extra}
""" + TOOLBAR + f"""
  <div id="list" {' '.join(attrs)}><p class="loading">Loading…</p></div>
"""
    return body


MARKETS = list_page(
    "markets.html",
    "Market lines",
    "Fixtures priced by an outside esportsbook or prediction market. These are the strongest lines on "
    "the site: Pinnacle and Unibet moneylines are de-vigged into probabilities, and Polymarket "
    "prediction prices are normalised. Where more than one source prices the same match the "
    "de-vigged probabilities are averaged, with Pinnacle weighted double as the sharp book.",
    method="MARKET",
    extra="""
  <div class="note good">
    <p><b>Why this tier is small.</b> Commercial books only price top-tier League of Legends. On the
       current board that is essentially the World Championship and EMEA Masters. Everything else on
       the Hotspawn board has no market at all &mdash; see
       <a href="model.html">Originated lines</a> and <a href="unresolved.html">Unresolved</a>.</p>
    <p><b>Hotspawn crowd percentages are not used.</b> Nothing on this page is derived from the
       Hotspawn lobby's pick split.</p>
  </div>
""",
)

MODEL = list_page(
    "model.html",
    "Originated lines",
    "Fixtures with no betting market, where we originate our own line. A proprietary Elo rating with "
    "recent-form blending is computed from completed matches recorded in Leaguepedia (the official "
    "League of Legends esports wiki), then shrunk toward 50% in proportion to how thin the underlying "
    "match history is.",
    method="MODEL",
    extra="""
  <div class="note">
    <p><b>How the model works, in short.</b> Every completed game involving a board team in the last
       420 days is pulled from Leaguepedia's <code>ScoreboardGames</code> Cargo table. Games are
       replayed in chronological order to produce an Elo rating (start 1500, K&nbsp;=&nbsp;28). The
       head-to-head Elo expectation is blended 70/30 with a 90-day win-rate differential, then shrunk
       toward 50% as <code>n/(n+12)</code> where <code>n</code> is the smaller team's game count.</p>
    <p><b>Known weakness.</b> Amateur rosters change between splits and Leaguepedia coverage of
       regional circuits is patchy, so ratings for thinly-documented teams are deliberately pulled
       close to even. Rows built on fewer than 5 games are additionally flagged.</p>
    <p>Full detail on the <a href="methodology.html">Methodology</a> page.</p>
  </div>
""",
)

UNRESOLVED = list_page(
    "unresolved.html",
    "Unresolved picks &amp; limitations",
    "Fixtures for which no external betting line and no usable Leaguepedia match history exists. "
    "These are published with a nominal 50/50 pick so the board is complete, and are never presented "
    "as having an edge.",
    method="UNRESOLVED",
    extra="""
  <h2 class="section">Why these picks cannot be resolved</h2>
  <div class="note warn">
    <p><b>1. There is no betting market for them.</b> We checked, in order: established esportsbooks
       (Pinnacle's public esports board, Unibet's Kambi esports feed), then prediction markets
       (Polymarket's League of Legends markets), then the odds-aggregator APIs
       (OddsPapi, PandaScore, Abios &mdash; all require a paid key we do not hold). Pinnacle and
       Unibet together price roughly a dozen League of Legends fixtures worldwide on any given day,
       and they are all World Championship / EMEA Masters. Tier&nbsp;C and Tier&nbsp;D regional and
       amateur circuits &mdash; which is what most of the Hotspawn board is &mdash; are not priced
       anywhere, by anyone.</p>
    <p><b>2. There is no reliable result history either.</b> Leaguepedia is the most complete public
       record of League of Legends esports, but coverage of the lowest tiers is partial: matches go
       unreported, team names are inconsistent between splits, and rosters in these circuits turn
       over every few weeks. Where neither team has a completed game in the last 420 days, there is
       simply nothing to model.</p>
    <p><b>3. Roster volatility makes any prior signal decay fast.</b> Even where a team does have
       history, an amateur roster that has turned over since those games were played is a different
       team. We do not have access to current roster data for these circuits from an official source,
       so we do not attempt to adjust for it.</p>
  </div>

  <h2 class="section">What we publish instead, and how to read it</h2>
  <div class="note">
    <p>Each unresolved fixture is published as a <b>nominal 50/50 pick</b>: both teams show 50.0%,
       the listed pick is simply team&nbsp;A (the team Hotspawn lists first), and the row is badged
       <span class="badge unresolved">Unresolved</span>. <b>There is no statistical edge behind that
       pick</b> &mdash; it exists only so that the board has a complete row set and so that the gap
       in coverage is visible rather than hidden.</p>
    <p>These rows still carry official source links: the Hotspawn fixture record and the Hotspawn
       match page, so you can verify that the fixture exists and check its tier, points and lock
       time yourself.</p>
  </div>

  <h2 class="section">Full list of unresolved fixtures</h2>
""",
)

METHODOLOGY = """
  <h1 class="page-title">Methodology</h1>
  <p class="lede">Exactly how every probability on this site is produced, and in what order evidence
     is trusted.</p>

  <h2 class="section">1. The match board</h2>
  <p>The board is read from Hotspawn's own fixture API, the same data source
     <a href="{lobby}" target="_blank" rel="noopener noreferrer">play.hotspawn.com/lol-pickems</a>
     renders:</p>
  <p><code>{api}</code></p>
  <p>Every record with <code>sport_alias = "lol"</code> and <code>status = "scheduled"</code> is
     included &mdash; that is the full League of Legends Pick'em board, not a filtered subset. Team
     names, tournament, tier, points, scheduled start time, pick-lock time and Hotspawn's crowd pick
     percentages all come from this one response.</p>
  <p>The lobby HTML is additionally parsed to harvest the server-rendered
     <code>www.hotspawn.com/matches/…</code> permalinks. Only 195 of the 264 fixtures have a permalink in that HTML. The rest are
     reconstructed from Hotspawn's public slug pattern &mdash; a rule validated by reconstructing
     <b>195 of 195</b> server-rendered permalinks byte-for-byte &mdash; and marked
     <span class="badge unverified">unverified</span> on the
     <a href="flagged.html">Flagged for Review</a> page, because <code>www.hotspawn.com</code>
     answers HTTP 403 to the automation runner and each URL could not be individually confirmed.
     The fixture record itself is official in both cases.</p>

  <h2 class="section">2. Evidence ladder</h2>
  <table class="data" style="min-width:0">
    <thead><tr><th>Tier</th><th>Source</th><th>What it gives us</th><th>Conversion</th></tr></thead>
    <tbody>
      <tr><td><span class="badge market">L1</span></td>
          <td><a href="{pinnacle}" target="_blank" rel="noopener noreferrer">Pinnacle</a> esports moneyline (keyless guest API)</td>
          <td>Sharp-book price for top-tier LoL</td>
          <td>American &rarr; decimal &rarr; implied &rarr; de-vigged. Weighted &times;2 in consensus.</td></tr>
      <tr><td><span class="badge market">L1</span></td>
          <td><a href="{unibet}" target="_blank" rel="noopener noreferrer">Unibet</a> Kambi esports feed</td>
          <td>Independent soft-book price</td>
          <td>Decimal &rarr; implied &rarr; de-vigged. Weight &times;1.</td></tr>
      <tr><td><span class="badge market">L1</span></td>
          <td><a href="{poly}" target="_blank" rel="noopener noreferrer">Polymarket</a> Gamma API</td>
          <td>Prediction-market price</td>
          <td>Outcome prices normalised to sum to 1. Weight &times;1.</td></tr>
      <tr><td><span class="badge model">L2</span></td>
          <td><a href="{lp}" target="_blank" rel="noopener noreferrer">Leaguepedia</a> Cargo <code>ScoreboardGames</code></td>
          <td>Official match history for teams with no market</td>
          <td>Elo + recent-form model with sample-size shrinkage (below).</td></tr>
      <tr><td><span class="badge unresolved">L3</span></td>
          <td>None available</td>
          <td>&mdash;</td>
          <td>Nominal 50/50 pick, flagged as unresolved. No edge claimed.</td></tr>
    </tbody>
  </table>
  <p>Where several L1 sources price the same fixture, their de-vigged probabilities are averaged with
     the weights above. Team-name matching is fuzzy (normalised alphanumeric comparison) and is
     cross-checked against the fixture start time where the source provides one.</p>

  <h2 class="section">3. De-vigging</h2>
  <p>A two-way book price contains the bookmaker's margin. For decimal prices
     <code>d1, d2</code> we compute implied probabilities <code>1/d1, 1/d2</code> and normalise them
     so they sum to&nbsp;1. That removes the overround and yields the book's implied win
     probabilities.</p>

  <h2 class="section">4. The originated-line model</h2>
  <ul class="plain">
    <li><b>History window:</b> every completed game in Leaguepedia's
        <code>ScoreboardGames</code> table in the last <b>420 days</b> involving any team on the
        board, backed by a per-team cache so repeat runs only query what is new.</li>
    <li><b>Elo:</b> games are replayed in chronological order. Both teams start at 1500,
        K&nbsp;=&nbsp;28. The rating difference gives a head-to-head expectation
        <code>1 / (1 + 10^((Rb-Ra)/400))</code>.</li>
    <li><b>Form:</b> a 90-day win-rate differential is blended 30% into the Elo expectation when both
        teams have at least 4 games in that window.</li>
    <li><b>Shrinkage:</b> the result is pulled toward 50% by a factor
        <code>n/(n+12)</code>, where <code>n</code> is the smaller team's game count. A team with 3
        recorded games therefore barely moves off 50%; a team with 40 games is barely shrunk.</li>
    <li><b>Confidence labels:</b> <i>Medium</i> when both teams have 10+ games, <i>Low</i> below
        that, <i>Very thin</i> below 3.</li>
  </ul>
  <p class="muted">The model is deliberately conservative: when the data is thin it returns something
     close to even money rather than a confident-looking number it cannot support.</p>

  <h2 class="section">5. What is deliberately excluded</h2>
  <div class="note warn">
    <p><b>Hotspawn's crowd pick percentages are never an input.</b> The "86% picked" style figures on
       the Hotspawn lobby are the crowd's own picks for a free Pick'em game. They are a popularity
       poll, not a line. We record them for reference and label them as such, and no probability on
       this site is derived from them.</p>
    <p><b>Paid odds-aggregator APIs are not used.</b> OddsPapi, PandaScore, Abios and The Odds API all
       require an account and key. Since this project must run with no manual input, we only use
       sources reachable without credentials &mdash; listed on the
       <a href="sources.html">Sources</a> page.</p>
  </div>

  <h2 class="section">6. Automation &amp; verification</h2>
  <p>A GitHub Actions workflow (<code>.github/workflows/update-picks.yml</code>) runs the pipeline
     every 6 hours and on demand. After every run it asserts that:</p>
  <ul class="plain">
    <li>at least one fixture was returned;</li>
    <li>every pick is one of the two teams on that fixture;</li>
    <li><code>prob_team1 + prob_team2 = 1.0</code> for every row;</li>
    <li>every method is one of <code>MARKET</code>, <code>MODEL</code>, <code>UNRESOLVED</code>;</li>
    <li>every row carries a Hotspawn match URL and at least one source link.</li>
  </ul>
  <p>Anything that could not be verified is written to <code>data/flagged.json</code> and published on
     the <a href="flagged.html">Flagged for Review</a> page rather than silently filled in.</p>
""".format(lobby=LOBBY, api=API, pinnacle=PINNACLE, unibet=UNIBET, poly=POLY, lp=LEAGUEPEDIA)

SOURCES = """
  <h1 class="page-title">Sources &amp; verification</h1>
  <p class="lede">Every external source this site uses, what it contributes, and the verification
     performed against it at the last collection run.</p>

  <div id="sources-list"><p class="loading">Loading source registry…</p></div>

  <h2 class="section">Sources we tested and rejected</h2>
  <table class="data" style="min-width:0">
    <thead><tr><th>Source</th><th>Result</th><th>Why</th></tr></thead>
    <tbody>
      <tr><td>OddsPapi (<code>api.oddspapi.io</code>)</td>
          <td><span class="badge unresolved">Not used</span></td>
          <td>Requires a free-tier API key; no credentials available for an unattended pipeline.</td></tr>
      <tr><td>PandaScore (<code>api.pandascore.co</code>)</td>
          <td><span class="badge unresolved">Not used</span></td>
          <td>Returns <code>403 Token is missing</code>.</td></tr>
      <tr><td>Abios (<code>api.abiosgaming.com</code>)</td>
          <td><span class="badge unresolved">Not used</span></td>
          <td>Returns <code>403 Token is missing</code>.</td></tr>
      <tr><td>DraftKings / FanDuel sportsbook APIs</td>
          <td><span class="badge unresolved">Not used</span></td>
          <td>Blocked from the runner (403 / geo-restricted).</td></tr>
      <tr><td>1xBet, GG.Bet, Thunderpick, Stake, Luckbox</td>
          <td><span class="badge unresolved">Not used</span></td>
          <td>Cloudflare challenge or connection failure from the runner; no keyless odds feed.</td></tr>
      <tr><td>Kalshi</td>
          <td><span class="badge unresolved">Not used</span></td>
          <td>Public API reachable but carries no League of Legends match markets.</td></tr>
      <tr><td>OddsPortal / BetExplorer</td>
          <td><span class="badge unresolved">Not used</span></td>
          <td>HTML-only, aggressive anti-bot, and not an official source. Rejected on
              verification grounds.</td></tr>
      <tr><td>Liquipedia</td>
          <td><span class="badge unresolved">Not used</span></td>
          <td>Rate-limited (429) from the runner; Leaguepedia provides the same role with a working
              Cargo API.</td></tr>
      <tr><td>www.hotspawn.com match pages</td>
          <td><span class="badge unverified">Context only</span></td>
          <td>Cloudflare returns 403 to the runner, so permalinks harvested from the lobby HTML are
              used as the official match link. Constructed permalinks are flagged.</td></tr>
    </tbody>
  </table>

  <h2 class="section">Hotspawn is a source of fixtures, never of probability</h2>
  <div class="note warn">
    <p>Hotspawn is used <b>only</b> to enumerate which matches exist, together with their tournament,
       tier, points, start/lock times and the crowd's pick split. The crowd's pick split is shown for
       context and is <b>never</b> an input to a probability on this site.</p>
  </div>
"""

FLAGGED = """
  <h1 class="page-title">Flagged for review</h1>
  <p class="lede">Items that could not be fully verified from an official source. Nothing here is
     filled in or inferred &mdash; each entry states exactly what is missing and links to the
     official record behind it.</p>

  <h2 class="section">Standing irregularities</h2>
  <div class="note warn">
    <p><b>1. Tier is reported as "WAITING FOR INFORMATION" for most fixtures.</b> This is Hotspawn's
       own value, copied verbatim from their API. It is not a gap in our data &mdash; Hotspawn has
       not assigned a tier to those competitions. Affected rows show
       <span class="badge tier">TIER TBC</span>.</p>
    <p><b>2. No betting market exists for most of the board.</b> Pinnacle and Unibet together price
       roughly a dozen League of Legends fixtures a day, all World Championship / EMEA Masters. The
       remainder of the board is unpriced anywhere. This is a property of the market, not of the
       pipeline.</p>
    <p><b>3. Leaguepedia coverage of amateur/regional circuits is partial.</b> Where a team has no
       completed game in the last 420 days we cannot originate a line and the fixture is marked
       unresolved.</p>
    <p><b>4. Some match permalinks are reconstructed rather than server-verified.</b> The lobby HTML
       only renders permalinks for the fixtures currently on the board (195 of 264). The remaining
       URLs are built from Hotspawn's public slug pattern &mdash; a rule we validated by
       reconstructing <b>195 of 195</b> server-rendered permalinks exactly (including Unicode
       transliteration such as <code>Phong V&#361; Buffalo &rarr; phong-vu-buffalo</code>). Those
       reconstructed URLs are still marked <span class="badge unverified">unverified</span> because
       <code>www.hotspawn.com</code> returns HTTP 403 to the automation runner, so each one could not
       be individually confirmed with a live request. The fixture record behind every one of them is
       official either way.</p>
    <p><b>5. Some fixtures stay at status <code>scheduled</code> after their start time.</b> These are
       retained for completeness and flagged as stale, but their pick window has closed.</p>
  </div>

  <h2 class="section">Currently flagged items</h2>
  <div id="flagged-list"><p class="loading">Loading flagged items…</p></div>
"""

PAGES = [
    ("index.html", "Executive Summary — Hotspawn LoL Pick Desk",
     "Independent win probabilities for every League of Legends match on the Hotspawn Pick'em board.",
     INDEX),
    ("picks.html", "All Picks — Hotspawn LoL Pick Desk",
     "Every scheduled Hotspawn League of Legends Pick'em with team win probabilities and picks.",
     PICKS),
    ("markets.html", "Market Lines — Hotspawn LoL Pick Desk",
     "Hotspawn LoL Pick'ems priced by Pinnacle, Unibet and Polymarket.", MARKETS),
    ("model.html", "Originated Lines — Hotspawn LoL Pick Desk",
     "Hotspawn LoL Pick'ems priced by our own Leaguepedia Elo model where no betting market exists.",
     MODEL),
    ("unresolved.html", "Unresolved Picks & Limitations — Hotspawn LoL Pick Desk",
     "Hotspawn LoL Pick'ems we could not resolve, and exactly why.", UNRESOLVED),
    ("methodology.html", "Methodology — Hotspawn LoL Pick Desk",
     "How every Hotspawn LoL Pick'em probability on this site is produced.", METHODOLOGY),
    ("sources.html", "Sources & Verification — Hotspawn LoL Pick Desk",
     "Official sources behind every Hotspawn LoL Pick'em probability, and what was rejected.",
     SOURCES),
    ("flagged.html", "Flagged for Review — Hotspawn LoL Pick Desk",
     "Unverified and irregular Hotspawn LoL Pick'em data, with source links.", FLAGGED),
]


def main():
    for filename, title, desc, body in PAGES:
        path = os.path.join(ROOT, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(page(filename, title, desc, body))
        print("wrote", filename)
    print("done")


if __name__ == "__main__":
    main()
