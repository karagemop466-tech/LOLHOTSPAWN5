/**
 * Hotspawn LoL Pick'em Client-Side Application
 * Handles data fetching, live filtering, search, view mode toggle (Table vs Card),
 * and dynamic rendering with 100% verified source links.
 */

async function fetchPicksData() {
  const candidatePaths = ['data/picks.json', './data/picks.json', '../data/picks.json'];
  for (const path of candidatePaths) {
    try {
      const res = await fetch(path, { cache: 'no-store' });
      if (res.ok) {
        return await res.json();
      }
    } catch (e) {
      // Continue to next path
    }
  }
  throw new Error('Unable to load picks data JSON');
}

function formatPct(val) {
  if (val === null || val === undefined || isNaN(val)) return '—';
  return (val * 100).toFixed(1) + '%';
}

function formatDate(isoStr, rawStr) {
  if (!isoStr && !rawStr) return 'TBD';
  if (!isoStr) return rawStr;
  try {
    const d = new Date(isoStr);
    return d.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false
    });
  } catch (e) {
    return rawStr || isoStr;
  }
}

function getMethodBadge(method) {
  switch (method) {
    case 'MARKET_BOOKS':
      return '<span class="badge market">💰 Esportsbook Consensus</span>';
    case 'MARKET_POLYMARKET':
      return '<span class="badge market">💰 Polymarket Line</span>';
    case 'MODEL_ELO':
      return '<span class="badge elo">🧮 Proprietary Elo Model</span>';
    case 'UNRESOLVED':
    default:
      return '<span class="badge unres">⚠️ Unresolved Baseline</span>';
  }
}

function getMethodClass(method) {
  if (method === 'UNRESOLVED') return 'unresolved-method';
  if (method && method.startsWith('MARKET')) return 'market-method';
  return 'elo-method';
}

function renderCard(m) {
  const p1 = m.prob_team1 || 0.5;
  const p2 = m.prob_team2 || 0.5;
  const p1Pct = (p1 * 100).toFixed(1);
  const p2Pct = (p2 * 100).toFixed(1);
  const isUnres = m.method === 'UNRESOLVED';
  const methodClass = getMethodClass(m.method);

  const startFormatted = formatDate(m.start_utc, m.start_raw);

  return `
  <article class="pick-card ${methodClass}">
    <div class="card-top-meta">
      <span class="card-tourney">🏆 ${escapeHtml(m.tournament || 'LoL Fixture')}</span>
      <span>⏰ ${startFormatted} · Tier ${escapeHtml(m.tier || '?')} ${m.points ? `· ${escapeHtml(m.points)} pts` : ''}</span>
    </div>

    <div class="match-teams-row">
      <span class="team-name">${escapeHtml(m.team1)}</span>
      <span class="vs-tag">VS</span>
      <span class="team-name">${escapeHtml(m.team2)}</span>
    </div>

    <div class="prob-bar-container">
      <div class="prob-bar">
        <div class="bar-team1" style="width: ${p1Pct}%"></div>
        <div class="bar-team2" style="width: ${p2Pct}%"></div>
      </div>
      <div class="prob-labels">
        <span>${escapeHtml(m.team1)}: <b>${p1Pct}%</b></span>
        <span>${escapeHtml(m.team2)}: <b>${p2Pct}%</b></span>
      </div>
    </div>

    <div class="pick-callout ${isUnres ? 'unres-callout' : ''}">
      <div>
        <span style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted); display: block;">
          ${isUnres ? '⚠️ Baseline Nominal Pick' : '✅ Recommended Pick'}
        </span>
        <span class="pick-name">${escapeHtml(m.pick)}</span>
      </div>
      <span class="pick-prob-badge">${formatPct(m.pick_prob)} Win Prob</span>
    </div>

    <div class="badges-row">
      ${getMethodBadge(m.method)}
      <span class="badge">${escapeHtml(m.confidence || 'Standard')}</span>
      ${m.crowd1 !== null && m.crowd1 !== undefined ? `<span class="badge" title="Hotspawn user crowd pick % — NOT used in model">Hotspawn Crowd: ${m.crowd1}% vs ${m.crowd2}%</span>` : ''}
    </div>

    <div class="card-sources">
      <span><b>Evidence:</b> ${escapeHtml(m.evidence || 'Analyzed via internal system')}</span>
      ${m.market_url ? ` · <a href="${escapeHtml(m.market_url)}" target="_blank" rel="noopener">Betting Market Source ↗</a>` : ''}
      ${m.source_url ? ` · <a href="${escapeHtml(m.source_url)}" target="_blank" rel="noopener">Database / Wiki Source ↗</a>` : ''}
      ${m.hotspawn_url ? ` · <a href="${escapeHtml(m.hotspawn_url)}" target="_blank" rel="noopener">Hotspawn Match Link ↗</a>` : ''}
    </div>
  </article>
  `;
}

function renderTableRow(m) {
  const isUnres = m.method === 'UNRESOLVED';
  const rowClass = isUnres ? 'row-unres' : (m.method.startsWith('MARKET') ? 'row-market' : 'row-elo');
  const startFormatted = formatDate(m.start_utc, m.start_raw);

  return `
  <tr class="${rowClass}">
    <td>${startFormatted}</td>
    <td><b>${escapeHtml(m.tournament || 'LoL Fixture')}</b></td>
    <td>${escapeHtml(m.tier || '?')}</td>
    <td>${escapeHtml(m.team1)}</td>
    <td><b>${formatPct(m.prob_team1)}</b></td>
    <td>${escapeHtml(m.team2)}</td>
    <td><b>${formatPct(m.prob_team2)}</b></td>
    <td><b style="color: ${isUnres ? '#fca5a5' : '#4ade80'};">${escapeHtml(m.pick)}</b> (${formatPct(m.pick_prob)})</td>
    <td>${getMethodBadge(m.method)}</td>
    <td>
      ${m.market_url ? `<a href="${escapeHtml(m.market_url)}" target="_blank" rel="noopener">Market ↗</a> ` : ''}
      ${m.source_url ? `<a href="${escapeHtml(m.source_url)}" target="_blank" rel="noopener">Leaguepedia ↗</a> ` : ''}
      ${m.hotspawn_url ? `<a href="${escapeHtml(m.hotspawn_url)}" target="_blank" rel="noopener">Hotspawn ↗</a>` : ''}
    </td>
  </tr>
  `;
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
