/* ============================================================
   ICARUS · Command Console (v3) — shared core
   Loaded by every screen. Provides:
     Icarus.api(url, opts)   real fetch; returns null if unreachable
     Icarus.fmt*             formatters
     Icarus.mountChrome(tab) live rail pills + run status + dev
   There is no simulated data. When the backend is unreachable
   api() returns null, the offline banner shows, and each screen
   renders its own empty/idle state. Run `python main.py` to go live.
   ============================================================ */
window.Icarus = (() => {
  'use strict';

  const fmtNum = (n) => (Number(n) || 0).toLocaleString('en-US');
  const fmtCompact = (n) => {
    n = Number(n) || 0;
    if (n >= 1e9) return (n / 1e9).toFixed(1).replace(/\.0$/, '') + 'B';
    if (n >= 1e6) return (n / 1e6).toFixed(1).replace(/\.0$/, '') + 'M';
    if (n >= 1e3) return (n / 1e3).toFixed(1).replace(/\.0$/, '') + 'K';
    return String(Math.round(n));
  };
  const pad2 = (n) => String(n).padStart(2, '0');
  const fmtDur = (s) => {
    s = Number(s) || 0;
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
    if (h) return h + 'h ' + m + 'm';
    if (m) return m + 'm';
    return (s | 0) + 's';
  };
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  let mockMode = false;
  const listeners = [];

  // ============================================================
  //  API LAYER
  // ============================================================
  async function api(url, opts = {}) {
    try {
      const ctrl = new AbortController();
      // 12s, not 4s: the real /api/career/runner snapshot can take several
      // seconds on the first poll / large action_history; a 4s abort wrongly
      // tripped the offline banner over a healthy server.
      const timer = setTimeout(() => ctrl.abort(), 12000);
      const res = await fetch(url, { ...opts, signal: ctrl.signal });
      clearTimeout(timer);
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const json = await res.json();
      // Reachable → clear the offline banner so a page opened before the server
      // was ready goes live on the next poll without a manual refresh.
      if (mockMode) {
        mockMode = false;
        document.querySelectorAll('.mockbar').forEach((m) => m.classList.remove('show'));
      }
      return json;
    } catch (e) {
      // Backend unreachable — show the offline notice and return null. No simulated
      // data is produced; each page renders its own empty/idle state.
      if (!mockMode) {
        mockMode = true;
        document.querySelectorAll('.mockbar').forEach((m) => m.classList.add('show'));
      }
      return null;
    }
  }

  // ============================================================
  //  SHARED LIVE CHROME  (rail pills + run status + dev toggles)
  // ============================================================
  // Single source of truth for the navbar dev toggles, persisted to localStorage
  // so they survive navigation across the multi-page v3 app (each page reloads
  // core.js fresh). app.js shares THIS object; both call persistToggles() on change.
  const devToggles = { tempt: false, burn: false, loop: false, finish: false, loopCount: 1 };
  // BUG #6: LOOP is a run-COUNT, not just on/off. Clicking cycles through these
  // (0 = infinite). run_count flows to /api/career/run. Persisted with devToggles.
  const LOOP_SEQ = [1, 2, 3, 5, 10, 0];
  const loopLabel = (n) => 'LOOP:' + (Number(n) === 0 ? '∞' : Number(n));
  function nextLoopCount() {
    const i = LOOP_SEQ.indexOf(Number(devToggles.loopCount));
    devToggles.loopCount = LOOP_SEQ[(i + 1) % LOOP_SEQ.length];
    devToggles.loop = devToggles.loopCount !== 1;   // keep legacy bool in sync
    persistToggles();
    return devToggles.loopCount;
  }
  try {
    const saved = JSON.parse(localStorage.getItem('icarus_dev_toggles') || '{}');
    if (saved && typeof saved === 'object') Object.assign(devToggles, saved);
  } catch (e) { /* corrupt value → keep defaults */ }
  // Migrate the legacy boolean loop (∞/1) to the new run-count.
  if (devToggles.loopCount == null) devToggles.loopCount = devToggles.loop ? 0 : 1;
  function persistToggles() {
    try { localStorage.setItem('icarus_dev_toggles', JSON.stringify(devToggles)); } catch (e) { /* ignore */ }
  }

  // --- TP recovery strategy (persisted) ---
  const RECOVERY_MODES = [
    ['items_carrots', 'Items \u2192 Carrots'],
    ['items', 'Items Only'],
    ['carrots', 'Carrots Only'],
  ];
  function getRecoveryMode() {
    const v = localStorage.getItem('icarus_tp_recovery');
    return RECOVERY_MODES.some((m) => m[0] === v) ? v : 'items_carrots';
  }
  function setRecoveryMode(v) {
    if (RECOVERY_MODES.some((m) => m[0] === v)) {
      localStorage.setItem('icarus_tp_recovery', v);
      // keep both rail renderers (dashboard + shared) in sync immediately
      document.querySelectorAll('.recov-sel').forEach((s) => { s.value = v; });
    }
  }
  function recoveryPill() {
    const cur = getRecoveryMode();
    const opts = RECOVERY_MODES.map(
      ([k, label]) => `<option value="${k}"${k === cur ? ' selected' : ''}>${label}</option>`
    ).join('');
    return `
      <div class="pill pill-recov">
        <div class="pill-k">TP RECOVERY</div>
        <select class="recov-sel" onchange="Icarus.setRecoveryMode(this.value)" title="How the bot restores TP before training">${opts}</select>
      </div>`;
  }

  let lastCareer = null;
  function careerPillHtml(career) {
    lastCareer = career || null;
    const ongoing = !!(career && career.active);
    return `<div class="pill pill-career" id="career-pill" role="button" tabindex="0" title="${ongoing ? 'Career in progress \u2014 click to delete' : 'No active career'}"><div class="pill-k">CAREER</div><div class="pill-v ${ongoing ? 'is-amber' : 'is-dim'}">${ongoing ? 'ONGOING' : 'NONE'}</div></div>`;
  }
  function renderPills(acc) {
    const host = document.getElementById('rail-pills');
    if (!host || !acc) return;
    // Don't rebuild the pills while the user is interacting with the TP-recovery
    // dropdown: the full innerHTML rebuild every poll (1.5s) was destroying the open
    // <select> mid-change. Skip the rebuild while it's focused/open; the next poll
    // after the user clicks away refreshes the values normally.
    const ae = document.activeElement;
    if (ae && ae.classList && ae.classList.contains('recov-sel') && host.contains(ae)) return;
    const tp = acc.tp || {}, c = acc.carrots || {};
    host.innerHTML = `
      <div class="pill"><div class="pill-k">TP</div><div class="pill-v">${pad2(tp.current || 0)}<span class="sub">/${tp.max || 0}</span></div></div>
      ${recoveryPill()}
      <div class="pill"><div class="pill-k">CARROTS</div><div class="pill-v is-amber">${fmtNum(c.total)}</div></div>
      <div class="pill"><div class="pill-k">GOLD</div><div class="pill-v">${fmtCompact(acc.gold)}</div></div>
      <div class="pill"><div class="pill-k">CLOCKS</div><div class="pill-v">${fmtNum(acc.clocks)}</div></div>
      ${careerPillHtml(acc.career)}`;
  }

  function renderLive(runner) {
    const live = document.getElementById('tab-live');
    const txt = document.getElementById('tab-live-text');
    if (live) live.className = 'tab-live ' + (runner.running ? '' : runner.paused ? 'is-paused' : 'is-idle');
    if (txt) txt.textContent = runner.status_text || (runner.running ? 'RUNNING' : 'IDLE');
  }

  // --- dev popover config (persisted in-session) ---
  const devConfig = {
    tempt:   { speed: 'safe', min: 2.5, max: 5 },
    retries: { carats: false, maxClocks: 2, g1DebutOnly: false, maxPerRace: -1 },
  };
  // BUG #7: persist the retries popover config so it survives menu switches and
  // reloads (it is NOT part of devToggles, so it was resetting every navigation).
  try {
    const _r = JSON.parse(localStorage.getItem('icarus_dev_retries') || '{}');
    if (_r && typeof _r === 'object') Object.assign(devConfig.retries, _r);
  } catch (e) { /* ignore */ }
  function persistRetries() {
    try { localStorage.setItem('icarus_dev_retries', JSON.stringify(devConfig.retries)); } catch (e) { /* ignore */ }
  }
  const SPEEDS = [
    ['safe', 'Safe', 'full delay (your custom range)'],
    ['fast', 'Fast', 'no turn delay'],
    ['faster', 'Faster', 'no turn delay, faster calls'],
    ['ludicrous', 'Ludicrous', 'no delay (max speed)'],
  ];
  const COG = '<svg class="cog" viewBox="0 0 24 24" width="11" height="11" fill="currentColor" aria-hidden="true"><path d="M19.14 12.94a7.5 7.5 0 0 0 .05-.94 7.5 7.5 0 0 0-.05-.94l2.03-1.58a.5.5 0 0 0 .12-.64l-1.92-3.32a.5.5 0 0 0-.6-.22l-2.39.96a7 7 0 0 0-1.62-.94l-.36-2.54a.5.5 0 0 0-.5-.42h-3.84a.5.5 0 0 0-.5.42l-.36 2.54a7 7 0 0 0-1.62.94l-2.39-.96a.5.5 0 0 0-.6.22L2.34 8.84a.5.5 0 0 0 .12.64l2.03 1.58c-.03.31-.05.62-.05.94s.02.63.05.94l-2.03 1.58a.5.5 0 0 0-.12.64l1.92 3.32a.5.5 0 0 0 .6.22l2.39-.96c.5.38 1.04.7 1.62.94l.36 2.54a.5.5 0 0 0 .5.42h3.84a.5.5 0 0 0 .5-.42l.36-2.54a7 7 0 0 0 1.62-.94l2.39.96a.5.5 0 0 0 .6-.22l1.92-3.32a.5.5 0 0 0-.12-.64l-2.03-1.58zM12 15.5A3.5 3.5 0 1 1 12 8.5a3.5 3.5 0 0 1 0 7z"/></svg>';

  let openPop = null;
  function closePop() {
    if (openPop) { openPop.remove(); openPop = null; }
    document.removeEventListener('mousedown', outsidePop, true);
    document.removeEventListener('keydown', escPop);
  }
  function outsidePop(e) {
    if (!openPop) return;
    if (openPop.contains(e.target)) return;
    if (openPop._owner && openPop._owner.contains(e.target)) return;
    closePop();
  }
  function escPop(e) { if (e.key === 'Escape') closePop(); }
  function showPop(anchor, html) {
    closePop();
    const pop = document.createElement('div');
    pop.className = 'dev-pop';
    pop.innerHTML = html;
    document.body.appendChild(pop);
    const r = anchor.getBoundingClientRect();
    let left = r.left;
    const pw = pop.offsetWidth;
    if (left + pw > window.innerWidth - 8) left = window.innerWidth - 8 - pw;
    pop.style.top = (r.bottom + 6) + 'px';
    pop.style.left = Math.max(8, left) + 'px';
    pop._owner = anchor;
    openPop = pop;
    setTimeout(() => {
      document.addEventListener('mousedown', outsidePop, true);
      document.addEventListener('keydown', escPop);
    }, 0);
    return pop;
  }
  function togglePop(btn, builder) {
    const wasOwner = openPop && openPop._owner === btn;
    closePop();
    if (!wasOwner) builder(btn);
  }

  function reflectTempt(btn) { btn.classList.toggle('on', devConfig.tempt.speed !== 'safe'); }
  function reflectRetries(btn) { btn.classList.toggle('on', devConfig.retries.carats || devConfig.retries.maxClocks > 0 || devConfig.retries.g1DebutOnly || devConfig.retries.maxPerRace >= 0); }

  function temptPop(btn) {
    const c = devConfig.tempt;
    const cards = SPEEDS.map(([k, t, d]) => `
      <button class="pop-card${c.speed === k ? ' sel' : ''}" data-speed="${k}" type="button">
        <div class="pop-card-t">${t}</div>
        <div class="pop-card-d">${d}</div>
      </button>`).join('');
    const pop = showPop(btn, `
      <div class="pop-h">BOT SPEED</div>
      <div class="pop-cards">${cards}</div>
      <div class="pop-h" style="margin-top:13px">CUSTOM DELAY (S)</div>
      <div class="pop-delay">
        <input class="pop-num" id="pop-dmin" type="number" step="0.1" min="0" value="${c.min}">
        <span class="pop-dash">\u2013</span>
        <input class="pop-num" id="pop-dmax" type="number" step="0.1" min="0" value="${c.max}">
      </div>`);
    // Apply Tempt Fate LIVE: bot speed is a server global (POST /api/settings/speed),
    // and the custom range sets the inter-turn delay (POST /api/settings/turn-delay).
    // Previously the popover only updated local state, so it did nothing.
    const pushSpeed = () => { fetch('/api/settings/speed', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ level: c.speed }) }).catch(() => {}); };
    const pushDelay = () => { fetch('/api/settings/turn-delay', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ min: c.min, max: c.max, disabled: c.speed !== 'safe' }) }).catch(() => {}); };
    pop.querySelectorAll('.pop-card').forEach((el) => {
      el.addEventListener('click', () => {
        c.speed = el.dataset.speed;
        pop.querySelectorAll('.pop-card').forEach((x) => x.classList.toggle('sel', x === el));
        reflectTempt(btn);
        pushSpeed();
      });
    });
    const dmin = pop.querySelector('#pop-dmin'), dmax = pop.querySelector('#pop-dmax');
    dmin.addEventListener('change', () => { c.min = parseFloat(dmin.value) || 0; pushDelay(); });
    dmax.addEventListener('change', () => { c.max = parseFloat(dmax.value) || 0; pushDelay(); });
  }

  function retriesPop(btn) {
    const c = devConfig.retries;
    const pop = showPop(btn, `
      <label class="pop-check">
        <input type="checkbox" id="pop-carats"${c.carats ? ' checked' : ''}>
        <span>Use carats when clocks run out</span>
      </label>
      <div class="pop-field">
        <span>Max clocks / career</span>
        <input class="pop-num" id="pop-maxc" type="number" min="0" step="1" value="${c.maxClocks}">
      </div>
      <label class="pop-check">
        <input type="checkbox" id="pop-g1"${c.g1DebutOnly ? ' checked' : ''}>
        <span>Use clocks on ONLY G1/Debut races</span>
      </label>
      <div class="pop-field">
        <span>Max retries / race</span>
        <input class="pop-num" id="pop-mpr" type="number" min="0" step="1" placeholder="default" value="${c.maxPerRace >= 0 ? c.maxPerRace : ''}">
      </div>`);
    const cb = pop.querySelector('#pop-carats');
    cb.addEventListener('change', () => { c.carats = cb.checked; persistRetries(); reflectRetries(btn); });
    const mc = pop.querySelector('#pop-maxc');
    mc.addEventListener('change', () => { c.maxClocks = parseInt(mc.value, 10) || 0; persistRetries(); reflectRetries(btn); });
    const g1 = pop.querySelector('#pop-g1');
    g1.addEventListener('change', () => { c.g1DebutOnly = g1.checked; persistRetries(); reflectRetries(btn); });
    const mpr = pop.querySelector('#pop-mpr');
    // blank = use preset/default (-1); 0 = no retries; N = cap
    mpr.addEventListener('change', () => {
      const v = mpr.value.trim();
      c.maxPerRace = (v === '') ? -1 : (parseInt(v, 10) || 0);
      persistRetries();
      reflectRetries(btn);
    });
  }

  function bindDevToggles() {
    // simple on/off toggles
    const map = {
      'dev-burn': ['burn', (on) => 'BURN:' + (on ? 'ON' : 'OFF')],
      'dev-finish': ['finish', (on) => 'FINISH:' + (on ? 'ON' : 'OFF')],
    };
    Object.entries(map).forEach(([id, [key, label]]) => {
      const b = document.getElementById(id);
      if (!b) return;
      b.addEventListener('click', () => {
        devToggles[key] = !devToggles[key];
        persistToggles();
        b.textContent = label(devToggles[key]);
        b.classList.toggle('on', devToggles[key]);
      });
      // Restore the persisted state into the button label (HTML defaults to OFF).
      b.textContent = label(devToggles[key]);
      b.classList.toggle('on', devToggles[key]);
    });

    // BUG #6: LOOP cycles a run-count (1/2/3/5/10/\u221e) instead of a boolean.
    const lb = document.getElementById('dev-loop');
    if (lb) {
      const syncLoop = () => { lb.textContent = loopLabel(devToggles.loopCount); lb.classList.toggle('on', Number(devToggles.loopCount) !== 1); };
      lb.addEventListener('click', () => { nextLoopCount(); syncLoop(); });
      syncLoop();
    }

    bindDevExtras();
  }

  // Restore the real bot speed from the server so the TEMPT FATE button doesn't
  // show a stale 'safe' state after page navigation (devConfig is per-page-load).
  async function loadSpeed() {
    try {
      const data = await api('/api/settings/speed');
      if (data && data.level) devConfig.tempt.speed = data.level;
    } catch (e) { /* keep current default */ }
  }

  // cog buttons + popovers (shared by dashboard, which binds its own toggles)
  function bindDevExtras() {
    // Tempt Fate → BOT SPEED popover
    const tempt = document.getElementById('dev-tempt');
    if (tempt && tempt.dataset.popBound) return;
    if (tempt) tempt.dataset.popBound = '1';
    if (tempt) {
      tempt.innerHTML = 'TEMPT FATE' + COG;
      tempt.classList.add('dev-cog');
      tempt.title = 'Tempt Fate \u2014 bot speed';
      reflectTempt(tempt);
      loadSpeed().then(() => reflectTempt(tempt));   // sync button to the real server speed
      tempt.addEventListener('click', (e) => { e.stopPropagation(); togglePop(tempt, temptPop); });
    }

    // Retries → inject button (left of LOOP) → RETRIES popover
    const cluster = document.getElementById('dev-cluster');
    if (cluster && !document.getElementById('dev-retries')) {
      const r = document.createElement('button');
      r.id = 'dev-retries'; r.type = 'button'; r.className = 'dev-btn dev-cog';
      r.title = 'Retries \u2014 clocks per career';
      r.innerHTML = 'RETRIES' + COG;
      cluster.insertBefore(r, document.getElementById('dev-loop') || null);
      reflectRetries(r);
      r.addEventListener('click', (e) => { e.stopPropagation(); togglePop(r, retriesPop); });
    }
  }

  // ============================================================
  //  NAVBAR LIFETIME METRICS  (moved out of the dashboard vitals column)
  //  Rendered into a bordered strip in the empty rail space on EVERY page,
  //  fed by the same /api/career/runner snapshot as the pills.
  // ============================================================
  function ensureLifetimeHost() {
    let host = document.getElementById('rail-lifetime');
    if (host) return host;
    const pills = document.getElementById('rail-pills');
    if (!pills || !pills.parentNode) return null;
    host = document.createElement('div');
    host.id = 'rail-lifetime';
    host.className = 'rail-lm';
    pills.parentNode.insertBefore(host, pills.nextSibling);
    return host;
  }
  // [label, value-fn] over the RAW runner.lifetime object (+ current_chara for career fans).
  const LM_DEFS = [
    ['FAN GAIN', (lt) => fmtCompact(lt.total_fans_gained_live ?? lt.total_fans_gained ?? 0)],
    ['FANS/HR', (lt) => fmtCompact(lt.fans_per_hour_live ?? lt.fans_per_hour ?? 0)],
    ['RUNTIME', (lt) => fmtDur(lt.total_runtime_seconds_live ?? lt.total_runtime_seconds ?? 0)],
    ['CAREERS', (lt) => String(lt.careers_completed ?? 0)],
  ];
  function renderLifetime(runner) {
    const host = ensureLifetimeHost();
    if (!host) return;
    const lt = (runner && runner.lifetime) || null;
    if (!lt) { host.innerHTML = ''; return; }
    const careerFans = (runner.current_chara && runner.current_chara.fans) || runner.fans_current || 0;
    const cells = LM_DEFS.map(([k, fn]) =>
      `<div class="lm-cell"><div class="lm-cell-k">${k}</div><div class="lm-cell-v">${esc(fn(lt))}</div></div>`);
    cells.push(`<div class="lm-cell"><div class="lm-cell-k">CAREER FANS</div><div class="lm-cell-v">${esc(fmtCompact(careerFans))}</div></div>`);
    host.innerHTML = cells.join('');
  }

  // ============================================================
  //  PER-TRAINEE THEME COLOURS
  //  The active trainee's ui_colors (card_id -> {main,sub,border}) recolour the
  //  cockpit accent (--amber family) via inline :root overrides, which beat the
  //  data-theme stylesheet rules. Cleared (→ manual logo theme) when no career.
  // ============================================================
  let _traineeColors = null, _traineeColorsP = null, _appliedCard = null;
  function loadTraineeColors() {
    if (_traineeColors) return Promise.resolve(_traineeColors);
    if (!_traineeColorsP) {
      _traineeColorsP = api('/api/character-profile/colors').then((d) => {
        _traineeColors = (d && d.colors) || {};
        return _traineeColors;
      }).catch(() => (_traineeColors = {}));
    }
    return _traineeColorsP;
  }
  // Multiply a #rrggbb toward black by factor t (0..1) for the soft border/fill vars.
  function _darken(hex, t) {
    hex = String(hex).replace('#', '');
    if (hex.length !== 6) return null;
    const ch = (i) => Math.round(parseInt(hex.slice(i, i + 2), 16) * t);
    return '#' + [ch(0), ch(2), ch(4)].map((v) => Math.min(255, v).toString(16).padStart(2, '0')).join('');
  }
  async function applyTraineeTheme(cardId) {
    cardId = Number(cardId) || 0;
    if (!cardId) { clearTraineeTheme(); return; }
    if (cardId === _appliedCard) return;
    const colors = await loadTraineeColors();
    const c = colors[String(cardId)];
    if (!c || !c.main) { return; }   // unknown card → keep whatever's applied
    _appliedCard = cardId;
    const main = '#' + String(c.main).replace('#', '');
    const root = document.documentElement.style;
    root.setProperty('--amber', main);
    root.setProperty('--amber-bd', _darken(main, 0.32) || main);
    root.setProperty('--amber-dk', _darken(main, 0.17) || main);
  }
  function clearTraineeTheme() {
    if (_appliedCard === null) return;
    _appliedCard = null;
    const root = document.documentElement.style;
    root.removeProperty('--amber');
    root.removeProperty('--amber-bd');
    root.removeProperty('--amber-dk');
  }

  async function pollChrome() {
    const snap = await api('/api/career/runner');
    if (snap && snap.account) renderPills(snap.account);
    if (snap && snap.runner) renderLive(snap.runner);
    renderLifetime(snap && snap.runner);                       // bordered metrics in the rail
    applyTraineeTheme(snap && snap.runner && snap.runner.current_chara && snap.runner.current_chara.card_id);
    setMonitor(snap);   // real rows on the bottom dock (null when offline → idle state)
    listeners.forEach((fn) => { try { fn(snap); } catch (e) {} });
  }

  // ---- Career pill → small confirm dialog (delete ongoing career / cancel) ----
  let careerModalEl = null;
  function closeCareerModal() {
    if (careerModalEl) { careerModalEl.remove(); careerModalEl = null; }
    document.removeEventListener('keydown', careerModalEsc);
  }
  function careerModalEsc(e) { if (e.key === 'Escape') closeCareerModal(); }
  function showCareerModal() {
    closeCareerModal();
    const ongoing = !!(lastCareer && lastCareer.active);
    const ov = document.createElement('div');
    ov.className = 'modal-overlay';
    ov.style.zIndex = '300';
    ov.innerHTML = `
      <div class="modal" style="width:380px" role="dialog" aria-modal="true">
        <div class="modal-head"><span class="modal-mark"></span><span class="modal-title">${ongoing ? 'DELETE CAREER?' : 'NO ACTIVE CAREER'}</span></div>
        <div class="modal-body" style="padding:18px">
          <p id="career-modal-copy" style="font:500 var(--fs-base)/1.7 var(--mono);color:${ongoing ? 'var(--ink-2)' : 'var(--dim)'};margin:0">${ongoing ? 'This will force-delete the ongoing career. This cannot be undone.' : 'There is no career in progress to delete.'}</p>
        </div>
        <div class="modal-foot">
          <button type="button" class="abtn" id="career-cancel-btn">${ongoing ? 'CANCEL' : 'CLOSE'}</button>
          ${ongoing ? '<button type="button" class="abtn danger" id="career-delete-btn" style="color:var(--red);border-color:var(--red-bd)">DELETE</button>' : ''}
        </div>
      </div>`;
    document.body.appendChild(ov);
    careerModalEl = ov;
    ov.addEventListener('mousedown', (e) => { if (e.target === ov) closeCareerModal(); });
    document.addEventListener('keydown', careerModalEsc);
    const cancel = ov.querySelector('#career-cancel-btn');
    if (cancel) cancel.addEventListener('click', closeCareerModal);
    const del = ov.querySelector('#career-delete-btn');
    if (del) del.addEventListener('click', () => deleteCareer(del, ov.querySelector('#career-modal-copy')));
  }
  let deletingCareer = false;
  async function deleteCareer(btn, copyEl) {
    if (deletingCareer) return;
    deletingCareer = true;
    if (btn) { btn.textContent = 'DELETING'; btn.disabled = true; btn.style.opacity = '.6'; }
    if (copyEl) copyEl.textContent = 'Deleting ongoing career\u2026';
    try {
      const turn = (lastCareer && lastCareer.turn) || 0;
      const data = await api('/api/career/delete', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(turn ? { current_turn: turn } : {}),
      });
      if (data && data.success === false) throw new Error(data.detail || 'Delete failed');
      deletingCareer = false;
      closeCareerModal();
      pollChrome();
    } catch (e) {
      deletingCareer = false;
      if (copyEl) copyEl.textContent = (e && e.message) || 'Delete failed.';
      if (btn) { btn.textContent = 'RETRY'; btn.disabled = false; btn.style.opacity = '1'; }
    }
  }
  document.addEventListener('click', (e) => {
    const pill = e.target.closest && e.target.closest('#career-pill');
    if (pill) showCareerModal();
  });
  document.addEventListener('keydown', (e) => {
    if ((e.key === 'Enter' || e.key === ' ') && document.activeElement && document.activeElement.id === 'career-pill') {
      e.preventDefault(); showCareerModal();
    }
  });

  // ============================================================
  //  BOTTOM MONITOR DOCK  (slim bar on every page; click to expand)
  // ============================================================
  // [ev, detail, tone, filter-category]
  const MON_EVENTS = [
    ['train', 'Speed training \u00b7 +12', 'green', 'gain'],
    ['score', 'goal-weighted pick \u00b7 mood 4', 'cyan', 'info'],
    ['hp_check', '77/100 (green)', 'mut', 'info'],
    ['fan_gain', '+3.3K', 'green', 'gain'],
    ['race', 'Osaka Hai \u00b7 1st', 'green', 'race'],
    ['train', 'Power training \u00b7 +15', 'green', 'gain'],
    ['skill', 'bought Professor of Curvature', 'cyan', 'gain'],
    ['warn', 'energy low \u00b7 resting this turn', 'amber', 'warn'],
    ['score', 'value pick \u00b7 SP 619', 'cyan', 'info'],
    ['race', 'Tenno Sho (Spring) \u00b7 2nd', 'green', 'race'],
    ['hp_check', '63/100 (amber)', 'amber', 'info'],
    ['error', 'screen read retry \u00b7 recovered', 'red', 'error'],
  ];

  function monChart(turn) {
    const frac = Math.min(1, turn / 78);
    const series = [
      ['SPD', '#36c5d0', 360], ['STA', '#4ade80', 332], ['PWR', '#f04444', 388],
      ['GUT', '#c084fc', 305], ['SP', '#f2a900', 619],
    ];
    const W = 480, H = 128, N = 11, maxV = 690;
    let svg = `<svg viewBox="0 0 ${W} ${H + 8}" preserveAspectRatio="none" style="width:100%;height:118px;display:block">`;
    [10, 44, 78, 112].forEach((y) => { svg += `<line x1="0" y1="${y}" x2="${W}" y2="${y}" stroke="#15181e"/>`; });
    const legend = [];
    series.forEach(([name, color, target]) => {
      const cur = Math.round(target * (0.34 + 0.66 * frac));
      let pts = '';
      for (let i = 0; i <= N; i++) {
        const f = i / N;
        const v = target * (0.30 + (cur / target - 0.30) * f) * (0.965 + 0.05 * Math.sin(i * 1.6 + target));
        const x = (W * i / N).toFixed(0);
        const y = (H - (v / maxV) * H + 4).toFixed(1);
        pts += `${x},${y} `;
      }
      svg += `<polyline fill="none" stroke="${color}" stroke-width="${name === 'SP' ? 2 : 1.6}" points="${pts.trim()}"/>`;
      legend.push(`<span><i style="background:${color}"></i>${name} ${cur}</span>`);
    });
    svg += '</svg>';
    return svg + `<div class="legend">${legend.join('')}</div>`;
  }

  // ---- Bottom MONITOR dock: render REAL career rows from the runner snapshot.
  // (Previously a hardcoded turn-50..78 ticker that never touched the backend.)
  let monDock = null, monRows = [], monFilter = 'all';
  const MON_STAT_KEY = { Speed: 'speed', Stamina: 'stamina', Power: 'power', Guts: 'guts', Wit: 'wit', Wiz: 'wit' };
  function monOrdinal(n) {
    n = Number(n) || 0; if (!n) return '';
    const s = ['th', 'st', 'nd', 'rd'], v = n % 100;
    return n + (s[(v - 20) % 10] || s[v] || s[0]);
  }
  function monActionLabel(e) {
    const a = String((e && e.action) || '').toLowerCase();
    const fac = String((e && e.facility) || '').trim();
    if (a.indexOf('race') >= 0) return (fac || 'Race').split(' · ')[0];   // short race name
    if (a === 'train') return (fac && !/^\d+$/.test(fac)) ? fac + ' training' : 'training';
    if (a === 'rest' || a === 'rest_summer') return 'Rest';
    if (a.indexOf('recreat') >= 0) return 'Recreation';
    if (a === 'medic' || a === 'infirmary') return 'Infirmary';
    if (a === 'finish') return 'Career finished';
    return fac || a || 'action';
  }
  function monRenderRows() {
    if (!monDock) return;
    const wrap = monDock.querySelector('#mon-rows');
    if (!wrap) return;
    const list = monRows.filter((r) => monFilter === 'all' || r.cat === monFilter);
    if (!list.length) { wrap.innerHTML = '<div class="mon-empty">No log rows for this filter.</div>'; return; }
    wrap.innerHTML = list.slice(-40).map((r) =>
      `<div class="mrow"><span class="t">${esc(r.time)}</span><span class="tn">T${r.turn}</span><span class="ev is-${r.tone}">${esc(r.ev)}</span><span class="dt">${esc(r.detail)}</span></div>`).join('');
    wrap.scrollTop = wrap.scrollHeight;
  }
  // Fed every poll from the real {runner, account} snapshot (null = preview/idle).
  // Emits a preview-style granular event stream per turn: hp_check, the action
  // (train +stat-gain / race +placement / rest / rec), and fan_gain on race turns.
  function setMonitor(snap) {
    if (!monDock) return;
    const runner = (snap && snap.runner) || null;
    const ah = (runner && Array.isArray(runner.action_history)) ? runner.action_history : [];
    const races = {};
    ((runner && Array.isArray(runner.race_results)) ? runner.race_results : []).forEach((r) => { if (r && r.turn != null) races[r.turn] = r; });
    const built = [];
    let prev = null;
    ah.forEach((e) => {
      const turn = (e && e.turn) || 0;
      const time = (e && e.time) || '';
      const st = (e && e.stats) || {};
      const a = String((e && e.action) || '').toLowerCase();
      // 1) HP check
      if (st.hp != null) {
        const hp = Number(st.hp) || 0;
        const tag = hp <= 15 ? 'critical' : hp <= 35 ? 'low' : 'ok';
        built.push({ time, turn, ev: 'hp_check', detail: `${hp}/${st.max_hp || 100} (${tag})`,
          tone: hp <= 15 ? 'red' : hp <= 35 ? 'amber' : 'cyan', cat: 'gain' });
      }
      // 2) the action itself
      let ev, tone, cat, detail = monActionLabel(e);
      const rr = races[turn];
      if (a.indexOf('race') >= 0) {
        ev = 'race'; tone = 'amber'; cat = 'race';
        const place = rr && (rr.place || rr.rank);
        if (place) detail += ' · ' + monOrdinal(place);
      } else if (a === 'rest' || a === 'rest_summer') { ev = 'rest'; tone = 'cyan'; cat = 'gain'; }
      else if (a.indexOf('recreat') >= 0) { ev = 'recreation'; tone = 'purple'; cat = 'gain'; }
      else if (a === 'medic' || a === 'infirmary') { ev = 'medic'; tone = 'red'; cat = 'warn'; }
      else if (a === 'finish') { ev = 'finish'; tone = 'cyan'; cat = 'gain'; }
      else {
        ev = 'train'; tone = 'green'; cat = 'gain';
        const key = MON_STAT_KEY[String((e && e.facility) || '').trim()];
        if (key && prev && prev.stats && st[key] != null && prev.stats[key] != null) {
          const d = Number(st[key]) - Number(prev.stats[key]);
          if (d > 0) detail += ' · +' + d;
        }
      }
      built.push({ time, turn, ev, detail, tone, cat });
      // 3) fan gain — per-turn delta of the trainee's cumulative fans (covers races
      // AND other sources), falling back to the real race fans when present.
      let fanGain = 0;
      if (e && e.fans != null && prev && prev.fans != null) fanGain = Number(e.fans) - Number(prev.fans);
      if (fanGain <= 0 && rr && (rr.fans || rr.fan)) fanGain = Number(rr.fans || rr.fan);
      if (fanGain > 0) built.push({ time, turn, ev: 'fan_gain', detail: '+' + fmtCompact(fanGain), tone: 'green', cat: 'gain' });
      // 4) skills bought this turn -> "skill bought <name>"
      ((e && Array.isArray(e.skills)) ? e.skills : []).forEach((nm) => {
        if (nm) built.push({ time, turn, ev: 'skill', detail: 'bought ' + nm, tone: 'amber', cat: 'gain' });
      });
      prev = e;
    });
    ((runner && Array.isArray(runner.warnings)) ? runner.warnings : []).forEach((w) =>
      built.push({ time: '', turn: (runner && runner.turn) || 0, ev: 'warn',
        detail: typeof w === 'string' ? w : ((w && w.message) || ''), tone: 'amber', cat: 'warn' }));
    if (runner && runner.last_error)
      built.push({ time: '', turn: runner.turn || 0, ev: 'error', detail: String(runner.last_error), tone: 'red', cat: 'error' });
    monRows = built.slice(-120);
    const st = monDock.querySelector('#mon-status');
    if (st) st.textContent = runner
      ? `turn ${runner.turn || 0} · ${runner.running ? 'live' : runner.paused ? 'paused' : runner.finished ? 'done' : 'idle'}`
      : 'idle';
    if (monDock.classList.contains('open')) {
      monRenderRows();
      const ch = monDock.querySelector('#mon-chart');
      if (ch) ch.innerHTML = monChart((runner && runner.turn) || 0);
    }
  }

  function mountMonitor() {
    const tagged = document.querySelector('.monitor .monitor-tag');
    let dock = tagged ? tagged.closest('.monitor') : null;
    if (!dock) {
      const shell = document.querySelector('.console') || document.body;
      dock = document.createElement('div');
      dock.className = 'monitor';
      shell.appendChild(dock);
    }
    if (dock.dataset.dockReady) return;
    dock.dataset.dockReady = '1';
    dock.classList.add('mon-dock');
    if (localStorage.getItem('icarus_mon_open') === '1') dock.classList.add('open');
    dock.innerHTML = `
      <div class="mon-bar" role="button" tabindex="0" aria-label="Toggle monitor">
        <span class="monitor-tag"><span class="dot"></span>MONITOR</span>
        <div class="tab-spacer"></div>
        <span class="monitor-meta" id="mon-status">idle</span>
        <span class="mon-caret">\u25b4</span>
      </div>
      <div class="monitor-grid">
        <div class="monitor-log">
          <div class="monitor-log-head">
            <span class="monitor-log-title">LIVE LOG</span>
            <button class="fbtn is-active" type="button" data-f="all">ALL</button>
            <button class="fbtn" type="button" data-f="race">RACE</button>
            <button class="fbtn" type="button" data-f="gain">GAIN</button>
            <button class="fbtn" type="button" data-f="warn">WARN</button>
            <button class="fbtn" type="button" data-f="error">ERROR</button>
          </div>
          <div class="monitor-rows" id="mon-rows"></div>
        </div>
        <div class="monitor-stats">
          <div class="monitor-stats-head">
            <span class="monitor-log-title">STATS</span>
            <button class="fbtn" type="button" data-tab="trace">CRASH TRACE</button>
          </div>
          <div class="monitor-chart" id="mon-chart"></div>
        </div>
      </div>`;

    monDock = dock;
    const bar = dock.querySelector('.mon-bar');
    const toggle = () => {
      dock.classList.toggle('open');
      localStorage.setItem('icarus_mon_open', dock.classList.contains('open') ? '1' : '0');
      if (dock.classList.contains('open')) monRenderRows();
    };
    bar.addEventListener('click', toggle);
    bar.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(); } });

    dock.querySelectorAll('.fbtn[data-f]').forEach((b) => b.addEventListener('click', (e) => {
      e.stopPropagation();
      dock.querySelectorAll('.fbtn[data-f]').forEach((x) => x.classList.remove('is-active'));
      b.classList.add('is-active'); monFilter = b.dataset.f; monRenderRows();
    }));

    // Rows now come from the live poll via setMonitor(snap) \u2014 app.js refresh() on
    // the dashboard, pollChrome() on the other pages. Until the first real
    // snapshot lands the dock shows idle/empty, never a fabricated career.
    const st0 = dock.querySelector('#mon-status'); if (st0) st0.textContent = 'idle';
    monRenderRows();
  }

  // ============================================================
  //  ACCENT THEME  — cycled by clicking the ICARUS logo
  // ============================================================
  const THEMES = ['amber', 'cyan', 'emerald', 'violet', 'rose', 'ice'];
  function applyTheme(t) {
    if (!THEMES.includes(t)) t = 'amber';
    if (t === 'amber') document.documentElement.removeAttribute('data-theme');
    else document.documentElement.setAttribute('data-theme', t);
    localStorage.setItem('icarus_theme', t);
  }
  function bindTheme() {
    applyTheme(localStorage.getItem('icarus_theme') || 'amber');
    const brand = document.querySelector('.rail-brand');
    if (brand && !brand.dataset.themeBound) {
      brand.dataset.themeBound = '1';
      brand.title = 'Click to switch accent theme';
      brand.addEventListener('click', (e) => {
        e.preventDefault();
        const cur = localStorage.getItem('icarus_theme') || 'amber';
        applyTheme(THEMES[(THEMES.indexOf(cur) + 1) % THEMES.length]);
      });
    }
  }

  // ============================================================
  //  DISPLAY SETTINGS  — font size + selectable fonts
  //  The type scale lives in styles.css (:root --fs-* rungs); this layer just
  //  drives the global --fs-scale multiplier and overrides the three family
  //  vars (--sans/--cond/--mono). Both persist to localStorage and re-apply on
  //  every page in mountChrome(). Non-default fonts come from Google Fonts: a
  //  <link> is injected lazily only when picked. Offline, the system fallback
  //  baked into each var's stack is used instead.
  // ============================================================
  const FS_SCALES = { small: 0.9, normal: 1, large: 1.1, xlarge: 1.2 };
  const FS_LABELS = [['small', 'Small'], ['normal', 'Normal'], ['large', 'Large'], ['xlarge', 'X-Large']];
  // role -> [cssVar, [ [label, css font stack, google css2 family spec | ''] ... ]]
  // The FIRST entry in each list is the default (already loaded by the page <link>).
  const FONT_ROLES = {
    body: ['--sans', [
      ['IBM Plex Sans', "'IBM Plex Sans', system-ui, sans-serif", ''],
      ['Inter', "'Inter', system-ui, sans-serif", 'Inter:wght@400;500;600;700'],
      ['Roboto', "'Roboto', system-ui, sans-serif", 'Roboto:wght@400;500;700'],
      ['Open Sans', "'Open Sans', system-ui, sans-serif", 'Open+Sans:wght@400;500;600;700'],
      ['Lato', "'Lato', system-ui, sans-serif", 'Lato:wght@400;700'],
      ['Nunito Sans', "'Nunito Sans', system-ui, sans-serif", 'Nunito+Sans:wght@400;600;700'],
      ['Source Sans 3', "'Source Sans 3', system-ui, sans-serif", 'Source+Sans+3:wght@400;500;600;700'],
      ['Work Sans', "'Work Sans', system-ui, sans-serif", 'Work+Sans:wght@400;500;600;700'],
      ['Atkinson Hyperlegible', "'Atkinson Hyperlegible', system-ui, sans-serif", 'Atkinson+Hyperlegible:wght@400;700'],
      ['Merriweather', "'Merriweather', Georgia, serif", 'Merriweather:wght@400;700'],
      ['Lora', "'Lora', Georgia, serif", 'Lora:wght@400;500;600;700'],
      ['System UI', "system-ui, -apple-system, 'Segoe UI', sans-serif", ''],
    ]],
    head: ['--cond', [
      ['Barlow Condensed', "'Barlow Condensed', sans-serif", ''],
      ['Oswald', "'Oswald', sans-serif", 'Oswald:wght@400;500;600;700'],
      ['Roboto Condensed', "'Roboto Condensed', sans-serif", 'Roboto+Condensed:wght@400;500;700'],
      ['Archivo Narrow', "'Archivo Narrow', sans-serif", 'Archivo+Narrow:wght@400;500;600;700'],
      ['Saira Condensed', "'Saira Condensed', sans-serif", 'Saira+Condensed:wght@400;500;600;700'],
      ['Teko', "'Teko', sans-serif", 'Teko:wght@400;500;600;700'],
      ['Montserrat', "'Montserrat', sans-serif", 'Montserrat:wght@400;500;600;700'],
      ['Archivo', "'Archivo', sans-serif", 'Archivo:wght@400;500;600;700'],
    ]],
    num: ['--mono', [
      ['JetBrains Mono', "'JetBrains Mono', ui-monospace, monospace", ''],
      ['Roboto Mono', "'Roboto Mono', ui-monospace, monospace", 'Roboto+Mono:wght@400;500;700'],
      ['IBM Plex Mono', "'IBM Plex Mono', ui-monospace, monospace", 'IBM+Plex+Mono:wght@400;500;600;700'],
      ['Source Code Pro', "'Source Code Pro', ui-monospace, monospace", 'Source+Code+Pro:wght@400;500;600;700'],
      ['Space Mono', "'Space Mono', ui-monospace, monospace", 'Space+Mono:wght@400;700'],
      ['Inconsolata', "'Inconsolata', ui-monospace, monospace", 'Inconsolata:wght@400;500;600;700'],
      ['DM Mono', "'DM Mono', ui-monospace, monospace", 'DM+Mono:wght@400;500'],
      ['Fira Code', "'Fira Code', ui-monospace, monospace", 'Fira+Code:wght@400;500;700'],
    ]],
  };
  const APP_KEYS = { size: 'icarus_fs_scale', body: 'icarus_font_body', head: 'icarus_font_head', num: 'icarus_font_num' };

  function appPref(k, fallback) {
    try { return localStorage.getItem(APP_KEYS[k]) || fallback; } catch (e) { return fallback; }
  }
  function ensureFontLink(spec) {
    if (!spec) return;
    const id = 'gf-' + spec.replace(/[^a-z0-9]/gi, '');
    if (document.getElementById(id)) return;
    const l = document.createElement('link');
    l.id = id; l.rel = 'stylesheet';
    l.href = 'https://fonts.googleapis.com/css2?family=' + spec + '&display=swap';
    (document.head || document.documentElement).appendChild(l);
  }
  function applyFontScale(key) {
    document.documentElement.style.setProperty('--fs-scale', String(FS_SCALES[key] != null ? FS_SCALES[key] : 1));
  }
  function applyFont(role, label) {
    const def = FONT_ROLES[role];
    if (!def) return;
    const list = def[1];
    const entry = list.find((e) => e[0] === label) || list[0];
    document.documentElement.style.setProperty(def[0], entry[1]);
    if (entry !== list[0]) ensureFontLink(entry[2]);   // default is already in the page <link>
  }
  // Read every saved pref and apply it. Called at load (FOUC-min) and in mountChrome.
  function applyAppearance() {
    const size = appPref('size', 'normal');
    applyFontScale(FS_SCALES[size] != null ? size : 'normal');
    ['body', 'head', 'num'].forEach((role) => applyFont(role, appPref(role, FONT_ROLES[role][1][0][0])));
  }

  function openAppearanceModal() {
    const curSize = appPref('size', 'normal');
    const sizeLabel = (k) => (FS_LABELS.find((x) => x[0] === k) || FS_LABELS[1])[1];
    const sizeBtns = FS_LABELS.map(([k, t]) =>
      `<button class="segbtn${k === curSize ? ' on' : ''}" type="button" data-fs="${k}">${t}</button>`).join('');
    const fontField = (role, title, help) => {
      const list = FONT_ROLES[role][1];
      const cur = appPref(role, list[0][0]);
      const opts = list.map((e) => `<option value="${esc(e[0])}"${e[0] === cur ? ' selected' : ''}>${esc(e[0])}${e === list[0] ? ' (default)' : ''}</option>`).join('');
      return `<div class="field">
          <div class="field-label">${title}</div>
          <select class="self" data-font-role="${role}">${opts}</select>
          <div class="field-help">${help}</div>
        </div>`;
    };
    const curTheme = localStorage.getItem('icarus_theme') || 'amber';
    const themeBtns = THEMES.map((t) =>
      `<button class="segbtn${t === curTheme ? ' on' : ''}" type="button" data-theme-pick="${t}" style="text-transform:capitalize">${t}</button>`).join('');
    const body = `
      <div class="fsec">
        <div class="fsec-title">TEXT SIZE</div>
        <div class="field">
          <div class="field-label">Font size <span class="val" id="ap-size-val">${esc(sizeLabel(curSize))}</span></div>
          <div class="segrow" id="ap-size">${sizeBtns}</div>
          <div class="field-help">Scales every font in the interface at once. Applies instantly and is remembered on this device.</div>
        </div>
      </div>
      <div class="fsec">
        <div class="fsec-title">FONTS</div>
        ${fontField('body', 'Body font', 'Paragraphs, descriptions and help text.')}
        ${fontField('head', 'Heading font', 'Labels, titles and the navbar.')}
        ${fontField('num', 'Numeric font', 'Monospace for stats, IDs and data columns.')}
        <div class="field-help" style="margin-top:-4px">Fonts load from Google Fonts (needs internet). Offline, a system font is used instead.</div>
      </div>
      <div class="fsec">
        <div class="fsec-title">ACCENT THEME</div>
        <div class="field">
          <div class="segrow" id="ap-theme">${themeBtns}</div>
          <div class="field-help">Highlight colour (also cycles by clicking the ICARUS logo).</div>
        </div>
      </div>`;
    const o = modal({ title: 'DISPLAY', sub: 'appearance', body });
    o.querySelectorAll('#ap-size .segbtn').forEach((b) => b.addEventListener('click', () => {
      const k = b.dataset.fs;
      try { localStorage.setItem(APP_KEYS.size, k); } catch (e) { /* ignore */ }
      applyFontScale(k);
      const v = o.querySelector('#ap-size-val'); if (v) v.textContent = sizeLabel(k);
    }));
    o.querySelectorAll('select[data-font-role]').forEach((s) => s.addEventListener('change', () => {
      const role = s.dataset.fontRole;
      try { localStorage.setItem(APP_KEYS[role], s.value); } catch (e) { /* ignore */ }
      applyFont(role, s.value);
    }));
    o.querySelectorAll('#ap-theme .segbtn').forEach((b) => b.addEventListener('click', () => applyTheme(b.dataset.themePick)));
  }

  // Inject the DISPLAY button into the (every-page) .rail-toggles, left of LOGOUT.
  function mountAppearance() {
    applyAppearance();
    const host = document.querySelector('.rail-toggles');
    if (host && !document.getElementById('appearance-btn')) {
      const b = document.createElement('button');
      b.id = 'appearance-btn'; b.type = 'button'; b.className = 'tog tog-cog';
      b.title = 'Display settings — font size & fonts';
      b.innerHTML = 'DISPLAY' + COG;
      host.insertBefore(b, host.firstChild);
      b.addEventListener('click', openAppearanceModal);
    }
  }
  // Mount the DISPLAY button + apply saved size/fonts as early as core.js runs, on
  // EVERY page. The dashboard's app.js never calls mountChrome(), so relying on it
  // alone left the button missing there; doing it at module load fixes all pages.
  // Idempotent + guarded against a double-mount when a page also calls mountChrome().
  mountAppearance();

  // ============================================================
  //  STEAM LOGIN GATE
  //  Shown when the backend is reachable but no account session
  //  exists yet. Uses a RAW fetch (never the mock-fallback api())
  //  so a failed request can't be mistaken for a successful login.
  // ============================================================
  let _needs2fa = false;
  async function rawJson(url, opts) {
    const res = await fetch(url, opts);
    return res.json();
  }
  function _lgErr(msg) {
    const e = document.getElementById('lg-err');
    if (!e) return;
    e.textContent = msg || '';
    e.style.display = msg ? 'block' : 'none';
  }
  async function submitLogin() {
    const btn = document.getElementById('lg-btn');
    const user = document.getElementById('lg-user');
    const pass = document.getElementById('lg-pass');
    const code = document.getElementById('lg-code');
    if (!btn) return;
    btn.disabled = true; btn.textContent = 'WORKING…'; _lgErr('');
    const payload = { username: user.value.trim(), password: pass.value, code: code ? code.value.trim() : '' };
    try {
      const data = await rawJson('/api/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      if (data && data.needs_2fa) {
        _needs2fa = true;
        document.getElementById('lg-std').style.display = 'none';
        document.getElementById('lg-2fa').style.display = 'block';
        btn.textContent = 'VALIDATE';
        _lgErr('Steam Guard code required — check your authenticator.');
        if (code) code.focus();
      } else if (data && data.success) {
        try { localStorage.setItem('saved_username', payload.username); localStorage.setItem('saved_password', payload.password); } catch (e) { /* ignore */ }
        location.reload();
        return;
      } else {
        _lgErr((data && data.detail) || 'Login failed. Check your username and password.');
        if (data && data.cooldown_seconds) _cooldown(data.cooldown_seconds);
      }
    } catch (e) {
      _lgErr('Network error reaching the bot. Is the server still running?');
    }
    btn.disabled = false; btn.textContent = _needs2fa ? 'VALIDATE' : 'LOGIN';
  }
  function _cooldown(seconds) {
    const btn = document.getElementById('lg-btn');
    if (!btn) return;
    let n = Math.max(1, Math.floor(seconds));
    btn.disabled = true;
    const base = _needs2fa ? 'VALIDATE' : 'LOGIN';
    const t = setInterval(() => {
      btn.textContent = base + ' · ' + n + 's';
      if (--n < 0) { clearInterval(t); btn.disabled = false; btn.textContent = base; }
    }, 1000);
  }
  function showLoginOverlay() {
    if (document.getElementById('login-overlay')) return;
    const fld = 'width:100%;background:var(--card);border:1px solid var(--line-card);border-radius:5px;color:var(--ink);font:500 var(--fs-lg) var(--mono);padding:11px 13px;margin-bottom:13px;outline:none';
    const lbl = 'display:block;font:600 var(--fs-xs) var(--cond);letter-spacing:.16em;color:var(--label);margin-bottom:6px';
    const ov = document.createElement('div');
    ov.id = 'login-overlay';
    ov.style.cssText = 'position:fixed;inset:0;z-index:99999;background:radial-gradient(circle at 50% 28%,#0c0f15,#050608 70%);display:flex;align-items:center;justify-content:center;padding:20px';
    ov.innerHTML = `
      <div style="width:380px;max-width:92vw;background:var(--bar);border:1px solid var(--line-card);border-radius:8px;padding:30px 28px;box-shadow:0 30px 90px rgba(0,0,0,.7)">
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:5px"><span style="width:11px;height:11px;background:var(--amber);transform:rotate(45deg)"></span><span style="font:700 var(--fs-4xl) var(--cond);letter-spacing:.22em;color:#fff">ICARUS</span></div>
        <div style="font:500 var(--fs-sm) var(--mono);color:var(--label);letter-spacing:.14em;margin-bottom:24px">STEAM LOGIN</div>
        <div id="lg-std">
          <label style="${lbl}">USERNAME</label>
          <input id="lg-user" type="text" autocomplete="username" style="${fld}">
          <label style="${lbl}">PASSWORD</label>
          <input id="lg-pass" type="password" autocomplete="current-password" style="${fld}">
        </div>
        <div id="lg-2fa" style="display:none">
          <label style="${lbl}">STEAM GUARD CODE</label>
          <input id="lg-code" type="text" inputmode="text" autocomplete="one-time-code" maxlength="7" style="${fld};letter-spacing:.3em;text-transform:uppercase">
        </div>
        <div id="lg-err" style="display:none;font:500 var(--fs-sm)/1.5 var(--mono);color:var(--red);background:#1a0c0c;border:1px solid var(--red-bd);border-radius:4px;padding:9px 11px;margin-bottom:13px"></div>
        <button id="lg-btn" type="button" style="width:100%;background:var(--amber);border:none;border-radius:5px;color:var(--panel);font:700 var(--fs-base) var(--cond);letter-spacing:.16em;padding:13px;cursor:pointer">LOGIN</button>
        <div style="font:500 var(--fs-xs)/1.6 var(--mono);color:var(--dim);margin-top:16px;text-align:center">Drives the real Steam client. Credentials are sent only to your local bot, never elsewhere.</div>
      </div>`;
    document.body.appendChild(ov);
    const user = document.getElementById('lg-user');
    const pass = document.getElementById('lg-pass');
    try {
      user.value = localStorage.getItem('saved_username') || '';
      pass.value = localStorage.getItem('saved_password') || '';
    } catch (e) { /* ignore */ }
    document.getElementById('lg-btn').addEventListener('click', submitLogin);
    ov.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); submitLogin(); } });
    (user.value ? pass : user).focus();
  }
  async function ensureAuth() {
    let sess = null;
    try {
      const res = await fetch('/api/session?t=' + Date.now());
      sess = await res.json();
    } catch (e) {
      return; // backend unreachable → preview/mock mode, no login gate
    }
    if (sess && sess.success) return; // already logged in
    showLoginOverlay();
  }
  function wireLogout() {
    const btn = document.getElementById('logout-btn');
    if (!btn || btn.dataset.bound) return;
    btn.dataset.bound = '1';
    btn.addEventListener('click', async () => {
      try { await fetch('/api/logout', { method: 'POST' }); } catch (e) { /* ignore */ }
      location.reload();
    });
  }

  function mountChrome() {
    bindTheme();
    mountAppearance();
    bindDevToggles();
    mountMonitor();
    wireLogout();
    ensureAuth();
    pollChrome();
    setInterval(pollChrome, 1500);
  }

  // ============================================================
  //  MODALS  — shared overlay + auto-wired controls
  // ============================================================
  function closeModal() {
    const all = document.querySelectorAll('.modal-overlay');
    const o = all[all.length - 1];
    if (o) o.remove();
    if (!document.querySelector('.modal-overlay')) document.removeEventListener('keydown', escClose);
  }
  // Esc defers to the topmost overlay's close guard (e.g. settings modals with
  // unsaved changes); overlays without a guard close immediately as before.
  function escClose(e) {
    if (e.key !== 'Escape') return;
    const all = document.querySelectorAll('.modal-overlay');
    const top = all[all.length - 1];
    if (top && typeof top._guardClose === 'function') top._guardClose(closeModal);
    else closeModal();
  }

  function modal(opts) {
    closeModal();
    const o = document.createElement('div');
    o.className = 'modal-overlay';
    o.innerHTML = `
      <div class="modal${opts.wide ? ' wide' : ''}${opts.full ? ' full' : ''}" role="dialog" aria-modal="true">
        <div class="modal-head">
          <span class="modal-mark"></span>
          <span class="modal-title">${esc(opts.title || '')}</span>
          ${opts.sub ? `<span class="modal-sub">· ${esc(opts.sub)}</span>` : ''}
          <button class="modal-x" type="button" data-close>${esc(opts.closeLabel || 'DONE')}</button>
        </div>
        <div class="modal-body">${opts.body || ''}</div>
        ${opts.foot ? `<div class="modal-foot">${opts.foot}</div>` : ''}
      </div>`;
    document.body.appendChild(o);
    // All close paths (DONE/X, backdrop, Esc) route through attemptClose so a
    // modal can install o._guardClose (see modals.js wireSave) to intercept a
    // close when there are unsaved changes. No guard => closes as before.
    const attemptClose = () => { if (typeof o._guardClose === 'function') o._guardClose(closeModal); else closeModal(); };
    o.addEventListener('mousedown', (e) => { if (e.target === o) attemptClose(); });
    o.querySelectorAll('[data-close]').forEach((b) => b.addEventListener('click', attemptClose));
    document.addEventListener('keydown', escClose);
    wireControls(o);
    if (opts.onMount) opts.onMount(o);
    return o;
  }

  // auto-wire interactive controls inside a root (sliders, toggles, segmented, chips, drag-priority)
  function wireControls(root) {
    // sliders -> live value label (data-val = id of label span, data-suffix optional)
    root.querySelectorAll('.rng[data-val]').forEach((r) => {
      const out = root.querySelector('#' + r.dataset.val);
      const upd = () => { if (out) out.textContent = r.value + (r.dataset.suffix || ''); };
      r.addEventListener('input', upd); upd();
    });
    // toggles
    root.querySelectorAll('.tgl').forEach((t) => t.addEventListener('click', () => t.classList.toggle('on')));
    // single-select segmented groups
    root.querySelectorAll('.segrow').forEach((g) => {
      if (g.dataset.multi === '1') return;
      g.querySelectorAll('.segbtn').forEach((b) => b.addEventListener('click', () => {
        g.querySelectorAll('.segbtn').forEach((x) => x.classList.remove('on'));
        b.classList.add('on');
      }));
    });
    // multi-select chips
    root.querySelectorAll('.chiptog').forEach((c) => c.addEventListener('click', () => c.classList.toggle('on')));
    // drag-reorder priority lists
    root.querySelectorAll('.prio').forEach(wirePrio);
  }

  function wirePrio(list) {
    let dragging = null;
    const renumber = () => list.querySelectorAll('.prio-item').forEach((it, i) => {
      const r = it.querySelector('.prio-rank'); if (r) r.textContent = i + 1;
    });
    list.querySelectorAll('.prio-item').forEach((it) => {
      it.setAttribute('draggable', 'true');
      it.addEventListener('dragstart', () => { dragging = it; it.classList.add('dragging'); });
      it.addEventListener('dragend', () => { it.classList.remove('dragging'); dragging = null; renumber(); });
      it.addEventListener('dragover', (e) => {
        e.preventDefault();
        if (!dragging || dragging === it) return;
        const rect = it.getBoundingClientRect();
        const after = e.clientY > rect.top + rect.height / 2;
        list.insertBefore(dragging, after ? it.nextSibling : it);
      });
    });
  }

  return {
    api, fmtNum, fmtCompact, fmtDur, pad2, esc,
    get isMock() { return mockMode; },
    onPoll: (fn) => listeners.push(fn),
    mountChrome, mountMonitor, modal, closeModal, wireControls, bindDevExtras, bindTheme,
    openAppearanceModal, mountAppearance, applyAppearance,
    ensureAuth, wireLogout,
    getRecoveryMode, setRecoveryMode, recoveryPill, careerPillHtml,
    devConfig,   // exposed so the dashboard run payload can read the RETRIES popover config
    devToggles,        // shared single source of truth for the navbar dev toggles
    persistToggles,    // app.js calls this after flipping a shared toggle
    persistRetries,    // app.js / popovers persist the retries config (BUG #7)
    loopLabel, nextLoopCount,   // LOOP run-count cycle, shared with the dashboard (BUG #6)
    setMonitor,        // feed the bottom MONITOR dock real rows from a live snapshot
    renderLifetime,    // bordered lifetime metrics in the navbar (fed the raw runner)
    applyTraineeTheme, clearTraineeTheme,   // recolour the accent to the active trainee
  };
})();
