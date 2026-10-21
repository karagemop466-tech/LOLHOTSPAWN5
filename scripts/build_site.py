#!/usr/bin/env python3
"""Render the static, mobile-first pick board from data/*.json."""
from __future__ import annotations

import html
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SITE = "https://karagemop466-tech.github.io/LOLHOTSPAWN5/"
REPO = "https://github.com/karagemop466-tech/LOLHOTSPAWN5"
NOW = datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def esc(s) -> str:
    return html.escape("" if s is None else str(s), quote=True)


def load(name):
    p = DATA / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def fmt_dt(iso: str | None) -> tuple[str, str]:
    if not iso:
        return ("TBD", "")
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return (iso, iso)
    return (dt.strftime("%a %d %b · %H:%M UTC"), dt.isoformat())


def pct(x) -> str:
    return "—" if x is None else f"{x * 100:.1f}%"


def dec(x) -> str:
    return "—" if x is None else f"{x:.2f}"


def rel(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return ""
    d = dt - NOW
    mins = int(d.total_seconds() // 60)
    if abs(mins) < 60:
        return f"in {mins} min" if mins >= 0 else f"{abs(mins)} min ago"
    hrs = mins // 60
    if abs(hrs) < 48:
        return f"in {hrs} h" if hrs >= 0 else f"{abs(hrs)} h ago"
    return f"in {hrs // 24} d" if hrs >= 0 else f"{abs(hrs) // 24} d ago"


CSS = (ROOT / "assets" / "site.css").read_text(encoding="utf-8") if (ROOT / "assets" / "site.css").exists() else ""


def page(title: str, desc: str, body: str, active: str = "", depth: int = 0) -> str:
    prefix = "../" * depth
    nav = [
        ("", "Summary"),
        ("picks/", "All picks"),
        ("unresolved/", "Unresolved"),
        ("methodology/", "Method"),
        ("sources/", "Sources"),
        ("review/", "Review"),
    ]
    links = "".join(
        f'<a class="navlink{" is-active" if active == href else ""}" href="{prefix}{href}">{label}</a>'
        for href, label in nav
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<meta name="theme-color" content="#12121c">
<link rel="icon" href="{prefix}assets/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="{prefix}assets/site.css">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:type" content="website">
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="site-head">
  <div class="head-inner">
    <a class="brand" href="{prefix}">
      <span class="brand-mark" aria-hidden="true">HS</span>
      <span class="brand-text"><b>LoL Pick Board</b><small>Hotspawn coverage · independent lines</small></span>
    </a>
    <div class="head-tools">
      <button id="tz" class="tzbtn" type="button" aria-pressed="false">Times: UTC</button>
    </div>
    <nav aria-label="Sections"><div class="navscroll">{links}</div></nav>
  </div>
</header>
<main id="main" class="wrap">
{body}
</main>
<footer class="site-foot">
  <div class="wrap">
    <p><b>Independent line generation.</b> Fixture list from Hotspawn Play.
    Market prices from public, citable exchange/bookmaker APIs. Hotspawn's crowd “% picked” is never used
    to set a probability.</p>
    <p class="tiny">Data {esc((load("meta.json") or {}).get("generated_utc", ""))} ·
    <a href="{prefix}methodology/">methodology</a> ·
    <a href="{prefix}sources/">source register</a> ·
    <a href="{prefix}review/">flagged for review</a> ·
    <a href="{REPO}">repository</a></p>
  </div>
</footer>
<script src="{prefix}assets/app.js" defer></script>
</body>
</html>"""


def conf_class(c: str | None) -> str:
    return {"high": "c-high", "medium": "c-med", "low": "c-low"}.get(c or "", "c-none")


def src_links(row, depth: int = 0) -> str:
    out = []
    for s in row.get("market_sources") or []:
        label = {"kalshi": "Kalshi", "pinnacle": "Pinnacle", "polymarket": "Polymarket"}.get(
            s["source"], s["label"])
        out.append(f'<a class="src-link" href="{esc(s["url"])}" rel="noopener">{esc(label)} line</a>')
    fx = row.get("hotspawn_url") or "https://play.hotspawn.com/lol-pickems"
    out.append(f'<a class="src-link" href="{esc(fx)}" rel="noopener">Hotspawn fixture</a>')
    if not row.get("market_sources"):
        out.append(f'<a class="src-link" href="{"../" * depth}methodology/">model inputs</a>')
    return "".join(out)


# --------------------------------------------------------------------------- #
# match card
# --------------------------------------------------------------------------- #
def match_card(r: dict, depth: int = 0) -> str:
    prefix = "../" * depth
    when, iso = fmt_dt(r.get("start_utc"))
    a, b = r["team_a"], r["team_b"]
    pa, pb = r.get("prob_a"), r.get("prob_b")
    picked = r.get("status") == "picked"
    pick = r.get("pick")
    conf = r.get("confidence")
    src = ((r.get("model") or {}).get("source") or "")
    basis = {"market": "Market line", "market+model": "Market + model",
             "model": "Results model" + (f" ({'Leaguepedia' if src == 'leaguepedia' else 'Hotspawn'} results)" if src else "")
             }.get(r.get("basis", ""), "—")
    if not picked:
        return f"""<article class="match is-unresolved" data-t="{esc(slug(r['competition']))}" data-q="{esc((a + ' ' + b + ' ' + r['competition']).lower())}">
  <div class="m-top"><time datetime="{esc(iso)}" data-utc="{esc(r.get('start_utc') or '')}">{esc(when)}</time>
    <span class="comp">{esc(r['competition'])}</span></div>
  <div class="m-teams"><div class="team"><span class="tname">{esc(a)}</span><span class="tpct muted">—</span></div>
    <div class="team"><span class="tname">{esc(b)}</span><span class="tpct muted">—</span></div></div>
  <div class="m-why"><span class="pill c-none">No pick</span> {esc(r.get('reason', ''))}</div>
  <div class="m-src"><a class="src-link" href="{esc(r.get('hotspawn_url'))}" rel="noopener">Hotspawn fixture</a>
    <a class="src-link" href="{prefix}unresolved/">Why no pick</a></div>
</article>"""
    aw = max(2.0, (pa or 0) * 100)
    bw = max(2.0, (pb or 0) * 100)
    return f"""<article class="match" data-t="{esc(slug(r['competition']))}" data-q="{esc((a + ' ' + b + ' ' + r['competition']).lower())}">
  <div class="m-top"><time datetime="{esc(iso)}" data-utc="{esc(r.get('start_utc') or '')}">{esc(when)}</time>
    <span class="comp">{esc(r['competition'])}</span>
    <span class="pill {conf_class(conf)}">{esc((conf or '').title())}</span></div>
  <div class="m-teams">
    <div class="team{' is-pick' if pick == a else ''}">
      <span class="tname">{esc(a)}{' <span class="pickmark">PICK</span>' if pick == a else ''}</span>
      <span class="tpct">{pct(pa)}</span>
      <span class="bar"><i style="width:{aw:.1f}%"></i></span>
    </div>
    <div class="team{' is-pick' if pick == b else ''}">
      <span class="tname">{esc(b)}{' <span class="pickmark">PICK</span>' if pick == b else ''}</span>
      <span class="tpct">{pct(pb)}</span>
      <span class="bar"><i style="width:{bw:.1f}%"></i></span>
    </div>
  </div>
  <div class="m-meta"><b>Pick: {esc(pick)}</b> <span class="sep">·</span> fair odds {dec(r.get('fair_decimal_a') if pick == a else r.get('fair_decimal_b'))}
    <span class="sep">·</span> {esc(basis)} <span class="sep">·</span> {esc(r.get('tier','')) if r.get('tier') not in ('waiting for information', None) else 'tier n/a'}</div>
  <div class="m-src">{src_links(r, depth)}</div>
</article>"""


# --------------------------------------------------------------------------- #
# pages
# --------------------------------------------------------------------------- #
def build_index(rows, meta):
    picked = [r for r in rows if r["status"] == "picked"]
    unresolved = [r for r in rows if r["status"] == "unresolved"]
    upcoming = sorted([r for r in picked if r.get("start_utc")], key=lambda r: r["start_utc"])
    soon = [r for r in upcoming if r["start_utc"] >= NOW.isoformat().replace("+00:00", "Z")][:6]
    if not soon:
        soon = upcoming[:6]
    c = meta["counts"]
    cov = c.get("coverage_upcoming_pct") or (c["picked"] / c["scheduled"] * 100 if c["scheduled"] else 0)
    stale = c.get("stale", 0)
    upcoming = c.get("upcoming", c["scheduled"] - stale)
    comps = Counter(r["competition"] for r in rows)
    comp_links = "".join(
        f'<a class="chiplink" href="picks/#{slug(x)}">{esc(x)} <span>{n}</span></a>'
        for x, n in sorted(comps.items(), key=lambda kv: (-kv[1], kv[0]))
    )
    stat = lambda v, l, cls="": f'<div class="stat {cls}"><b>{v}</b><span>{l}</span></div>'
    try:
        gen = datetime.fromisoformat(meta["generated_utc"].replace("Z", "+00:00"))
        nxt = gen.replace(minute=17, second=0, microsecond=0)
        while nxt <= NOW:
            nxt += timedelta(hours=6)
        next_run = nxt.strftime("%Y-%m-%d %H:%M")
    except Exception:  # noqa: BLE001
        next_run = "—"
    v = meta.get("verification") or {}
    if v.get("checked"):
        verif_text = (f"{v.get('agree')} of {v.get('checked')} completed matches that appear in both the "
                      f"Hotspawn and Leaguepedia feeds agree on the winner "
                      f"({v.get('agree', 0) / v['checked'] * 100:.1f}%); any disagreement is listed on "
                      '<a href="review/">review</a>.')
    else:
        verif_text = ('no unambiguous overlapping completed matches in the current window to compare; '
                      'the cross-check runs on every refresh.')
    body = f"""
<section class="hero">
  <div class="hero-copy">
    <p class="eyebrow">Executive summary · updated {esc(meta['generated_utc'][:16].replace('T',' '))} UTC</p>
    <h1>Every Hotspawn LoL pick&rsquo;em fixture — priced, or flagged with the reason.</h1>
    <p class="lede">We mirror the full League of Legends pick&rsquo;em list from Hotspawn Play ({c['scheduled']}
    fixtures right now), price each match from independent bookmaker, exchange and prediction-market data
    where it exists, and fall back to a results-only strength model where no market does. Anything we cannot
    defend is published as <b>unresolved</b> with the limitation instead of guessed.</p>
    <div class="cta">
      <a class="btn primary" href="picks/">See all {c['scheduled']} fixtures &amp; picks</a>
      <a class="btn" href="unresolved/">Unresolved ({c['unresolved']})</a>
    </div>
  </div>
</section>

<section class="stats" aria-label="Coverage at a glance">
  {stat(c['scheduled'], 'Hotspawn fixtures listed')}
  {stat(c['picked'], f'Picks generated ({cov:.0f}% of {upcoming} upcoming)', 'good')}
  {stat(c['market_backed'], 'Market-backed picks')}
  {stat(c['unresolved'], f'Unresolved ({stale} stale entries)', 'warn')}
</section>

<section class="card summary">
  <h2>What this board tells you</h2>
  <ul class="findings">
    <li><b>{c['picked']} of {upcoming} upcoming fixtures</b> carry a pick ({cov:.0f}%).
      <b>{c['market_backed']}</b> use a real external line (Kalshi exchange, Pinnacle, Polymarket);
      <b>{c['model_only']}</b> use our results-only Elo because no bookmaker prices that league.</li>
    <li><b>{c['unresolved']} fixtures are unresolved</b> — {stale} are stale Hotspawn entries whose start time
      has passed but which Hotspawn still lists as scheduled, and the rest lack enough verified match history.
      Every one is listed with its exact reason and what would fix it.
      <a href="unresolved/">Open the unresolved list</a>.</li>
    <li><b>Hotspawn&rsquo;s crowd percentages are never used.</b> Our probabilities come from de-vigged
      external market prices and from completed-match results only. <a href="methodology/">How the numbers are built</a>.</li>
    <li><b>Results cross-check:</b> {verif_text}</li>
    <li><b>Refresh cadence:</b> the collector runs every 6 hours via GitHub Actions
      (<code>17 */6 * * *</code>). Last successful run {esc(meta['generated_utc'][:16].replace('T',' '))} UTC;
      next scheduled run {next_run} UTC. <a href="sources/">Source register &amp; status</a>.</li>
    <li><b>Limitations:</b> licensed books price only the top leagues and international events. Low-tier
      national leagues have no market anywhere we could verify, so those probabilities are model-derived and
      marked <i>low</i> confidence. <a href="review/">Flagged for review</a>.</li>
  </ul>
</section>

<section class="quick">
  <h2>Find picks fast</h2>
  <div class="cards">
    <a class="qcard" href="picks/"><b>All picks</b><span>Full table, filter by tournament or team, phone-first.</span></a>
    <a class="qcard" href="picks/#worlds-2026-main-event"><b>Worlds 2026</b><span>Main-event fixtures with exchange lines.</span></a>
    <a class="qcard" href="unresolved/"><b>Unresolved</b><span>No pick + the reason + what would resolve it.</span></a>
    <a class="qcard" href="methodology/"><b>Method</b><span>De-vig, Elo, shrinkage, confidence tiers.</span></a>
  </div>
</section>

<section class="card">
  <div class="sechead"><h2>Next up</h2><a class="more" href="picks/">All fixtures →</a></div>
  <div class="matchlist">{''.join(match_card(r) for r in soon)}</div>
</section>

<section class="card">
  <h2>Browse by tournament</h2>
  <p class="muted small">{len(comps)} competitions in the current Hotspawn list. Tap a competition to jump
  straight to its section on the picks page.</p>
  <div class="chipwrap">{comp_links}</div>
</section>

<section class="card">
  <h2>How coverage is split</h2>
  <div class="split">
    <div><b>{c['market_backed']}</b><span>market-backed</span></div>
    <div><b>{c['model_only']}</b><span>model-only</span></div>
    <div><b>{c['unresolved']}</b><span>unresolved</span></div>
  </div>
  <p class="muted small">Unresolved fixtures stay visible on the site and on the
  <a href="review/">flagged page</a> until a source appears. Nothing is filled in by hand.</p>
</section>
"""
    return page("Hotspawn LoL Pick Board — every fixture, our own line",
                "Executive summary, coverage and links to every Hotspawn League of Legends pick'em pick.",
                body, active="", depth=0)


def build_picks(rows, meta):
    comps = defaultdict(list)
    for r in rows:
        comps[r["competition"]].append(r)
    order = sorted(comps.items(), key=lambda kv: (min(x.get("start_utc") or "" for x in kv[1]), kv[0]))
    chips = '<button class="chip is-on" data-filter="all">All <span>%d</span></button>' % len(rows)
    chips += "".join(
        f'<button class="chip" data-filter="{esc(slug(name))}">{esc(name)} <span>{len(v)}</span></button>'
        for name, v in sorted(comps.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    )
    sections = []
    for name, rs in order:
        rs.sort(key=lambda r: (r.get("start_utc") or "", r["team_a"]))
        sections.append(f"""<section class="compblock" id="{esc(slug(name))}" data-t="{esc(slug(name))}">
  <h2 class="comph">{esc(name)} <span class="count">{len(rs)}</span></h2>
  <div class="matchlist">{''.join(match_card(r, depth=1) for r in rs)}</div>
</section>""")
    body = f"""
<div class="pagehead">
  <h1>All Hotspawn LoL fixtures</h1>
  <p class="lede">Every fixture currently listed on Hotspawn&rsquo;s League of Legends pick&rsquo;em lobby,
  {esc(meta['generated_utc'][:16].replace('T',' '))} UTC. Probabilities are ours; the input for each row is
  shown under the pick.</p>
</div>
<div class="toolbar">
  <label class="search"><span class="sr">Search team or tournament</span>
    <input id="q" type="search" placeholder="Search team or tournament…" autocomplete="off"></label>
  <div class="chipline" id="chips">{chips}</div>
  <p class="muted small" id="count" aria-live="polite">{len(rows)} fixtures shown</p>
</div>
{''.join(sections)}
<p class="muted small endnote">Jump back to the <a href="../">executive summary</a> or see
<a href="../unresolved/">which fixtures have no pick</a>.</p>
"""
    return page("All picks — Hotspawn LoL Pick Board",
                "Full mobile-friendly table of Hotspawn League of Legends fixtures with our win probabilities.",
                body, active="picks/", depth=1)


def build_unresolved(rows, meta):
    un = [r for r in rows if r["status"] == "unresolved"]
    cats = defaultdict(list)
    for r in un:
        reason = r.get("reason", "")
        if "start time has already passed" in reason:
            key = "Stale Hotspawn entry (start time passed)"
        elif "TBD" in reason:
            key = "Teams not announced"
        elif "fewer than 3" in reason:
            key = "Too little verified match history"
        elif "No bookmaker" in reason:
            key = "No external line and no match history"
        else:
            key = "Other"
        cats[key].append(r)
    blocks = []
    for key in sorted(cats, key=lambda k: -len(cats[k])):
        rs = sorted(cats[key], key=lambda r: r.get("start_utc") or "")
        items = "".join(
            f"""<tr><td data-l="Start"><time datetime="{esc(r.get('start_utc') or '')}">{esc(fmt_dt(r.get('start_utc'))[0])}</time></td>
<td data-l="Fixture"><b>{esc(r['team_a'])}</b> vs <b>{esc(r['team_b'])}</b><br><span class="muted small">{esc(r['competition'])}</span></td>
<td data-l="Why no pick">{esc(r.get('reason',''))}<br><span class="muted small">{esc(r.get('remedy',''))}</span></td>
<td data-l="Source"><a class="src-link" href="{esc(r.get('hotspawn_url'))}" rel="noopener">Hotspawn</a></td></tr>"""
            for r in rs)
        blocks.append(f"""<section class="card">
  <div class="sechead"><h2>{esc(key)} <span class="count">{len(rs)}</span></h2></div>
  <div class="tablewrap"><table class="grid">
    <thead><tr><th>Start</th><th>Fixture</th><th>Why no pick / what would fix it</th><th>Source</th></tr></thead>
    <tbody>{items}</tbody></table></div>
</section>""")
    body = f"""
<div class="pagehead">
  <h1>Unresolved picks</h1>
  <p class="lede">These Hotspawn fixtures deliberately have <b>no pick</b>. Each row states the limitation
  and what would resolve it. This section is part of the executive summary: it is the honest edge of our
  coverage, not a silent gap.</p>
</div>
<div class="stats smallstats">
  <div class="stat warn"><b>{len(un)}</b><span>unresolved fixtures</span></div>
  <div class="stat"><b>{meta['counts'].get('picked', 0)}</b><span>fixtures with a pick</span></div>
  <div class="stat"><b>{meta['counts'].get('upcoming', meta['counts']['scheduled'])}</b><span>upcoming fixtures</span></div>
  <div class="stat"><b>{meta['counts'].get('stale', 0)}</b><span>stale Hotspawn entries</span></div>
</div>
<div class="callout"><b>Why this happens.</b> Licensed bookmakers publish League of Legends prices almost
exclusively for tier-1 leagues and international events. National third divisions, regional cups and
promotion brackets have no market we could verify, and many of their teams have too few completed matches in
publicly accessible data for a defensible rating. We do not invent a number to fill the gap.
<a href="../methodology/#limits">Full limitations</a> · <a href="../review/">Flagged for review</a></div>
{''.join(blocks) if blocks else '<p class="muted">Nothing unresolved right now.</p>'}
"""
    return page("Unresolved picks and limitations — Hotspawn LoL",
                "Fixtures without a pick, the exact reason, and what would resolve them.",
                body, active="unresolved/", depth=1)


def build_methodology(meta):
    body = f"""
<div class="pagehead">
  <h1>Methodology</h1>
  <p class="lede">How a fixture becomes a probability. Every step is deterministic and reproducible from
  the committed scripts and the public sources listed on the <a href="../sources/">source register</a>.</p>
</div>

<section class="card">
  <h2>1. Fixture inventory</h2>
  <p>We read the same public fixtures feed that powers
  <a href="https://play.hotspawn.com/lol-pickems" rel="noopener">play.hotspawn.com/lol-pickems</a>:
  <code>GET /api/v1/fixtures?sport_alias=lol&amp;tenantId=1</code>. The current snapshot contains
  <b>{meta['hotspawn']['scheduled']}</b> fixtures with status <code>scheduled</code> and
  <b>{meta['hotspawn']['ended_in_reference']}</b> completed fixtures used as the results reference.
  Team names, competition, tier, start time and fixture id are taken verbatim; nothing is renamed.
  Where the server-rendered lobby exposes a match permalink we attach it, otherwise the row links the lobby.</p>
</section>

<section class="card">
  <h2>2. Market prices (primary signal)</h2>
  <p>For each fixture we look for an external, timestamped price:</p>
  <ul>
    <li><b>Kalshi</b> — CFTC-regulated event exchange, series <code>KXLOLGAME</code>. We take the
      mid-point of the yes bid/ask for both outcomes and normalise the pair to 100%.</li>
    <li><b>Pinnacle</b> — licensed bookmaker, esports moneyline. American prices are converted to decimal,
      implied probabilities are computed as <code>1/decimal</code>, then normalised
      (proportional de-vig): <code>p_i = (1/o_i) / Σ(1/o_j)</code>.</li>
    <li><b>Polymarket</b> — prediction market, “Match Winner” market only; outcome prices are normalised.</li>
  </ul>
  <p>A quote is attached only when <b>both</b> team names match after normalisation and the quote starts
  within 36 hours of the Hotspawn fixture. No fuzzy matching, no manual overrides.</p>
  <p class="formula">When several venues quote the same match we blend them:
  <code>p_market = Σ(w·p) / Σw</code> with w = 0.5 Pinnacle, 0.4 Kalshi, 0.3 Polymarket.</p>
</section>

<section class="card">
  <h2>3. Results model (fallback for unpriced leagues)</h2>
  <p>A standard Elo run over completed fixtures, ordered by date:</p>
  <pre class="code">expected = 1 / (1 + 10^((R_b - R_a)/400))
R' = R + K · recency · (score - expected)
K = 32 (S) · 28 (A) · 24 (B) · 20 (C) · 16 (D / unknown)
recency = 0.5 ^ (age_in_days / 180)</pre>
  <p>Ratings start at 1500. Because a team with two matches must not look as certain as a team with
  twenty, ratings are shrunk toward the mean before conversion:
  <code>R_shrunk = 1500 + (R - 1500) · n/(n+8)</code>.</p>
  <p>Series length: if Hotspawn publishes <code>best_of</code>, the single-game probability is expanded to a
  series probability; otherwise the fixture is treated as a single game.</p>
  <p><b>Which ratings are used.</b> Two independent Elo pools are maintained: one from the Leaguepedia
  CargoExport match archive (preferred, independent of Hotspawn) and one from completed Hotspawn fixtures
  (fallback for competitions Leaguepedia does not carry). A match uses the Leaguepedia pool when both teams
  have at least three completed matches there, otherwise the Hotspawn pool, otherwise it is unresolved.
  The pool used is shown on every pick row.</p>
  <p><b>Minimum evidence.</b> A model pick is only published when <b>both</b> teams have at least
  3 completed fixtures in the reference set. Otherwise the match is unresolved.</p>
</section>

<section class="card">
  <h2>4. Final probability and confidence</h2>
  <table class="grid">
    <thead><tr><th>Situation</th><th>Probability</th><th>Confidence label</th></tr></thead>
    <tbody>
      <tr><td data-l="Situation">Market + model agree</td><td data-l="Probability"><code>0.75·p_market + 0.25·p_model</code></td><td data-l="Confidence">High</td></tr>
      <tr><td data-l="Situation">Market only</td><td data-l="Probability"><code>p_market</code></td><td data-l="Confidence">High</td></tr>
      <tr><td data-l="Situation">Model, both teams ≥ 8 fixtures</td><td data-l="Probability"><code>p_model</code></td><td data-l="Confidence">Medium</td></tr>
      <tr><td data-l="Situation">Model, 3–7 fixtures</td><td data-l="Probability"><code>p_model</code></td><td data-l="Confidence">Low</td></tr>
      <tr><td data-l="Situation">Anything less</td><td data-l="Probability">not published</td><td data-l="Confidence">Unresolved</td></tr>
    </tbody>
  </table>
  <p>Probabilities are floored at 2% and capped at 98%. Fair odds are <code>1/p</code>; they are our line,
  not a quote copied from a book.</p>
</section>

<section class="card" id="limits">
  <h2>5. Known limitations (also on the review page)</h2>
  <ul>
    <li>Bookmaker coverage of national third divisions, regional cups and promotion brackets is effectively
      zero; those rows cannot have a market-derived line.</li>
    <li>Elo is only as good as the results reference. If a team changed roster, the rating lags reality.</li>
    <li>Cross-league comparisons are weak by construction: a Tunisian and a German third-division team never
      share opponents. Ratings are interpretable inside a competition, which is where they are used.</li>
    <li>Some Hotspawn fixtures stay <code>scheduled</code> long after their start time. They are excluded and
      flagged rather than priced.</li>
    <li>Markets move. Every quote carries its retrieval time; a row is only as fresh as the last pipeline run
      (every 6 hours).</li>
  </ul>
</section>

<section class="card">
  <h2>6. What we deliberately do not do</h2>
  <ul>
    <li>We do not use Hotspawn&rsquo;s crowd “% picked”, tiers or points as a probability input.</li>
    <li>We do not infer a missing result, roster or price.</li>
    <li>We do not carry a value forward from a previous run without a timestamp.</li>
  </ul>
</section>
"""
    return page("Methodology — Hotspawn LoL Pick Board",
                "De-vigging, Elo, shrinkage, confidence tiers and limitations.",
                body, active="methodology/", depth=1)


def build_sources(meta):
    s = meta["sources"]
    ok = lambda b: '<span class="pill c-high">live</span>' if b else '<span class="pill c-none">unavailable</span>'
    rows = [
        ("Hotspawn Play — LoL pick&rsquo;em lobby", "Fixture inventory (official)",
         "https://play.hotspawn.com/lol-pickems", ok(meta["hotspawn"]["ok"]),
         f"{meta['hotspawn']['scheduled']} scheduled fixtures"),
        ("Hotspawn fixtures API", "Fixture inventory (public JSON API)",
         "https://phpstack-1372681-6459848.cloudwaysapps.com/api/v1/fixtures?sport_alias=lol&amp;tenantId=1",
         ok(meta["hotspawn"]["ok"]), "same ids as the lobby"),
        ("Hotspawn match pages", "Permalinks (SSR lobby)",
         "https://www.hotspawn.com/matches/", ok(meta.get("hotspawn_links", {}).get("ok")),
         f"{meta.get('hotspawn_links', {}).get('verified_links', 0)} verified links"),
        ("Kalshi — KXLOLGAME series", "Exchange prices (market signal)",
         "https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXLOLGAME&amp;status=open",
         ok(s["kalshi"]["ok"]), f"{s['kalshi']['quotes']} two-way quotes this run"),
        ("Pinnacle — esports moneyline", "Bookmaker prices (market signal)",
         "https://guest.api.arcadia.pinnacle.com/0.1/sports/12/matchups", ok(s["pinnacle"]["ok"]),
         f"{s['pinnacle']['quotes']} quotes; leagues: {', '.join(s['pinnacle'].get('leagues') or []) or 'none'}"),
        ("Polymarket — LoL events", "Prediction-market prices (market signal)",
         "https://gamma-api.polymarket.com/events?tag_slug=league-of-legends&amp;closed=false",
         ok(s["polymarket"]["ok"]), f"{s['polymarket']['quotes']} future match markets"),
        ("Leaguepedia — CargoExport", "Independent results reference (Elo)",
         "https://lol.fandom.com/wiki/Special:CargoExport", ok(meta["model"]["leaguepedia"]["ok"]),
         f"{meta['model']['leaguepedia']['matches']} completed matches, {meta['model']['leaguepedia']['teams_rated']} teams"),
        ("Hotspawn completed fixtures", "Fallback results reference for the Elo model",
         "https://phpstack-1372681-6459848.cloudwaysapps.com/api/v1/fixtures?sport_alias=lol&amp;tenantId=1",
         ok(meta["hotspawn"]["ok"]), f"{meta['model']['history_matches']} completed fixtures, {meta['model']['teams_rated']} teams"),
    ]
    trs = "".join(
        f"<tr><td data-l='Source'><b>{n}</b></td><td data-l='Type'>{t}</td><td data-l='Use'>{url}</td>"
        f"<td data-l='Status'>{st}<br><span class='muted small'>{d}</span></td>"
        f"<td data-l='Link'><a class='src-link' href='{url}' rel='noopener'>official</a></td></tr>"
        for n, t, url, st, d in rows
    )
    body = f"""
<div class="pagehead">
  <h1>Source register</h1>
  <p class="lede">Every input used by the pipeline, with the public endpoint it is read from. Status is
  written by the most recent run, not by hand.</p>
</div>
<section class="card">
  <div class="tablewrap"><table class="grid">
    <thead><tr><th>Source</th><th>Type</th><th>What it is used for</th><th>Last run</th><th>Link</th></tr></thead>
    <tbody>{trs}</tbody>
  </table></div>
</section>
<section class="card">
  <h2>Venues checked during source research</h2>
  <p class="muted small">Reproducible with <code>scripts/probe*.sh</code> from GitHub Actions on
  2026-10-21 (UTC). A venue is only used if it returns machine-readable prices without authentication.</p>
  <div class="tablewrap"><table class="grid">
    <thead><tr><th>Venue</th><th>What was tested</th><th>Result</th><th>Used?</th></tr></thead>
    <tbody>
      <tr><td data-l="Venue">Pinnacle</td><td data-l="Tested">Guest esports API, LoL moneylines</td><td data-l="Result">200, 2 LoL leagues priced</td><td data-l="Used">Yes</td></tr>
      <tr><td data-l="Venue">Kalshi</td><td data-l="Tested">KXLOLGAME series, per-game markets</td><td data-l="Result">200, two-way bid/ask</td><td data-l="Used">Yes</td></tr>
      <tr><td data-l="Venue">Polymarket</td><td data-l="Tested">Gamma events, Match Winner markets</td><td data-l="Result">200, no open future LoL match market</td><td data-l="Used">Collector on, 0 quotes</td></tr>
      <tr><td data-l="Venue">OddsPortal</td><td data-l="Tested">LoL odds hub</td><td data-l="Result">200 HTML, no public data API; only 2 league links rendered</td><td data-l="Used">No (no stable public feed)</td></tr>
      <tr><td data-l="Venue">BetExplorer</td><td data-l="Tested">/esports/league-of-legends/</td><td data-l="Result">404</td><td data-l="Used">No</td></tr>
      <tr><td data-l="Venue">EGamersWorld</td><td data-l="Tested">LoL matches</td><td data-l="Result">403</td><td data-l="Used">No (blocked)</td></tr>
      <tr><td data-l="Venue">Thunderpick / GG.BET / BetOnline / EsportsBets / Fanatics</td><td data-l="Tested">LoL esports lobbies</td><td data-l="Result">403</td><td data-l="Used">No (bot-protected)</td></tr>
      <tr><td data-l="Venue">DraftKings</td><td data-l="Tested">LoL esports</td><td data-l="Result">404 on the LoL path</td><td data-l="Used">No</td></tr>
      <tr><td data-l="Venue">Bovada / Midnite / Unikrn</td><td data-l="Tested">LoL pages</td><td data-l="Result">200 HTML shell, no stable public JSON</td><td data-l="Used">No</td></tr>
      <tr><td data-l="Venue">bo3.gg</td><td data-l="Tested">API filters for LoL</td><td data-l="Result">200 but filters ignored (CS2 returned)</td><td data-l="Used">No</td></tr>
      <tr><td data-l="Venue">Leaguepedia</td><td data-l="Tested">api.php + Special:CargoExport</td><td data-l="Result">api.php rate-limited; CargoExport 200</td><td data-l="Used">CargoExport (results)</td></tr>
      <tr><td data-l="Venue">Liquipedia</td><td data-l="Tested">API + article HTML</td><td data-l="Result">406 / 403</td><td data-l="Used">No (blocked)</td></tr>
      <tr><td data-l="Venue">gol.gg</td><td data-l="Tested">Tournament list</td><td data-l="Result">200, tier-1 tournaments only</td><td data-l="Used">No</td></tr>
    </tbody>
  </table></div>
</section>

<section class="card">
  <h2>Access notes</h2>
  <ul>
    <li>All endpoints above are public and unauthenticated; the pipeline sends an identifying user agent and
      rate-limits itself.</li>
    <li><b>Not used:</b> Hotspawn crowd pick percentages, Hotspawn tiers/points, any third-party prediction
      article, or any screen-scraped bookmaker page that forbids automated access.</li>
    <li>Leaguepedia/Fandom was evaluated for results history but returned
      <code>ratelimited</code> from CI, and Liquipedia returned HTTP 403/406 for automated access, so neither
      is used as a live input. This is recorded on the <a href="../review/">review page</a>.</li>
  </ul>
</section>
"""
    return page("Source register — Hotspawn LoL Pick Board",
                "Public endpoints behind every number on the board.",
                body, active="sources/", depth=1)


def build_review(rows, meta):
    un = [r for r in rows if r["status"] == "unresolved"]
    stale = [r for r in un if "start time has already passed" in (r.get("reason") or "")]
    thin = [r for r in un if "fewer than 3" in (r.get("reason") or "")]
    noline = [r for r in un if "No bookmaker" in (r.get("reason") or "") and r not in thin and r not in stale]
    tbd = [r for r in un if "TBD" in (r.get("reason") or "")]
    disagreement_rows = "".join(
        f"<tr><td data-l='Fixture'>{esc(d['fixture'])}</td><td data-l='Start'>{esc(d['start_utc'][:16].replace('T',' '))}</td>"
        f"<td data-l='Hotspawn winner'>{esc(d['hotspawn_winner'])}</td>"
        f"<td data-l='Leaguepedia winner'>{esc(d['leaguepedia_winner'])}</td>"
        f"<td data-l='Sources'><a class='src-link' href='https://play.hotspawn.com/lol-pickems' rel='noopener'>Hotspawn</a>"
        f"<a class='src-link' href='https://lol.fandom.com/wiki/Special:CargoExport' rel='noopener'>Leaguepedia</a></td></tr>"
        for d in (meta.get('verification') or {}).get('disagreements', [])
    )
    unresolved_rows = "".join(
        f"<tr><td data-l='Item'>{esc(t)}</td><td data-l='Detail'>{esc(d)}</td><td data-l='Status'>"
        f"<span class='pill c-low'>open</span></td><td data-l='Source'>{s}</td></tr>"
        for t, d, s in [
            ("Hotspawn list vs API",
             f"The lobby renders 195 match cards while the fixtures API returns {meta['hotspawn']['scheduled']} "
             "scheduled fixtures. We publish the API superset so nothing is silently dropped; the 69 extra "
             "fixtures have no rendered permalink and link to the lobby instead.",
             '<a class="src-link" href="https://play.hotspawn.com/lol-pickems" rel="noopener">lobby</a>'),
            ("Stale fixtures", f"{len(stale)} fixtures are still 'scheduled' although their start time passed. "
             "They are excluded from picks and listed as unresolved.", '<a class="src-link" href="../unresolved/">list</a>'),
            ("No external line", f"{len(noline) + len(thin)} fixtures have no market quote from any venue we can "
             "cite. Model-only rows are marked low/medium confidence; the rest are unresolved.", '<a class="src-link" href="https://guest.api.arcadia.pinnacle.com/0.1/sports/12/leagues" rel="noopener">Pinnacle board</a>'),
            ("Thin history", f"{len(thin)} fixtures involve a team with fewer than three completed fixtures in "
             "the reference set.", '<a class="src-link" href="../methodology/">method</a>'),
            ("Teams not announced", f"{len(tbd)} fixtures list TBD participants on Hotspawn.", '<a class="src-link" href="https://play.hotspawn.com/lol-pickems" rel="noopener">lobby</a>'),
            ("Results reference source", "The Elo model uses completed-fixture scores from the Hotspawn fixtures "
             "feed because Leaguepedia (ratelimited) and Liquipedia (403/406) block automated access from CI. "
             "Hotspawn crowd percentages are never read by the model.", '<a class="src-link" href="../sources/">sources</a>'),
            ("Results cross-check", f"{meta.get('verification',{}).get('agree','—')} of "
             f"{meta.get('verification',{}).get('checked','—')} overlapping completed matches agree between "
             "Hotspawn and Leaguepedia. Disagreements are listed below when they occur.",
             '<a class="src-link" href="../sources/">sources</a>'),
            ("Name collisions", "Ambiguous short names exist in the pool (e.g. T1 vs SYR T1, LØS vs LOS). "
             "Joins require exact normalised names plus a 36-hour time window, so a collision can only drop a "
             "quote, never attach a wrong one.", '<a class="src-link" href="../methodology/">join rule</a>'),
            ("Polymarket coverage", "No future LoL match markets were open at the last run, so Polymarket "
             "contributed 0 quotes. The collector stays enabled for when they reopen.", '<a class="src-link" href="https://gamma-api.polymarket.com/events?tag_slug=league-of-legends&amp;closed=false" rel="noopener">API</a>'),
            ("Pinnacle coverage", "Pinnacle listed only World Championship and EMEA Masters on its esports "
             "board at the last run; every lower-tier league had no price.", '<a class="src-link" href="https://guest.api.arcadia.pinnacle.com/0.1/sports/12/leagues" rel="noopener">API</a>'),
        ]
    )
    body = f"""
<div class="pagehead">
  <h1>Flagged for review</h1>
  <p class="lede">Irregularities, unverified items and access limits found while building this board.
  Nothing here blocks publication; it is the audit trail for a human to check.</p>
</div>
<div class="callout"><b>Rule in force:</b> a value that cannot be confirmed from a public source is left blank
and flagged here rather than inferred.</div>
<section class="card">
  <div class="tablewrap"><table class="grid">
    <thead><tr><th>Item</th><th>Detail</th><th>Status</th><th>Source</th></tr></thead>
    <tbody>{unresolved_rows}</tbody>
  </table></div>
</section>
<section class="card">
  <h2>Results cross-check disagreements</h2>
  <p class="muted small">Same fixture, same date window, different winner between the Hotspawn results feed and
  Leaguepedia. Both links are given; we do not silently pick one. The Elo model prefers Leaguepedia, and these
  rows are listed so the discrepancy can be checked by hand.</p>
  <div class="tablewrap"><table class="grid">
    <thead><tr><th>Fixture</th><th>Start (UTC)</th><th>Hotspawn winner</th><th>Leaguepedia winner</th><th>Sources</th></tr></thead>
    <tbody>{disagreement_rows or '<tr><td data-l="Status" colspan="5">No disagreements in the current window.</td></tr>'}</tbody>
  </table></div>
</section>

<section class="card">
  <h2>Rows without a third-party price</h2>
  <p class="muted">Model-only rows are not “unverified values”: they are computed, reproducible estimates.
  They are listed here because no external venue confirms them.</p>
  <div class="tablewrap"><table class="grid">
    <thead><tr><th>Fixture</th><th>Competition</th><th>Confidence</th><th>Model sample</th></tr></thead>
    <tbody>{''.join(
        f"<tr><td data-l='Fixture'>{esc(r['team_a'])} vs {esc(r['team_b'])}</td><td data-l='Competition'>{esc(r['competition'])}</td>"
        f"<td data-l='Confidence'><span class='pill {conf_class(r.get('confidence'))}'>{esc((r.get('confidence') or '').title())}</span></td>"
        f"<td data-l='Sample'>{(r.get('model') or {}).get('games_a','—')} / {(r.get('model') or {}).get('games_b','—')}</td></tr>"
        for r in rows if r['status'] == 'picked' and r.get('basis') == 'model')}</tbody>
  </table></div>
</section>
"""
    return page("Flagged for review — Hotspawn LoL Pick Board",
                "Irregularities and unverified items, with source links.",
                body, active="review/", depth=1)


def build_404():
    body = """
<div class="pagehead"><h1>Page not found</h1>
<p class="lede">The fixture or page you asked for is not on the board.</p>
<div class="cta"><a class="btn primary" href="/LOLHOTSPAWN5/">Executive summary</a>
<a class="btn" href="/LOLHOTSPAWN5/picks/">All picks</a></div></div>
"""
    return page("Not found — Hotspawn LoL Pick Board", "Page not found.", body, depth=0)


def main():
    meta = load("meta.json")
    picks = load("picks.json")
    if not meta or not picks:
        raise SystemExit("run scripts/pipeline.py first")
    rows = picks["rows"]
    (ROOT / "index.html").write_text(build_index(rows, meta), encoding="utf-8")
    for folder, fn in [("picks", build_picks), ("unresolved", build_unresolved),
                       ("methodology", lambda r, m: build_methodology(m)),
                       ("sources", lambda r, m: build_sources(m)),
                       ("review", build_review)]:
        d = ROOT / folder
        d.mkdir(exist_ok=True)
        (d / "index.html").write_text(fn(rows, meta), encoding="utf-8")
    (ROOT / "404.html").write_text(build_404(), encoding="utf-8")
    urls = ["", "picks/", "unresolved/", "methodology/", "sources/", "review/"]
    (ROOT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"<url><loc>{SITE}{u}</loc></url>\n" for u in urls) + "</urlset>\n",
        encoding="utf-8")
    (ROOT / ".nojekyll").write_text("", encoding="utf-8")
    print("site built:", meta["counts"])


if __name__ == "__main__":
    main()
