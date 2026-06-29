/* Diag / AI — fetches /api/ai/dashboard + /api/diagnostics/summary. */
(() => {
  'use strict';
  const I = window.Icarus;
  const { api, fmtCompact, esc } = I;
  const $ = (id) => document.getElementById(id);

  let ai = {}, diag = {};

  // ---- map the real (nested) backend responses to the flat shape this view
  //      renders. The AI dashboard returns success:false when the model hasn't
  //      been trained yet — handle that explicitly instead of rendering blanks. ----
  function relTime(ts) {
    ts = Number(ts) || 0;
    if (!ts) return '—';
    const s = Math.max(0, (Date.now() / 1000) - ts);
    if (s < 90) return Math.round(s) + 's ago';
    if (s < 5400) return Math.round(s / 60) + 'm ago';
    if (s < 129600) return Math.round(s / 3600) + 'h ago';
    return Math.round(s / 86400) + 'd ago';
  }
  function clockOf(ts) {
    ts = Number(ts) || 0;
    if (!ts) return '';
    const d = new Date(ts * 1000);
    return String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0');
  }
  const baseName = (p) => String(p || '').split(/[\\/]/).pop();

  function adaptAi(d, status, advisor) {
    const trained = d.success !== false;
    const td = (status && status.turn_decisions) || {};
    const sm = d.shadow_mode || {};
    const auto = d.auto_training || (status && status.auto_training) || {};
    const llm = d.local_llm || auto.local_llm || (status && status.local_llm) || {};
    const cfg = llm.config || {};
    let style = [];
    const sa = (d.style_adaptation && d.style_adaptation.report) || d.style || [];
    if (Array.isArray(sa)) {
      style = sa.slice(0, 5).map((r) => Array.isArray(r)
        ? r : [r.name || r.style || r.label || '?', Math.round(Number(r.pct ?? r.percent ?? r.share ?? 0))]);
    }
    const advice = advisor && (advisor.summary || advisor.advice || advisor.text || advisor.headline || advisor.message);
    const pct = (v) => (v != null ? Math.round(Number(v) * 100) : 0);
    return {
      trained,
      detail: d.detail || '',
      dataset: Number(td.rows ?? td.live_rows ?? 0) || 0,
      accuracy: pct(sm.precision ?? sm.accuracy),
      last_train: relTime(d.updated_at || auto.last_run_at || auto.updated_at),
      shadow_win: pct(sm.precision),
      advisor: advice || (trained ? 'No advisor note for the latest run.' : (d.detail || 'AI not trained yet.')),
      auto_training: !!(auto.enabled ?? auto.running ?? auto.active),
      model_version: d.version || '',
      local_llm: { connected: !!(llm.connected || llm.enabled || llm.ok), endpoint: llm.endpoint || cfg.endpoint || '', model: llm.model || cfg.model || '' },
      style,
    };
  }

  function adaptDiag(d) {
    const snap = d.snapshot || {};
    const runner = d.runner || {};
    const md = snap.master_data || snap.masterdata || {};
    const con = [];
    if (d.latest_report) con.push([clockOf(d.latest_report_mtime), 'latest report · ' + baseName(d.latest_report), 'mut']);
    (d.manager_logs || []).slice(0, 4).forEach((p) => con.push(['', 'manager log · ' + baseName(p), 'mut']));
    return {
      server: '● online' + (d.python ? ' · py ' + d.python : ''),
      steam: (runner.logged_in || snap.logged_in || runner.account) ? '● authed' : (d.accounts_exists ? 'configured' : 'not set'),
      userdata: d.runtime_root ? ('set · ' + baseName(d.runtime_root)) : (d.settings_exists ? 'set' : 'not set'),
      master_data: md.status || md.label || (md.stale ? 'stale' : (snap.master_data_version || snap.masterdata_version || '—')),
      console: con,
    };
  }

  function aiView() {
    const statusColor = { online: 'green', authed: 'green', set: 'ink-2' };
    const style = (ai.style || []).map(([k, v]) => `
      <div style="flex:1"><div style="display:flex;justify-content:space-between;font:500 var(--fs-sm) var(--mono);margin-bottom:5px"><span style="color:var(--label)">${esc(k)}</span><span style="color:${v >= 40 ? 'var(--cyan)' : 'var(--ink-2)'}">${v}%</span></div>
      <div class="barmini"><div class="${v >= 40 ? 'fill-cyan' : ''}" style="width:${v}%"></div></div></div>`).join('');
    const untrained = !ai.trained ? `
      <div class="card" style="border-color:var(--amber-dk)">
        <div class="card-body"><p class="rcard-text" style="margin:0;color:var(--amber)">${esc(ai.detail || 'AI model not trained yet — run Train Now or let auto-training build it. Dataset counts + system health below are live.')}</p></div>
      </div>` : '';
    return `
      ${untrained}
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px">
        <div class="statbox"><div class="statbox-k">DATASET</div><div class="statbox-v">${fmtCompact(ai.dataset)}</div><div class="statbox-sub c-mut">turn decisions</div></div>
        <div class="statbox"><div class="statbox-k">ACCURACY</div><div class="statbox-v cyan" style="color:var(--cyan)">${ai.accuracy}%</div><div class="statbox-sub c-mut">model precision</div></div>
        <div class="statbox"><div class="statbox-k">LAST TRAIN</div><div class="statbox-v">${esc(ai.last_train)}</div><div class="statbox-sub">auto-training</div></div>
        <div class="statbox"><div class="statbox-k">SHADOW WIN</div><div class="statbox-v" style="color:var(--amber)">${ai.shadow_win}%</div><div class="statbox-sub">vs live policy</div></div>
      </div>
      <div class="card">
        <div class="card-head"><span class="card-title">TRAINING PIPELINE</span><span class="col-meta c-green">auto-training ${ai.auto_training ? 'ON' : 'OFF'}</span></div>
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;padding:13px 14px">
          <button class="abtn cyan" type="button">REBUILD DATASET</button>
          <button class="abtn cyan" type="button">IMPORT LOGS</button>
          <button class="abtn amber" type="button">TRAIN NOW</button>
          <button class="abtn" type="button">DOWNLOAD MODEL</button>
        </div>
      </div>
      <div style="display:flex;gap:14px">
        <div class="card" style="flex:1">
          <div class="card-head"><span class="card-title">ADVISOR · LATEST</span></div>
          <div class="card-body">
            <p class="rcard-text" style="margin-bottom:10px">${esc(ai.advisor)}</p>
            <div style="display:flex;gap:6px"><button class="abtn cyan" type="button">VIEW POST-RUN</button><button class="abtn cyan" type="button">BACKTEST</button></div>
          </div>
        </div>
        <div class="card" style="flex:1">
          <div class="card-head"><span class="card-title">LOCAL LLM</span><span class="col-meta ${ai.local_llm && ai.local_llm.connected ? 'c-green' : 'c-mut'}">${ai.local_llm && ai.local_llm.connected ? 'connected' : 'off'}</span></div>
          <div class="card-body" style="display:flex;flex-direction:column;gap:8px">
            <div style="display:flex;justify-content:space-between;font:500 var(--fs-sm) var(--mono)"><span class="c-mut">endpoint</span><span style="color:var(--ink-2)">${esc((ai.local_llm || {}).endpoint || '—')}</span></div>
            <div style="display:flex;justify-content:space-between;font:500 var(--fs-sm) var(--mono)"><span class="c-mut">model</span><span class="c-amber">${esc((ai.local_llm || {}).model || '—')}</span></div>
            <div style="display:flex;gap:6px;margin-top:4px"><button class="abtn cyan" type="button">TEST</button><button class="abtn cyan" type="button">ANALYZE RUN</button></div>
          </div>
        </div>
      </div>
      <div class="card" style="padding:13px 14px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:11px"><span class="card-title">STYLE ADAPTATION</span><span class="col-meta">last 12 runs</span></div>
        <div style="display:flex;gap:10px">${style}</div>
      </div>`;
  }

  function diagView() {
    return `
      <div class="card">
        <div class="card-head"><span class="card-title">SYSTEM HEALTH</span></div>
        <div class="card-body" style="display:flex;flex-direction:column;gap:9px">
          ${diagRow('FastAPI server', diag.server, 'green')}
          ${diagRow('Steam bridge', diag.steam, 'green')}
          ${diagRow('Userdata path', diag.userdata, 'ink-2')}
          ${diagRow('Master data', diag.master_data, 'amber')}
        </div>
      </div>
      <div class="card">
        <div class="card-head"><span class="card-title">BUNDLES &amp; EXPORTS</span></div>
        <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:8px;padding:13px 14px">
          <button class="abtn cyan" type="button">EXPORT LOGS</button>
          <button class="abtn cyan" type="button">DEBUG BUNDLE</button>
          <button class="abtn cyan" type="button">CRASH TRACE</button>
          <button class="abtn cyan" type="button">DIAG SUMMARY</button>
        </div>
      </div>
      <div class="card">
        <div class="card-head"><span class="card-title">USERDATA</span></div>
        <div class="card-body"><p class="rcard-text is-mut" style="margin:0">Userdata folder configured. Settings, presets, accounts, and Steam auth persist across version upgrades. Wire to <span class="c-cyan" style="font-family:var(--mono);font-size:var(--fs-md)">/api/userdata/info</span>.</p></div>
      </div>`;
  }
  function diagRow(k, v, tone) {
    return `<div style="display:flex;justify-content:space-between;font:500 var(--fs-md) var(--mono)"><span class="c-mut">${esc(k)}</span><span class="c-${tone}">${esc(v || '—')}</span></div>`;
  }

  function systemPanel() {
    const console_ = (diag.console || []).map((r) => `
      <div class="mrow" style="grid-template-columns:60px 1fr"><span class="t">${esc(r[0])}</span><span class="ev is-${r[2]}">${esc(r[1])}</span></div>`).join('');
    return `
      <div class="col-head"><span class="col-title">SYSTEM</span><span class="col-meta">127.0.0.1:1616</span></div>
      <div style="padding:13px 16px;border-bottom:1px solid var(--line-soft);display:flex;flex-direction:column;gap:9px">
        ${diagRow('FastAPI server', '● ' + (diag.server || 'online'), 'green')}
        ${diagRow('Steam bridge', '● ' + (diag.steam || 'authed'), 'green')}
        ${diagRow('Userdata path', diag.userdata || 'set', 'ink-2')}
        ${diagRow('Master data', diag.master_data || 'stale · 3d', 'amber')}
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;padding:11px 16px;border-bottom:1px solid var(--line-soft)">
        <button class="abtn cyan" type="button" data-modal="userdata">USERDATA FOLDER</button>
        <button class="abtn cyan" type="button" data-modal="discord">DISCORD WEBHOOK</button>
      </div>
      <div style="display:flex;align-items:center;gap:8px;padding:10px 16px;border-bottom:1px solid var(--line-soft)">
        <span class="card-title">CONSOLE</span><span class="fbtn is-active">ALL</span><span class="fbtn">WARN</span><span class="fbtn">ERROR</span>
      </div>
      <div class="monitor-rows">${console_}</div>
      <div style="display:flex;align-items:center;gap:8px;padding:10px 16px;border-top:1px solid var(--line-soft)">
        <span class="card-title">LIVE API</span><span class="col-meta" id="diag-stream-meta">/api/stream · SSE</span>
      </div>
      <div class="monitor-rows" id="diag-stream-rows" style="max-height:170px"></div>`;
  }

  // Live game-API call feed via Server-Sent Events (/api/stream). Additive, isolated
  // to this page; the dashboard keeps polling. EventSource auto-reconnects.
  let _es = null;
  function startStream() {
    if (_es || typeof EventSource === 'undefined') return;
    try { _es = new EventSource('/api/stream'); } catch (e) { return; }
    _es.onmessage = (e) => {
      let d;
      try { d = JSON.parse(e.data); } catch (_) { return; }
      const rows = $('diag-stream-rows');
      if (!rows || !d || d.dir === 'OPEN') return;
      const tone = d.dir === 'ERR' ? 'error' : (d.rc && d.rc !== 1 ? 'warn' : 'mut');
      const row = document.createElement('div');
      row.className = 'mrow';
      row.style.gridTemplateColumns = '54px 1fr 46px';
      row.innerHTML = `<span class="t">${esc(clockOf(d.ts))}</span>`
        + `<span class="ev is-${tone}">${esc(d.dir + ' ' + (d.ep || ''))}</span>`
        + `<span class="t" style="text-align:right">${esc(d.rc != null ? 'rc' + d.rc : (d.err ? 'err' : ''))}</span>`;
      rows.insertBefore(row, rows.firstChild);
      while (rows.children.length > 50) rows.removeChild(rows.lastChild);
    };
    _es.onerror = () => {};  // transient; EventSource reconnects on its own
  }

  function render(sub) {
    $('diag-left').innerHTML = sub === 'diag' ? diagView() : aiView();
    $('diag-right').innerHTML = systemPanel();
    $('diag-model').innerHTML = '● model ' + (ai.model_version ? 'healthy' : 'untrained');
    $('diag-version').textContent = (ai.model_version || 'v—') + ' · ' + fmtCompact(ai.dataset) + ' samples';
  }

  async function boot() {
    I.mountChrome();
    document.addEventListener('click', (e) => {
      const t = e.target.closest('[data-modal]');
      if (t && I.Modals && I.Modals[t.dataset.modal]) I.Modals[t.dataset.modal]();
    });
    const [aiData, statusData, advisorData, diagData] = await Promise.all([
      api('/api/ai/dashboard'), api('/api/ai/status'),
      api('/api/ai/advisor/latest'), api('/api/diagnostics/summary'),
    ]);
    ai = adaptAi(aiData || {}, statusData || {}, advisorData || {});
    diag = adaptDiag(diagData || {});
    render('ai');
    startStream();
    document.querySelectorAll('.seg[data-sub]').forEach((s) => s.addEventListener('click', () => {
      document.querySelectorAll('.seg[data-sub]').forEach((x) => x.classList.remove('is-active'));
      s.classList.add('is-active');
      render(s.dataset.sub);
    }));
  }
  boot();
})();
