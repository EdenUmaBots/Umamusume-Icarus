/* ============================================================
   ICARUS · Command Console (v3) — dashboard logic
   Vanilla, no build step. Talks to the SAME API as the old UI
   (GET /api/career/runner every 1.5s). When the backend is not
   reachable, api() returns null, the OFFLINE banner shows, and the
   last render is kept (empty/idle on first load). No simulated data.
   Start `python main.py` and the real data takes over.
   ============================================================ */
(() => {
  'use strict';

  // ---------- tiny helpers ----------
  const $ = (id) => document.getElementById(id);
  const el = (tag, cls, html) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (html != null) n.innerHTML = html;
    return n;
  };
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const fmtNum = (n) => (Number(n) || 0).toLocaleString('en-US');
  const fmtCompact = (n) => {
    n = Number(n) || 0;
    if (n >= 1e9) return (n / 1e9).toFixed(1).replace(/\.0$/, '') + 'B';
    if (n >= 1e6) return (n / 1e6).toFixed(1).replace(/\.0$/, '') + 'M';
    if (n >= 1e3) return (n / 1e3).toFixed(1).replace(/\.0$/, '') + 'K';
    return String(n);
  };
  const pad2 = (n) => String(n).padStart(2, '0');
  const hpTone = (hp) => hp <= 15 ? 'red' : hp <= 35 ? 'amber' : 'green';

  // ---------- runtime state ----------
  const state = {
    runner: null,
    account: null,
    reasonTab: 'decision',
    logHist: {},      // turn -> action row  (accumulated archive)
    reasonHist: {},   // turn -> decision card (accumulated archive)
    devToggles: { tempt: false, burn: false, loop: false, finish: false },
  };

  // ============================================================
  //  API LAYER — real fetch; returns null when the backend is unreachable.
  // ============================================================
  async function api(url, opts = {}) {
    try {
      const ctrl = new AbortController();
      // 12s (not 4s): a real career's /api/career/runner snapshot (up to 300
      // action_history rows, ~50-250KB) can take several seconds to fetch+parse
      // on the first poll or modest hardware. A 4s abort wrongly tripped mock.
      const timer = setTimeout(() => ctrl.abort(), 12000);
      const res = await fetch(url, { ...opts, signal: ctrl.signal });
      clearTimeout(timer);
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const json = await res.json();
      const mb = $('mockbar'); if (mb) mb.classList.remove('show');
      return json;
    } catch (e) {
      // Backend unreachable / transient failure → show the offline notice and
      // return null. No simulated data is ever produced; callers keep the last
      // render (or render an empty/idle state on first load).
      const mb = $('mockbar'); if (mb) mb.classList.add('show');
      return null;
    }
  }

  // ============================================================
  //  RENDER
  // ============================================================
  // Free race-retry continue readout for the navbar. Shows the live free-continue
  // count and, when the free pool is empty, an ESTIMATED next-refresh countdown
  // (free continues refresh daily; free_continue_time is the daily stamp, rolled
  // forward to the next future occurrence). Data comes from the live career's
  // home_info via the runner status (runner.clocks); hidden until a career sets it.
  function freeClockPill() {
    const rc = (state.runner && state.runner.clocks) || null;
    if (!rc || !rc.seen) return '';
    let suffix = '';
    if (rc.free <= 0 && rc.refreshAt > 0) {
      let target = rc.refreshAt;
      const now = Date.now() / 1000;
      while (target <= now) target += 86400;   // daily refresh; roll to the next one
      const secs = target - now;
      const h = Math.floor(secs / 3600), m = Math.floor((secs % 3600) / 60);
      suffix = `<span class="sub"> ~${h}h${String(m).padStart(2, '0')}</span>`;
    }
    const tone = rc.free > 0 ? ' is-amber' : ' is-dim';
    const title = `Free race-retry continues (refresh daily). Free now: ${rc.free}, standard clocks: ${rc.std}.`
      + (suffix ? ' The ~time is the estimated next daily free refresh.' : '');
    return `<div class="pill" title="${title}"><div class="pill-k">FREE CLK</div><div class="pill-v${tone}">${rc.free}${suffix}</div></div>`;
  }

  function renderPills(account) {
    const host = $('rail-pills');
    if (!host) return;
    // Don't rebuild the rail while the user is interacting with the native
    // TP-recovery <select>: the dashboard runs THIS renderPills (not core.js's
    // guarded copy) on the 1.5s poll, and the innerHTML rebuild was collapsing
    // the open dropdown mid-hover. Skip the rebuild while it's focused/open.
    const ae = document.activeElement;
    if (ae && ae.classList && ae.classList.contains('recov-sel') && host.contains(ae)) return;
    const tp = account.tp || {};
    const c = account.carrots || {};
    const html = `
      <div class="pill"><div class="pill-k">TP</div><div class="pill-v">${pad2(tp.current || 0)}<span class="sub">/${tp.max || 0}</span></div></div>
      ${window.Icarus && Icarus.recoveryPill ? Icarus.recoveryPill() : ''}
      <div class="pill"><div class="pill-k">CARROTS</div><div class="pill-v is-amber">${fmtNum(c.total)}</div></div>
      <div class="pill"><div class="pill-k">GOLD</div><div class="pill-v">${fmtCompact(account.gold)}</div></div>
      <div class="pill"><div class="pill-k">CLOCKS</div><div class="pill-v">${fmtNum(account.clocks)}</div></div>
      ${freeClockPill()}
      ${window.Icarus && Icarus.careerPillHtml ? Icarus.careerPillHtml(account.career) : ''}`;
    host.innerHTML = html;
  }

  function renderVitals(runner) {
    const t = runner.trainee || {};
    $('trainee-name').textContent = t.name || 'NO CAREER';
    $('trainee-meta').textContent = `${t.scenario || '—'} · ${t.rank || ''} · T${runner.turn || 0}`.replace(' ·  ·', ' ·');
    $('portrait-live').innerHTML = runner.running ? '◷ live' : '◷ idle';
    $('portrait-live').className = 'portrait-live ' + (runner.running ? 'c-cyan' : 'c-mut');

    const hp = runner.hp ?? 0;
    const tone = hpTone(hp);
    const hpLabel = $('hp-label');
    hpLabel.textContent = tone === 'red' ? 'HP · CRITICAL' : tone === 'amber' ? 'HP · LOW' : 'HP';
    hpLabel.className = 'hp-label ' + (tone === 'red' ? 'c-red' : tone === 'amber' ? 'c-amber' : 'c-mut');
    $('hp-num').innerHTML = `${pad2(runner.hpRaw ?? hp)}<span class="sub">/${runner.hpMax ?? 100}</span>`;
    const fill = $('hp-fill');
    fill.style.width = hp + '%';
    fill.className = 'hp-fill fill-' + tone;
    if (tone === 'red') fill.style.animation = 'critpulse 1.1s infinite'; else fill.style.animation = '';

    const mood = runner.mood || {};
    const mv = $('mood-v');
    mv.textContent = mood.label ? `${mood.label} · ${mood.value}` : '—';
    mv.className = 'kv-v c-' + (mood.tone || 'mut');
    $('fans-v').textContent = fmtCompact(runner.fans || 0);

    const list = $('attr-list');
    list.innerHTML = '';
    (runner.stats || []).forEach((s) => {
      const pct = Math.min(100, Math.round((s.v / (s.max || 600)) * 100));
      const accent = s.accent ? 'amber' : (pct >= 70 ? 'green' : null);
      const row = el('div', 'attr');
      row.innerHTML = `
        <span class="attr-k${s.accent ? ' c-amber' : ''}">${s.k}</span>
        <div class="attr-track"><div class="attr-bar${accent ? ' fill-' + accent : ''}" style="width:${pct}%"></div></div>
        <span class="attr-v${s.accent ? ' c-amber' : (pct >= 70 ? ' c-green' : '')}">${s.v}</span>`;
      list.appendChild(row);
    });

    // Lifetime metrics now live in the navbar (Icarus.renderLifetime), not here.
  }

  function renderLog(runner) {
    // accumulate every turn we see — never drop earlier turns
    (runner.action_rows || []).forEach((r) => { if (r && r.turn != null) state.logHist[r.turn] = r; });
    const rows = Object.values(state.logHist).sort((a, b) => a.turn - b.turn);
    $('feed-meta').textContent = `${rows.length} TURN${rows.length === 1 ? '' : 'S'} · ${runner.running ? 'LIVE' : 'IDLE'}`;
    const wrap = $('log-rows');
    const stick = wrap.scrollTop + wrap.clientHeight >= wrap.scrollHeight - 4;      // following live → keep pinned to newest (bottom)
    const prev = wrap.scrollTop;
    wrap.innerHTML = '';
    rows.forEach((r, i) => {
      const tone = hpTone(r.hp);
      const row = el('div', 'log-row' + (i === 0 ? ' is-current' : ''));
      const hpTxt = r.hpDelta ? r.hpDelta : pad2(r.hp);
      const hpClr = r.hpDelta ? 'green' : tone;
      row.innerHTML = `
        <span class="log-turn">${r.turn}</span>
        <span class="log-act"><span class="rcard-badge bg-${r.actTone}">${r.act}</span></span>
        <span class="log-target${r.act === 'REST' || r.act === 'REC' ? ' is-mut' : ''}">${esc(r.target)}</span>
        <span class="log-hp r c-${hpClr}">${hpTxt}</span>
        <span class="log-mood r">${r.mood ?? '—'}</span>`;
      wrap.appendChild(row);
    });
    wrap.scrollTop = stick ? wrap.scrollHeight : prev;
  }

  // ---- Shop-item icons (game8 source), keyed by the in-game item name as it
  //      appears in decision-reasoning text. Served from /api/item-icons/<id>.<ext>.
  //      Ported from the old UI so the Decision Reasoning panel shows item icons. ----
  const ITEM_ICON_MAP = {
    'Speed Notepad': '/api/item-icons/1001.jpg', 'Stamina Notepad': '/api/item-icons/1002.png',
    'Power Notepad': '/api/item-icons/1003.png', 'Guts Notepad': '/api/item-icons/1004.png',
    'Wit Notepad': '/api/item-icons/1005.png',
    'Speed Manual': '/api/item-icons/1101.png', 'Stamina Manual': '/api/item-icons/1102.png',
    'Power Manual': '/api/item-icons/1103.png', 'Guts Manual': '/api/item-icons/1104.png',
    'Wit Manual': '/api/item-icons/1105.jpg',
    'Speed Scroll': '/api/item-icons/1201.png', 'Stamina Scroll': '/api/item-icons/1202.png',
    'Power Scroll': '/api/item-icons/1203.jpg', 'Guts Scroll': '/api/item-icons/1204.png',
    'Wit Scroll': '/api/item-icons/1205.png',
    'Vita 20': '/api/item-icons/2001.png', 'Vita 40': '/api/item-icons/2002.png',
    'Vita 65': '/api/item-icons/2003.png', 'Royal Kale Juice': '/api/item-icons/2101.png',
    'Energy Drink MAX': '/api/item-icons/2201.png', 'Energy Drink MAX EX': '/api/item-icons/2202.png',
    'Plain Cupcake': '/api/item-icons/2301.jpg', 'Berry Sweet Cupcake': '/api/item-icons/2302.png',
    'Yummy Cat Food': '/api/item-icons/3001.png', 'Grilled Carrots': '/api/item-icons/3101.jpg',
    'Pretty Mirror': '/api/item-icons/4001.jpg', "Reporter's Binoculars": '/api/item-icons/4002.png',
    'Master Practice Guide': '/api/item-icons/4003.png', "Scholar's Hat": '/api/item-icons/4004.png',
    'Fluffy Pillow': '/api/item-icons/4101.png', 'Pocket Planner': '/api/item-icons/4102.png',
    'Rich Hand Cream': '/api/item-icons/4103.png', 'Smart Scale': '/api/item-icons/4104.png',
    'Aroma Diffuser': '/api/item-icons/4105.png', 'Practice Drills DVD': '/api/item-icons/4106.png',
    'Miracle Cure': '/api/item-icons/4201.png',
    'Speed Training Application': '/api/item-icons/5001.png', 'Stamina Training Application': '/api/item-icons/5002.png',
    'Power Training Application': '/api/item-icons/5003.png', 'Guts Training Application': '/api/item-icons/5004.png',
    'Wit Training Application': '/api/item-icons/5005.png',
    'Reset Whistle': '/api/item-icons/7001.png',
    'Coaching Megaphone': '/api/item-icons/8001.png', 'Motivating Megaphone': '/api/item-icons/8002.png',
    'Empowering Megaphone': '/api/item-icons/8003.png',
    'Speed Ankle Weights': '/api/item-icons/9001.png', 'Stamina Ankle Weights': '/api/item-icons/9002.png',
    'Power Ankle Weights': '/api/item-icons/9003.png', 'Guts Ankle Weights': '/api/item-icons/9004.png',
    'Good-Luck Charm': '/api/item-icons/10001.png',
    'Artisan Cleat Hammer': '/api/item-icons/11001.png', 'Master Cleat Hammer': '/api/item-icons/11002.png',
    'Glow Sticks': '/api/item-icons/11003.png',
  };
  let _itemIconRegex = null;
  const _itemIconByEscaped = {};
  function _ensureItemIconRegex() {
    if (_itemIconRegex) return;
    const names = Object.keys(ITEM_ICON_MAP).sort((a, b) => b.length - a.length); // longest-first
    const alts = names.map((n) => {
      const e = esc(n);
      _itemIconByEscaped[e] = { name: n, path: ITEM_ICON_MAP[n] };
      return e.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    });
    _itemIconRegex = new RegExp('(' + alts.join('|') + ')', 'g');
  }
  // Prepend each shop item's icon before its name in already-esc'd reason text.
  function decorateItemIcons(escapedText) {
    if (!escapedText) return escapedText;
    _ensureItemIconRegex();
    return escapedText.replace(_itemIconRegex, (m) => {
      const hit = _itemIconByEscaped[m];
      if (!hit) return m;
      return `<img class="reason-item-icon" src="${hit.path}" alt="" title="${m}" loading="lazy" onerror="this.style.display='none'">${m}`;
    });
  }
  function itemChip(name) {
    const path = ITEM_ICON_MAP[name];
    const icon = path ? `<img class="reason-item-icon" src="${path}" alt="" loading="lazy" onerror="this.style.display='none'">` : '';
    return `<span class="chip">${icon}${esc(name)}</span>`;
  }

  function renderReasoning(runner) {
    // accumulate every decision card we see (do this even on the profile tab)
    (runner.reasoning || []).forEach((r) => { if (r && r.turn != null) state.reasonHist[r.turn] = r; });
    const body = $('reason-body');
    const cards = Object.values(state.reasonHist).sort((a, b) => a.turn - b.turn);
    const stick = body.scrollTop + body.clientHeight >= body.scrollHeight - 4;
    const prev = body.scrollTop;
    body.innerHTML = '';
    cards.forEach((r, i) => {
      const fromEnd = (cards.length - 1) - i;   // 0 = most recent turn
      const cls = fromEnd === 0 ? 'is-current' : fromEnd <= 2 ? 'is-faded' : 'is-dim';
      const card = el('div', 'rcard ' + cls);
      const items = (r.items && r.items.length)
        ? `<div class="rcard-items"><span class="k">ITEMS</span>${r.items.map((it) => itemChip(it)).join('')}</div>` : '';
      const turnCls = fromEnd === 0 ? 'is-amber' : 'is-mut';
      const mutCls = fromEnd !== 0 ? ' is-mut' : '';
      // Per-turn reasoning as bullet points (a clean single <p> when there's just one line).
      const lines = (r.lines && r.lines.length) ? r.lines : (r.text ? [r.text] : []);
      const bodyHtml = lines.length > 1
        ? `<ul class="rcard-lines${mutCls}">${lines.slice(0, 6).map((l) => `<li>${decorateItemIcons(esc(l))}</li>`).join('')}</ul>`
        : `<p class="rcard-text${mutCls}">${decorateItemIcons(esc(lines[0] || ''))}</p>`;
      card.innerHTML = `
        <div class="rcard-head">
          <span class="rcard-turn ${turnCls}">${esc(r.title)}</span>
          <span class="rcard-badge bg-${r.badgeBg}">${esc(r.badge)}</span>
        </div>
        ${r.sub ? `<div class="rcard-sub">${esc(r.sub)}</div>` : ''}
        ${bodyHtml}
        ${items}`;
      body.appendChild(card);   // outer #reason-body DOM node (was shadowed by the html string)
    });
    body.scrollTop = stick ? body.scrollHeight : prev;
  }

  function renderMonitor(runner) {
    $('monitor-meta').textContent = `turn ${runner.turn || 0} · ${runner.running ? 'live' : 'idle'}`;
    const wrap = $('monitor-rows');
    wrap.innerHTML = '';
    (runner.monitor || []).forEach((m) => {
      const row = el('div', 'mrow');
      row.innerHTML = `<span class="t">${m.time}</span><span class="tn">T${m.turn}</span><span class="ev is-${m.evTone}">${esc(m.ev)}</span><span class="dt">${esc(m.detail)}</span>`;
      wrap.appendChild(row);
    });
    const legend = $('stat-legend');
    if (!legend.childElementCount && runner.stats) {
      const colors = { SPD: '#36c5d0', STA: '#4ade80', PWR: '#f04444', GUT: '#c084fc', SP: '#f2a900' };
      legend.innerHTML = runner.stats.filter((s) => colors[s.k]).map((s) =>
        `<span><span class="swatch" style="background:${colors[s.k]}"></span>${s.k} ${s.v}</span>`).join('');
    }
  }

  function renderLive(runner) {
    const live = $('tab-live');
    const txt = $('tab-live-text');
    live.className = 'tab-live ' + (runner.running ? '' : runner.paused ? 'is-paused' : 'is-idle');
    txt.textContent = runner.status_text || (runner.running ? 'RUNNING' : 'IDLE');

    const running = runner.running, paused = runner.paused;
    $('run-btn').disabled = running;
    $('run-btn').textContent = runner.finished ? 'RUN AGAIN' : 'RUN CAREER';
    $('stop-btn').disabled = !running && !paused;
    $('pause-btn').disabled = !running && !paused;
    $('pause-btn').textContent = paused ? 'RESUME' : 'PAUSE';
  }

  function render(snap) {
    if (!snap || !snap.runner) return;
    state.runner = snap.runner;
    state.account = snap.account;
    if (snap.account) renderPills(snap.account);
    renderVitals(snap.runner);
    renderLog(snap.runner);
    renderReasoning(snap.runner);
    renderLive(snap.runner);
  }

  // ============================================================
  //  REAL-BACKEND ADAPTER
  //  Maps the live /api/career/runner payload ({success, runner,
  //  account}) into the view-model the redesign renders. Live state
  //  is in runner.current_chara; per-turn rows in runner.action_history;
  //  mood is motivation 1-5; lifetime in runner.lifetime.
  // ============================================================
  function fmtDur(s) {
    s = Number(s) || 0;
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
    if (h) return h + 'h ' + m + 'm';
    if (m) return m + 'm';
    return (s | 0) + 's';
  }
  const MOOD_MAP = { 5: ['Great', 'green'], 4: ['Good', 'green'], 3: ['Normal', 'cyan'], 2: ['Bad', 'amber'], 1: ['Awful', 'red'] };
  // Live status carries scenario_id (int), not a label; this bot runs Trackblazer (4).
  const SCENARIO_MAP = { 4: 'TRACKBLAZER' };
  function moodFromMotivation(m) {
    const e = MOOD_MAP[Number(m)] || ['—', 'mut'];
    return { label: e[0], value: Number(m) || '', tone: e[1] };
  }
  // Tones match the preview/mock: TRAIN green, RACE amber, REST cyan, REC purple.
  const ACT_META = {
    train: ['TRAIN', 'green'], rest: ['REST', 'cyan'], recreation: ['REC', 'purple'],
    recreate: ['REC', 'purple'], race: ['RACE', 'amber'], race_progress: ['RACE', 'amber'],
    finish: ['FINISH', 'green'], medic: ['MEDIC', 'red'], infirmary: ['MEDIC', 'red'],
    rest_summer: ['REST', 'cyan'],
  };
  function actMeta(a) {
    a = String(a || '').toLowerCase();
    return ACT_META[a] || [(a.toUpperCase().slice(0, 6)) || '—', 'mut'];
  }
  const FAC_MAP = { '101': 'Speed', '102': 'Stamina', '103': 'Power', '104': 'Guts', '105': 'Wit' };
  // Live action rows put a stat summary (HP 80/100 | MOOD 4 | SPD … ) in `detail`,
  // which must never be used as a human label or reasoning sentence.
  const isStatDump = (s) => /^\s*HP\s*\d/i.test(String(s || '')) || /\bSPD\s*\d+\s*STA\s*\d+/i.test(String(s || ''));
  const cleanDetail = (r) => { const d = r && r.detail; return (d && !isStatDump(d)) ? d : ''; };
  function facLabel(r) {
    const a = String(r.action || '').toLowerCase();
    const fac = String(r.facility || '').trim();
    const numeric = /^\d+$/.test(fac);
    // race: facility holds the race label (e.g. "Satsuki Sho \u00b7 G1 \u00b7 2000m \u00b7 Turf").
    if (a === 'race' || a === 'race_progress') return fac || cleanDetail(r) || r.race_name || r.name || 'Race';
    // train: facility is ALREADY the stat name ("Speed"/"Stamina"/...) from the
    // backend's TRAINING_LABELS \u2014 so use it directly ("Speed training"), matching
    // the preview, instead of wrapping it as "Facility Speed Training".
    if (a === 'train') {
      if (fac && !numeric) return fac + ' training';
      return (FAC_MAP[fac] ? FAC_MAP[fac] + ' training' : 'Training');
    }
    if (a === 'rest' || a === 'rest_summer') return 'Rest';
    if (a === 'recreation' || a === 'recreate') return 'Recreation';
    if (a === 'medic' || a === 'infirmary') return 'Infirmary';
    if (a === 'finish') return cleanDetail(r) || 'Career Finished';
    return cleanDetail(r) || (fac && !numeric ? fac : (FAC_MAP[fac] ? FAC_MAP[fac] + ' training' : 'Action'));
  }
  // Small category label under each decision card's title (preview style).
  function subFor(a) {
    a = String(a || '').toLowerCase();
    if (a === 'train') return 'GOAL-AWARE SCORER';
    if (a === 'race' || a === 'race_progress') return 'SMART RACE SOLVER';
    if (a === 'rest' || a === 'rest_summer') return 'ENERGY GUARD';
    if (a === 'recreation' || a === 'recreate') return 'MOOD GUARD';
    if (a === 'medic' || a === 'infirmary') return 'INFIRMARY';
    if (a === 'finish') return 'CAREER';
    return '';
  }
  // Per-action reasoning sentence when the live row carries no `reasoning` lines,
  // so cards read like the design instead of dumping the stat summary.
  function reasonFor(r) {
    const a = String(r.action || '').toLowerCase();
    if (a === 'train') return 'Highest goal-weighted training score this turn — support bonuses and mood factored in.';
    if (a === 'race' || a === 'race_progress') return 'Selected by the Smart Race Solver for value on the planned route.';
    if (a === 'rest' || a === 'rest_summer') return 'Energy below threshold — rested to protect HP before the next cluster.';
    if (a === 'recreation' || a === 'recreate') return 'Recreation chosen to lift mood before the next training cluster.';
    if (a === 'medic' || a === 'infirmary') return 'Treated to clear a negative condition before it compounded.';
    if (a === 'finish') return 'Career complete.';
    return 'Highest-scoring action available this turn.';
  }

  function adaptReal(data) {
    const runner = (data && data.runner) || {};
    const account = (data && data.account) || null;
    const cur = runner.current_chara || {};
    const ah = Array.isArray(runner.action_history) ? runner.action_history : [];
    const last = ah.length ? ah[ah.length - 1] : null;
    const lastStats = (last && last.stats) || {};
    const cs = Object.keys(cur.stats || {}).length ? cur.stats : lastStats;

    const hpNow = Number(cur.vital ?? lastStats.hp ?? 0);
    const hpMax = Number(cur.max_vital ?? lastStats.max_hp ?? 100) || 100;
    const motivation = cur.motivation ?? lastStats.motivation;
    const hasCareer = !!(cur.turn || ah.length || runner.running || runner.finished || runner.paused);

    const sRow = (k, key, accent, max) => ({ k, v: Number(cs[key] || 0), max: max || 1200, accent: !!accent });
    // SP (skill points) can live on the chara top-level OR in either stats dict.
    const skillPoints = Number(cur.skill_point ?? cs.skill_point ?? lastStats.skill_point ?? 0);
    const stats = [
      sRow('SPD', 'speed', true), sRow('STA', 'stamina'), sRow('PWR', 'power'),
      sRow('GUT', 'guts'), sRow('WIT', 'wit'),
      // Skill Points row (preview style): bar + number, amber. SP is a spendable
      // resource so the bar is scaled to a soft 700 cap (the number is the truth).
      { k: 'SP', v: skillPoints, max: 700, accent: true },
    ];

    const action_rows = ah.map((r) => {
      const meta = actMeta(r.action);
      const st = r.stats || {};
      return {
        turn: r.turn, act: meta[0], actTone: meta[1],
        target: facLabel(r),
        hp: Number(st.hp ?? 0),
        mood: st.motivation != null ? moodFromMotivation(st.motivation).value : '—',
      };
    });

    const reasoning = ah.map((r) => {
      const meta = actMeta(r.action);
      // Real reasoning text (old-UI style): the backend's per-turn reasoning lines,
      // else the decision reason, else a generic sentence — never the stat dump.
      // Kept as an ARRAY of lines so the panel renders them as bullet points;
      // esc + icon decoration happens at render time.
      const reasons = Array.isArray(r.reasoning) ? r.reasoning.filter(Boolean) : [];
      const lines = reasons.length ? reasons
        : (r.reason && !isStatDump(r.reason) ? [r.reason] : [reasonFor(r)]);
      return {
        turn: r.turn,
        title: `T${r.turn ?? '?'} · ${facLabel(r).toUpperCase()}`,
        badge: meta[0], badgeBg: meta[1],
        sub: subFor(r.action),
        lines,
        items: Array.isArray(r.items) ? r.items.filter(Boolean) : [],
      };
    });

    const lt = runner.lifetime || {};
    const lifetime = {
      total_fan_gain: lt.total_fans_gained_live ?? lt.total_fans_gained ?? runner.fans_gained ?? 0,
      fans_per_hour: lt.fans_per_hour_live ?? runner.fans_per_hour ?? 0,
      runtime: fmtDur(lt.total_runtime_seconds_live ?? lt.total_runtime_seconds ?? 0),
      careers_done: lt.careers_completed ?? runner.careers_completed ?? 0,
      career_fan_gain: cur.fans ?? 0,
    };

    if (account) account.runs = lt.careers_completed ?? account.runs ?? 0;
    const careerName = (account && account.career && account.career.name) || cur.name || 'CAREER';
    const turn = cur.turn || runner.turn || 0;
    // The backend sends scenario_id (int) and no status_text — synthesize both so
    // the vitals line shows the scenario and the live pill shows the turn
    // ("RUNNING · T50"), matching the mock instead of "—" / bare "RUNNING".
    const scenarioId = Number((account && account.career && account.career.scenario_id) ?? runner.scenario_id ?? cur.scenario_id ?? 0);
    const scenario = SCENARIO_MAP[scenarioId] || '';
    const status_text = runner.running ? `RUNNING · T${turn}`
      : runner.paused ? `PAUSED · T${turn}`
      : runner.finished ? 'FINISHED' : 'IDLE';

    return {
      account,
      runner: {
        running: !!runner.running, finished: !!runner.finished, paused: !!runner.paused,
        turn, status_text,
        cardId: Number(cur.card_id || (account && account.career && account.career.card_id) || 0),
        trainee: hasCareer ? { name: careerName, scenario, rank: '' } : {},
        hp: Math.max(0, Math.min(100, Math.round((hpNow / hpMax) * 100))),
        hpRaw: hpNow, hpMax,
        mood: motivation != null ? moodFromMotivation(motivation) : {},
        fans: cur.fans || runner.fans || 0,
        stats: hasCareer ? stats : [],
        lifetime, action_rows, reasoning,
        run_id: runner.run_id || '',   // new-career detection for loop mode (#5)
        clocks: {
          std: Number(runner.standard_clocks || 0),
          free: Number(runner.free_clocks || 0),
          refreshAt: Number(runner.free_continue_time || 0),
          total: Number(runner.clocks_left || 0),
          seen: ('free_clocks' in runner) || ('clocks_left' in runner),
        },
      },
    };
  }

  // ============================================================
  //  POLL LOOP  (mirrors the old UI's bgSetInterval 1.5s cadence)
  // ============================================================
  // ---------- 3D portrait + PNG toggle ----------
  // Single 3D model: the chibi Seiun Sky (model-test/mini.html). It loads ONCE and
  // spins continuously — never reloaded per trainee/career, so the spin stays smooth.
  // A "3D"/"PNG" toggle (bottom-left of the box) swaps to a flat PNG of the active
  // trainee (served from /api/images/<card_id>.png) and back.
  let lastRunId = null;
  let portraitMode = '3d';   // '3d' | 'png'
  let selectedCardId = 0;    // Setup-selected trainee (PNG fallback when no career)
  function setPortrait() {
    const f = $('portrait-3d');
    if (f && !/model-test\/mini\.html/.test(f.getAttribute('src') || '')) f.src = 'model-test/mini.html?v=3';
  }
  // The PNG shows the ACTIVE career trainee, or (when idle) the Setup-selected one.
  async function loadSelectedTrainee() {
    try {
      const r = await fetch('/api/session?t=' + Date.now());
      const j = await r.json();
      selectedCardId = Number((j && j.selection && j.selection.trainee && j.selection.trainee.id) || 0);
      if (portraitMode === 'png') applyPortraitPng();
    } catch (e) { /* keep 0 */ }
  }
  function applyPortraitPng() {
    const img = $('portrait-png');
    if (!img) return;
    const cid = (state.runner && state.runner.cardId) || selectedCardId;
    if (cid) {
      const src = '/api/card-art/' + cid + '.png?v=2';   // 512px standing illustration (?v=2 busts stale cache)
      if (img.getAttribute('src') !== src) img.src = src;
      img.style.display = 'block';
      img.onerror = () => { img.style.display = 'none'; };
    } else {
      img.removeAttribute('src');
      img.style.display = 'none';   // no trainee → empty box, never a broken-image alt
    }
  }
  function setPortraitMode(mode) {
    portraitMode = (mode === 'png') ? 'png' : '3d';
    const f = $('portrait-3d'), img = $('portrait-png'), b = $('portrait-mode'), tag = $('portrait-tag');
    const png = portraitMode === 'png';
    if (f) f.style.display = png ? 'none' : 'block';
    if (img) { img.style.display = png ? 'block' : 'none'; if (png) applyPortraitPng(); }
    if (b) b.textContent = png ? 'PNG' : 'Seiun';
    if (tag) tag.textContent = png ? 'TRAINEE · PNG' : '3D MODEL · .PMX';
  }
  function syncPortrait() { setPortrait(); }

  async function refresh() {
    const raw = await api('/api/career/runner');
    // Offline / transient poll failure → keep the last render and retry next poll.
    if (raw == null) return;
    const snap = adaptReal(raw);
    // New career started (incl. mid-loop): backend run_id changed → drop the old
    // run's accumulated feed/reasoning so the dashboard switches to the new run. (#5)
    const rid = snap.runner && snap.runner.run_id;
    if (rid && rid !== lastRunId) { lastRunId = rid; state.logHist = {}; state.reasonHist = {}; }
    render(snap);
    // Feed the shared bottom MONITOR dock from the same live snapshot.
    if (window.Icarus && Icarus.setMonitor) Icarus.setMonitor(raw);
    // Bordered lifetime metrics in the navbar + recolour the accent to the active
    // trainee (the dashboard runs its own poll, not core's pollChrome).
    if (window.Icarus && Icarus.renderLifetime) Icarus.renderLifetime(raw.runner);
    if (window.Icarus && Icarus.applyTraineeTheme) {
      const cid = raw.runner && raw.runner.current_chara && raw.runner.current_chara.card_id;
      Icarus.applyTraineeTheme(cid);
    }
    // Keep the PNG portrait fresh if the user is viewing it.
    if (portraitMode === 'png') applyPortraitPng();
  }
  function startPolling() {
    refresh();
    setInterval(refresh, 1500);
  }

  // ============================================================
  //  START CAREER — builds the real /api/career/run payload from the
  //  server-persisted Setup selection (trainee/deck/friend/parents).
  //  Resumes instead when a career is already active.
  // ============================================================
  function flashRun(msg) {
    const b = $('run-btn');
    if (!b) return;
    const prev = b.textContent;
    b.textContent = msg;
    setTimeout(() => { b.textContent = prev; }, 2600);
  }
  async function rawPost(url, body) {
    const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) });
    return res.json();
  }
  // Parents: mirror the old UI's selectedParentStartPayload — own[0]+guest
  // (parent_selection_mode 'own_guest') when a guest parent is picked in Setup,
  // else own[0]+own[1] ('own_own'). Without this the rental fields were dropped
  // and a chosen guest parent was silently ignored at career start.
  function parentStartPayload(sel) {
    const own = (sel.veterans || []).filter(Boolean);
    const guest = (sel.guestParents || []).filter(Boolean)[0] || null;
    if (guest && own[0]) {
      return {
        parent_id_1: Number(own[0].instance_id || 0), parent_id_2: 0,
        rental_viewer_id: Number(guest.viewer_id || 0),
        rental_trained_chara_id: Number(guest.instance_id || guest.id || 0),
        rental_card_id: Number(guest.card_id || 0),
        parent_selection_mode: 'own_guest',
      };
    }
    return {
      parent_id_1: Number((own[0] || {}).instance_id || 0),
      parent_id_2: Number((own[1] || {}).instance_id || 0),
      rental_viewer_id: 0, rental_trained_chara_id: 0, rental_card_id: 0,
      parent_selection_mode: 'own_own',
    };
  }
  // Retry budget from the RETRIES dev popover (core.js devConfig). Sent on every
  // run (fresh + resume), matching the old UI; previously never sent at all.
  function retryStartPayload() {
    const r = (window.Icarus && Icarus.devConfig && Icarus.devConfig.retries) || {};
    const mpr = (typeof r.maxPerRace === 'number') ? r.maxPerRace : -1;  // -1 = use preset/default
    return {
      carats_enabled: !!r.carats,
      max_clocks_per_career: Math.max(0, Number(r.maxClocks) || 0),
      clocks_g1_debut_only: !!r.g1DebutOnly,
      max_retries_per_race: mpr,
    };
  }
  // Read the active preset's persisted race mode + manual race list so a run uses
  // what was set in Setup (Smart plan or hand-picked Manual). The backend also has
  // a defense-in-depth fallback, but sending it explicitly is the correct path.
  async function racePayload() {
    try {
      const r = await fetch('/api/smart-solver/config?t=' + Date.now());
      const j = await r.json();
      const mode = (j && j.source === 'manual') ? 'manual' : 'smart';
      const ids = ((j && j.config && j.config.extra_race_list) || []).map((x) => Number(x)).filter((n) => Number.isFinite(n));
      return { race_planner_mode: mode, manual_race_ids: mode === 'manual' ? ids : [] };
    } catch (e) { return { race_planner_mode: 'smart', manual_race_ids: [] }; }
  }
  async function startCareer() {
    let sess = null;
    try { const r = await fetch('/api/session?t=' + Date.now()); sess = await r.json(); } catch (e) { /* ignore */ }
    const sel = (sess && sess.selection) || {};
    const account = sess && sess.account;
    const active = !!(account && account.career && account.career.active);
    // BUG #6: LOOP is a run-count now (0 = ∞). Fall back to the legacy bool.
    const runCount = (state.devToggles.loopCount != null)
      ? Number(state.devToggles.loopCount)
      : (state.devToggles.loop ? 0 : 1);
    const rp = await racePayload();   // persisted race mode + manual picks from the active preset
    let body;
    if (active) {
      body = {
        preset_name: '', max_steps: 2500, burn_clocks: state.devToggles.burn,
        finalize_single_runs: state.devToggles.finish, dev_mode: runCount !== 1,
        run_count: runCount, ...rp,
        ...retryStartPayload(),
      };
    } else {
      if (!sel.trainee || !sel.trainee.id) { flashRun('PICK A TRAINEE IN SETUP'); return; }
      if (!sel.deck || !(sel.deck.cards || []).length) { flashRun('BUILD/PICK A DECK'); return; }
      if (!sel.friend || !sel.friend.support_card_id) { flashRun('PICK A FRIEND SUPPORT'); return; }
      body = {
        card_id: Number(sel.trainee.id),
        support_card_ids: (sel.deck.cards || []).map((c) => Number(c.id)),
        friend_viewer_id: Number(sel.friend.viewer_id || 0),
        friend_card_id: Number(sel.friend.support_card_id || 0),
        ...parentStartPayload(sel),
        deck_id: Number(sel.deck.id) || 1,
        scenario_id: 4, use_tp: 30, difficulty_id: 0, difficulty: 0, is_boost: 0,
        preset_name: '', max_steps: 2500, burn_clocks: state.devToggles.burn,
        finalize_single_runs: state.devToggles.finish, dev_mode: runCount !== 1,
        run_count: runCount, ...rp,
        ...retryStartPayload(),
      };
    }
    flashRun(active ? 'RESUMING…' : 'STARTING…');
    try {
      const data = await rawPost('/api/career/run', body);
      if (!data || !data.success) flashRun((data && data.detail) ? String(data.detail).slice(0, 32) : 'START FAILED');
    } catch (e) { flashRun('START REQUEST FAILED'); }
    refresh();
  }

  // ============================================================
  //  INTERACTIONS
  // ============================================================
  function bind() {
    // run / stop / pause — POST to the real runner endpoints.
    $('run-btn').addEventListener('click', async () => { await startCareer(); });
    $('stop-btn').addEventListener('click', async () => {
      await api('/api/career/runner/stop', { method: 'POST' });
      refresh();
    });
    $('pause-btn').addEventListener('click', async () => {
      const paused = state.runner && state.runner.paused;
      await api('/api/career/runner/' + (paused ? 'resume' : 'pause'), { method: 'POST' });
      refresh();
    });

    // reasoning tabs
    $('rt-decision').addEventListener('click', () => setReasonTab('decision'));

    // 3D / PNG portrait toggle (bottom-left of the model box)
    { const pm = $('portrait-mode'); if (pm) pm.addEventListener('click', () => setPortraitMode(portraitMode === '3d' ? 'png' : '3d')); }

    // dev toggles (tempt + retries are popovers, wired by Icarus.bindDevExtras)
    // Share core.js's single devToggles object so the state is one source of
    // truth across every page; core loads it from localStorage at init so a
    // toggle set here survives navigation to setup/diag/etc.
    if (window.Icarus && Icarus.devToggles) state.devToggles = Icarus.devToggles;
    const devMap = {
      'dev-burn': ['burn', (on) => 'BURN:' + (on ? 'ON' : 'OFF')],
      'dev-finish': ['finish', (on) => 'FINISH:' + (on ? 'ON' : 'OFF')],
    };
    const applyToggleLabel = (id, key, label) => {
      const b = $(id);
      if (!b) return;
      const on = !!state.devToggles[key];
      b.textContent = label(on);
      b.classList.toggle('on', on);
      if (key === 'finish') { const f = $('finish-run-btn'); if (f) f.textContent = 'FINISH RUN · ' + (on ? 'ON' : 'OFF'); }
    };
    Object.entries(devMap).forEach(([id, [key, label]]) => {
      $(id).addEventListener('click', () => {
        state.devToggles[key] = !state.devToggles[key];
        if (window.Icarus && Icarus.persistToggles) Icarus.persistToggles();
        applyToggleLabel(id, key, label);
        // Burn clocks is a LIVE runner toggle — POST it so a running career picks
        // it up immediately (it's also sent in the start payload for new careers).
        if (key === 'burn') {
          fetch('/api/career/runner/burn_clocks', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ burn_clocks: state.devToggles.burn }) }).catch(() => {});
        }
      });
      // Restore the persisted label on load (HTML defaults to OFF).
      applyToggleLabel(id, key, label);
    });
    // BUG #6: LOOP cycles a run-count (1/2/3/5/10/∞) via the shared core helper.
    { const lb = $('dev-loop'); if (lb && window.Icarus && Icarus.loopLabel) {
        const syncLoop = () => { lb.textContent = Icarus.loopLabel(state.devToggles.loopCount); lb.classList.toggle('on', Number(state.devToggles.loopCount) !== 1); };
        lb.addEventListener('click', () => { Icarus.nextLoopCount(); syncLoop(); });
        syncLoop();
      } }
    { const f = $('finish-run-btn'); if (f) f.addEventListener('click', () => $('dev-finish').click()); }


    // not-yet-built tabs: gentle notice (these become real pages next)
    document.querySelectorAll('.tab[data-soon]').forEach((a) => {
      a.addEventListener('click', (e) => {
        e.preventDefault();
        const t = $('tab-live-text');
        const prev = t.textContent;
        t.textContent = a.dataset.soon.toUpperCase() + ' · NEXT';
        setTimeout(() => { t.textContent = prev; }, 1400);
      });
    });
  }

  function setReasonTab(tab) {
    state.reasonTab = tab;
    $('rt-decision').classList.toggle('is-active', tab === 'decision');
    if (state.runner) renderReasoning(state.runner);
  }

  // ---------- boot ----------
  bind();
  if (window.Icarus && Icarus.bindTheme) Icarus.bindTheme();
  if (window.Icarus && Icarus.wireLogout) Icarus.wireLogout();
  if (window.Icarus && Icarus.ensureAuth) Icarus.ensureAuth();
  if (window.Icarus && Icarus.mountMonitor) Icarus.mountMonitor();
  if (window.Icarus && Icarus.bindDevExtras) Icarus.bindDevExtras();
  syncPortrait();
  loadSelectedTrainee();
  startPolling();
})();
