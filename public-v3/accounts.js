/* Accounts — fetches /api/accounts/status, renders the multi-account roster. */
(() => {
  'use strict';
  const I = window.Icarus;
  const { api, fmtCompact, esc } = I;
  const $ = (id) => document.getElementById(id);

  const STATUS = {
    running: { dot: 'running', txt: '● RUNNING', cls: 'c-green', row: 'is-running' },
    idle: { dot: 'idle', txt: '○ IDLE', cls: 'c-mut', row: '' },
    error: { dot: 'error', txt: '● ERROR', cls: 'c-red', row: 'is-error' },
  };

  function renderKpis(list) {
    const running = list.filter((a) => a.status === 'running').length;
    const runs = list.reduce((s, a) => s + (a.runs || 0), 0);
    const fans = list.reduce((s, a) => s + (a.fans || 0), 0);
    $('acc-kpis').innerHTML = `
      <div class="kpi"><div class="kpi-k">ACCOUNTS</div><div class="kpi-v">${list.length}</div></div>
      <div class="kpi"><div class="kpi-k">RUNNING</div><div class="kpi-v green">${running}</div></div>
      <div class="kpi"><div class="kpi-k">TOTAL RUNS</div><div class="kpi-v">${runs}</div></div>
      <div class="kpi"><div class="kpi-k">FANS TODAY</div><div class="kpi-v amber">${fmtCompact(fans)}</div></div>`;
  }

  function controlFor(a) {
    if (a.status === 'running') return `<button class="abtn" type="button">PAUSE</button><button class="abtn danger" type="button">STOP</button>`;
    if (a.status === 'error') return `<button class="abtn cyan" type="button">RE-LOGIN</button>`;
    return `<button class="abtn green" type="button">START</button>`;
  }

  function renderRows(list) {
    const host = $('acc-rows');
    host.innerHTML = '';
    list.forEach((a, i) => {
      const s = STATUS[a.status] || STATUS.idle;
      const row = document.createElement('div');
      row.className = 'trow ' + s.row;
      row.style.cssText = 'grid-template-columns:44px 1fr 90px 130px 70px 90px 150px' + (a.status === 'idle' ? ';opacity:.82' : '');
      row.innerHTML = `
        <span class="statusdot ${s.dot}"></span>
        <div><div style="font:700 var(--fs-lg) var(--cond);letter-spacing:.04em;color:var(--ink)">${esc(a.name)}</div>
        <div style="font:500 var(--fs-xs) var(--mono);color:${a.status === 'error' ? 'var(--red)' : 'var(--label)'};margin-top:2px">${esc(a.trainee)}</div></div>
        <span style="font:600 var(--fs-md) var(--mono);color:var(--ink-2)">${a.port}</span>
        <span style="font:600 var(--fs-sm) var(--mono)" class="${s.cls}">${s.txt}</span>
        <span class="r" style="font:600 var(--fs-md) var(--mono);color:var(--ink-2)">${a.runs}</span>
        <span class="r" style="font:600 var(--fs-md) var(--mono);color:var(--amber)">${fmtCompact(a.fans)}</span>
        <span style="display:flex;gap:6px;justify-content:flex-end">${controlFor(a)}</span>`;
      host.appendChild(row);
    });
  }

  // Real supervisor log built from each account's live health (source/detail/error/
  // hint) — no fabricated timestamps/events. Empty state when there's nothing to show.
  function renderLog(list, manager) {
    const ev = list.map((a) => {
      const h = a.health || {};
      const tone = a.status === 'running' ? 'green' : a.status === 'error' ? 'red' : 'mut';
      const msg = h.detail || h.manager_error || h.hint
        || (a.status === 'running' ? 'career runner active' : a.status === 'error' ? 'unreachable' : 'reachable · idle');
      return [':' + a.port, tone, msg];
    });
    $('acc-log').innerHTML = ev.length
      ? ev.map((r) => `
        <div class="mrow" style="grid-template-columns:60px 1fr">
          <span class="ev is-${r[1]}">${esc(r[0])}</span><span class="dt">${esc(r[2])}</span>
        </div>`).join('')
      : '<div class="mon-empty">No supervisor activity.</div>';
    const running = list.filter((a) => a.status === 'running').length;
    const pid = manager && (manager.pid || manager.manager_pid);
    $('acc-pid').textContent = running
      ? ('manager · ' + running + ' running' + (pid ? ' · pid ' + pid : ''))
      : (manager ? 'manager idle' : 'manager not started');
  }

  // The backend returns a `health` object per account (reachable / process_running /
  // runner_running) — NOT a `status` string. Derive the status the UI renders, so a
  // live bot on a port reads as RUNNING instead of always IDLE.
  function deriveStatus(a) {
    const h = a.health || {};
    a.status = h.runner_running ? 'running'
      : (h.reachable || h.process_running) ? 'idle'
        : 'error';
    if (a.trainee == null) a.trainee = h.detail || '—';
    if (a.runs == null) a.runs = 0;
    if (a.fans == null) a.fans = 0;
    return a;
  }

  async function boot() {
    I.mountChrome();
    const data = await api('/api/accounts/status');
    const list = ((data && data.accounts) || []).map(deriveStatus);
    renderKpis(list); renderRows(list); renderLog(list, data && data.manager_status);
  }
  boot();
})();
