(() => {
  const DATA_URL = new URL('data/matches.json', document.baseURI);
  const date = (value) => {
    if (!value) return 'Start time not confirmed';
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return String(value);
    return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short', timeZone: 'UTC' }).format(parsed) + ' UTC';
  };
  const safeUrl = (value) => {
    try { const u = new URL(value, document.baseURI); return ['http:', 'https:'].includes(u.protocol) ? u.href : ''; }
    catch { return ''; }
  };
  const el = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  };
  function sourceAnchor(url, label) {
    const href = safeUrl(url);
    if (!href) return document.createTextNode('Source link unavailable');
    const a = el('a', '', label || 'External source');
    a.href = href; a.target = '_blank'; a.rel = 'noopener noreferrer';
    return a;
  }
  function fillEmpty(tbody, message, columns = 4) {
    const tr = document.createElement('tr'); const td = el('td', 'empty-state', message);
    td.colSpan = columns; tr.append(td); tbody.replaceChildren(tr);
  }
  function makeMatchName(match) {
    const td = document.createElement('td');
    const title = el('span', 'match-title', `${match.team_a || 'Team not confirmed'} vs ${match.team_b || 'Team not confirmed'}`);
    td.append(title);
    if (match.tournament) td.append(el('span', 'match-meta', match.tournament));
    td.append(el('span', 'match-meta', date(match.start_time_utc)));
    if (match.format) td.append(el('span', 'match-meta', match.format));
    return td;
  }
  function renderPriced(matches) {
    const tbody = document.querySelector('#priced-matches');
    if (!matches.length) { fillEmpty(tbody, 'No verified external match-winner lines are available in this snapshot. Listed matches without lines appear in the unresolved section below.'); return; }
    const rows = matches.map((match) => {
      const tr = document.createElement('tr'); tr.dataset.search = `${match.team_a || ''} ${match.team_b || ''} ${match.tournament || ''}`.toLowerCase();
      tr.append(makeMatchName(match));
      const prob = document.createElement('td'); prob.className = 'probability';
      prob.append(el('span', 'prob-chip', `${match.probability_a}%`), el('span', 'prob-vs', 'vs'), el('span', 'prob-chip', `${match.probability_b}%`));
      tr.append(prob);
      const pick = document.createElement('td'); pick.append(el('span', 'pick-label', match.pick || 'Not resolved'));
      tr.append(pick);
      const source = document.createElement('td'); source.className = 'source-cell';
      const books = Array.isArray(match.bookmaker_sources) && match.bookmaker_sources.length ? match.bookmaker_sources : [{name: match.odds_source_name || 'Odds source', url: match.odds_source_url}];
      books.forEach((book, index) => { if (index) source.append(document.createTextNode(' · ')); source.append(sourceAnchor(book.url, book.name)); });
      source.append(el('small', '', `Captured ${match.odds_fetched_at ? date(match.odds_fetched_at) : 'time not available'}`));
      if (match.odds_provider_url) { source.append(sourceAnchor(match.odds_provider_url, 'Odds data provider')); }
      if (match.hotspawn_url) { source.append(document.createTextNode(' · '), sourceAnchor(match.hotspawn_url, 'Hotspawn match')); }
      tr.append(source); return tr;
    });
    tbody.replaceChildren(...rows);
  }
  function renderUnresolved(matches) {
    const tbody = document.querySelector('#unresolved-matches');
    if (!matches.length) { fillEmpty(tbody, 'No unpriced matches in this snapshot. This does not imply complete line coverage; see the source-status note.'); return; }
    const rows = matches.map((match) => {
      const tr = document.createElement('tr'); tr.dataset.search = `${match.team_a || ''} ${match.team_b || ''} ${match.tournament || ''}`.toLowerCase();
      tr.append(makeMatchName(match));
      const prob = document.createElement('td'); prob.append(el('span', 'badge', 'No verified line')); tr.append(prob);
      const reason = document.createElement('td'); reason.textContent = match.unresolved_reason || 'No external line verified'; tr.append(reason);
      const source = document.createElement('td'); source.className = 'source-cell';
      source.append(sourceAnchor(match.hotspawn_url || match.hotspawn_lobby_url, 'Hotspawn listing'));
      if (match.odds_search_url) { source.append(document.createTextNode(' · '), sourceAnchor(match.odds_search_url, 'Market lookup')); }
      tr.append(source); return tr;
    });
    tbody.replaceChildren(...rows);
  }
  function updateStats(data) {
    const all = data.matches || [];
    const priced = all.filter(m => Number.isFinite(Number(m.probability_a)) && Number.isFinite(Number(m.probability_b)) && m.odds_source_url && m.pick);
    const unresolved = all.filter(m => !priced.includes(m));
    document.querySelector('#stat-total').textContent = String(all.length);
    document.querySelector('#stat-priced').textContent = String(priced.length);
    document.querySelector('#stat-unresolved').textContent = String(unresolved.length);
    renderPriced(priced); renderUnresolved(unresolved);
    const stamp = document.querySelector('#updated-at');
    const status = document.querySelector('#update-status');
    const dot = document.querySelector('.status-dot');
    if (data.fetched_at) {
      stamp.textContent = `Snapshot ${date(data.fetched_at)} · source: ${data.collector?.status || 'unknown'}`;
      status.textContent = data.collector?.status === 'ok' ? 'Latest source check completed' : 'Latest snapshot available';
      dot.classList.toggle('ok', data.collector?.status === 'ok');
    } else {
      stamp.textContent = 'No successful automated snapshot yet'; status.textContent = 'Awaiting verified match data';
    }
    const note = document.querySelector('#coverage-note');
    if (data.collector?.message) note.textContent = data.collector.message;
    const search = document.querySelector('#match-search');
    search.addEventListener('input', () => {
      const q = search.value.trim().toLowerCase();
      document.querySelectorAll('#priced-matches tr, #unresolved-matches tr').forEach(row => {
        row.hidden = Boolean(q) && !row.dataset.search?.includes(q);
      });
    });
  }
  async function load() {
    try {
      const response = await fetch(DATA_URL, { cache: 'no-store' });
      if (!response.ok) throw new Error(`data fetch ${response.status}`);
      const data = await response.json();
      if (!Array.isArray(data.matches)) throw new Error('invalid match data');
      updateStats(data);
    } catch (err) {
      document.querySelector('#update-status').textContent = 'Match data unavailable';
      document.querySelector('#updated-at').textContent = 'The static data file could not be loaded.';
      document.querySelector('#coverage-note').textContent = 'Dashboard data failed to load. No probabilities are shown; use the Hotspawn source link and Flagged for Review page.';
      fillEmpty(document.querySelector('#priced-matches'), 'Data unavailable. Please use the source links and review page.', 4);
      fillEmpty(document.querySelector('#unresolved-matches'), 'Data unavailable. No match data has been inferred.', 4);
    }
  }
  async function loadReview() {
    const target = document.querySelector('#generated-flags');
    if (!target) return;
    try {
      const res = await fetch(new URL('../data/review.json', document.baseURI), { cache: 'no-store' });
      if (!res.ok) throw new Error('Review feed is not available');
      const feed = await res.json();
      if (!Array.isArray(feed.flags) || !feed.flags.length) { target.append(el('p', '', 'No automated data-quality flags are recorded in the latest successful run. Known limitations remain listed below.')); return; }
      for (const item of feed.flags) {
        const article = el('article', 'flag-entry'); article.append(el('h3', '', item.title || 'Data flagged for review'));
        article.append(el('p', '', item.detail || 'Details not supplied.'));
        if (item.source_url) { const p = document.createElement('p'); p.append(sourceAnchor(item.source_url, item.source_name || 'Review source')); article.append(p); }
        if (item.match_url) { const p = document.createElement('p'); p.append(sourceAnchor(item.match_url, 'Hotspawn match source')); article.append(p); }
        target.append(article);
      }
    } catch { target.append(el('p', '', 'No automated review feed is available yet. The known limitations and primary source links are listed below.')); }
  }
  if (document.body.dataset.page === 'review') loadReview(); else load();
})();
