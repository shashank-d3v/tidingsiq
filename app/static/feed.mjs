export const PAGE_SIZE = 10;
export const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function safeURL(value) {
  try { const url = new URL(value); return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password ? url.href : ''; }
  catch { return ''; }
}
export function rangeRows(rows, days, asOf) {
  const cutoff = new Date(`${asOf}T00:00:00Z`);
  cutoff.setUTCDate(cutoff.getUTCDate() - Number(days));
  const lower = cutoff.toISOString().slice(0,10);
  return rows.filter(r => r.serving_date >= lower && r.serving_date <= asOf);
}
export function selectRows(rows, state, asOf) {
  const query = state.search.trim().toLocaleLowerCase();
  const filtered = rangeRows(rows, state.days, asOf).filter(r =>
    (!state.language || (r.language || 'und') === state.language) &&
    (!state.country || (r.mentioned_country_name || 'Unknown') === state.country) &&
    (!query || `${r.title} ${r.source_name}`.toLocaleLowerCase().includes(query))
  );
  const representatives = new Map();
  for (const row of filtered) {
    const key = row.story_id || row.article_id;
    const previous = representatives.get(key);
    if (!previous || representativeOrder(row, previous) < 0) representatives.set(key, row);
  }
  return [...representatives.values()].sort((a,b) => {
    const score = state.sort === 'low' ? a.happy_factor-b.happy_factor : b.happy_factor-a.happy_factor;
    return score || timestamp(b)-timestamp(a) || compareID(b.article_id, a.article_id);
  });
}
export function summary(rows) {
  return {count:rows.length, average:rows.length ? rows.reduce((n,r)=>n+r.happy_factor,0)/rows.length : null,
    sources:new Set(rows.map(r=>r.source_name).filter(Boolean)).size,
    countries:new Set(rows.map(r=>r.mentioned_country_name).filter(Boolean)).size};
}

export function scoreBand(score) {
  if (!Number.isFinite(score) || score < 65 || score > 100) return 'neutral';
  if (score >= 90) return 'deep';
  if (score >= 80) return 'green';
  if (score >= 70) return 'sage';
  return 'amber';
}

function timestamp(row) {
  let value = String(row.published_at || row.ingested_at || `${row.serving_date}T00:00:00Z`).replace(' ', 'T');
  if (!/(Z|[+-]\d{2}:\d{2})$/.test(value)) value += 'Z';
  return Date.parse(value) || 0;
}
function compareID(a,b) { return String(a) < String(b) ? -1 : String(a) > String(b) ? 1 : 0; }
function representativeOrder(a,b) {
  return b.happy_factor-a.happy_factor || timestamp(b)-timestamp(a) || compareID(b.article_id,a.article_id);
}

// Reevaluate the loaded edition locally; this never fetches a newer manifest.
export function createFreshnessMonitor({document, onChange, now=Date.now,
  setTimeout:later=setTimeout, clearTimeout:cancel=clearTimeout}) {
  const maxAge = 36 * 60 * 60 * 1000;
  let edition, timer;
  function refresh() {
    cancel(timer);
    timer = undefined;
    if (!edition) return;
    const age = now() - Date.parse(edition.latest_data_at || `${edition.as_of}T00:00:00Z`);
    const stale = !Number.isFinite(age) || age > maxAge;
    onChange(stale, edition);
    if (!stale && document.visibilityState === 'visible') {
      timer = later(refresh, Math.min(maxAge - age + 1, 2147483647));
    }
  }
  document.addEventListener('visibilitychange', refresh);
  return {update(next) { edition = next; refresh(); }};
}
