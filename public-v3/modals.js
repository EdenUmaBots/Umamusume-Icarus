/* Icarus settings sub-modals — shared across Setup, Diag/AI, dashboard.
   Field set mirrors the real app.js modal builders (renderTrainingSettings /
   renderRacingSettings / renderScenarioSettings) and the Smart Race Solver
   Settings doc. Labels/keys map straight to preset.mant_config / solver config.
   Controls auto-wire through core.js. Save POSTs to the real endpoint. */
(() => {
  'use strict';
  const I = window.Icarus;
  const { modal, api, closeModal, esc } = I;

  const STATS = ['Speed', 'Stamina', 'Power', 'Guts', 'Wit'];
  const DISTANCES = ['Sprint', 'Mile', 'Medium', 'Long'];
  const SURFACES = ['Turf', 'Dirt'];
  const GRADES = ['G1', 'G2', 'G3', 'OP', 'Pre-OP'];
  const STYLES = ['Front', 'Pace', 'Late', 'End'];
  const STYLE_OPTS = [['auto', 'Auto'], ['front', 'Front Runner'], ['pace', 'Pace Chaser'], ['late', 'Late Surger'], ['end', 'End Closer']];
  const STYLE_NAMES = ['Front Runner', 'Pace Chaser', 'Late Surger', 'End Closer'];
  const RACE_OVR = [
    ['Kikuka Sho', '3000m', 'G1'], ['Tenno Sho (Spring)', '3200m', 'G1'], ['Tenno Sho (Autumn)', '2000m', 'G1'],
    ['Arima Kinen', '2500m', 'G1'], ['Japan Cup', '2400m', 'G1'], ['Takarazuka Kinen', '2200m', 'G1'],
    ['Satsuki Sho', '2000m', 'G1'], ['Niigata Junior Stakes', '1600m', 'G3'],
  ];
  const APTS = ['Sprint', 'Mile', 'Medium', 'Long', 'Turf', 'Dirt'];

  // ---- control builders (settings-row pattern: label+desc left, control right) ----
  const row = (label, help, ctrl, full = false) =>
    `<div class="srow${full ? ' full' : ''}"><div class="srow-text"><strong>${label}</strong>${help ? `<span>${help}</span>` : ''}</div><div class="srow-ctrl">${ctrl}</div></div>`;
  const slider = (id, label, min, max, val, step = 1, suffix = '', help = '', k = '') =>
    row(label, help, `<div class="srow-slider"><input class="rng" type="range" min="${min}" max="${max}" step="${step}" value="${val}" data-val="${id}-v" data-suffix="${suffix}"${k ? ` data-k="${k}" data-type="num"` : ''}><span class="val" id="${id}-v">${val}${suffix}</span></div>`);
  const toggle = (label, on, help = '', k = '') =>
    row(label, help, `<div class="tgl${on ? ' on' : ''}"${k ? ` data-k="${k}" data-type="bool"` : ''}><span class="tgl-sw"></span></div>`);
  const seg = (label, opts, activeIdx, help = '') =>
    row(label, help, `<div class="segrow">${opts.map((o, i) => `<button class="segbtn${i === activeIdx ? ' on' : ''}" type="button">${esc(o)}</button>`).join('')}</div>`);
  // chip opt = [value, on] or [value, on, label] (label defaults to value, so a
  // chip can store a backend-format value, e.g. 'sprint', while showing 'Sprint').
  const chips = (label, opts, help = '', k = '') =>
    row(label, help, `<div class="segrow" data-multi="1"${k ? ` data-k="${k}" data-type="chips"` : ''}>${opts.map((o) => `<button class="chiptog${o[1] ? ' on' : ''}" type="button" data-chip="${esc(o[0])}">${esc(o[2] || o[0])}</button>`).join('')}</div>`, opts.length > 5);
  // Smart-solver boolean / string controls -> trackblazer_solver_settings[key]
  // (mirrors the proven legacy public/app.js wiring; round-tripped by the solver
  // collector + initSolverWeights via data-ssb / data-sss).
  const ssToggle = (label, on, help, key) =>
    row(label, help, `<div class="tgl${on ? ' on' : ''}" data-ssb="${key}"><span class="tgl-sw"></span></div>`);
  const ssSelect = (label, opts, active, help, key) =>
    row(label, help, `<select class="self" data-sss="${key}">${opts.map(([v, l]) => `<option value="${esc(v)}"${String(v) === String(active) ? ' selected' : ''}>${esc(l)}</option>`).join('')}</select>`);
  const sel = (label, opts, activeVal, help = '', k = '') =>
    row(label, help, `<select class="self"${k ? ` data-k="${k}" data-type="str"` : ''}>${opts.map(([v, l]) => `<option value="${esc(v)}"${String(v) === String(activeVal) ? ' selected' : ''}>${esc(l)}</option>`).join('')}</select>`);
  const numf = (label, val, help = '', k = '') =>
    row(label, help, `<input class="numf" type="number" value="${val}"${k ? ` data-k="${k}" data-type="num"` : ''}>`);
  // Per-distance running-style select. collectPreset/applyPreset round-trip the
  // four of these into mant_config.race_strategy_by_distance via the data-rsbd key.
  const dsel = (label, bucket, help = '') =>
    row(label, help, `<select class="self rsbd" data-rsbd="${bucket}">${STYLE_OPTS.map(([v, l]) => `<option value="${esc(v)}">${esc(l)}</option>`).join('')}</select>`);
  // priority registry: id -> { label, items (current), def (default) }
  const PRIO = {};
  const prioChipsHtml = (items) => items.map((n, i) => `<span class="prio-chip"><span class="n">${i + 1}</span>${esc(n)}</span>`).join('');
  const prio = (id, label, items, help = '') => {
    PRIO[id] = { label, items: items.slice(), def: items.slice() };
    return row(label, help, `<div class="prio-compact" style="width:100%"><div class="prio-chips" data-prio="${id}">${prioChipsHtml(items)}</div><span class="prio-edit" data-prio-edit="${id}">EDIT ▸</span></div>`);
  };
  function renderPrioCompact(id) {
    const host = document.querySelector(`[data-prio="${id}"]`);
    if (host) host.innerHTML = prioChipsHtml(PRIO[id].items);
  }
  function openPriorityEditor(id) {
    const rec = PRIO[id]; if (!rec) return;
    const listHtml = (items) => `<div class="prio cyan">${items.map((n, i) => `<div class="prio-item"><span class="prio-rank">${i + 1}</span><span class="prio-name">${esc(n)}</span><span class="prio-grip">≡</span></div>`).join('')}</div>`;
    const ov = document.createElement('div');
    ov.className = 'modal-overlay'; ov.style.zIndex = '70';
    ov.innerHTML = `<div class="modal" style="width:440px">
      <div class="modal-head"><span class="modal-mark"></span><span class="modal-title">${esc(rec.label)}</span><button class="modal-x" type="button" data-ed-close>×</button></div>
      <div class="modal-body"><p class="field-help" style="margin:0 0 14px;letter-spacing:.14em">DRAG TO REORDER · TOP = HIGHEST</p><div id="pe-list">${listHtml(rec.items)}</div></div>
      <div class="modal-foot" style="justify-content:space-between"><button class="abtn danger" type="button" data-ed-reset>RESET</button><button class="abtn" type="button" data-ed-all>SELECT ALL</button></div>
    </div>`;
    document.body.appendChild(ov);
    I.wireControls(ov);
    const readOrder = () => [...ov.querySelectorAll('.prio-name')].map((n) => n.textContent);
    const commit = () => { rec.items = readOrder(); renderPrioCompact(id); ov.remove(); };
    ov.addEventListener('mousedown', (e) => { if (e.target === ov) commit(); });
    ov.querySelector('[data-ed-close]').addEventListener('click', commit);
    const restore = (items) => { const wrap = ov.querySelector('#pe-list'); wrap.innerHTML = listHtml(items); I.wireControls(wrap); };
    ov.querySelector('[data-ed-reset]').addEventListener('click', () => restore(rec.def.slice()));
    ov.querySelector('[data-ed-all]').addEventListener('click', () => restore(rec.def.slice()));
  }
  const sec = (title, ...fields) => `<div class="fsec"><div class="fsec-title">${title}</div>${fields.join('')}</div>`;
  // Defaults mirror the engine's DEFAULT_TARGETS (mant_trackblazer.py) so an
  // untouched save writes the same numbers the engine already uses (no silent
  // behaviour change). applyPreset overrides these from the saved preset.
  const TARGETS = { Sprint: [1200, 600, 1200, 600, 1200], Mile: [1200, 600, 1200, 600, 1200], Medium: [1200, 600, 1200, 600, 1200], Long: [1200, 800, 1200, 500, 1200] };
  const STAT_COLS = ['Speed', 'Stamina', 'Power', 'Guts', 'Wit'];
  const statTargetsRow = () => {
    const head = `<div class="sttg-head sttg-dist">Distance</div>${STAT_COLS.map((c) => `<div class="sttg-head">${c}</div>`).join('')}`;
    const rows = Object.entries(TARGETS).map(([d, vals]) => `<div class="sttg-dist">${d}</div>${vals.map((v) => `<input class="numf sttg-input" data-stg="${d.toLowerCase()}" type="number" min="1" value="${v}">`).join('')}`).join('');
    return `<div class="srow" style="grid-template-columns:minmax(0,1fr) minmax(0,2.2fr)">
        <div class="srow-text"><strong>Stat Targets by Distance</strong><span>Native stat target table used by the training scorer.</span></div>
        <div class="sttg">${head}${rows}</div>
      </div>`;
  };
  // Global stat target — one Spd/Sta/Pow/Guts/Wit row applied to EVERY distance
  // when the "Use Global Stat Target" toggle is on (overrides the table above).
  const globalStatTargetRow = () => {
    const head = STAT_COLS.map((c) => `<div class="sttg-head">${c}</div>`).join('');
    const inputs = [1200, 1200, 1200, 1200, 1200].map((v) => `<input class="numf gstg-input" type="number" min="1" value="${v}">`).join('');
    return `<div class="srow" style="grid-template-columns:minmax(0,1fr) minmax(0,2.2fr)">
        <div class="srow-text"><strong>Global Stat Target</strong><span>Used for every distance when the toggle above is on. Ignores the per-distance table.</span></div>
        <div class="sttg" style="grid-template-columns:repeat(5,1fr)">${head}${inputs}</div>
      </div>`;
  };
  const aptGrid = () => row('Manual Solver Aptitudes', 'Override Sprint / Mile / Medium / Long / Turf / Dirt grades (per trainee).',
    `<div class="row2" style="grid-template-columns:repeat(6,1fr);width:100%">${APTS.map((a, i) => `<div><div style="font:600 var(--fs-2xs) var(--cond);letter-spacing:.1em;color:var(--label);text-align:center;margin-bottom:4px">${a.slice(0, 4).toUpperCase()}</div><select class="self" style="min-width:0;width:100%;padding:7px 4px;font-size:var(--fs-md);text-align:center">${['S', 'A', 'B', 'C', 'D', 'E', 'F', 'G'].map((g) => `<option${g === ['A', 'B', 'A', 'A', 'A', 'G'][i] ? ' selected' : ''}>${g}</option>`).join('')}</select></div>`).join('')}</div>`, true);

  const saveBtn = (endpoint, label = 'SAVE') => `<button class="abtn amber" type="button" data-save="${endpoint}">${label}</button>`;
  // Registry of per-modal value collectors. A collector returns the exact
  // payload object to POST for its endpoint, or null to skip. Without a
  // collector we NEVER post an empty body to a config endpoint (that would
  // overwrite the user's real preset/skill/solver config with {}).
  const SAVE_COLLECTORS = {
    '/api/settings/discord-webhook': (o) => {
      const inp = o.querySelector('#discord-url');
      const url = inp ? inp.value.trim() : '';
      const tgl = (key) => { const t = o.querySelector(`.tgl[data-k="${key}"]`); return t ? t.classList.contains('on') : true; };
      return {
        webhook_url: url, enabled: !!url,
        notify_on_finish: tgl('notify_on_finish'),
        notify_on_crash: tgl('notify_on_crash'),
        notify_on_epithet: o.querySelector('.tgl[data-k="notify_on_epithet"]')
          ? o.querySelector('.tgl[data-k="notify_on_epithet"]').classList.contains('on') : false,
      };
    },
  };
  // Optional post-save hooks keyed by endpoint, run after a successful save with
  // (overlay, payload, response) — e.g. to push a result into another module.
  const SAVE_HOOKS = {};
  function wireSave(o) {
    o.querySelectorAll('[data-save]').forEach((b) => b.addEventListener('click', async () => {
      const url = b.dataset.save;
      const collector = SAVE_COLLECTORS[url] || SAVE_COLLECTORS[b.dataset.collect];
      const payload = collector ? collector(o) : null;
      if (!payload) {
        // No collector → nothing to persist yet. Close without a destructive
        // empty POST so existing config is never wiped.
        b.textContent = 'CLOSE';
        setTimeout(closeModal, 250);
        return;
      }
      b.textContent = 'SAVING…';
      try {
        const r = await api(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
        const ok = (r && r.success !== false);
        b.textContent = ok ? 'SAVED ✓' : 'SAVE FAILED';
        if (ok && SAVE_HOOKS[url]) { try { SAVE_HOOKS[url](o, payload, r); } catch (e) { /* hook is best-effort */ } }
      } catch (e) { b.textContent = 'SAVE FAILED'; }
      setTimeout(closeModal, 500);
    }));
    // Unsaved-changes guard: if this overlay can save, intercept its close paths
    // (DONE/X, backdrop, Esc -- routed through core.js attemptClose / escClose) so
    // a dirty modal prompts Save / Discard instead of closing silently. The SAVE
    // button itself closes via closeModal() and bypasses this (no double prompt).
    if (o.querySelector('[data-save]')) {
      o._guardClose = (close) => {
        if (o._cleanSnap != null && snapshot(o) !== o._cleanSnap) showUnsavedConfirm(o, close);
        else close();
      };
    }
  }
  // The modal's exact "what SAVE would persist" payload as a stable string, via the
  // SAME collector the save button uses -> "dirty" means a *saveable* change only
  // (display-only controls with no collector entry never trigger the prompt).
  function collectorFor(o) {
    const b = o.querySelector('[data-save]');
    if (!b) return null;
    return SAVE_COLLECTORS[b.dataset.save] || SAVE_COLLECTORS[b.dataset.collect] || null;
  }
  function snapshot(o) {
    const c = collectorFor(o);
    let payload = null;
    try { payload = c ? c(o) : null; } catch (e) { payload = null; }
    return JSON.stringify(payload != null ? payload : null);
  }
  // Capture the clean baseline AFTER a modal's async init has populated its controls.
  // Until armed (_cleanSnap == null) the guard degrades to a silent close.
  function armUnsavedGuard(o) { if (o) o._cleanSnap = snapshot(o); }
  // Save / Discard prompt for a dirty settings modal. Built as a raw overlay (NOT
  // modal(), which would close the settings modal first). Dismissing it via backdrop
  // or Esc (core escClose targets the topmost overlay, which has no guard) = keep editing.
  function showUnsavedConfirm(o, close) {
    const ov = document.createElement('div');
    ov.className = 'modal-overlay';
    ov.style.zIndex = '80';
    ov.innerHTML = `<div class="modal" style="width:400px">
      <div class="modal-head"><span class="modal-mark"></span><span class="modal-title">UNSAVED CHANGES</span></div>
      <div class="modal-body" style="padding:18px"><p style="font:500 var(--fs-base)/1.7 var(--mono);color:var(--ink-2);margin:0">You’ve made changes that haven’t been saved. Save them before closing?</p></div>
      <div class="modal-foot"><button class="abtn" type="button" data-uc-discard>DISCARD CHANGES</button><button class="abtn amber" type="button" data-uc-save>SAVE CHANGES</button></div>
    </div>`;
    document.body.appendChild(ov);
    ov.addEventListener('mousedown', (e) => { if (e.target === ov) ov.remove(); }); // keep editing
    ov.querySelector('[data-uc-discard]').addEventListener('click', () => { ov.remove(); close(); });
    ov.querySelector('[data-uc-save]').addEventListener('click', () => {
      ov.remove();
      const btn = o.querySelector('[data-save]');
      if (btn) btn.click(); else close();
    });
  }

  // ============================================================
  //  SETTINGS PRESET round-trip (load active → apply → collect → save)
  //  Settings live on the preset object (target 'preset') or its
  //  mant_config (target 'mant'); the whole preset is POSTed back.
  // ============================================================
  const SETTINGS_PRIO = { 'tr-main': 'training_stat_priority', 'tr-event': 'event_choice_stat_priority', 'tr-summer': 'summer_stat_priority' };
  function presetGet(p, t, k) { const o = t === 'mant' ? (p.mant_config || {}) : p; return o ? o[k] : undefined; }
  function presetSet(p, t, k, v) { if (t === 'mant') { p.mant_config = p.mant_config || {}; p.mant_config[k] = v; } else { p[k] = v; } }
  async function loadActivePreset() {
    try {
      const all = await api('/api/settings-presets');
      const list = all && Array.isArray(all.presets) ? all.presets : [];
      const act = all && all.active;
      let p = list.find((x) => x && (x.name || x) === act) || list[0];
      if (!p) return { name: '', mant_config: {} };
      return (typeof p === 'object') ? p : { name: p, mant_config: {} };
    } catch (e) { return null; }
  }
  function applyPreset(o, p) {
    o.querySelectorAll('[data-k]').forEach((el) => {
      const parts = el.dataset.k.split('.'); const t = parts[0]; const k = parts.slice(1).join('.'); const type = el.dataset.type;
      const v = presetGet(p, t, k); if (v === undefined || v === null) return;
      if (type === 'bool') el.classList.toggle('on', !!v);
      else if (type === 'num') { el.value = v; const out = document.getElementById(el.dataset.val); if (out) out.textContent = v + (el.dataset.suffix || ''); }
      else if (type === 'str') el.value = String(v);
      else if (type === 'chips') { const arr = Array.isArray(v) ? v.map(String) : []; el.querySelectorAll('.chiptog').forEach((c) => c.classList.toggle('on', arr.includes(c.dataset.chip))); }
    });
    // Stat-target grids (arrays — not simple data-k scalar types)
    const _stbd = (p.mant_config || {}).stat_targets_by_distance || {};
    ['sprint', 'mile', 'medium', 'long'].forEach((d) => {
      const arr = _stbd[d];
      if (!Array.isArray(arr)) return;
      o.querySelectorAll(`.sttg-input[data-stg="${d}"]`).forEach((el, i) => { if (arr[i] !== undefined && arr[i] !== null) el.value = arr[i]; });
    });
    const _gst = (p.mant_config || {}).global_stat_target;
    if (Array.isArray(_gst)) o.querySelectorAll('.gstg-input').forEach((el, i) => { if (_gst[i] !== undefined && _gst[i] !== null) el.value = _gst[i]; });
    // BUG #3: per-distance running styles + per-race style overrides.
    const _rsbd = (p.mant_config || {}).race_strategy_by_distance || {};
    o.querySelectorAll('.rsbd[data-rsbd]').forEach((el) => { const v = _rsbd[el.dataset.rsbd]; if (v) el.value = v; });
    const _ovr = (p.mant_config || {}).per_race_style_overrides;
    if (Array.isArray(_ovr) && _ovr.length) {
      const byMatch = {};
      _ovr.forEach((r) => { if (r && r.match) byMatch[String(r.match).toLowerCase()] = r; });
      o.querySelectorAll('.rovr').forEach((el) => {
        const r = byMatch[String(el.dataset.race || '').toLowerCase()];
        if (!r) return;
        const styleSel = el.querySelector('.rovr-style'); if (styleSel && r.style) styleSel.value = r.style;
        const stam = el.querySelector('.rovr-stam-input'); if (stam && r.stamina_below != null) stam.value = r.stamina_below;
      });
    }
    Object.entries(SETTINGS_PRIO).forEach(([id, key]) => {
      const v = presetGet(p, 'preset', key);
      // Stored lowercase (engine format); Title-case for the chip display so the
      // editor's labels/reset match the seeded ['Speed','Power','Wit',...] options.
      if (Array.isArray(v) && v.length && PRIO[id]) {
        PRIO[id].items = v.map((s) => { const t = String(s); return t.charAt(0).toUpperCase() + t.slice(1).toLowerCase(); });
        if (typeof renderPrioCompact === 'function') renderPrioCompact(id);
      }
    });
  }
  function collectPreset(o, p) {
    o.querySelectorAll('[data-k]').forEach((el) => {
      const parts = el.dataset.k.split('.'); const t = parts[0]; const k = parts.slice(1).join('.'); const type = el.dataset.type;
      let v;
      if (type === 'bool') v = el.classList.contains('on');
      else if (type === 'num') v = parseFloat(el.value);
      else if (type === 'str') v = el.value;
      else if (type === 'chips') v = [...el.querySelectorAll('.chiptog.on')].map((c) => c.dataset.chip);
      else return;
      presetSet(p, t, k, v);
    });
    // Stat-target grids -> mant_config arrays. Only written when the inputs are
    // present in this overlay (the Training modal), so other settings modals that
    // share /api/settings-presets leave these keys untouched.
    const _stbd = {};
    ['sprint', 'mile', 'medium', 'long'].forEach((d) => {
      const inputs = o.querySelectorAll(`.sttg-input[data-stg="${d}"]`);
      if (inputs.length === 5) _stbd[d] = [...inputs].map((el) => Math.max(1, parseInt(el.value, 10) || 0));
    });
    if (Object.keys(_stbd).length) presetSet(p, 'mant', 'stat_targets_by_distance', _stbd);
    const _gin = o.querySelectorAll('.gstg-input');
    if (_gin.length === 5) presetSet(p, 'mant', 'global_stat_target', [..._gin].map((el) => Math.max(1, parseInt(el.value, 10) || 0)));
    // BUG #3: per-distance running styles -> mant_config.race_strategy_by_distance
    // (only non-'auto' entries; engine reads it via running_style.py).
    if (o.querySelector('.rsbd')) {
      const _rsbd = {};
      o.querySelectorAll('.rsbd[data-rsbd]').forEach((el) => { if (el.value && el.value !== 'auto') _rsbd[el.dataset.rsbd] = el.value; });
      presetSet(p, 'mant', 'race_strategy_by_distance', _rsbd);
    }
    // BUG #3: per-race style overrides -> mant_config.per_race_style_overrides
    // ({match, style, stamina_below?}) so they persist and the engine applies them
    // (runner.py:_per_race_style_override). Empty when none selected.
    if (o.querySelector('.rovr')) {
      const ovr = [];
      o.querySelectorAll('.rovr').forEach((el) => {
        const styleSel = el.querySelector('.rovr-style');
        const style = styleSel ? styleSel.value : '';
        if (!style) return;
        const stam = el.querySelector('.rovr-stam-input');
        const rule = { match: el.dataset.race, style };
        if (stam && stam.value !== '') rule.stamina_below = Math.max(0, parseInt(stam.value, 10) || 0);
        ovr.push(rule);
      });
      presetSet(p, 'mant', 'per_race_style_overrides', ovr);
    }
    // Priority-order arrays: persist the user's reorder. Written LOWERCASE to match
    // the engine's stat-name format (config_store defaults + items.py lower-cases).
    // Scoped to this overlay (only when the prio control exists) so other settings
    // modals sharing /api/settings-presets never touch these keys.
    Object.entries(SETTINGS_PRIO).forEach(([id, key]) => {
      if (!o.querySelector(`[data-prio="${id}"]`)) return;
      const rec = PRIO[id];
      if (rec && Array.isArray(rec.items) && rec.items.length) {
        presetSet(p, 'preset', key, rec.items.map((s) => String(s).toLowerCase()));
      }
    });
    return p;
  }
  async function initSettingsModal(o) {
    const p = await loadActivePreset();
    if (!p) return;
    o._preset = p;
    applyPreset(o, p);
  }
  SAVE_COLLECTORS['/api/settings-presets'] = (o) => (o && o._preset) ? { preset: collectPreset(o, o._preset) } : null;

  // ---- Smart Solver scoring weights (data-sw index 0-9). 0-7 live in
  //      trackblazer_weights, 8-9 in trackblazer_solver_settings. Round-trips
  //      the whole config so aptitudes/epithets/threshold are preserved. ----
  const SOLVER_SW = [
    ['w', 'raceValue'], ['w', 'epithetValue'], ['w', 'fanWeight'], ['w', 'hintRewardWeight'],
    ['w', 'consecutiveRacePenalty'], ['w', 'summerPenalty'], ['w', 'raceBonusPct'], ['w', 'raceCostPct'],
    ['s', 'fan_bonus'], ['s', 'max_races_in_row'],
  ];
  async function initSolverWeights(o) {
    let cfg = {};
    try { const r = await api('/api/smart-solver/config'); cfg = (r && r.config) || {}; } catch (e) { /* preview */ }
    cfg.trackblazer_weights = cfg.trackblazer_weights || {};
    cfg.trackblazer_solver_settings = cfg.trackblazer_solver_settings || {};
    o._solverCfg = cfg;
    o.querySelectorAll('[data-sw]').forEach((inp) => {
      const map = SOLVER_SW[+inp.dataset.sw]; if (!map) return;
      const src = map[0] === 'w' ? cfg.trackblazer_weights : cfg.trackblazer_solver_settings;
      if (src[map[1]] !== undefined && src[map[1]] !== null) inp.value = src[map[1]];
    });
    // Boolean solver weights (data-swb) -> trackblazer_weights[key]. Reflect the
    // saved value so the toggle shows the real state (default OFF when absent).
    o.querySelectorAll('[data-swb]').forEach((el) => {
      el.classList.toggle('on', !!cfg.trackblazer_weights[el.dataset.swb]);
    });
    // Boolean / string solver SETTINGS (data-ssb / data-sss) -> trackblazer_solver_settings[key].
    // Only override the markup default when a saved value is present (preserves each
    // control's backend default, e.g. Live Re-Planning ON, when the key is absent).
    o.querySelectorAll('[data-ssb]').forEach((el) => {
      const v = cfg.trackblazer_solver_settings[el.dataset.ssb];
      if (v !== undefined && v !== null) el.classList.toggle('on', !!v);
    });
    o.querySelectorAll('[data-sss]').forEach((el) => {
      const v = cfg.trackblazer_solver_settings[el.dataset.sss];
      if (v !== undefined && v !== null && v !== '') el.value = v;
    });
  }
  SAVE_COLLECTORS['/api/smart-solver/config'] = (o) => {
    if (!o || !o._solverCfg) return null;
    const cfg = o._solverCfg;
    o.querySelectorAll('[data-sw]').forEach((inp) => {
      const map = SOLVER_SW[+inp.dataset.sw]; if (!map) return;
      const dst = map[0] === 'w' ? cfg.trackblazer_weights : cfg.trackblazer_solver_settings;
      const v = parseFloat(inp.value); if (!isNaN(v)) dst[map[1]] = v;
    });
    cfg.trackblazer_weights = cfg.trackblazer_weights || {};
    o.querySelectorAll('[data-swb]').forEach((el) => {
      cfg.trackblazer_weights[el.dataset.swb] = el.classList.contains('on');
    });
    cfg.trackblazer_solver_settings = cfg.trackblazer_solver_settings || {};
    o.querySelectorAll('[data-ssb]').forEach((el) => {
      cfg.trackblazer_solver_settings[el.dataset.ssb] = el.classList.contains('on');
    });
    o.querySelectorAll('[data-sss]').forEach((el) => {
      cfg.trackblazer_solver_settings[el.dataset.sss] = el.value;
    });
    return { config: cfg, preset: '' };
  };

  // ---- Skill config (flat config; controls keyed 'sk.<key>'). Round-trips the
  //      whole config so the skill_strategy/tiers arrays are preserved. ----
  async function initSkillCfg(o) {
    let cfg = {};
    try { const r = await api('/api/skill-config'); cfg = (r && r.config) || {}; } catch (e) { /* preview */ }
    o._skillCfg = cfg;
    o.querySelectorAll('[data-k^="sk."]').forEach((el) => {
      const key = el.dataset.k.slice(3); const type = el.dataset.type; const v = cfg[key];
      if (v === undefined || v === null) return;
      if (type === 'bool') el.classList.toggle('on', !!v);
      else if (type === 'num') el.value = v;
      else if (type === 'str') el.value = String(v);
    });
  }
  SAVE_COLLECTORS['/api/skill-config'] = (o) => {
    if (!o) return null;
    const cfg = o._skillCfg || {};
    o.querySelectorAll('[data-k^="sk."]').forEach((el) => {
      const key = el.dataset.k.slice(3); const type = el.dataset.type;
      if (type === 'bool') cfg[key] = el.classList.contains('on');
      else if (type === 'num') { const v = parseFloat(el.value); if (!isNaN(v)) cfg[key] = v; }
      else if (type === 'str') cfg[key] = el.value;
    });
    // Manual tier plan: map UI selection back to skill_strategy (forced_skills /
    // blacklist) + manual_skill_tiers ("1"."5"), keyed by skill NAME.
    if (typeof o._collectSkillStrategy === 'function') {
      const s = o._collectSkillStrategy();
      const strat = (cfg.skill_strategy && typeof cfg.skill_strategy === 'object') ? cfg.skill_strategy : {};
      strat.forced_skills = s.forced_skills;
      strat.blacklist = s.blacklist;
      cfg.skill_strategy = strat;
      cfg.manual_skill_tiers = s.manual_skill_tiers;
      cfg.skill_manual_auto_fallback = s.auto;
      cfg.manual_skill_tiers_dont_spend_extra = !s.auto;
      cfg.show_only_selected_skills = s.showOnly;
    }
    return { config: cfg, preset: '' };
  };
  const GRADES8 = ['S', 'A', 'B', 'C', 'D', 'E', 'F', 'G'];
  const APT_ALL = ['Sprint', 'Mile', 'Medium', 'Long', 'Turf', 'Dirt'];
  const gi = (g) => GRADES8.indexOf(g);
  const finalGrade = (manual, sparks) => GRADES8[Math.max(0, gi(manual) - sparks)];
  // [name, id, { apt: [baseGrade, sparks] }]
  let SOLVER_CHARS = [
    ['Air Shakur', 100021, { Sprint: ['G', 0], Mile: ['E', 3], Medium: ['A', 2], Long: ['A', 3], Turf: ['A', 1], Dirt: ['G', 0] }],
    ['Silence Suzuka', 100201, { Sprint: ['B', 1], Mile: ['A', 2], Medium: ['A', 1], Long: ['C', 0], Turf: ['A', 2], Dirt: ['G', 0] }],
    ['Maruzensky', 100401, { Sprint: ['A', 1], Mile: ['A', 3], Medium: ['B', 1], Long: ['E', 0], Turf: ['A', 2], Dirt: ['C', 1] }],
    ['Gold Ship', 100701, { Sprint: ['G', 0], Mile: ['C', 1], Medium: ['A', 2], Long: ['A', 3], Turf: ['A', 2], Dirt: ['E', 0] }],
    ['Vodka', 100801, { Sprint: ['E', 0], Mile: ['A', 2], Medium: ['A', 2], Long: ['B', 1], Turf: ['A', 2], Dirt: ['C', 1] }],
    ['Daiwa Scarlet', 100901, { Sprint: ['C', 0], Mile: ['A', 2], Medium: ['A', 3], Long: ['B', 1], Turf: ['A', 2], Dirt: ['G', 0] }],
    ['Grass Wonder', 101101, { Sprint: ['E', 0], Mile: ['B', 1], Medium: ['A', 2], Long: ['A', 2], Turf: ['A', 2], Dirt: ['G', 0] }],
    ['Mejiro McQueen', 101201, { Sprint: ['G', 0], Mile: ['E', 0], Medium: ['A', 2], Long: ['A', 3], Turf: ['A', 2], Dirt: ['G', 0] }],
    ['Special Week', 101301, { Sprint: ['D', 0], Mile: ['A', 1], Medium: ['A', 3], Long: ['A', 2], Turf: ['A', 2], Dirt: ['C', 0] }],
    ['Symboli Rudolf', 101401, { Sprint: ['E', 0], Mile: ['A', 1], Medium: ['A', 3], Long: ['A', 2], Turf: ['A', 2], Dirt: ['G', 0] }],
    ['Tokai Teio', 101501, { Sprint: ['E', 0], Mile: ['B', 1], Medium: ['A', 3], Long: ['A', 2], Turf: ['A', 2], Dirt: ['G', 0] }],
    ['Oguri Cap', 101601, { Sprint: ['B', 1], Mile: ['A', 2], Medium: ['A', 2], Long: ['B', 1], Turf: ['A', 2], Dirt: ['B', 1] }],
    ['Taiki Shuttle', 101701, { Sprint: ['A', 2], Mile: ['A', 3], Medium: ['C', 0], Long: ['G', 0], Turf: ['A', 2], Dirt: ['A', 1] }],
    ['Rice Shower', 101801, { Sprint: ['G', 0], Mile: ['D', 0], Medium: ['A', 2], Long: ['A', 3], Turf: ['A', 2], Dirt: ['G', 0] }],
    ['El Condor Pasa', 101901, { Sprint: ['C', 1], Mile: ['A', 2], Medium: ['A', 2], Long: ['C', 0], Turf: ['A', 2], Dirt: ['A', 2] }],
    ['Mihono Bourbon', 102001, { Sprint: ['C', 1], Mile: ['A', 2], Medium: ['A', 2], Long: ['C', 0], Turf: ['A', 2], Dirt: ['B', 1] }],
  ].map(([name, id, apt]) => ({ name, id, apt }));
  let SOLVER_CHAR_MAP = Object.fromEntries(SOLVER_CHARS.map((c) => [c.id, c]));
  const charById = (id) => SOLVER_CHAR_MAP[id] || SOLVER_CHARS[0];
  // The list above is just a fallback. The FULL roster (every character, real card
  // ids + base aptitudes) is loaded from the backend the first time the solver modal
  // opens — the static list was missing most characters and had several wrong ids.
  function rebuildSolverChars(list) {
    if (Array.isArray(list) && list.length) SOLVER_CHARS = list;
    SOLVER_CHAR_MAP = Object.fromEntries(SOLVER_CHARS.map((c) => [c.id, c]));
  }
  let _rosterLoaded = false;
  async function loadSolverRoster() {
    if (_rosterLoaded) return false;
    try {
      const r = (window.Icarus && Icarus.api) ? await Icarus.api('/api/character-profile/roster') : null;
      if (r && r.success && Array.isArray(r.characters) && r.characters.length) { rebuildSolverChars(r.characters); _rosterLoaded = true; return true; }
    } catch (e) { /* keep the built-in fallback list */ }
    return false;
  }

  const EPITHETS = [
    ['All-Around Otaku', 'Agnes Digital only — win the Japan Dirt Derby, Mile Championship, February Stakes, Yasuda Kinen, and Tenno Sho (Autumn)', 'Win the Arima Kinen (Senior)'],
    ['All-Rounder', 'Win 3 turf G1 races', 'Win 3 dirt G1 races'],
    ['Apple Far from the Tree', 'Inherit memories from parents that did not win any graded races', 'Win at least one G1 race'],
    ['Bakushin King', 'Sakura Bakushin O only — win 11 races with a length of 1400m or lower', 'Win the Sprinters Stakes (Senior) as the most popular'],
    ['Beauty of the Century', 'Gold City only — win the Hanshin Juvenile Fillies and raise all trainings to at least 3', 'Complete the Career'],
    ['Best Actress', 'Mejiro McQueen only — win the Kikuka Sho and Tenno Sho (Spring); reach 1200+ Stamina', 'Earn a total of at least 320,000 fans'],
    ['Blinding Flash', 'Eishin Flash only — win the Tokyo Yushun as a Late Surger', 'Win the Tenno Sho (Autumn) as a Late Surger'],
    ['Blooming Sakura', 'Sakura Chiyono O only — inherit a parent who won the Asahi Hai and reach 1200+ Speed', 'Win the Asahi Hai Futurity Stakes'],
    ['Breakneck Miler', 'Trackblazer scenario only — win the NHK Mile Cup and Mile Championship', 'Reward: 2 random stats +15'],
    ['Crimson Comet', 'Win 5 races as an End Closer', 'Reach 1000 or more Power'],
    ['Dirt Sovereign', 'Win the February Stakes and Champions Cup', 'Win 4 dirt G1 races'],
    ['Endless Stamina', 'Reach 1200 or more Stamina', 'Win a 3000m or longer race'],
    ['Front-Runner Legend', 'Win 6 races wire-to-wire as a Front Runner', 'Win the Takarazuka Kinen'],
    ['Golden Generation', 'Win every Classic Triple Crown race', 'Reward: 3 random stats +20'],
    ['Heart of Glory', 'Hold a Mood level of Great for 10 straight turns', 'Win the Arima Kinen'],
    ['Late Bloomer', 'Win your first G1 in the Senior class', 'Win 3 G1 races in one season'],
    ['Mile Monarch', 'Win the Yasuda Kinen, Mile Championship, and Victoria Mile', 'Reach 1100 or more Speed'],
    ['Queen of the Turf', 'Win 4 turf G1 races as a filly', 'Earn 250,000 fans'],
    ['Rising Phoenix', 'Recover from a losing streak of 3+ to win a G1', 'Win the Japan Cup'],
    ['Spring Tenno Triumph', 'Win the Tenno Sho (Spring)', 'Win the Tenno Sho (Spring) two years running'],
    ['Undefeated Sprinter', 'Win every sprint race entered (minimum 5)', 'Win the Sprinters Stakes'],
  ];
  const OW_PRESETS = {
    fans: ['1', '1', '0.001', '8', '3', '5', '26', '100', '0', '4'],
    stat: ['1', '3', '0', '12', '4', '6', '18', '100', '0', '3'],
  };
  const SCOREW = [
    ['Race Value Weight', '1', 'Multiplier on race stat/SP reward.'],
    ['Epithet Value Weight', '1', 'Bonus for races that progress target epithets.'],
    ['Fan Weight', '0.001', 'Score per projected fan.'],
    ['Hint Reward Weight', '8', 'Bonus for skill-hint epithets.'],
    ['Consecutive Race Penalty', '3', 'Penalty after 3+ race streaks.'],
    ['Summer Block Penalty', '5', 'Penalty for summer camp racing.'],
    ['Race Bonus %', '26', 'Projected race reward uplift.'],
    ['Race Cost %', '100', 'Cost subtracted from each race.'],
    ['Fan Bonus %', '0', 'Projected in-game fan bonus applied to fan rewards.'],
    ['Max Streak', '4', 'Maximum planned consecutive race streak.'],
  ];

  const note = (html, amber = false) => `<div class="snote${amber ? ' amber' : ''}">${html}</div>`;
  const charRow = (name, id, on) => `<button class="charrow${on ? ' on' : ''}" type="button" data-char="${id}"><span class="charrow-name">${esc(name)}</span><span class="charrow-id">ID ${id}</span></button>`;
  const gradeBtns = (apt, manual) => GRADES8.map((g) => `<button class="gradebtn${g === manual ? ' on' : ''}" type="button" data-apt="${apt}" data-grade="${g}">${g}</button>`).join('') + `<button class="gradebtn base" type="button" data-apt-base="${apt}">Base</button>`;
  function aptRowHtml(name, base, sparks, manual) {
    const final = finalGrade(manual, sparks);
    const desc = `Base ${base} · Manual Start ${manual} · Sparks +${sparks} · Solver Final ${final}`;
    return `<div class="srow aptrow"><div class="srow-text"><strong>${name}</strong><span>${desc}</span></div><div class="srow-ctrl gradeset">${gradeBtns(name, manual)}</div></div>`;
  }
  function aptRowsHtml() {
    const c = charById(SV.charId);
    return APT_ALL.map((name) => { const [base, sparks] = c.apt[name]; return aptRowHtml(name, base, sparks, SV.manual[name] || base); }).join('');
  }
  const threshHtml = (active) => `<div class="gradeset thresh">${GRADES8.map((g) => `<button class="gradebtn${g === active ? ' on' : ''}" type="button" data-thresh="${g}">${g}</button>`).join('')}</div>`;
  const epCard = (e, kind, i, on) => `<button class="epcard${on ? ' on' : ''}" type="button" data-ep="${kind}" data-i="${i}"><div class="epcard-name">${esc(e[0])}</div><div class="epcard-cond">${esc(e[1])}</div>${e[2] ? `<div class="epcard-rew">${esc(e[2])}</div>` : ''}</button>`;
  const epGrid = (kind) => EPITHETS.map((e, i) => epCard(e, kind, i, SV.ep[kind].has(i))).join('');
  function epSection(title, kind, desc) {
    return sec(title,
      `<div class="ephead"><div class="ephead-text"><div class="epcount">Selected <span data-epcount="${kind}">${SV.ep[kind].size}</span> / 217</div><p class="field-help" style="margin:5px 0 0">${desc}</p></div><button class="abtn danger ep-clear" type="button" data-epclear="${kind}">CLEAR</button></div>`,
      `<div class="search epsearch"><span class="ic">⌕</span><input type="text" placeholder="Search 217 epithets…" data-epsearch="${kind}"></div>`,
      `<div class="epgrid" data-epgrid="${kind}">${epGrid(kind)}</div>`);
  }
  const swField = ([label, val, desc], i) => `<div class="swfield"><label class="swlabel">${esc(label)}</label><input class="numf" type="number" step="any" value="${val}" data-sw="${i}"><p class="swdesc">${esc(desc)}</p></div>`;

  let SV; // live solver UI state (reset each open)

  function mountSolver(o) {
    const reApt = () => { const h = o.querySelector('#solver-apt-rows'); if (h) h.innerHTML = aptRowsHtml(); };
    const reChars = (f) => {
      const h = o.querySelector('#solver-char-list'); if (!h) return;
      const q = (f || '').toLowerCase();
      h.innerHTML = SOLVER_CHARS.filter((c) => !q || c.name.toLowerCase().includes(q)).map((c) => charRow(c.name, c.id, c.id === SV.charId)).join('');
    };
    const setName = () => { const el = o.querySelector('#solver-char-name'); if (el) el.textContent = charById(SV.charId).name; };
    const epCount = (kind) => { const el = o.querySelector(`[data-epcount="${kind}"]`); if (el) el.textContent = SV.ep[kind].size; };

    o.addEventListener('click', (e) => {
      const ch = e.target.closest('[data-char]');
      if (ch) { SV.charId = +ch.dataset.char; SV.manual = {}; setName(); reApt(); reChars(o.querySelector('#solver-char-search') && o.querySelector('#solver-char-search').value); return; }
      const g = e.target.closest('[data-grade]');
      if (g) { SV.manual[g.dataset.apt] = g.dataset.grade; reApt(); return; }
      const gb = e.target.closest('[data-apt-base]');
      if (gb) { delete SV.manual[gb.dataset.aptBase]; reApt(); return; }
      const th = e.target.closest('[data-thresh]');
      if (th) { SV.thresh = th.dataset.thresh; o.querySelectorAll('[data-thresh]').forEach((b) => b.classList.toggle('on', b.dataset.thresh === SV.thresh)); return; }
      const ow = e.target.closest('[data-owp]');
      if (ow) { o.querySelectorAll('[data-owp]').forEach((b) => b.classList.toggle('on', b === ow)); const p = OW_PRESETS[ow.dataset.owp]; o.querySelectorAll('[data-sw]').forEach((inp) => { inp.value = p[+inp.dataset.sw]; }); return; }
      const ep = e.target.closest('[data-ep]');
      if (ep) { const k = ep.dataset.ep, i = +ep.dataset.i, set = SV.ep[k]; set.has(i) ? set.delete(i) : set.add(i); ep.classList.toggle('on', set.has(i)); epCount(k); return; }
      const epc = e.target.closest('[data-epclear]');
      if (epc) { const k = epc.dataset.epclear; SV.ep[k].clear(); o.querySelectorAll(`[data-ep="${k}"]`).forEach((c) => c.classList.remove('on')); epCount(k); return; }
      const rf = e.target.closest('#solver-refresh');
      if (rf) { SV.manual = {}; reApt(); rf.textContent = 'REFRESHED ✓'; setTimeout(() => { rf.textContent = 'REFRESH PROFILE'; }, 900); return; }
      const ra = e.target.closest('#solver-reset-apt');
      if (ra) { SV.manual = {}; reApt(); return; }
    });
    o.addEventListener('input', (e) => {
      if (e.target.id === 'solver-char-search') { reChars(e.target.value); return; }
      const es = e.target.closest('[data-epsearch]');
      if (es) { const k = es.dataset.epsearch, q = es.value.toLowerCase(); o.querySelectorAll(`[data-ep="${k}"]`).forEach((c) => { c.style.display = (!q || c.textContent.toLowerCase().includes(q)) ? '' : 'none'; }); }
    });
    // Pull the full character roster from the backend, then make the Character
    // Preset FOLLOW the trainee selected in Setup (issue #1). The active
    // trainee's card_id is nested under resolved_from on /active -- the old code
    // read top-level a.card_id, so the sync never fired and the picker fell back
    // to the alphabetically-first roster entry ("Admire Vega"). solver_char_match
    // resolves it (exact card_id -> chara_id outfit variant -> display name).
    loadSolverRoster().then(async (changed) => {
      let resolved = null;
      try {
        const a = (window.Icarus && Icarus.api) ? await Icarus.api('/api/character-profile/active') : null;
        const SM = window.IcarusSolverMatch;
        if (a && SM) resolved = SM.resolveActiveToRoster(a, SOLVER_CHARS);
      } catch (e) { /* keep fallback on any failure */ }
      if (resolved) { SV.charId = resolved; SV.manual = {}; }
      // No active trainee match AND the current id isn't a real roster id (the
      // static 100021 default goes stale once the backend roster loads): snap to
      // the first roster entry so the shown name matches the highlighted row
      // instead of silently mismatching via charById().
      else if (!SOLVER_CHAR_MAP[SV.charId] && SOLVER_CHARS.length) { SV.charId = +SOLVER_CHARS[0].id; SV.manual = {}; }
      if (changed || resolved) { setName(); reApt(); reChars((o.querySelector('#solver-char-search') || {}).value); }
    });
  }

  // ============================================================
  //  SKILLS full-page modal
  // ============================================================
  const SK_COLORS = {
    speed: 'linear-gradient(135deg,#f4b14a,#e0722a)',
    accel: 'linear-gradient(135deg,#f4b14a,#e0722a)',
    green: 'linear-gradient(135deg,#5bd07a,#33a85a)',
    recovery: 'linear-gradient(135deg,#5bd07a,#33a85a)',
    blue: 'linear-gradient(135deg,#5aa0f2,#3a6fd8)',
    unique: 'linear-gradient(135deg,#b07cf2,#8a4fd8)',
    debuff: 'linear-gradient(135deg,#f25a6f,#d83a4f)',
  };
  const TIERS = [
    { k: 'S', idx: 1, name: 'Tier S', desc: 'Buy first when available', color: '#e879a6' },
    { k: 'A', idx: 2, name: 'Tier A', desc: 'Buy after S', color: '#f2a900' },
    { k: 'B', idx: 3, name: 'Tier B', desc: 'Buy after A', color: '#5a8def' },
    { k: 'C', idx: 4, name: 'Tier C', desc: 'Buy after B', color: '#36c5d0' },
    { k: 'D', idx: 5, name: 'Tier D', desc: 'Buy last, only if SP remains', color: '#3fbfa8' },
  ];
  // Fallback list used only when /api/skills can't be reached (e.g. static preview).
  const SK_SKILLS = [
    ['Professor of Curvature', 201081, 'blue'], ['Corner Adept \u25cb', 200332, 'blue'],
    ['Straightaway Acceleration', 200532, 'speed'], ['Pace Strategy', 200012, 'blue'],
    ['Swinging Maestro', 200421, 'speed'], ['Final Push', 201601, 'speed'],
    ['Gourmet of the Track', 110521, 'green'], ['Lay Low', 200251, 'blue'],
    ['Breath of Fresh Air', 200381, 'unique'], ['Soft Step \u25cb', 200191, 'green'],
    ['Hawkeye', 200831, 'blue'], ['Deep Breathing', 201341, 'green'],
    ['Tail Held High', 201082, 'speed'], ['Calm in a Crowd', 200611, 'green'],
    ['Updraft', 200561, 'speed'], ['Furious Feat', 201501, 'speed'],
    ['Restart', 200041, 'blue'], ['Frenzied Pace', 201201, 'debuff'],
    ['Slick Surge', 200671, 'speed'], ['Outer Swell', 200721, 'blue'],
    ['Position Sense', 200201, 'green'], ['Standard Distance \u25cb', 200911, 'green'],
    ['Concentration', 200021, 'green'], ['Prepared to Pass', 200471, 'blue'],
    ['Productive Lines', 201131, 'blue'], ['Up-Tempo', 200351, 'speed'],
    ['Tether \u25cb', 201741, 'debuff'], ['Shrewd Step', 200351, 'green'],
  ].map(([name, id, color]) => ({ name, id: String(id), icon: '', color }));

  // Derive a swatch colour (fallback behind the real icon image) from skill metadata.
  function skColor(info) {
    const g = +(info.grade_value || 0);
    const cat = +(info.skill_category || 0);
    const s = String(info.icon_id || info.iconId || '');
    if (g < 0) return 'debuff';
    if (cat === 5) return 'unique';
    if (/^(2001|2004|2005|2006|2009)/.test(s)) return 'speed';
    if (/^(1001|1002|1003|1004|1005|1006)/.test(s)) return 'green';
    return 'blue';
  }
  // Normalize the /api/skills dict into the picker's list: buyable skills only
  // (need_skill_point > 0 drops inherited uniques/events), de-duped by name.
  function normalizeSkills(obj) {
    if (!obj || typeof obj !== 'object') return [];
    const out = []; const seen = new Set();
    for (const [id, info] of Object.entries(obj)) {
      if (!info || typeof info !== 'object') continue;
      const name = String(info.name || '').trim();
      if (!name || seen.has(name)) continue;
      if (+(info.need_skill_point || 0) <= 0) continue;
      seen.add(name);
      out.push({ id: String(id), name, icon: info.icon_id || info.iconId || '', color: skColor(info) });
    }
    out.sort((a, b) => a.name.localeCompare(b.name));
    return out;
  }
  let SK_SKILLS_CACHE = null;
  async function loadSkillLibrary() {
    if (SK_SKILLS_CACHE) return SK_SKILLS_CACHE;
    try {
      const r = await api('/api/skills');
      const list = normalizeSkills(r && r.skills);
      if (list.length) { SK_SKILLS_CACHE = list; return list; }
    } catch (e) { /* static preview — fall back */ }
    return SK_SKILLS.slice();
  }

  const skSec = (label, inner) => `<div class="sk-seclabel">${label}</div><div class="sk-card">${inner}</div>`;
  const tglRow = (id, label, on, help) => `<div class="srow"><div class="srow-text"><strong>${label}</strong>${help ? `<span>${help}</span>` : ''}</div><div class="srow-ctrl"><div class="tgl${on ? ' on' : ''}" id="${id}"><span class="tgl-sw"></span></div></div></div>`;
  // Skill-type filters are GLOBAL (one skip_* flag each), so only the primary
  // plan binds them to config keys; the other plan tabs reuse the same globals.
  const skFilters = (bind) => skSec('SKILL TYPE FILTERS',
    toggle('Skip Green Skills', true, 'Exclude green stat-trigger skills.', bind ? 'sk.skip_green_skills' : '') +
    toggle('Skip Red Skills', true, 'Exclude red debuff skills.', bind ? 'sk.skip_red_skills' : '') +
    toggle('Skip Unique Skills', false, 'Exclude inherited unique legacy skills.', bind ? 'sk.skip_unique_skills' : ''));

  function skillsBody() {
    return `
      <div class="sk-info"><div class="sk-info-head"><span>\u24d8</span> How skill spending works <span class="x">\u2303</span></div><div class="sk-info-body"><p>Allows configuration of automated skill point spending.</p><p style="margin-top:8px">This feature buys skills automatically once the Skill Point Threshold is reached. Use it to make rank-farming runs less of a hassle.</p></div></div>

      ${skSec('OPTIMIZE SP SPEND', `<div class="sk-explain"><p><b>What it does:</b> spends your skill points to squeeze out the most total skill value per point \u2014 a value-for-money optimizer \u2014 instead of buying strictly top-to-bottom in your priority order.</p><p style="margin-top:6px"><b>How it works:</b> at every purchase point it ranks each affordable skill by its value \u00f7 SP cost and fills your available SP with the best-value picks first.</p><p style="margin-top:6px"><b>Turning it off:</b> leave it off (the default) to keep the standard priority-order buying. You can flip it any time, and the change applies to your next run.</p></div>` + toggle('Optimize SP spend', false, 'Value-per-point buying (off = priority order).', 'opt.enabled'))}

      ${skSec('STYLE', row('Running Style', 'Dictates which skills are considered for purchase based on the preferred running style.', '<span class="sk-badge">FROM RACING</span>') + row('Track Distance', 'Dictates which skills are considered for purchase based on the track distance.', '<span class="sk-badge">FROM TRAINING</span>') + row('Track Surface', 'Dictates which skills are considered for purchase based on the terrain.', '<span class="sk-badge">ANY</span>'))}

      <div class="sk-info"><div class="sk-info-head"><span>\u24d8</span> How Running Style affects skill picks <span class="x">\u2303</span></div><div class="sk-info-body"><p>Running Style is inherited from Racing Settings. Configure Skills only filters and weights skill purchases; it does not own race strategy.</p></div></div>

      <div class="sk-seclabel">SKILL PLANS</div>
      <div class="sk-plans"><button class="sk-plan on" type="button" data-plan="check">Skill Point Check</button><button class="sk-plan" type="button" data-plan="prefinals">Pre-Finals</button><button class="sk-plan" type="button" data-plan="complete">Career Complete</button></div>
      <div data-planpanel="check">
        <div class="sk-card">${toggle('Enable Skill Point Check', true, 'Allow automatic skill spending once the threshold is reached.', 'sk.enable_skill_point_check')}${numf('Skill Point Threshold', 420, 'The number of skill points to accumulate before purchasing skills.', 'sk.learn_skill_threshold')}${toggle('Stop After Recommended Skills', false, 'When ON, stop spending SP once your recommended/top-tier skills are owned. Leave OFF to keep buying good skills (the pre-finals dump still overrides this).', 'sk.skill_stop_after_recommended')}${toggle('Enable Skill Point Check Plan (Beta)', true, 'Purchase skills based on this plan configuration.', 'sk.enable_skill_point_check_plan')}${toggle('Purchase All Negative Skills', false, 'Attempt to buy all negative skills when available.', 'sk.purchase_negative_skills')}</div>
        ${skFilters(true)}
      </div>
      <div data-planpanel="prefinals" style="display:none">
        <div class="sk-card"><p style="margin:8px 0;font:400 var(--fs-base) var(--sans);color:var(--dim)">This plan uses the same weighted purchase rules when triggered by pre finals.</p>${toggle('Enable Plan', false, 'Purchase skills during pre finals.', 'sk.pre_finals_enabled')}</div>
      </div>
      <div data-planpanel="complete" style="display:none">
        <div class="sk-card"><p style="margin:8px 0;font:400 var(--fs-base) var(--sans);color:var(--dim)">This plan uses the same weighted purchase rules when triggered by career complete.</p>${toggle('Enable Plan', false, 'Purchase skills during career complete.', 'sk.career_complete_enabled')}</div>
      </div>

      ${skSec('STRATEGY &amp; PLANNED SKILLS', sel('Automated Skill Point Spending Strategy', [['best_skills_first', 'Best Skills First'], ['optimize_rank', 'Optimize Rank']], 'best_skills_first', '', 'sk.skill_spending_strategy') + sel('Skill Optimization Target', [['career', 'Career (Fans / Single-Mode)'], ['team_trials', 'Team Trials'], ['champions', 'Champions Meeting (PvP)']], 'career', 'Career (default) keeps fans-first single-mode value. Team Trials / Champions instead weight each skill by its rank on your finished uma in that mode — and KEEP single-mode-disabled skills, which Career hard-drops because the game turns them off during a career run. Works alongside (not instead of) the strategy above.', 'sk.skill_optimization_target') + `<div class="srow"><div class="srow-text"><strong>Planned Skills</strong><span id="sk-selcount">Selected 0 / ${SK_SKILLS.length} skills</span></div><div class="srow-ctrl"><button class="abtn danger" type="button" id="sk-clear">CLEAR</button></div></div><div class="sk-tabs"><button class="sk-tab on" type="button" data-listtab="plan">Plan (0)</button><button class="sk-tab" type="button" data-listtab="blacklist">Blacklist (0)</button></div>` + tglRow('sk-showsel', 'Show Only Selected Skills', false, 'Filter the list to only currently selected skills.') + `<input class="sk-search" id="sk-search" placeholder="Search skills by name..."><div style="font:400 var(--fs-sm) var(--sans);color:var(--dim);margin:2px 0 6px">Click a skill to add it to the plan (the tier picker opens automatically) · right-click any skill to add it to a tier list.</div><div class="sk-list" id="sk-list"></div>`)}

      <div class="sk-seclabel">MANUAL SKILL TIERS <span class="sk-status off" id="sk-status">INACTIVE \u2014 NO TIERS SET (AUTO PLAN IN USE)</span></div>
      <div class="sk-card" style="padding:16px 18px">
        <p style="margin:0 0 12px;font:400 var(--fs-base)/1.7 var(--sans);color:var(--dim)">Build a tier list of the skills you want the bot to buy. Whenever any tier has skills, this list <b style="color:var(--ink-2)">drives purchasing</b> \u2014 the bot buys these by tier (T1 first), and manually-listed skills are bought even if they're off-distance/off-style. Within a tier, smart score / cost breaks ties.<br>If all tiers are empty, the bot uses the automatic skill-point plan instead.</p>
        ${tglRow('sk-auto', 'After selected skills are bought, switch to AUTO purchasing', false, 'Off (default) buys only the skills in these tiers then stops; on lets the automatic plan spend the rest once your listed skills are all owned.')}
        <div id="sk-tiers"></div>
        <p style="margin:10px 0 0;font:400 var(--fs-md) var(--sans);color:var(--dim)">Right-click a skill in <b style="color:var(--ink-2)">Planned Skills</b> above to add it to a tier.</p>
      </div>`;
  }

  async function mountSkills(o) {
    let SKILLS = await loadSkillLibrary();
    const byId = {}; const byName = {};
    const index = (s) => { byId[s.id] = s; byName[s.name.toLowerCase()] = s; };
    SKILLS.forEach(index);
    // Resolve a stored skill NAME to a list entry, synthesizing a placeholder
    // for any name not in the buyable library so it stays selectable + round-trips.
    function resolveName(name) {
      const key = String(name || '').toLowerCase();
      let s = byName[key];
      if (!s) { s = { id: 'x:' + name, name: String(name), icon: '', color: 'blue', synth: true }; SKILLS.push(s); index(s); }
      return s;
    }
    const state = { listTab: 'plan', onlySel: false, search: '', selected: {}, tiers: { S: [], A: [], B: [], C: [], D: [] }, addTier: 'B' };
    let dragId = null;
    const q = (sel) => o.querySelector(sel);

    // ---- seed selection + tiers from the loaded skill-config (forced_skills /
    //      blacklist live on skill_strategy; tiers in manual_skill_tiers "1".."5"). ----
    const cfg = o._skillCfg || {};
    const strat = (cfg.skill_strategy && typeof cfg.skill_strategy === 'object') ? cfg.skill_strategy : {};
    (strat.forced_skills || []).forEach((n) => { state.selected[resolveName(n).id] = 'plan'; });
    (strat.blacklist || []).forEach((n) => { const id = resolveName(n).id; if (state.selected[id] !== 'plan') state.selected[id] = 'blacklist'; });
    const mt = cfg.manual_skill_tiers || {};
    TIERS.forEach((t) => { (mt[String(t.idx)] || []).forEach((n) => { const id = resolveName(n).id; if (!state.tiers[t.k].includes(id)) state.tiers[t.k].push(id); }); });
    const autoTgl = q('#sk-auto');
    if (autoTgl) autoTgl.classList.toggle('on', !!cfg.skill_manual_auto_fallback);
    const showSelTgl = q('#sk-showsel');
    if (showSelTgl) showSelTgl.classList.toggle('on', !!cfg.show_only_selected_skills);
    state.onlySel = !!cfg.show_only_selected_skills;
    // "Optimize SP spend" is a global setting on its own endpoint, not part of
    // the per-preset skill-config — load + persist it independently.
    const optTgl = o.querySelector('[data-k="opt.enabled"]');
    if (optTgl) {
      api('/api/skills/optimizer').then((r) => { if (r && typeof r.enabled !== 'undefined') optTgl.classList.toggle('on', !!r.enabled); }).catch(() => {});
      optTgl.addEventListener('click', () => setTimeout(() => {
        api('/api/skills/optimizer', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ enabled: optTgl.classList.contains('on') }) }).catch(() => {});
      }, 0));
    }

    // ---- collector consumed by the /api/skill-config SAVE_COLLECTOR ----
    o._collectSkillStrategy = () => {
      const nameOf = (id) => (byId[id] && byId[id].name) || null;
      const forced_skills = [], blacklist = [];
      Object.entries(state.selected).forEach(([id, tab]) => { const n = nameOf(id); if (!n) return; (tab === 'plan' ? forced_skills : blacklist).push(n); });
      const tiers = {};
      TIERS.forEach((t) => { tiers[String(t.idx)] = state.tiers[t.k].map(nameOf).filter(Boolean); });
      const auto = !!(autoTgl && autoTgl.classList.contains('on'));
      const showOnly = !!(showSelTgl && showSelTgl.classList.contains('on'));
      return { forced_skills, blacklist, manual_skill_tiers: tiers, auto, showOnly };
    };

    o.querySelectorAll('.sk-info-head').forEach((h) => h.addEventListener('click', () => h.parentElement.classList.toggle('collapsed')));
    o.querySelectorAll('.sk-plan').forEach((b) => b.addEventListener('click', () => {
      o.querySelectorAll('.sk-plan').forEach((x) => x.classList.remove('on')); b.classList.add('on');
      o.querySelectorAll('[data-planpanel]').forEach((p) => { p.style.display = p.dataset.planpanel === b.dataset.plan ? '' : 'none'; });
    }));
    o.querySelectorAll('.sk-tab').forEach((b) => b.addEventListener('click', () => {
      state.listTab = b.dataset.listtab; o.querySelectorAll('.sk-tab').forEach((x) => x.classList.remove('on')); b.classList.add('on'); renderList();
    }));
    q('#sk-search').addEventListener('input', (e) => { state.search = e.target.value.toLowerCase(); renderList(); });
    const showSel = q('#sk-showsel');
    showSel.addEventListener('click', () => setTimeout(() => { state.onlySel = showSel.classList.contains('on'); renderList(); }, 0));
    q('#sk-clear').addEventListener('click', () => { Object.keys(state.selected).forEach((id) => { if (state.selected[id] === state.listTab) delete state.selected[id]; }); renderList(); });

    function updateCounts() {
      const plan = Object.values(state.selected).filter((v) => v === 'plan').length;
      const bl = Object.values(state.selected).filter((v) => v === 'blacklist').length;
      const pt = o.querySelector('[data-listtab="plan"]'); if (pt) pt.textContent = `Plan (${plan})`;
      const bt = o.querySelector('[data-listtab="blacklist"]'); if (bt) bt.textContent = `Blacklist (${bl})`;
      const sc = q('#sk-selcount'); if (sc) sc.textContent = `Selected ${state.listTab === 'plan' ? plan : bl} / ${SKILLS.length} skills`;
    }
    function skillIco(s) {
      const grad = SK_COLORS[s.color] || SK_COLORS.blue;
      const img = s.icon ? `<img src="/api/skill-icons/${encodeURIComponent(s.icon)}.png" style="width:100%;height:100%;border-radius:inherit;object-fit:cover" onerror="this.remove()">` : '';
      return `<div class="sk-skill-ico" style="background:${grad}">${img}</div>`;
    }
    function renderList() {
      const list = q('#sk-list');
      const items = SKILLS.filter((s) => s.name.toLowerCase().includes(state.search) && (!state.onlySel || state.selected[s.id] === state.listTab));
      list.innerHTML = items.length
        ? items.map((s) => `<div class="sk-skill${state.selected[s.id] === state.listTab ? ' sel' : ''}" data-id="${esc(String(s.id))}">${skillIco(s)}<div><div class="sk-skill-name">${esc(s.name)}</div><div class="sk-skill-id">ID: ${esc(String(s.id))}</div></div></div>`).join('')
        : `<div class="sk-empty">No skills match the current filters.</div>`;
      updateCounts();
    }
    q('#sk-list').addEventListener('click', (e) => {
      const r = e.target.closest('.sk-skill'); if (!r) return;
      const id = r.dataset.id;
      const wasSelected = state.selected[id] === state.listTab;
      if (wasSelected) delete state.selected[id]; else state.selected[id] = state.listTab;
      renderList();
      // Adding a skill to the Plan auto-opens the tier picker so it can be planned
      // AND tiered in one go (replaces the removed "add to tier" search bar).
      if (!wasSelected && state.listTab === 'plan') openCtx(e.clientX, e.clientY, id);
    });
    q('#sk-list').addEventListener('contextmenu', (e) => { const r = e.target.closest('.sk-skill'); if (!r) return; e.preventDefault(); openCtx(e.clientX, e.clientY, r.dataset.id); });

    function openCtx(x, y, id) {
      closeCtx();
      const m = document.createElement('div'); m.className = 'sk-ctx';
      m.style.left = Math.min(x, window.innerWidth - 220) + 'px'; m.style.top = Math.min(y, window.innerHeight - 230) + 'px';
      m.innerHTML = `<div class="sk-ctx-title">${esc((byId[id] || {}).name || '')}</div>` + TIERS.map((t) => `<div class="sk-ctx-item" data-tier="${t.k}">Move to ${t.name} (T${t.idx})</div>`).join('');
      document.body.appendChild(m);
      m.querySelectorAll('.sk-ctx-item').forEach((it) => it.addEventListener('click', () => { addToTier(id, it.dataset.tier); closeCtx(); }));
      setTimeout(() => document.addEventListener('mousedown', ctxOutside), 0);
    }
    function ctxOutside(e) { if (!e.target.closest('.sk-ctx')) closeCtx(); }
    function closeCtx() { const m = document.querySelector('.sk-ctx'); if (m) m.remove(); document.removeEventListener('mousedown', ctxOutside); }

    function addToTier(id, k) { TIERS.forEach((t) => { state.tiers[t.k] = state.tiers[t.k].filter((x) => x !== id); }); state.tiers[k].push(id); renderTiers(); }
    function renderTiers() {
      q('#sk-tiers').innerHTML = TIERS.map((t) => {
        const ids = state.tiers[t.k];
        const chips = ids.length ? ids.map((id) => `<span class="sk-chip" draggable="true" data-id="${esc(String(id))}" data-tier="${t.k}">${esc((byId[id] || {}).name || '')} <span class="rm">\u00d7</span></span>`).join('') : `<span class="sk-tier-hint">No skills in ${t.name} yet \u2014 drag a chip here or right-click a skill.</span>`;
        return `<div class="sk-tier" data-tier="${t.k}" style="border-left-color:${t.color}"><div class="sk-tier-head"><span class="sk-tier-num">T${t.idx}</span><span class="sk-tier-name">${t.name}</span><span class="sk-tier-desc">${t.desc}</span><span class="sk-tier-count">${ids.length} skill(s)</span></div><div class="sk-tier-chips">${chips}</div></div>`;
      }).join('');
      const any = TIERS.some((t) => state.tiers[t.k].length);
      const st = q('#sk-status'); if (st) { st.className = 'sk-status ' + (any ? 'on' : 'off'); st.textContent = any ? 'ACTIVE \u2014 BUYING LISTED SKILLS ONLY, THEN STOPPING' : 'INACTIVE \u2014 NO TIERS SET (AUTO PLAN IN USE)'; }
      wireTierDnD();
    }
    function wireTierDnD() {
      o.querySelectorAll('.sk-chip').forEach((c) => {
        c.addEventListener('dragstart', () => { dragId = c.dataset.id; c.classList.add('dragging'); });
        c.addEventListener('dragend', () => { c.classList.remove('dragging'); dragId = null; });
        c.querySelector('.rm').addEventListener('click', (e) => { e.stopPropagation(); const k = c.dataset.tier; const rid = c.dataset.id; state.tiers[k] = state.tiers[k].filter((x) => String(x) !== rid); renderTiers(); });
      });
      o.querySelectorAll('.sk-tier').forEach((t) => {
        t.addEventListener('dragover', (e) => { e.preventDefault(); t.classList.add('drop'); });
        t.addEventListener('dragleave', () => t.classList.remove('drop'));
        t.addEventListener('drop', (e) => { e.preventDefault(); t.classList.remove('drop'); if (dragId != null) addToTier(dragId, t.dataset.tier); });
      });
    }
    renderList(); renderTiers();
  }

  // ============================================================
  //  Library modals wired to live session/userdata endpoints
  // ============================================================
  // contain (not cover): source icons are square 128px; cover cropped card art
  // edges in the wider modal cells. contain shows the whole icon, no crop.
  const cardImg = (id, h) => `<img src="/api/images/${esc(String(id || ''))}.png" alt="" style="width:100%;height:${h}px;object-fit:contain;display:block" onerror="this.style.visibility='hidden'">`;
  const rarityRibbon = (rarity) => {
    const R = String(rarity || '').toUpperCase(); if (!R) return '';
    const bg = R === 'SSR' ? 'linear-gradient(120deg,#7ad7f0,#b98cff,#ff9ec7)' : R === 'SR' ? 'linear-gradient(135deg,#f6d36a,#caa13a)' : 'linear-gradient(135deg,#cdd4df,#9aa3b2)';
    return `<span style="position:absolute;top:5px;left:5px;font:800 var(--fs-2xs) var(--cond);letter-spacing:.05em;color:#1a1206;background:${bg};padding:2px 5px;border-radius:3px;box-shadow:0 1px 2px rgba(0,0,0,.45)">${esc(R)}</span>`;
  };
  const cornerStar = '<span style="position:absolute;top:4px;right:5px;color:#f6c945;font-size:var(--fs-base);text-shadow:0 1px 2px rgba(0,0,0,.5)">\u2605</span>';
  const udSource = (s) => ({ pointer: 'pointer file', env: 'environment variable', build: 'in-build folder', legacy: 'legacy path' }[String(s || '').toLowerCase()] || (s || '\u2014'));

  // ---- Build Custom Deck: owned support cards from /api/session, applied to
  //      the live selection via POST /api/selection (5 own cards + 1 friend). ----
  async function mountCustomDeck(o) {
    o._deckState = { cards: [], selection: {}, supports: [] };
    const status = o.querySelector('#cd-status');
    let sess = null;
    try { sess = await api('/api/session'); } catch (e) { /* preview */ }
    if (sess && sess.selection) o._deckState.selection = sess.selection;
    o._deckState.supports = ((sess && sess.supports) || []).filter((c) => c && c.id && !String(c.id).includes('{') && !String(c.name || '').includes('Unknown'));
    const cur = o._deckState.selection.deck;
    if (cur && cur.id === 'custom' && Array.isArray(cur.cards)) o._deckState.cards = cur.cards.slice(0, 5).map((c) => ({ ...c }));
    const search = o.querySelector('#cd-search');
    const typeF = o.querySelector('#cd-type');
    const has = (id) => o._deckState.cards.some((c) => String(c.id) === String(id));
    const toRun = (c) => ({ id: c.id, name: c.name, type: c.type, rarity: c.rarity, limit_break_count: Number(c.limit_break ?? c.limit_break_count ?? 0), exp: Number(c.exp ?? 0) });
    function renderSlots() {
      const slots = o.querySelector('#cd-slots');
      const cards = o._deckState.cards;
      slots.innerHTML = Array.from({ length: 5 }, (_, i) => { const c = cards[i]; return c ? `<div class="deckslot filled" data-rm="${esc(String(c.id))}" title="${esc(c.name)} \u2014 click to remove">${esc(String(c.name || '').split(' ')[0].toUpperCase())}</div>` : `<div class="deckslot">EMPTY</div>`; }).join('') + `<div class="deckslot">+ FRIEND</div>`;
      slots.querySelectorAll('[data-rm]').forEach((el) => el.addEventListener('click', () => { const id = el.dataset.rm; o._deckState.cards = o._deckState.cards.filter((c) => String(c.id) !== id); renderAll(); }));
    }
    function renderOwned() {
      const grid = o.querySelector('#cd-grid');
      const q = (search.value || '').toLowerCase().trim();
      const tf = (typeF.value || '').toLowerCase();
      let rows = o._deckState.supports;
      if (q) rows = rows.filter((c) => String(c.name || '').toLowerCase().includes(q));
      if (tf && tf !== 'all types') rows = rows.filter((c) => String(c.type || '').toLowerCase() === tf);
      if (status) status.textContent = o._deckState.supports.length ? `${rows.length} owned card(s) \u00b7 ${o._deckState.cards.length}/5 selected` : 'No owned cards \u2014 log in and load your account first.';
      grid.innerHTML = rows.slice(0, 500).map((c) => `<div class="cardcell" data-id="${esc(String(c.id))}" title="${esc(c.name)}" style="${has(c.id) ? 'outline:2px solid var(--amber);outline-offset:-2px' : ''}"><div class="cardcell-img" style="height:64px">${cardImg(c.id, 64)}</div><div class="cardcell-name">${esc(String(c.name || '').toUpperCase())}</div></div>`).join('') || `<div class="sk-empty">No owned cards match.</div>`;
      grid.querySelectorAll('.cardcell').forEach((el) => el.addEventListener('click', () => {
        const id = el.dataset.id;
        if (has(id)) o._deckState.cards = o._deckState.cards.filter((c) => String(c.id) !== id);
        else { if (o._deckState.cards.length >= 5) { if (status) status.textContent = 'Max 5 cards (the 6th slot is a borrowed friend support).'; return; } const card = o._deckState.supports.find((c) => String(c.id) === id); if (card) o._deckState.cards.push(toRun(card)); }
        renderAll();
      }));
    }
    function renderAll() { renderSlots(); renderOwned(); }
    search.addEventListener('input', renderOwned);
    typeF.addEventListener('change', renderOwned);
    const clr = o.querySelector('#cd-clear');
    if (clr) clr.addEventListener('click', () => { o._deckState.cards = []; renderAll(); });
    renderAll();
  }
  SAVE_COLLECTORS['/api/selection'] = (o) => {
    const st = o && o._deckState; if (!st || !st.cards.length) return null;
    const cur = st.selection || {};
    const deck = { id: 'custom', name: 'Custom Deck', cards: st.cards.map((c) => ({ ...c })) };
    return { selection: { deck, friend: cur.friend || null, trainee: cur.trainee || null, veterans: cur.veterans || [], guestParents: cur.guestParents || [] } };
  };
  // After applying a custom deck, push the new selection into the live Setup
  // view so its team slots refresh immediately (not just on next session load).
  SAVE_HOOKS['/api/selection'] = (o, payload) => {
    if (I.applyExternalSelection && payload && payload.selection) I.applyExternalSelection(payload.selection);
  };

  // ---- Recommended Supports: owned-collection picks for the selected trainee. ----
  async function mountRecSupports(o) {
    const grid = o.querySelector('#rs-grid');
    const subEl = o.querySelector('#rs-sub');
    let sess = null;
    try { sess = await api('/api/session'); } catch (e) { /* preview */ }
    const trainee = sess && sess.selection && sess.selection.trainee;
    if (!trainee || !trainee.id) { grid.innerHTML = `<div class="sk-empty">Select a trainee in Setup to see recommended support cards.</div>`; return; }
    if (subEl) subEl.textContent = String(trainee.name || 'this trainee');
    grid.innerHTML = `<div class="sk-empty">Finding recommended supports for ${esc(trainee.name || 'this trainee')}\u2026</div>`;

    const ownedBadge = (c) => c.owned
      ? `<span style="display:inline-block;font:700 var(--fs-2xs) var(--cond);letter-spacing:.06em;padding:2px 6px;border-radius:3px;background:rgba(123,255,176,.16);color:#7bffb0">OWNED${c.owned_limit_break != null ? ' LB' + Math.max(0, Number(c.owned_limit_break)) : ''}</span>`
      : `<span style="display:inline-block;font:700 var(--fs-2xs) var(--cond);letter-spacing:.06em;padding:2px 6px;border-radius:3px;background:rgba(255,255,255,.06);color:var(--label)">NOT OWNED</span>`;
    const setupCard = (c) => `<div class="cardcell" style="position:relative;${c.owned ? '' : 'opacity:.6'}"><div class="cardcell-img" style="height:78px;position:relative">${cardImg(c.card_id || '10001', 78)}${rarityRibbon(c.rarity)}${c.owned ? cornerStar : ''}</div><div style="padding:9px"><div style="font:700 var(--fs-md) var(--cond);letter-spacing:.04em;color:var(--ink)">${esc(c.name || 'Unknown')}${c.epithet ? ` <em style="font-style:italic;opacity:.7">${esc(c.epithet)}</em>` : ''}</div><div style="font:600 var(--fs-xs) var(--mono);color:var(--label);margin-top:3px">${esc([c.type, c.owned ? ('LB' + Math.max(0, Number(c.owned_limit_break ?? 0))) : null].filter(Boolean).join(' \u00b7 ') || 'support')}</div><div style="margin-top:5px">${ownedBadge(c)}</div></div></div>`;
    const setupBlock = (label, cards, bonus) => `<div style="margin-bottom:16px"><div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px"><span style="font:700 var(--fs-md) var(--cond);letter-spacing:.14em;color:var(--ink)">${esc(label || 'Setup')}</span>${bonus != null && bonus !== '' ? `<span style="font:700 var(--fs-xs) var(--mono);color:var(--panel);background:var(--amber);padding:2px 7px;border-radius:3px">RACE BONUS ${esc(String(bonus))}</span>` : ''}</div><div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px">${(cards || []).map(setupCard).join('')}</div></div>`;

    // 1) Prefer the scraped Game8 Trackblazer build (setups / budget / alternates).
    let sg = null;
    try { sg = await api(`/api/trainee/support-setups?card_id=${encodeURIComponent(trainee.id)}`); } catch (e) { /* preview */ }
    if (sg && sg.found && ((sg.setups && sg.setups.length) || sg.budget)) {
      const src = sg.source_url ? `<a href="${esc(sg.source_url)}" target="_blank" rel="noopener" style="color:var(--cyan);font:600 var(--fs-xs) var(--mono);text-decoration:none">Game8 source \u2197</a>` : '';
      const notes = (sg.notes && sg.notes.length) ? `<div style="font:500 var(--fs-sm)/1.6 var(--mono);color:var(--dim);margin-bottom:12px">${esc(sg.notes.join(' \u00b7 '))}</div>` : '';
      let html = `<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px"><span style="font:500 var(--fs-sm) var(--mono);color:var(--label)">Trackblazer build \u2014 cards you own are marked ${ownedBadge({ owned: true })}</span>${src}</div>${notes}`;
      (sg.setups || []).forEach((s, i) => { html += setupBlock(s.label || `Setup ${i + 1}`, s.cards, s.race_bonus); });
      if (sg.budget && (sg.budget.cards || []).length) html += setupBlock('Budget Build' + (sg.budget.label ? ' \u2014 ' + sg.budget.label : ''), sg.budget.cards, sg.budget.race_bonus);
      if ((sg.alternates || []).length) html += setupBlock('Alternates', sg.alternates);
      grid.innerHTML = html;
      return;
    }

    // 2) Fallback: owned-collection picks scored for the trainee's stat focus.
    let data = null;
    try { data = await api(`/api/trainee/recommended-supports?card_id=${encodeURIComponent(trainee.id)}`); } catch (e) { /* preview */ }
    const recs = (data && data.recommended) || [];
    if (!recs.length) { grid.innerHTML = `<div class="sk-empty">${data && data.owned_count === 0 ? 'No owned support cards loaded \u2014 log in and load your account first.' : 'No recommendations available for this trainee.'}</div>`; return; }
    const recCard = (c) => `<div class="cardcell" style="position:relative"><div class="cardcell-img" style="height:78px;position:relative">${cardImg(c.id || c.card_id || '10001', 78)}${rarityRibbon(c.rarity)}${cornerStar}</div><div style="padding:9px"><div style="font:700 var(--fs-md) var(--cond);letter-spacing:.04em;color:var(--ink)">${esc(c.name || 'Unknown')}</div><div style="font:600 var(--fs-xs) var(--mono);color:var(--label);margin-top:3px">${esc([c.type, c.limit_break != null ? ('LB' + Math.max(0, Number(c.limit_break))) : null].filter(Boolean).join(' \u00b7 ') || 'support')}</div>${c.reason ? `<div style="font:500 var(--fs-xs)/1.4 var(--mono);color:var(--cyan);margin-top:5px">${esc(c.reason)}</div>` : ''}</div></div>`;
    grid.innerHTML = `<div style="font:500 var(--fs-sm) var(--mono);color:var(--dim);margin-bottom:12px">No Game8 Trackblazer build for this trainee \u2014 best picks from your ${data.owned_count || recs.length} owned cards.</div><div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px">${recs.map(recCard).join('')}</div>`;
  }

  // ---- Userdata folder: live info + set-path (path + non-destructive migrate). ----
  async function mountUserdata(o) {
    let info = null;
    try { info = await api('/api/userdata/info'); } catch (e) { /* preview */ }
    if (!info) return;
    const set = (sel2, v) => { const el = o.querySelector(sel2); if (el) el.textContent = v; };
    set('#ud-current', info.current_path || '(none)');
    set('#ud-source', udSource(info.current_source));
    set('#ud-pointer', info.pointer_file || '(none)');
    const inp = o.querySelector('#ud-path');
    if (inp && !inp.value) inp.value = info.pointer_target || info.current_path || '';
    const warns = [];
    if (info.detection_warning) warns.push(info.detection_warning);
    if (info.is_fallback_build_dir) warns.push("You're using the in-build folder \u2014 settings are lost on the next version unless you reuse the same folder.");
    if (info.is_legacy_path) warns.push('Resolving via a legacy path. Set an Icarus path here to migrate cleanly.');
    const w = o.querySelector('#ud-warn');
    if (w && warns.length) { w.style.display = ''; w.innerHTML = warns.map((p) => `<div style="font:500 var(--fs-sm)/1.5 var(--mono);color:var(--amber);background:#1a1206;border:1px solid var(--amber);border-radius:4px;padding:8px 10px;margin-bottom:6px">\u26a0 ${esc(p)}</div>`).join(''); }
  }
  SAVE_COLLECTORS['/api/userdata/set-path'] = (o) => {
    const inp = o && o.querySelector('#ud-path'); const path = inp ? inp.value.trim() : '';
    if (!path) return null;
    const mig = o.querySelector('#ud-migrate');
    return { path, migrate_current: !!(mig && mig.classList.contains('on')) };
  };

  // ============================================================
  const Modals = {
    training() {
      modal({
        title: 'TRAINING SETTINGS', wide: true, foot: saveBtn('/api/settings-presets'),
        body: `
          ${sec('PRIORITIES',
              chips('Blacklist', [['speed', false, 'Speed'], ['stamina', false, 'Stamina'], ['power', false, 'Power'], ['guts', false, 'Guts'], ['wiz', false, 'Wit']], 'Stats excluded from training unless the skill-hint override is enabled.', 'mant.training_blacklist'),
              prio('tr-main', 'Prioritization', ['Speed', 'Power', 'Wit', 'Stamina', 'Guts'], 'Main stat order used by the native training scorer.'),
              prio('tr-event', 'Event Choice Prioritization', ['Speed', 'Power', 'Wit', 'Stamina', 'Guts'], 'Stat order used when scoring event choices.'),
              prio('tr-summer', 'Summer Training Prioritization', ['Speed', 'Power', 'Wit', 'Stamina', 'Guts'], 'Stat order used during Summer Training.'))}
          ${sec('BEHAVIOR',
              sel('Decision Engine', [['trackblazer', 'Trackblazer Engine'], ['legacy', 'Classic']], 'trackblazer', 'Trackblazer Engine (default) is the modern training/race decision core. Classic is the original legacy engine.', 'mant.decision_mode'),
              sel('Stat Focus', [['balanced', 'Balanced (even spread)'], ['capped', 'Capped (max priority stats)']], 'balanced', 'Balanced spreads training evenly toward targets. Capped concentrates priority stats toward the cap.', 'mant.stat_focus_mode'),
              slider('tr-mfc', 'Set Maximum Failure Chance', 5, 95, 20, 5, '%', 'Trainings above this failure rate are rejected unless Riskier Training allows them.', 'mant.maximum_failure_chance'),
              toggle('Disable Training on Maxed Stats', true, 'Skip stats that have reached their active target/cap buffer.', 'mant.disable_training_on_maxed_stats'),
              toggle('Enable Riskier Training', false, 'Allow high-gain trainings to pass a separate higher failure limit.', 'mant.enable_risky_training'),
              slider('tr-rg', 'Minimum Main Stat Gain Threshold', 20, 100, 20, 5, '', 'Minimum main-stat gain required for Riskier Training.', 'mant.risky_training_min_stat_gain'),
              slider('tr-rf', 'Risky Training Maximum Failure Chance', 5, 95, 30, 5, '%', 'Maximum failure rate accepted for Riskier Training.', 'mant.risky_training_max_failure_chance'),
              toggle('Prioritize Skill Hints', false, 'Boost trainings with skill hints and allow hint turns through the blacklist.', 'mant.enable_prioritize_skill_hints'),
              toggle('Must Rest before Summer', true, 'Use the pre-summer conservation rule before Summer Training.', 'mant.must_rest_before_summer'),
              toggle('Train Wit During Finale', false, 'Use Wit instead of pure recovery in Finale when possible.', 'mant.train_wit_during_finale'))}
          ${sec('SCORING',
              toggle('Weight Score by Training Level', true, 'Boost top-priority stats when native training level fields are present.', 'mant.enable_training_level_weighting'),
              toggle('Rainbow Training Bonus', true, 'Apply the friendship/rainbow multiplier in training scoring.', 'mant.enable_rainbow_training_bonus'),
              toggle('Attenuate Rainbow on Capped Stats', true, 'Scale the rainbow bonus down as the trained stat fills toward its cap. Off = flat 2.0x as before.', 'mant.rainbow_attenuate_by_usefulness'),
              slider('tr-raf', 'Rainbow Attenuation Floor', 0, 1, 0.25, 0.05, '', 'Minimum fraction of the rainbow bonus kept even on a fully-capped stat.', 'mant.rainbow_attenuate_floor'),
              toggle('Near-Max Friendship Boost', true, 'Reward near-rainbow bond stacks without outranking true rainbow turns.', 'mant.enable_near_rainbow_bonus'),
              slider('tr-bvo', 'Low-Bond Training Value', 0, 2, 0.4, 0.1, '', 'How much an un-bonded (orange, <60) support partner is worth to train near.', 'mant.bond_value_orange'),
              slider('tr-bfp', 'Bond-to-Rainbow Push', 0, 2, 1.0, 0.1, '', 'Extra weight for finishing a green (60-79) bond up to rainbow (80).', 'mant.bond_finish_push_cap'),
              slider('tr-bw', 'Bond Priority Weight', 0, 1, 0.15, 0.05, '', 'How heavily bond/friendship counts vs raw stat gain in the training score.', 'mant.bond_weight'))}
          ${sec('DISTANCE',
              sel('Preferred Distance', [['auto', 'Auto'], ['sprint', 'Sprint'], ['mile', 'Mile'], ['medium', 'Medium'], ['long', 'Long']], 'auto', 'Used to resolve stat targets when Auto is not desired.', 'mant.preferred_distance'),
              toggle('Disable Stat Targets', false, 'Treat every stat as live instead of tapering at per-distance targets.', 'mant.disable_stat_targets'),
              statTargetsRow(),
              toggle('Use Global Stat Target', false, 'Override the per-distance table above with one target applied to every distance.', 'mant.enable_global_stat_target'),
              globalStatTargetRow(),
              slider('tr-cm', 'End of Classic Year Milestone', 0, 100, 33, 1, '%', 'Percent of final targets to aim for by the end of Classic Year.', 'mant.classic_year_milestone_pct'),
              slider('tr-sm', 'End of Senior Year Milestone', 0, 100, 66, 1, '%', 'Percent of final targets to aim for by the end of Senior Year.', 'mant.senior_year_milestone_pct'))}
          ${sec('GROUP CARDS (SIRIUS / THRONE)',
              sel('Sirius Throne Strategy', [['', 'Auto (Scheduled on group deck)'], ['scheduled', 'Scheduled'], ['free', 'Free'], ['off', 'Off']], '', 'How to use Team Sirius / Heirs to the Throne outings. Scheduled = fixed calendar, Free = opportunistic, Off = never. Auto picks Scheduled when a group card is in the deck.', 'mant.sirius_throne_strategy'))}
          <div id="st-subsettings">${sec('GROUP CARD OPTIONS (scheduled mode)',
              toggle('Card-Step Outings', true, 'Run the multi-step card story outings (Throne t51/t59, Sirius t58). Scheduled mode only.', 'mant.sirius_throne_card_outing'),
              toggle('Junior Bond Focus', true, 'Favor Group-card facilities in the first 11 turns so outings unlock on schedule. Scheduled mode only.', 'mant.sirius_throne_junior_focus'),
              toggle('Summer All-Out', true, 'On group decks, train all-out in summer camp instead of recreation. Scheduled mode only.', 'mant.summer_all_out'),
              toggle('Recreation Debug Dump', true, 'Write recreation_debug_tN.json (needed to live-verify card-step ids). Scheduled mode only.', 'mant.dump_recreation_debug'))}</div>
        `,
        onMount: (o) => {
          wireSave(o);
          // Show the scheduled-only sub-options only when the strategy is Scheduled
          // (or Auto, which resolves to Scheduled on a group deck). Hidden for Free/Off.
          const _stSel = o.querySelector('[data-k="mant.sirius_throne_strategy"]');
          const _stSub = o.querySelector('#st-subsettings');
          const _stSync = () => { if (_stSub) _stSub.style.display = (!_stSel || ['', 'scheduled'].includes(_stSel.value)) ? '' : 'none'; };
          if (_stSel) _stSel.addEventListener('change', _stSync);
          const _r = initSettingsModal(o);
          Promise.resolve(_r).then(() => { _stSync(); armUnsavedGuard(o); }, () => { _stSync(); armUnsavedGuard(o); });
          _stSync();
        },
      });
    },

    racing() {
      modal({
        title: 'RACING SETTINGS', wide: true, foot: saveBtn('/api/settings-presets'),
        body: `            ${sec('RACE BEHAVIOR',
              toggle('Enable Farming Fans', false, 'Run extra races on matching turns when no train-lock blocks them.', 'mant.enable_farming_fans'),
              slider('rc-days', 'Days to Run Extra Races', 1, 15, 5, 1, '', '', 'mant.days_to_run_extra_races'),
              toggle('Ignore Consecutive Race Warning', false, 'Disable the race-chain safety break.', 'mant.ignore_consecutive_race_warning'),
              toggle('Ignore Low Energy Racing Block', false, 'Do not block voluntary racing at critical HP during a streak.', 'mant.ignore_low_energy_racing_block'),
              toggle('Complete Career on Failure', true, '', 'mant.complete_career_on_failure'),
              toggle('Stop on Mandatory Races', false, '', 'mant.stop_on_mandatory_races'),
              toggle('Force Racing', false, '', 'mant.force_racing'))}
            ${sec('OUTCOME RISK',
              toggle('Enable Outcome-Risk Avoidance', true, 'Penalize races historically lost so the solver avoids them.', 'mant.enable_outcome_risk'),
              slider('rc-orw', 'Outcome-Risk Weight', 0, 5, 1, 0.5, '', '', 'mant.outcome_risk_weight'))}
            ${sec('STRATEGY',
              toggle('Per-Distance Strategy', false, 'Use separate running styles by race distance.', 'mant.enable_per_distance_strategy'),
              sel('Junior Year Strategy', STYLE_OPTS, 'auto', 'Running style used during Junior Year races.', 'mant.junior_running_style'),
              sel('Original Strategy', STYLE_OPTS, 'end', 'Default running style for Year 2+ and fallback races.', 'mant.original_running_style'),
              dsel('Sprint Strategy', 'sprint', 'Running style to use for sprint races when per-distance strategy is enabled.'),
              dsel('Mile Strategy', 'mile', 'Running style to use for mile races when per-distance strategy is enabled.'),
              dsel('Medium Strategy', 'medium', 'Running style to use for medium races when per-distance strategy is enabled.'),
              dsel('Long Strategy', 'long', 'Running style to use for long races when per-distance strategy is enabled.'),
              row('Per-Race Style Overrides', 'Override the running style for specific races, optionally only when Stamina is below a threshold (blank = always). Applies even in Manual mode and reverts to your main style on the next race. Requires a concrete Original Strategy (not Auto).',
                `<div class="rovr-list">${RACE_OVR.map((r) => `<div class="rovr" data-race="${esc(r[0])}"><div class="rovr-race"><strong>${esc(r[0])}</strong><span>${r[1]} \u00b7 ${r[2]}</span></div><div class="rovr-ctrl"><div class="rovr-stam"><label>Stamina &lt;</label><input class="numf rovr-stam-input" type="number" placeholder="any"></div><select class="self rovr-style"><option value="">No override</option>${STYLE_OPTS.slice(1).map(([v, l]) => `<option value="${esc(v)}">${esc(l)}</option>`).join('')}</select></div></div>`).join('')}</div>`, true))}
`,
        onMount: (o) => { wireSave(o); Promise.resolve(initSettingsModal(o)).then(() => armUnsavedGuard(o)); },
      });
    },

    scenario() {
      // BUG #9: full Trackblazer shop item set (data/mant_shop_core.json). The
      // engine slug-matches (display_to_slug) so these display names are correct.
      const SHOP = ['Speed Notepad', 'Stamina Notepad', 'Power Notepad', 'Guts Notepad', 'Wit Notepad', 'Speed Manual', 'Stamina Manual', 'Power Manual', 'Guts Manual', 'Wit Manual', 'Speed Scroll', 'Stamina Scroll', 'Power Scroll', 'Guts Scroll', 'Wit Scroll', 'Vita 20', 'Vita 40', 'Vita 65', 'Royal Kale Juice', 'Energy Drink MAX', 'Energy Drink MAX EX', 'Plain Cupcake', 'Berry Sweet Cupcake', 'Yummy Cat Food', 'Grilled Carrots', 'Pretty Mirror', "Reporter's Binoculars", 'Master Practice Guide', "Scholar's Hat", 'Fluffy Pillow', 'Pocket Planner', 'Rich Hand Cream', 'Smart Scale', 'Aroma Diffuser', 'Practice Drills DVD', 'Miracle Cure', 'Speed Training Application', 'Stamina Training Application', 'Power Training Application', 'Guts Training Application', 'Wit Training Application', 'Reset Whistle', 'Coaching Megaphone', 'Motivating Megaphone', 'Empowering Megaphone', 'Speed Ankle Weights', 'Stamina Ankle Weights', 'Power Ankle Weights', 'Guts Ankle Weights', 'Good-Luck Charm', 'Artisan Cleat Hammer', 'Master Cleat Hammer', 'Glow Sticks'];
      modal({
        title: 'SCENARIO OVERRIDES', wide: true, foot: `<button class="abtn danger" type="button" data-close>RESET TRACKBLAZER</button>${saveBtn('/api/settings-presets')}`,
        body: `            ${sec('RACING',
              slider('sc-crl', 'Consecutive Races Limit', 3, 30, 3, 1, '', '', 'mant.race_chain_target'),
              chips('Preferred Track Distances', [['sprint', false, 'Sprint'], ['mile', false, 'Mile'], ['medium', false, 'Medium'], ['long', false, 'Long']], 'Bias the solver toward these distances (blank = no preference, uses aptitude).', 'preset.preferred_distances'),
              chips('Preferred Track Surfaces', [['turf', false, 'Turf'], ['dirt', false, 'Dirt']], 'Bias the solver toward these surfaces (blank = no preference).', 'preset.preferred_surfaces'))}
            ${sec('ENERGY & RESOURCES',
              slider('sc-ert', 'Energy Threshold to use Energy Items', 0, 100, 40, 1, '', '', 'mant.energy_recovery_threshold'),
              slider('sc-ftf', 'Force-Train Energy Floor', 0, 50, 20, 1, '', '', 'mant.force_train_energy_floor'),
              slider('sc-sbm', 'Skip Items During Bad Mood Below Gain', 0, 50, 15, 1, '', '', 'mant.trackblazer_skip_bad_mood_items_below_gain'),
              toggle('Skip Energy Items on Year-End Races', false, '', 'mant.skip_energy_items_year_end'))}
            ${sec('TRAINING',
              slider('sc-charm', 'Skip Risky Charm Training Below Gain', 20, 100, 20, 1, '', '', 'mant.charm_min_main_gain'),
              toggle('Enable Irregular Training', true, 'Allow high-value training to hijack planned voluntary races.', 'mant.enable_irregular_training'),
              slider('sc-itm', 'Min Main Gain for Irregular Training', 20, 100, 30, 1, '', '', 'mant.irregular_training_min_main_gain'),
              toggle('Reset Whistle Forces Training', true, '', 'mant.whistle_forces_training'))}
            ${sec('SHOP & ITEMS',
              slider('sc-scf', 'Shop Check Frequency', 1, 4, 1, 1, '', '1 = every opportunity, 2 = every other, …', 'mant.trackblazer_shop_check_frequency'),
              chips('Race Grades to Check Shop After', [['G1', true], ['G2', true], ['G3', true]], 'Only check the shop after a race of one of these grades.', 'mant.trackblazer_shop_check_grades'),
              chips('Items to Exclude from Shop', SHOP.map((n) => [n, false]), '', 'mant.exclude_shop_items'))}
            ${sec('SHOP PURCHASE LOGIC',
              slider('sc-coin', 'Coin Reserve Override', 0, 300, 0, 5, '', '0 = automatic finale-aware reserve curve.', 'mant.mant_coin_reserve'),
              slider('sc-bbq', 'BBQ Buy Threshold (unmaxxed cards)', 0, 6, 3, 1, '', '', 'mant.bbq_unmaxxed_cards'),
              toggle('Fast Learner Shop Boost', false, '', 'mant.enable_fast_learner_shop_boost'),
              toggle('Preemptive Cure Reserve', false, '', 'mant.preemptive_cure_reserve'))}
            ${sec('ITEM CONSERVATION',
              slider('sc-eir', 'Energy Item Emergency Reserve', 0, 3, 1, 1, '', '', 'mant.trackblazer_energy_item_reserve'),
              slider('sc-cup', 'Cupcake Reserve (Kale synergy)', 0, 3, 1, 1, '', '', 'mant.trackblazer_cupcake_reserve'),
              slider('sc-mh', 'Master Cleat Hammer Finale Reserve', 0, 3, 3, 1, '', '', 'mant.trackblazer_master_hammer_finale_reserve'),
              slider('sc-ah3', 'Artisan Hammer Min Stock for G3', 0, 3, 0, 1, '', '', 'mant.trackblazer_artisan_hammer_min_stock_for_g3'),
              slider('sc-ah2', 'Artisan Hammer Min Stock for G2', 0, 3, 0, 1, '', '', 'mant.trackblazer_artisan_hammer_min_stock_for_g2'),
              slider('sc-gs', 'Glow Stick Final-Day Reserve', 0, 3, 1, 1, '', '', 'mant.trackblazer_glow_stick_final_reserve'),
              slider('sc-gsf', 'Glow Stick Minimum Fans', 0, 30000, 20000, 1000, '', '', 'mant.trackblazer_glow_stick_min_fans'))}
`,
        onMount: (o) => { wireSave(o); Promise.resolve(initSettingsModal(o)).then(() => armUnsavedGuard(o)); },
      });
    },

    solver() {
      SV = { charId: 100021, manual: {}, thresh: 'C', ep: { target: new Set(), forced: new Set() } };
      const distModes = note(`<b style="color:var(--amber)">Distance Preference Modes</b><ul style="margin:7px 0 0;padding-left:16px"><li><b>Strict:</b> Only uses preferred distances unless a mandatory race or forced epithet requires otherwise.</li><li><b>Balanced:</b> Strongly prefers selected distances, but allows valuable safe exceptions.</li><li><b>Loose:</b> Treats distance preference as a light scoring bonus only.</li></ul>`);
      modal({
        title: 'SMART RACE SOLVER SETTINGS', wide: true,
        foot: `<button class="abtn cyan" type="button">SOLVE PREVIEW</button><button class="abtn danger" type="button" id="solver-reset-apt">RESET APTITUDES</button>${saveBtn('/api/smart-solver/config')}`,
        body: `
            ${sec('SMART RACE SOLVER',
              `<div class="srow"><div class="srow-text"><strong>Active Mode</strong><span>Use the compact Smart Race Solver / Manual Selection buttons on the Trackblazer card to switch modes.</span></div><div class="srow-ctrl"><span style="color:var(--cyan);font:700 var(--fs-base) var(--mono)">Smart Race Solver</span></div></div>`,
              `<div class="srow"><div class="srow-text"><strong>Character Preset</strong><span>Uses the trainee selected in Setup. Changing this list updates the active trainee selection.</span></div><div class="srow-ctrl" style="flex-direction:column;align-items:flex-end;gap:8px"><span id="solver-char-name" style="color:var(--amber);font:700 var(--fs-lg) var(--mono)">Air Shakur</span><button class="abtn amberline" type="button" id="solver-refresh">REFRESH PROFILE</button></div></div>`,
              `<div class="search charsearch"><span class="ic">⌕</span><input type="text" placeholder="Search characters…" id="solver-char-search"></div><div class="charlist" id="solver-char-list">${SOLVER_CHARS.map((c) => charRow(c.name, c.id, c.id === SV.charId)).join('')}</div>`)}
            ${sec('APTITUDES',
              `<p class="field-help" style="margin:0 0 6px">Manual Start replaces the trainee preset for solver planning. Estimated Parent Sparks are added on top, and Solver Final is sent to the route solver.</p>`,
              `<div id="solver-apt-rows">${aptRowsHtml()}</div>`)}
            ${sec('APTITUDE THRESHOLD',
              `<p class="field-help" style="margin:0 0 12px">Minimum aptitude (distance AND surface) required for a race to be eligible.</p>${threshHtml('C')}`)}
            ${sec('ELIGIBILITY & DISTANCE',
              ssToggle('Include OP / Pre-OP races', false, 'Also consider lower-grade races. Useful for weak characters or special routing.', 'include_op'),
              ssToggle('Allow racing during Summer (Classic / Senior)', false, 'Allows solver races in the 4 summer-camp turns each year when a valuable target lands there.', 'allow_summer_racing'),
              ssSelect('Distance Preference Mode', [['strict', 'Strict'], ['balanced', 'Balanced'], ['loose', 'Loose']], 'balanced', 'Controls how strongly Smart Race Solver follows selected/trainee distances.', 'distance_preference_mode'),
              distModes)}
            ${sec('RE-PLANNING',
              ssToggle('Live Schedule Re-Planning', true, 'Master switch (smart mode only): when ON (default), the solver re-solves the remaining schedule live as the run unfolds (gated by the two options below). When OFF, the schedule solved at career start is locked in for the whole run — no live re-planning at all. Manual race mode ignores this.', 'enable_live_smart_replan'),
              note('This is the parent of the two settings below. With it OFF, “Re-Plan Only on Race Events” and “Disable Re-Plan Upon Race Loss” have no effect because no live re-planning happens.'),
              ssToggle('Re-Plan Only on Race Events', true, 'Solve the schedule once and reuse it, re-planning only when a race is lost or a planned race becomes unavailable — instead of re-solving every turn. Prevents the per-turn churn that piled up race streaks and dropped winnable races. Defaults to ON.', 'replan_on_events_only'),
              note('When ON (recommended), the plan is computed once and stays stable through the run — winning a race keeps the plan, and only a loss or an unavailable planned race triggers a re-solve. Turn OFF to restore the old behavior of re-solving the remaining schedule every turn.'),
              ssToggle('Disable Schedule Re-Plan Upon Race Loss', false, 'When a race is lost, keep the original schedule instead of re-planning the remaining turns. The loss is still recorded; epithets that depended on the lost race won\u2019t be re-routed. Defaults to off.', 'disable_schedule_replan_on_race_loss'),
              note('By default, losing a race re-plans the remaining turns (the lost race may be re-routed to a later turn and epithet branches re-evaluated). Turn this on to lock in the original schedule after a loss instead.'))}
            ${sec('SET-BONUS CHASING',
              row('Chase Achievable Set-Bonuses (Epithets)', 'When ON, the solver adds a soft reward for completing every achievable race set/title (Triple Crowns, distance/regional/surface sets, etc.), re-prioritizing the route toward the +random-stat set bonuses. Soft, so it can never make the schedule infeasible. Costs some fans in exchange for stats. Defaults to OFF.', '<div class="tgl" data-swb="enableOpportunisticEpithets"><span class="tgl-sw"></span></div>'),
              note('The Target Epithets below bias the route only when this is ON. Forced Epithets are hard constraints and apply regardless of this toggle.'))}
            ${sec('OPTIMIZATION WEIGHT PRESET',
              `<div class="owpreset"><button class="owbtn" type="button" data-owp="stat">Stat Epithets</button><button class="owbtn on" type="button" data-owp="fans">Fans + Epithets</button></div>`,
              `<p class="field-help" style="margin:12px 0 0">This is a UI macro that adjusts the solver scoring weights below; the backend consumes those weights, not this label directly.</p>`)}
            ${sec('SCORING WEIGHTS', `<div class="swgrid">${SCOREW.map(swField).join('')}</div>`)}
            ${epSection('TARGET EPITHETS', 'target', 'Target epithets bias the route toward races named in their conditions.')}
            ${epSection('FORCED EPITHETS', 'forced', 'Forced epithets are hard constraints: every selected forced epithet must have at least one matching scheduled race under the native matcher.')}
`,
        onMount: (o) => { wireSave(o); mountSolver(o); Promise.resolve(initSolverWeights(o)).then(() => armUnsavedGuard(o)); },
      });
    },

    skills() {
      modal({ title: 'SKILLS', full: true, closeLabel: 'DONE', foot: saveBtn('/api/skill-config', 'SAVE'), body: skillsBody(), onMount: (o) => { wireSave(o); initSkillCfg(o).then(() => mountSkills(o)).then(() => armUnsavedGuard(o)); } });
    },

    customDeck() {
      modal({
        title: 'BUILD CUSTOM DECK', wide: true, closeLabel: 'CLOSE',
        foot: `<button class="abtn" type="button" id="cd-clear">CLEAR</button>${saveBtn('/api/selection', 'APPLY DECK')}`,
        body: `
          <div class="fsec"><div class="fsec-title">SELECTED CARDS · 5 OF YOUR OWN + 1 FRIEND</div>
            <div class="deckslots" id="cd-slots"></div>
          </div>
          <div class="fsec">
            <div style="display:flex;gap:10px;margin-bottom:12px">
              <div class="search" style="flex:1;border:1px solid var(--line-card);border-radius:4px;padding:8px 11px"><span class="ic">⌕</span><input type="text" id="cd-search" placeholder="search owned support cards"></div>
              <select class="self" id="cd-type" style="width:160px"><option>All types</option><option>Speed</option><option>Stamina</option><option>Power</option><option>Guts</option><option>Wit</option><option>Friend</option></select>
            </div>
            <div id="cd-status" style="font:500 var(--fs-xs) var(--mono);color:var(--label);margin-bottom:8px"></div>
            <div class="cardgrid" id="cd-grid"></div>
          </div>`,
        onMount: (o) => { wireSave(o); Promise.resolve(mountCustomDeck(o)).then(() => armUnsavedGuard(o)); },
      });
    },

    recSupports() {
      modal({
        title: 'RECOMMENDED SUPPORT CARDS', closeLabel: 'CLOSE',
        body: `<p class="field-help" style="margin:0 0 14px">Recommended supports for <span id="rs-sub" style="color:var(--amber)">the selected trainee</span> \u2014 the scraped Game8 Trackblazer build when available, otherwise the best picks from the cards you own.</p>
          <div id="rs-grid"></div>`,
        onMount: (o) => { mountRecSupports(o); },
      });
    },

    userdata() {
      modal({
        title: 'USERDATA FOLDER',
        foot: `<button class="abtn" type="button" data-close>I'LL HANDLE IT LATER</button>${saveBtn('/api/userdata/set-path', 'APPLY PATH')}`,
        body: `
          <p class="field-help" style="margin:0 0 16px">Your settings, presets, accounts, and Steam auth live in a userdata folder. Pointing this somewhere stable means your data survives version upgrades.</p>
          <div class="fsec"><div class="fsec-title">CURRENT</div>
            <div style="display:flex;justify-content:space-between;font:500 var(--fs-md) var(--mono);margin-bottom:8px"><span class="c-mut">Folder</span><span id="ud-current" style="color:var(--ink-2)">…</span></div>
            <div style="display:flex;justify-content:space-between;font:500 var(--fs-md) var(--mono);margin-bottom:8px"><span class="c-mut">Resolved via</span><span id="ud-source" style="color:var(--ink-2)">…</span></div>
            <div style="display:flex;justify-content:space-between;font:500 var(--fs-md) var(--mono)"><span class="c-mut">Pointer</span><span id="ud-pointer" class="c-cyan">…</span></div>
          </div>
          <div id="ud-warn" style="display:none"></div>
          <div class="fsec"><div class="fsec-title">SET A STABLE FOLDER</div>
            <input id="ud-path" class="numf" type="text" placeholder="C:\\Umamusume API Bot\\Icarus_userdata" style="font-size:var(--fs-md);margin-bottom:10px">
            <div class="srow"><div class="srow-text"><strong>Also copy current settings/presets/auth</strong><span>Non-destructive copy into the new folder.</span></div><div class="srow-ctrl"><div class="tgl on" id="ud-migrate"><span class="tgl-sw"></span></div></div></div>
          </div>`,
        onMount: (o) => { wireSave(o); Promise.resolve(mountUserdata(o)).then(() => armUnsavedGuard(o)); },
      });
    },

    discord() {
      modal({
        title: 'DISCORD WEBHOOK',
        foot: `<button class="abtn cyan" type="button" id="discord-test">TEST</button>${saveBtn('/api/settings/discord-webhook')}`,
        body: `
          <p class="field-help" style="margin:0 0 14px">Get a ping in Discord when a career finishes, crashes, or hits a milestone.</p>
          <div class="field"><div class="field-label"><span>WEBHOOK URL</span></div>
          <input id="discord-url" class="numf" type="password" placeholder="https://discord.com/api/webhooks/…" style="font-size:var(--fs-md)"></div>
          ${toggle('Notify on career finish', true, '', 'notify_on_finish')}
          ${toggle('Notify on crash / stuck', true, '', 'notify_on_crash')}
          ${toggle('Notify on new epithet', false, '', 'notify_on_epithet')}`,
        onMount: (o) => {
          // Restore the saved webhook + the 3 notify toggle states from the backend.
          const setTgl = (key, on) => { const t = o.querySelector(`.tgl[data-k="${key}"]`); if (t) t.classList.toggle('on', !!on); };
          const initDiscord = api('/api/settings/discord-webhook').then((d) => {
            if (!d) return;
            const inp = o.querySelector('#discord-url');
            if (inp && d.webhook_url && !String(d.webhook_url).includes('••')) inp.value = d.webhook_url;
            setTgl('notify_on_finish', d.notify_on_finish);
            setTgl('notify_on_crash', d.notify_on_crash);
            setTgl('notify_on_epithet', d.notify_on_epithet);
          }).catch(() => {});
          wireSave(o); Promise.resolve(initDiscord).then(() => armUnsavedGuard(o));
          // TEST sends a probe via the SAVED webhook (POST /api/settings/discord-webhook/test);
          // save the URL first.
          const tb = o.querySelector('#discord-test');
          if (tb) tb.addEventListener('click', async () => {
            tb.textContent = 'TESTING…';
            try { const r = await api('/api/settings/discord-webhook/test', { method: 'POST' }); tb.textContent = (r && r.success) ? 'SENT ✓' : 'FAILED'; }
            catch (e) { tb.textContent = 'FAILED'; }
            setTimeout(() => { tb.textContent = 'TEST'; }, 1500);
          });
        },
      });
    },
  };

  document.addEventListener('click', (e) => {
    const ed = e.target.closest('[data-prio-edit]');
    if (ed) { e.preventDefault(); openPriorityEditor(ed.dataset.prioEdit); }
  });

  I.Modals = Modals;
})();
