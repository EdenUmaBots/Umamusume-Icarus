/* Setup — team slots, settings presets, Smart Race Solver, library, race schedule.
   LIVE: pulls the master payload from /api/session (umas, parents, decks,
   supports, friends, selection) and persists picks to /api/selection.
   Presets come from /api/settings-presets. Falls back to a mock dataset
   (preview only) when the backend is unreachable. */
(() => {
  'use strict';
  const I = window.Icarus;
  const { api, esc } = I;
  const $ = (id) => document.getElementById(id);
  // Flat placeholder fills (no diagonal hatching). These sit behind the 128px
  // icons; with object-fit:contain the leftover area shows this solid colour
  // instead of grey lines.
  const STRIPE = '#0f1217';
  const SEL_STRIPE = '#15160d';
  // Game single_mode_rank ids → grade labels (must match public/app.js:1809 +
  // main.py CAREER_RANK_LABEL_BY_ID). The old map was shifted one tier high, so
  // SS (17) showed as S+, etc.
  const RANK = { 1: 'G', 2: 'G+', 3: 'F', 4: 'F+', 5: 'E', 6: 'E+', 7: 'D', 8: 'D+', 9: 'C', 10: 'C+', 11: 'B', 12: 'B+', 13: 'A', 14: 'A+', 15: 'S', 16: 'S+', 17: 'SS', 18: 'SS+', 19: 'UG', 20: 'UF', 21: 'UE', 22: 'UD' };

  const MONTHS =['EARLY JAN', 'LATE JAN', 'EARLY FEB', 'LATE FEB', 'EARLY MAR', 'LATE MAR', 'EARLY APR', 'LATE APR', 'EARLY MAY', 'LATE MAY', 'EARLY JUN', 'LATE JUN', 'EARLY JUL', 'LATE JUL', 'EARLY AUG', 'LATE AUG', 'EARLY SEP', 'LATE SEP', 'EARLY OCT', 'LATE OCT', 'EARLY NOV', 'LATE NOV', 'EARLY DEC', 'LATE DEC'];
  const gradeColor = { G1: 'red', G2: 'cyan', G3: 'green', OP: 'amber' };
  const RACE_YEARS = ['JUNIOR YEAR', 'CLASSIC YEAR', 'SENIOR YEAR'];
  const MONTH_NUM = { JAN: 1, FEB: 2, MAR: 3, APR: 4, MAY: 5, JUN: 6, JUL: 7, AUG: 8, SEP: 9, OCT: 10, NOV: 11, DEC: 12 };

  // ---- live state ----
  let data = null;                 // /api/session payload
  let online = false;
  let presets = ['Air Shakur'];
  let activePreset = '';            // the backend's active preset (keeps the dropdown in sync)
  let libTab = 'trainees';
  let serverUp = false;
  let friendsState = 'idle';  // idle | loading | loaded | error
  let guestsState = 'idle';
  let friendsExclude = [];
  let guestsExclude = [];
  const sel = { deck: null, friend: null, trainee: null, veterans: [], guestParents: [] };
  let lastPlan = null;
  // ---- race schedule / manual picker state (per active preset) ----
  let raceMode = 'smart';              // 'smart' | 'manual' (mirrors extra_race_list_source)
  const selectedRaceIds = new Set();   // program_ids picked (by the solver or by hand)
  let raceByCell = {};                 // { 'JUNIOR YEAR': { monthIndex: [race,…] }, … }
  let showOP = (() => { try { return localStorage.getItem('icarus_show_op') === '1'; } catch (e) { return false; } })();  // OP races hidden by default

  // ---- lazy on-demand loaders (separate endpoints, blocked during active careers) ----
  async function loadFriends(force) {
    if (!online || friendsState === 'loading') return;
    friendsState = 'loading';
    if (libTab === 'friends') renderLibBody();
    try {
      const r = await api('/api/career/friends', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ exclude_viewer_ids: force ? friendsExclude : [] }),
      });
      if (r && r.success) {
        data.friends = r.friends || [];
        friendsExclude = r.exclude_viewer_ids || [];
        friendsState = 'loaded';
      } else { friendsState = 'error'; data._friendErr = (r && r.detail) || 'Friend load failed'; }
    } catch (e) { friendsState = 'error'; data._friendErr = 'Friend load failed'; }
    renderLibrary();
  }
  async function loadGuests(force) {
    if (!online || guestsState === 'loading') return;
    guestsState = 'loading';
    if (libTab === 'guests') renderLibBody();
    try {
      const r = await api('/api/career/guest_parents', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ exclude_viewer_ids: force ? guestsExclude : [], force_refresh: !!force }),
      });
      if (r && r.success) {
        data.guestParents = r.guestParents || [];
        guestsExclude = r.exclude_viewer_ids || [];
        guestsState = 'loaded';
      } else { guestsState = 'error'; data._guestErr = (r && r.detail) || 'Guest parent load failed'; }
    } catch (e) { guestsState = 'error'; data._guestErr = 'Guest parent load failed'; }
    renderLibrary();
  }
  function loadPanel(label) {
    return `<div style="text-align:center;padding:30px 18px">
      <div style="font:500 var(--fs-md)/1.7 var(--mono);color:var(--mut);margin-bottom:14px;max-width:440px;margin-left:auto;margin-right:auto">${label}</div>
      <button class="abtn cyan" type="button" data-load="${libTab}" style="min-width:200px">LOAD ${libTab === 'friends' ? 'FRIEND SUPPORTS' : 'GUEST PARENTS'}</button>
    </div>`;
  }
  function refreshPanel(label) {
    return `<div style="text-align:center;padding:26px 18px">
      <div style="font:500 var(--fs-md)/1.7 var(--mono);color:var(--label);margin-bottom:14px">${label}</div>
      <button class="abtn" type="button" data-load="${libTab}" data-force="1" style="min-width:160px">REFRESH</button>
    </div>`;
  }

  // ---- helpers ----
  const lists = () => ({
    trainees: (data && data.umas) || [],
    parents: (data && data.parents) || [],
    guests: (data && data.guestParents) || [],
    decks: (data && data.decks) || [],
    friends: (data && data.friends) || [],
    cards: (data && data.supports) || [],
  });
  function imgTag(id, h, art) {
    const safe = esc(String(id || ''));
    // contain (not cover): the source icons are square 128px, so cover cropped
    // heads/edges off in the wider grid cells. contain shows the whole icon.
    // art=true → the 512px standing illustration (/api/card-art), used for trainees.
    // ?v=2 busts the browser cache after the card_art set was re-extracted per card_id
    // (the URL is otherwise unchanged + cached a week, so old uniforms would stick).
    const src = art ? `/api/card-art/${safe}.png?v=2` : `/api/images/${safe}.png`;
    return `<img src="${src}" alt="" style="width:100%;height:${h}px;object-fit:contain;display:block"
      onerror="this.style.visibility='hidden';this.parentElement.style.background='${STRIPE}'">`;
  }
  function gridCard(opts) {
    const { imgId, name, kicker, badge, rarity, star, selected, attrs = '', h = 84, lb, art, isSupport, favIid, favKind, isFav } = opts;
    const R = String(rarity || '').toUpperCase();
    const ribBg = R === 'SSR' ? 'linear-gradient(120deg,#7ad7f0,#b98cff,#ff9ec7)' : R === 'SR' ? 'linear-gradient(135deg,#f6d36a,#caa13a)' : 'linear-gradient(135deg,#cdd4df,#9aa3b2)';
    const ribbon = R ? `<span style="position:absolute;top:5px;left:5px;font:800 var(--fs-xs) var(--cond);letter-spacing:.05em;color:#1a1206;background:${ribBg};padding:2px 6px;border-radius:3px;box-shadow:0 1px 2px rgba(0,0,0,.45)">${esc(R)}</span>` : '';
    const check = '<span style="position:absolute;top:5px;left:5px;width:16px;height:16px;border-radius:4px;background:var(--amber);color:var(--panel);display:flex;align-items:center;justify-content:center;font-size:var(--fs-sm);font-weight:700;box-shadow:0 1px 3px rgba(0,0,0,.5)">✓</span>';
    const topRight = badge
      ? `<span style="position:absolute;top:5px;right:5px;font:700 var(--fs-xs) var(--mono);color:var(--panel);background:var(--cyan);padding:2px 5px;border-radius:3px">${esc(badge)}</span>`
      : (star ? '<span style="position:absolute;top:4px;right:5px;color:#f6c945;font-size:var(--fs-lg);text-shadow:0 1px 2px rgba(0,0,0,.5)">★</span>' : '');
    // LB level — a prominent colored badge in the lower-right, styled like the
    // rarity ribbon (top-left). Shown whenever an lb value is supplied.
    const lbStr = (lb != null && lb !== '' && String(lb) !== '?') ? String(lb) : '';
    // Support cards max out at LB4 (5 copies) — show MLB instead of "LB4".
    const lbText = (isSupport && Number(lbStr) >= 4) ? 'MLB' : 'LB' + esc(lbStr);
    const lbBadge = lbStr ? `<span style="position:absolute;bottom:5px;right:5px;font:800 var(--fs-sm) var(--cond);letter-spacing:.03em;color:#06121a;background:linear-gradient(135deg,#7ad7f0,#36a9d6);padding:2px 6px;border-radius:3px;box-shadow:0 1px 3px rgba(0,0,0,.5)">${lbText}</span>` : '';
    // Favorite star (bottom-left, clickable) for parents/guests; coexists with the
    // rank badge (top-right) and LB badge (bottom-right). data-fav-* is handled by
    // the global click handler (stops it from also selecting the card).
    const favBadge = (favIid != null && favIid !== '')
      ? `<span class="fav-star" role="button" tabindex="0" title="Toggle favorite" data-fav-iid="${esc(String(favIid))}" data-fav-kind="${esc(String(favKind || 'parents'))}" style="position:absolute;bottom:4px;left:4px;font-size:var(--fs-2xl);line-height:1;cursor:pointer;text-shadow:0 1px 3px rgba(0,0,0,.7);color:${isFav ? '#f6c945' : 'rgba(255,255,255,.5)'}">${isFav ? '★' : '☆'}</span>`
      : '';
    return `<div ${attrs} style="border:1px solid ${selected ? 'var(--amber)' : 'var(--line-card)'};border-radius:5px;overflow:hidden;background:var(--card);position:relative;cursor:pointer${selected ? ';box-shadow:0 0 0 1px var(--amber)' : ''}">
      <div style="height:${h}px;background:${selected ? SEL_STRIPE : STRIPE};position:relative">${imgId !== undefined ? imgTag(imgId, h, art) : ''}
        ${selected ? check : ribbon}
        ${topRight}
        ${lbBadge}
        ${favBadge}
      </div>
      <div style="padding:8px">
        <div style="font:${selected ? 700 : 600} 12px var(--cond);letter-spacing:.03em;color:${selected ? 'var(--amber)' : 'var(--ink)'};line-height:1.2;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(name)}</div>
        ${kicker ? `<div style="font:600 var(--fs-xs) var(--cond);letter-spacing:.08em;color:var(--label);margin-top:3px">${esc(kicker)}</div>` : ''}
      </div>
    </div>`;
  }

  // ---- selection ----
  async function saveSelection() {
    if (!online) return;
    try {
      await api('/api/selection', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ selection: { deck: sel.deck, friend: sel.friend, trainee: sel.trainee, veterans: sel.veterans, guestParents: sel.guestParents } }),
      });
    } catch (e) { /* best effort */ }
  }
  function applyServerSelection(s) {
    if (!s) return;
    const L = lists();
    if (s.trainee) sel.trainee = L.trainees.find((u) => String(u.id) === String(s.trainee.id)) || s.trainee;
    if (s.deck) sel.deck = L.decks.find((d) => Number(d.id) === Number(s.deck.id)) || s.deck;
    if (Array.isArray(s.veterans)) s.veterans.forEach((v) => {
      const p = L.parents.find((pp) => Number(pp.instance_id) === Number(v.instance_id));
      if (p && sel.veterans.length < 2) sel.veterans.push(p);
    });
    if (s.friend) sel.friend = s.friend;
    if (Array.isArray(s.guestParents)) sel.guestParents = s.guestParents;
  }
  // When a career is in progress (e.g. started manually in-game), ITS parents are
  // the truth. Reflect them in the PARENT slots and persist the selection so the
  // resumed career shows + uses the real parents, overriding the saved picks.
  function applyActiveCareerParents() {
    const car = data && data.account && data.account.career;
    if (!car || !car.active) return;
    const ids = [Number(car.parent_id_1 || 0), Number(car.parent_id_2 || 0)].filter((n) => n > 0);
    if (!ids.length) return;
    const L = lists();
    sel.veterans = ids.slice(0, 2).map((id) =>
      L.parents.find((p) => Number(p.instance_id) === id) ||
      { instance_id: id, name: 'Career parent ' + id, rank: '', card_id: 0 });
    saveSelection();
  }
  function selectTrainee(u) { sel.trainee = u; renderSlots(); renderLibBody(); saveSelection(); }
  function toggleVeteran(p) {
    const i = sel.veterans.findIndex((v) => Number(v.instance_id) === Number(p.instance_id));
    if (i >= 0) sel.veterans.splice(i, 1);
    else if (sel.veterans.length < 2) sel.veterans.push(p);
    renderSlots(); renderLibBody(); saveSelection();
  }
  function toggleGuest(p) {
    // The career start uses ONE own parent + one guest (parent_selection_mode
    // 'own_guest'), so the guest is a single selection that occupies PARENT 2.
    const cur = (sel.guestParents || [])[0];
    if (cur && Number(cur.instance_id) === Number(p.instance_id)) sel.guestParents = [];
    else sel.guestParents = [p];
    renderSlots(); renderLibBody(); saveSelection();
  }
  function selectDeck(d) { sel.deck = d; renderSlots(); renderLibBody(); saveSelection(); renderDeckBonusesPanel(); }
  // A friend support is uniquely identified by its LENDER (viewer_id), not its
  // support_card_id — many different players lend the SAME card (e.g. several
  // "Fine Motion"). Keying selection by support_card_id highlighted/selected ALL
  // copies at once and could send a borrowed friend that duplicates an owned deck
  // card → result_code 2511. Key by viewer_id|card so only the clicked one picks.
  const friendKey = (f) => f ? String(f.viewer_id || f.trainer_id || '') + '|' + String(f.support_card_id || f.card_id || f.id || '') : '';
  function selectFriend(f) {
    const key = friendKey(f);
    const cur = sel.friend ? friendKey(sel.friend) : null;
    sel.friend = cur === key ? null : { viewer_id: String(f.viewer_id || f.trainer_id || ''), support_card_id: String(f.support_card_id || f.card_id || f.id || ''), name: f.name };
    renderSlots(); renderLibBody(); saveSelection();
  }

  // ---- renders ----
  function slotCard(role, accent, inner, attrs) {
    return `<div ${attrs || ''} style="background:var(--card);border:1px solid var(--line-card);${accent ? 'border-left:2px solid var(--amber);' : ''}border-radius:5px;padding:11px${attrs ? ';cursor:pointer' : ''}">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:9px">
        <span style="font:600 var(--fs-xs) var(--cond);letter-spacing:.16em;color:${accent ? 'var(--amber)' : 'var(--label)'}">${role}</span>
        <span style="font:500 var(--fs-2xs) var(--cond);letter-spacing:.1em;color:var(--dim)">CLEAR</span>
      </div>${inner}</div>`;
  }
  function filledSlot(name, meta, imgId) {
    const thumb = imgId != null && imgId !== ''
      ? `<img src="/api/images/${esc(String(imgId))}.png" alt="" style="width:34px;height:34px;border-radius:5px;object-fit:cover;border:1px solid var(--line-card);flex-shrink:0;background:${STRIPE}" onerror="this.style.visibility='hidden'">`
      : `<div style="width:34px;height:34px;border-radius:5px;background:${STRIPE};border:1px solid var(--line-card);flex-shrink:0"></div>`;
    return `<div style="display:flex;align-items:center;gap:9px">${thumb}<div style="min-width:0"><div style="font:700 var(--fs-base) var(--cond);letter-spacing:.04em;color:var(--ink);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(name)}</div><div style="font:500 var(--fs-xs) var(--mono);color:var(--label)">${meta || ''}</div></div></div>`;
  }
  function emptySlot(text) {
    return `<div style="display:flex;align-items:center;gap:9px;color:var(--dim)"><div style="width:34px;height:34px;border-radius:5px;background:${STRIPE};border:1px dashed var(--line-card);flex-shrink:0"></div><div style="font:500 var(--fs-sm) var(--mono);color:var(--dim)">${text || 'select'}</div></div>`;
  }
  function renderSlots() {
    const t = sel.trainee, v0 = sel.veterans[0], v1 = sel.veterans[1], d = sel.deck, f = sel.friend;
    // A selected guest parent takes the PARENT 2 slot (own_guest uses own[0] + guest).
    const guest = (sel.guestParents || [])[0] || null;
    const p2Inner = guest
      ? filledSlot(guest.name, 'GUEST' + (RANK[guest.rank] ? ' · ' + RANK[guest.rank] : ''), guest.card_id)
      : (v1 ? filledSlot(v1.name, RANK[v1.rank] || '', v1.card_id) : emptySlot());
    const deckInner = d
      ? `<div style="display:flex;gap:4px">${(d.cards || []).slice(0, 6).map((c) => `<div style="flex:1;height:34px;border-radius:4px;overflow:hidden;background:${SEL_STRIPE};border:1px solid var(--amber)"><img src="/api/images/${esc(String(c.id || c.support_card_id || ''))}.png" alt="" style="width:100%;height:100%;object-fit:cover;display:block" onerror="this.style.visibility='hidden'"></div>`).join('') || emptySlot('build')}</div>`
      : `<div style="display:flex;gap:4px">${Array.from({ length: 6 }, (_, i) => `<div style="flex:1;height:34px;border-radius:4px;background:${STRIPE};border:1px dashed var(--line-card)"></div>`).join('')}</div>`;
    $('setup-slots').innerHTML = [
      slotCard('TRAINEE', true, t ? filledSlot(t.name, t.scenario || 'Trackblazer', t.id) : emptySlot('pick a trainee')),
      slotCard('PARENT 1', false, v0 ? filledSlot(v0.name, RANK[v0.rank] || '', v0.card_id) : emptySlot()),
      slotCard(guest ? 'PARENT 2 · GUEST' : 'PARENT 2', false, p2Inner),
      slotCard('DECK · SLOT 4', false, deckInner, 'data-modal="customDeck"'),
      slotCard('FRIEND', false, f ? filledSlot(f.name || 'Friend', 'support', f.support_card_id || f.card_id || f.id) : emptySlot()),
    ].join('');
  }

  function renderControls() {
    const presetOpts = presets.map((p) => `<option${String(p) === String(activePreset) ? ' selected' : ''}>${esc(p)}</option>`).join('');
    $('setup-controls').innerHTML = `
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
        <button class="abtn cyan" type="button" data-modal="training">TRAINING SETTINGS</button>
        <button class="abtn cyan" type="button" data-modal="racing">RACING SETTINGS</button>
        <button class="abtn cyan" type="button" data-modal="scenario">SCENARIO OVERRIDES</button>
        <a class="abtn cyan" href="events.html" style="text-align:center;text-decoration:none">EVENT CHOICES</a>
      </div>
      <button class="abtn" type="button" style="width:100%" data-modal="skills">CONFIGURE SKILLS</button>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
        <button class="abtn" type="button" data-modal="customDeck">BUILD CUSTOM DECK</button>
        <button class="abtn" type="button" data-modal="recSupports">RECOMMENDED SUPPORTS</button>
      </div>

      <div class="card" style="padding:13px">
        <div class="card-title" style="margin-bottom:11px">SETTINGS PRESETS</div>
        <select class="form-sel" id="setup-preset" style="width:100%;background:var(--card);border:1px solid var(--line-card);color:var(--ink-2);font:600 var(--fs-md) var(--mono);padding:9px 11px;border-radius:4px;margin-bottom:9px">${presetOpts}</select>
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px">
          <button class="abtn amber" type="button" style="padding:7px 4px;font-size:var(--fs-xs)" id="preset-new">NEW</button>
          <button class="abtn amber" type="button" style="padding:7px 4px;font-size:var(--fs-xs)" id="preset-save">SAVE</button>
          <button class="abtn amber" type="button" style="padding:7px 4px;font-size:var(--fs-xs)" id="preset-load">LOAD</button>
          <button class="abtn danger" type="button" style="padding:7px 4px;font-size:var(--fs-xs)" id="preset-del">DEL</button>
        </div>
      </div>

      <div class="card" style="padding:13px">
        <div class="card-title" style="margin-bottom:11px">TRACKBLAZER</div>
        <div style="display:flex;flex-direction:column;gap:7px;margin-bottom:12px" id="setup-tb-stats">
          ${kv('smart_backend', '<span class="c-amber">MILP</span>')}
          ${kv('milp_available', '<span class="c-green">yes</span>')}
          ${kv('beam_fallback', '<span class="c-green">ready</span>')}
          ${kv('races_cache', '<span style="color:var(--ink-2)">—</span>')}
        </div>
        <div style="display:flex;gap:6px;margin-bottom:10px">
          <button class="abtn${raceMode === 'smart' ? ' amber' : ''}" type="button" style="flex:1" id="tb-mode-smart">SMART RACE SOLVER</button>
          <button class="abtn${raceMode === 'manual' ? ' amber' : ''}" type="button" style="flex:1" id="tb-mode-manual">MANUAL</button>
        </div>
        <button class="abtn cyan" type="button" data-modal="solver" style="width:100%;margin-bottom:11px">SOLVER SETTINGS</button>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:11px">
          <button class="abtn cyan" type="button" style="font-size:var(--fs-xs);padding:8px" id="setup-sync">SYNC DATA</button>
          <button class="abtn cyan" type="button" style="font-size:var(--fs-xs);padding:8px" id="setup-solve">SOLVE SMART</button>
          <button class="abtn cyan" type="button" style="font-size:var(--fs-xs);padding:8px" id="setup-apply">APPLY SMART</button>
          <button class="abtn amber" type="button" style="font-size:var(--fs-xs);padding:8px" id="setup-apply-manual">APPLY MANUAL</button>
          <button class="abtn danger" type="button" style="font-size:var(--fs-xs);padding:8px" id="setup-reset">RESET PLAN</button>
        </div>
        <div id="setup-solve-status" style="font:500 var(--fs-xs) var(--mono);color:var(--green);background:#0b1611;border:1px solid var(--green-bd);border-radius:4px;padding:8px 10px">Ready. Pick a trainee, then Solve Smart.</div>
        <div id="setup-plan"></div>
      </div>

      <div class="card" style="padding:13px">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px;gap:8px">
          <span style="font:700 var(--fs-md) var(--cond);letter-spacing:.16em;color:var(--ink)">RACE SCHEDULE</span>
          <div style="display:flex;align-items:center;gap:8px">
            <button class="abtn${showOP ? ' amber' : ''}" type="button" id="tb-op-toggle" style="font-size:var(--fs-2xs);padding:4px 9px" title="Show Open (OP) races in the schedule">OP RACES</button>
            <span style="font:500 var(--fs-xs) var(--mono);color:var(--label)" id="setup-sched-meta">${raceMode === 'manual' ? 'manual selection — click races' : 'smart race solver'}</span>
          </div>
        </div>
        <div style="font:500 var(--fs-xs) var(--mono);color:var(--dim);margin-bottom:12px">${raceMode === 'manual' ? 'Click a race to add/remove it (one per turn).' : 'Smart Race Solver picks the schedule. Switch to Manual to hand-pick.'}</div>
        <div id="setup-schedule" style="max-height:520px;overflow:auto;padding-right:6px"></div>
      </div>`;
    // ---- Smart Race Solver: solve (preview) + apply (persist to active preset) ----
    // The backend needs the trainee in the body and returns the full plan
    // (schedule, est fans, score, aptitudes, projected epithets, ledger…).
    const planFmt = (n) => (I.fmtCompact ? I.fmtCompact(n) : String(n));
    function renderPlan(plan) {
      const host = $('setup-plan');
      if (!host) return;
      if (!plan || plan.success === false) { host.innerHTML = ''; return; }
      const sched = plan.schedule || [];
      const apt = plan.aptitudes_used && Object.keys(plan.aptitudes_used).length
        ? Object.entries(plan.aptitudes_used).map(([k, v]) => `${k}:${v}`).join(' ') : '';
      const pref = (plan.preferred_distances || []).length
        ? `Distance mode: ${plan.distance_preference_mode || 'balanced'} · preferred ${(plan.preferred_distances || []).join(', ')}` : '';
      const epis = (plan.projected_epithets || []).length
        ? `Projected epithets: ${(plan.projected_epithets || []).slice(0, 8).join(', ')}${(plan.projected_epithets || []).length > 8 ? '…' : ''}` : '';
      const ledger = (plan.epithet_ledger || []).length
        ? `Epithet ledger: ${(plan.epithet_ledger || []).filter((e) => e.status && e.status !== 'untouched').slice(0, 6).map((e) => `${e.name}:${e.status}`).join(', ')}` : '';
      const notes = (plan.notes || []).length ? (plan.notes || []).slice(0, 3).join(' · ') : '';
      const tname = plan.trainee_name || (sel.trainee && sel.trainee.name) || '';
      const dim = (t) => t ? `<div style="font:500 var(--fs-xs)/1.5 var(--mono);color:var(--dim);margin-top:5px">${esc(t)}</div>` : '';
      const rows = sched.map((r) => {
        const meta = [r.grade, r.distance, planFmt(r.est_fans || r.fans || 0)].filter((x) => x !== '' && x != null).join(' · ');
        return `<div style="display:flex;align-items:baseline;gap:9px;padding:6px 0;border-top:1px solid var(--line-card)">
          <span style="font:700 var(--fs-sm) var(--mono);color:var(--amber);flex-shrink:0;width:30px">T${esc(String(r.turn || '?'))}</span>
          <span style="font:700 var(--fs-sm) var(--cond);letter-spacing:.04em;color:var(--ink);flex:1;min-width:0">${esc(r.name || r.program_id || 'Race')}</span>
          <span style="font:500 var(--fs-xs) var(--mono);color:var(--label);flex-shrink:0">${esc(meta)}</span>
        </div>`;
      }).join('');
      host.innerHTML = `<div style="margin-top:11px;border:1px solid var(--line-card);border-radius:6px;background:var(--card);padding:12px">
        <div style="font:700 var(--fs-md) var(--cond);letter-spacing:.04em;color:var(--ink-2)">${esc(plan.solver || 'Smart Race Solver')} picked <span style="color:var(--amber)">${esc(String(plan.race_count || sched.length || 0))}</span> races · est. <span style="color:var(--amber)">${esc(planFmt(plan.estimated_fans || 0))}</span> fans${plan.objective_score ? ` · score ${esc(String(plan.objective_score))}` : ''}${plan.fallback_used ? ' <span class="c-amber">(fallback)</span>' : ''}</div>
        ${dim(tname ? `Trainee: ${tname}` : '')}${dim(apt ? `Aptitudes: ${apt}` : '')}${dim(pref)}${dim(epis)}${dim(ledger)}${dim(notes)}
        ${rows ? `<div style="margin-top:9px;max-height:300px;overflow:auto">${rows}</div>` : '<div style="font:500 var(--fs-sm) var(--mono);color:var(--dim);margin-top:9px">No race rows returned.</div>'}
      </div>`;
    }
    const APT_RANK = { S: 8, A: 7, B: 6, C: 5, D: 4, E: 3, F: 2, G: 1 };
    const aptRank = (l) => APT_RANK[String(l || 'C').toUpperCase()] || 5;
    async function buildPlanBody() {
      const body = { trainee_name: sel.trainee.name || '', trainee_id: String(sel.trainee.id || ''), solver: 'smart' };
      // Pull the persisted Smart Race Solver config (weights, epithets, distances,
      // thresholds) so Solve respects SOLVER SETTINGS — same as the original.
      try {
        const r = await api('/api/smart-solver/config');
        const cfg = (r && r.config) || {};
        const s = cfg.trackblazer_solver_settings || {};
        body.weights = cfg.trackblazer_weights || {};
        body.target_epithets = cfg.trackblazer_target_epithets || [];
        body.forced_epithets = cfg.trackblazer_forced_epithets || [];
        body.primary_distances = Array.isArray(cfg.preferred_distances) ? cfg.preferred_distances : [];
        body.distance_preference_mode = s.distance_preference_mode || 'balanced';
        body.fan_bonus = Number(s.fan_bonus || 0);
        body.max_races_in_row = Number(s.max_races_in_row || 2);
        body.include_op = Boolean(s.include_op);
        body.min_aptitude_floor = aptRank(s.min_aptitude_floor || 'C');
      } catch (e) { /* fall back to backend defaults (trainee profile aptitudes) */ }
      return body;
    }
    async function solvePlan(apply) {
      const status = $('setup-solve-status');
      if (!online) { status.textContent = 'Preview mode — start the server to solve.'; return; }
      if (!sel.trainee || !sel.trainee.id) { status.textContent = 'Select a trainee before solving.'; return; }
      status.textContent = apply ? '… solving + applying via scipy MILP…' : '… solving via scipy MILP…';
      try {
        const body = await buildPlanBody();
        const plan = await api('/api/trackblazer/plan', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });
        if (!plan || plan.success === false) { status.textContent = (plan && plan.detail) || 'Solver returned no plan.'; return; }
        lastPlan = plan;
        renderPlan(plan);
        const races = plan.extra_race_list || [];
        if (apply) {
          await api('/api/presets/save_races', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ races, source: 'smart' }),
          });
          // Reflect the applied plan in the schedule grid + return to smart mode.
          raceMode = 'smart';
          selectedRaceIds.clear(); races.forEach((id) => selectedRaceIds.add(Number(id)));
          renderSchedule();
          status.textContent = `✓ Applied ${races.length || plan.race_count || 0} races to the active preset.`;
        } else {
          status.textContent = `✓ Solved — ${plan.race_count || races.length || 0} races picked. Click Apply Smart to use this plan.`;
        }
      } catch (e) { status.textContent = (apply ? 'Apply' : 'Solve') + ' request failed.'; }
    }
    $('setup-solve').addEventListener('click', () => solvePlan(false));
    $('setup-apply').addEventListener('click', () => solvePlan(true));
    // BUG #10: explicit APPLY MANUAL — switch to manual mode and persist the
    // hand-picked schedule (manual already auto-saves on each pick; this gives
    // the symmetric, deliberate confirm the Smart side has).
    { const am = $('setup-apply-manual'); if (am) am.addEventListener('click', () => {
        setRaceMode('manual');
        saveRaces('manual');
        const s = $('setup-solve-status'); if (s) s.textContent = `✓ Manual schedule applied — ${selectedRaceIds.size} race(s) saved to this preset.`;
      }); }

    const setStatus = (msg) => { const s = $('setup-solve-status'); if (s) s.textContent = msg; };
    const presetName = () => { const s = $('setup-preset'); return s ? s.value : ''; };
    // ---- preset CRUD ----
    $('preset-load').addEventListener('click', async () => {
      if (!online) return setStatus('Preview mode — start the server.');
      const name = presetName(); if (!name) return;
      setStatus('Loading preset “' + name + '”…');
      try {
        await api('/api/settings-presets/active', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }) });
        // Restore the team saved on this preset: push its selection into the global
        // /api/selection so the post-reload boot (and a run) use the preset's team.
        // (Normal navigation keeps the global selection, so unsaved picks aren't lost.)
        try {
          const all = await api('/api/settings-presets');
          const cur = (all && Array.isArray(all.presets) ? all.presets : []).find((p) => (p && (p.name || p)) === name);
          if (cur && typeof cur === 'object' && cur.selection) {
            await api('/api/selection', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ selection: cur.selection }) });
          }
        } catch (e) { /* best effort — fall through to reload */ }
        location.reload();
      } catch (e) { setStatus('Load failed.'); }
    });
    $('preset-del').addEventListener('click', async () => {
      if (!online) return setStatus('Preview mode — start the server.');
      const name = presetName(); if (!name) return;
      if (!window.confirm('Delete preset “' + name + '”?')) return;
      try {
        await api('/api/settings-presets/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }) });
        presets = presets.filter((p) => p !== name);
        if (activePreset === name) activePreset = presets[0] || '';
        renderControls();
        setStatus('Deleted preset “' + name + '”.');
      } catch (e) { setStatus('Delete failed.'); }
    });
    $('preset-new').addEventListener('click', async () => {
      if (!online) return setStatus('Preview mode — start the server.');
      const name = (window.prompt('New preset name:') || '').trim(); if (!name) return;
      try {
        await api('/api/settings-presets', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ preset: { name } }) });
        if (!presets.includes(name)) presets.push(name);
        activePreset = name;
        renderControls();
        await api('/api/settings-presets/active', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }) });
        setStatus('Created preset “' + name + '”.');
      } catch (e) { setStatus('Create failed.'); }
    });
    $('preset-save').addEventListener('click', async () => {
      if (!online) return setStatus('Preview mode — start the server.');
      const name = presetName(); if (!name) return;
      setStatus('Saving “' + name + '”…');
      try {
        // round-trip the active preset so the current selection is persisted onto it
        const all = await api('/api/settings-presets');
        const cur = (all && Array.isArray(all.presets) ? all.presets : []).find((p) => (p.name || p) === name);
        const preset = (cur && typeof cur === 'object') ? cur : { name };
        preset.selection = { deck: sel.deck, friend: sel.friend, trainee: sel.trainee, veterans: sel.veterans, guestParents: sel.guestParents };
        await api('/api/settings-presets', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ preset }) });
        setStatus('Saved “' + name + '”.');
      } catch (e) { setStatus('Save failed.'); }
    });
    // ---- trackblazer actions ----
    const tbAct = (id, url, label) => {
      const b = $(id); if (!b) return;
      b.addEventListener('click', async () => {
        if (!online) return setStatus('Preview mode — start the server.');
        setStatus(label + '…');
        try {
          const r = await api(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
          setStatus(r && r.success !== false ? '✓ ' + label + ' done.' : (r && r.detail) || (label + ' failed.'));
        } catch (e) { setStatus(label + ' failed.'); }
      });
    };
    tbAct('setup-sync', '/api/trackblazer/sync', 'Sync race data');
    $('setup-reset').addEventListener('click', () => { lastPlan = null; const p = $('setup-plan'); if (p) p.innerHTML = ''; setStatus('Plan reset. Solve again to rebuild.'); });
    const bms = $('tb-mode-smart'); if (bms) bms.addEventListener('click', () => setRaceMode('smart'));
    const bmm = $('tb-mode-manual'); if (bmm) bmm.addEventListener('click', () => setRaceMode('manual'));
    const bop = $('tb-op-toggle'); if (bop) bop.addEventListener('click', () => setShowOP(!showOP));
    renderSchedule();
  }
  function kv(k, v) {
    return `<div style="display:flex;justify-content:space-between;font:500 var(--fs-sm) var(--mono)"><span class="c-mut">${k}</span>${v}</div>`;
  }

  function renderLibrary() {
    const L = lists();
    const tabs = [['trainees', 'TRAINEES', L.trainees.length], ['parents', 'PARENTS', L.parents.length], ['guests', 'GUEST PARENTS', L.guests.length], ['decks', 'DECKS', L.decks.length], ['friends', 'FRIEND SUPPORTS', L.friends.length], ['cards', 'OWNED CARDS', L.cards.length]];
    $('setup-library').innerHTML = `
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:13px">
        <span style="font:700 var(--fs-base) var(--cond);letter-spacing:.18em;color:var(--ink)">LIBRARY</span>
        <div class="search" style="border:1px solid var(--line-card);border-radius:4px;width:200px;padding:7px 11px"><span class="ic">⌕</span><input type="text" id="lib-search" placeholder="search library"></div>
      </div>
      <div style="display:flex;gap:6px;border-bottom:1px solid var(--line);margin-bottom:14px;flex-wrap:wrap">
        ${tabs.map(([k, l, n]) => `<button class="setup-libtab" data-tab="${k}" type="button" style="font:600 var(--fs-sm) var(--cond);letter-spacing:.12em;padding:8px 14px;border:none;background:${k === libTab ? 'var(--amber)' : 'none'};color:${k === libTab ? 'var(--panel)' : 'var(--label)'};cursor:pointer;border-radius:4px 4px 0 0">${l}${online ? ` · ${n}` : ''}</button>`).join('')}
      </div>
      <div id="setup-libbody"></div>`;
    document.querySelectorAll('.setup-libtab').forEach((b) => b.addEventListener('click', () => { libTab = b.dataset.tab; renderLibrary(); }));
    const search = $('lib-search');
    if (search) search.addEventListener('input', () => renderLibBody(search.value.trim().toLowerCase()));
    renderLibBody();
    wireSparks();
  }

  function emptyTab(label) {
    return `<div style="font:600 var(--fs-sm) var(--cond);letter-spacing:.16em;color:var(--label);padding:22px 0;text-align:center">${label}</div>`;
  }
  function grid(html, cols) {
    return `<div style="display:grid;grid-template-columns:repeat(${cols || 6},1fr);gap:10px">${html}</div>`;
  }

  // ---- Sparks hover (Parents + Guest Parents): main parent + 2 grandparents,
  //      each with G1/G2/G3 win counts and colour-coded factor rows. ----
  let SPARK_ITEMS = [];
  let _sparkTip = null;
  const FACTOR_BG = {
    stat: 'linear-gradient(90deg,#2f7fc4,#245f97)',
    aptitude: 'linear-gradient(90deg,#d8559a,#b23e7e)',
    unique: 'linear-gradient(90deg,#5aa84f,#3d7a36)',
    scenario: 'linear-gradient(90deg,#caa13a,#a07f28)',
  };
  function factorRow(f) {
    const cat = String(f.category || '').toLowerCase();
    const bg = FACTOR_BG[cat];
    const n = Math.max(0, Math.min(3, Number(f.stars || 0)));
    const stars = n ? `<span style="color:#ffd54a;font-size:var(--fs-xs);letter-spacing:-1px;flex-shrink:0">${'\u2605'.repeat(n)}</span>` : '';
    return `<div style="display:flex;align-items:center;justify-content:space-between;gap:6px;padding:4px 7px;border-radius:4px;${bg ? `background:${bg}` : 'background:#14161c;border:1px solid var(--line-card)'}">
      <span style="font:600 var(--fs-xs) var(--cond);letter-spacing:.02em;color:${bg ? '#fff' : 'var(--ink-2)'};overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(f.name || '')}</span>${stars}</div>`;
  }
  function winChips(w) {
    if (!w) return '';
    const chip = (l, v) => `<span style="font:700 var(--fs-2xs) var(--mono);color:var(--ink-3);background:#11131a;border:1px solid var(--line-card);padding:1px 5px;border-radius:8px">${l} ${v || 0}</span>`;
    return `<div style="display:flex;gap:4px;margin-top:3px">${chip('G1', w.g1)}${chip('G2', w.g2)}${chip('G3', w.g3)}</div>`;
  }
  function sparkNode(node, fallbackImg, isSelf) {
    if (!node || !(node.factors || []).length) return '';
    const img = node.card_id || fallbackImg;
    return `<div style="border:1px solid ${isSelf ? 'var(--amber)' : 'var(--line-card)'};border-radius:7px;padding:8px;background:var(--card)">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:7px">
        <img src="/api/images/${esc(String(img || ''))}.png" alt="" style="width:26px;height:26px;border-radius:50%;object-fit:cover;flex-shrink:0;border:1px solid var(--line-card)" onerror="this.style.visibility='hidden'">
        <div style="min-width:0"><div style="font:700 var(--fs-md) var(--cond);letter-spacing:.04em;color:var(--ink);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(node.name || ('Card ' + (node.card_id || '?')))}</div>${winChips(node.wins)}</div>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:5px">${(node.factors || []).map(factorRow).join('')}</div>
    </div>`;
  }
  function parentSparksHtml(p) {
    const tree = p.tree || {};
    const self = sparkNode(tree.self, p.card_id, true);
    const p1 = sparkNode(tree.p1, p.card_id, false);
    const p2 = sparkNode(tree.p2, p.card_id, false);
    const title = `<div style="font:800 var(--fs-sm) var(--cond);letter-spacing:.2em;color:var(--amber);margin-bottom:10px">SPARKS</div>`;
    if (!self && !p1 && !p2) return `${title}<div style="font:500 var(--fs-md) var(--mono);color:var(--dim);padding:6px 2px">No spark factors returned for ${esc(p.name || 'this parent')}.</div>`;
    const grand = (p1 || p2) ? `<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px">${p1}${p2}</div>` : '';
    return `${title}${self}${grand}`;
  }
  function ensureSparkTip() {
    if (_sparkTip) return _sparkTip;
    _sparkTip = document.createElement('div');
    _sparkTip.style.cssText = 'position:fixed;z-index:9000;display:none;pointer-events:none;width:440px;max-width:92vw;background:#0b0d12;border:1px solid var(--line);border-radius:10px;box-shadow:0 18px 50px rgba(0,0,0,.6);padding:14px';
    document.body.appendChild(_sparkTip);
    return _sparkTip;
  }
  function positionSparkTip(x, y) {
    const t = _sparkTip, w = t.offsetWidth, h = t.offsetHeight;
    let nx = x + 18, ny = y + 18;
    if (nx + w > window.innerWidth - 8) nx = x - w - 18;
    if (nx < 8) nx = 8;
    if (ny + h > window.innerHeight - 8) ny = window.innerHeight - h - 8;
    if (ny < 8) ny = 8;
    t.style.left = nx + 'px'; t.style.top = ny + 'px';
  }
  function wireSparks() {
    if (document._sparksWired) return;
    document._sparksWired = true;
    document.addEventListener('mouseover', (e) => {
      const card = e.target.closest && e.target.closest('[data-spark]');
      if (!card) return;
      const item = SPARK_ITEMS[+card.dataset.spark];
      if (!item) return;
      const t = ensureSparkTip();
      t.innerHTML = parentSparksHtml(item);
      t.style.display = 'block';
      positionSparkTip(e.clientX, e.clientY);
    });
    document.addEventListener('mousemove', (e) => { if (_sparkTip && _sparkTip.style.display === 'block') positionSparkTip(e.clientX, e.clientY); });
    document.addEventListener('mouseout', (e) => {
      const card = e.target.closest && e.target.closest('[data-spark]');
      if (!card) return;
      const to = e.relatedTarget;
      if (to && to.closest && to.closest('[data-spark]') === card) return;
      if (_sparkTip) _sparkTip.style.display = 'none';
    });
  }

  // ---- Parents search + factor filter (operates on parent.tree factors) ----
  const PF_RANK = { 'SS+': 13, 'SS': 12, 'S+': 11, 'S': 10, 'A+': 9, 'A': 8, 'B+': 7, 'B': 6, 'C+': 5, 'C': 4, 'D+': 3, 'D': 2, 'E': 1 };
  const PF_AGES = [[0, 'Cleanup age\u2026'], [1, 'Created < 1h ago'], [6, 'Created < 6h ago'], [12, 'Created < 12h ago'], [24, 'Created < 24h ago'], [48, 'Created < 48h ago'], [72, 'Created < 3d ago'], [168, 'Created < 7d ago']];
  // Spark categories -> the EXACT factor names in data/factor_map.json. The
  // aptitude checkbox labels are short (Front/Pace/Late/End); APT_NAME maps each
  // to its full factor name so the filter matches the data.
  const ATTR_KEYS = ['Speed', 'Stamina', 'Power', 'Guts', 'Wit'];
  const APT_LABELS = ['Turf', 'Dirt', 'Sprint', 'Mile', 'Medium', 'Long', 'Front', 'Pace', 'Late', 'End'];
  const APT_NAME = { Turf: ['Turf'], Dirt: ['Dirt'], Sprint: ['Sprint'], Mile: ['Mile'], Medium: ['Medium'], Long: ['Long'], Front: ['Front Runner'], Pace: ['Pace Chaser'], Late: ['Late Surger'], End: ['End Closer'] };
  const PF_SORTS = [['rating', 'Rating'], ['sparks', 'Sparks'], ['skills', 'Skills'], ['track', 'Track'], ['distance', 'Distance'], ['style', 'Style'], ['date', 'Date Acquired'], ['name', 'Name'], ['fav', 'Favorites']];
  // Default: everything checked, All stars, self-only (origin off) = a no-op that
  // shows all parents, mirroring the in-game default.
  const defaultPF = () => ({ sort: 'date', attr: { keys: ATTR_KEYS.slice(), min: 1, origin: false }, apt: { keys: APT_LABELS.slice(), min: 1, origin: false }, uniq: { on: false, min: 1, origin: false }, maxAgeH: 0 });
  const PF = defaultPF();
  try {
    const saved = JSON.parse(localStorage.getItem('icarus_parent_filter') || '{}');
    if (saved && typeof saved === 'object') {
      if (PF_SORTS.some((s) => s[0] === saved.sort)) PF.sort = saved.sort;
      ['attr', 'apt', 'uniq'].forEach((k) => { if (saved[k] && typeof saved[k] === 'object') Object.assign(PF[k], saved[k]); });
      if (typeof saved.maxAgeH === 'number') PF.maxAgeH = saved.maxAgeH;
    }
  } catch (e) {}
  const pfSave = () => { try { localStorage.setItem('icarus_parent_filter', JSON.stringify(PF)); } catch (e) {} };

  // ---- Favorited parents / guest parents (localStorage; pinned to top + star) ----
  const _favLoad = (k) => { try { return new Set((JSON.parse(localStorage.getItem(k) || '[]') || []).map(String)); } catch (e) { return new Set(); } };
  const FAV = { parents: _favLoad('icarus_fav_parents'), guests: _favLoad('icarus_fav_guests') };
  function favSave() {
    try {
      localStorage.setItem('icarus_fav_parents', JSON.stringify([...FAV.parents]));
      localStorage.setItem('icarus_fav_guests', JSON.stringify([...FAV.guests]));
    } catch (e) {}
  }
  function toggleFav(kind, iid) {
    const s = FAV[kind === 'guests' ? 'guests' : 'parents'];
    iid = String(iid);
    if (s.has(iid)) s.delete(iid); else s.add(iid);
    favSave();
  }
  // Stable favorites-first ordering (preserves the incoming order within each group).
  function favFirst(list, kind) {
    const s = FAV[kind === 'guests' ? 'guests' : 'parents'];
    const fav = [], rest = [];
    list.forEach((p) => (s.has(String(p.instance_id)) ? fav : rest).push(p));
    return fav.concat(rest);
  }
  function parentFactors(p) {
    const m = new Map(); let total = 0;
    const tree = p.tree || {};
    ['self', 'p1', 'p2'].forEach((k) => {
      const node = tree[k]; if (!node) return;
      (node.factors || []).forEach((f) => {
        const label = String(f.name || '').trim(); if (!label) return;
        const key = label.toLowerCase();
        const cat = String(f.category || 'other').toLowerCase();
        const st = Math.max(0, Number(f.stars || 0));
        if (!m.has(key)) m.set(key, { label, cat, total: 0, self: 0 });
        const row = m.get(key); row.total += st; if (k === 'self') row.self += st; total += st;
      });
    });
    return { factors: m, total };
  }
  // ---- Spark matching over the parent's self node (+ 2 origin legacies) ----
  function nodeFactors(p, includeOrigin) {
    const tree = p.tree || {}; const out = [];
    (includeOrigin ? ['self', 'p1', 'p2'] : ['self']).forEach((k) => {
      const n = tree[k]; if (n) (n.factors || []).forEach((f) => out.push(f));
    });
    return out;
  }
  const aptNames = (labels) => labels.reduce((a, l) => a.concat(APT_NAME[l] || []), []);
  function sparkHit(p, category, names, minStars, includeOrigin) {
    const want = names ? new Set(names) : null;
    for (const f of nodeFactors(p, includeOrigin)) {
      if (String(f.category || '').toLowerCase() !== category) continue;
      if (want && !want.has(f.name)) continue;
      if (Number(f.stars || 0) >= minStars) return true;
    }
    return false;
  }
  function sumStars(p, category, names) {
    const want = names ? new Set(names) : null; let s = 0;
    nodeFactors(p, true).forEach((f) => {
      if (String(f.category || '').toLowerCase() !== category) return;
      if (want && !want.has(f.name)) return;
      s += Number(f.stars || 0);
    });
    return s;
  }
  // A spark section only FILTERS when narrowed: stars raised above All, or some
  // (not all) boxes checked. All-checked + All-stars = pass-through (show all).
  const sectionActive = (sec, allKeys) => sec.keys.length > 0 && (sec.min > 1 || sec.keys.length < allKeys.length);
  function pfActiveCount(s) {
    let n = 0;
    if (sectionActive(s.attr, ATTR_KEYS)) n++;
    if (sectionActive(s.apt, APT_LABELS)) n++;
    if (s.uniq.on) n++;
    return n;
  }
  function pfPasses(p) {
    if (sectionActive(PF.attr, ATTR_KEYS) && !sparkHit(p, 'stat', PF.attr.keys, PF.attr.min, PF.attr.origin)) return false;
    if (sectionActive(PF.apt, APT_LABELS) && !sparkHit(p, 'aptitude', aptNames(PF.apt.keys), PF.apt.min, PF.apt.origin)) return false;
    if (PF.uniq.on && !sparkHit(p, 'unique', null, PF.uniq.min, PF.uniq.origin)) return false;
    return true;
  }
  function pfMetric(p) {
    switch (PF.sort) {
      case 'rating': return PF_RANK[p.rank] || 0;
      case 'sparks': return parentFactors(p).total;
      case 'skills': return sumStars(p, 'skill');
      case 'track': return sumStars(p, 'aptitude', ['Turf', 'Dirt']);
      case 'distance': return sumStars(p, 'aptitude', ['Sprint', 'Mile', 'Medium', 'Long']);
      case 'style': return sumStars(p, 'aptitude', ['Front Runner', 'Pace Chaser', 'Late Surger', 'End Closer']);
      case 'date': return Number(p.create_date || 0);
      default: return 0;
    }
  }
  function pfList(all) {
    const out = all.filter(pfPasses);
    if (PF.sort === 'name') out.sort((a, b) => String(a.name || '').localeCompare(String(b.name || '')));
    else if (PF.sort !== 'fav') out.sort((a, b) => pfMetric(b) - pfMetric(a));
    return favFirst(out, 'parents');   // favorited parents always pinned to the top
  }
  function pfSummary() {
    const n = pfActiveCount(PF);
    const sortLabel = (PF_SORTS.find((s) => s[0] === PF.sort) || ['', 'Date Acquired'])[1];
    return `Sort: ${sortLabel} · ${n ? `${n} filter${n > 1 ? 's' : ''}` : 'no filters'}`;
  }
  function pfBarHtml() {
    const n = pfActiveCount(PF);
    const dot = n ? `<span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--red)"></span>` : '';
    return `<div style="display:flex;align-items:center;gap:12px;margin-bottom:14px;flex-wrap:wrap">
      <button type="button" id="pf-display" style="display:inline-flex;align-items:center;gap:8px;font:700 var(--fs-sm) var(--cond);letter-spacing:.12em;padding:9px 16px;border-radius:6px;border:1px solid var(--line-card);background:var(--card);color:var(--ink);cursor:pointer">DISPLAY SETTINGS ${dot}</button>
      <span style="font:500 var(--fs-sm) var(--mono);color:var(--label)">${pfSummary()}</span>
      <span id="pf-count" style="font:500 var(--fs-sm) var(--mono);color:var(--dim);margin-left:auto"></span>
    </div>`;
  }
  // ---- The in-game-style Display Settings modal (Sort + Filter tabs) ----
  function dsSortTab(W) {
    return `<div style="font:800 var(--fs-xs) var(--cond);letter-spacing:.2em;color:var(--amber);margin-bottom:12px">SORT BY</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:11px 16px">${PF_SORTS.map(([v, l]) =>
        `<label style="display:inline-flex;align-items:center;gap:8px;cursor:pointer;font:600 var(--fs-md) var(--mono);color:var(--ink-2)"><input type="radio" name="ds-sort" value="${v}"${W.sort === v ? ' checked' : ''}>${l}</label>`).join('')}</div>`;
  }
  function dsStarRadio(sect, W) {
    const opt = (v, l) => `<label style="display:inline-flex;align-items:center;gap:5px;cursor:pointer;font:600 var(--fs-sm) var(--mono);color:var(--ink-2)"><input type="radio" name="ds-${sect}-min" value="${v}"${W[sect].min === v ? ' checked' : ''}>${l}</label>`;
    return `<div style="display:flex;gap:16px;flex-wrap:wrap;margin:9px 0 5px">${opt(1, 'All')}${opt(2, '\u2605\u2605 or Above')}${opt(3, '\u2605\u2605\u2605 Only')}</div>`;
  }
  const dsOrigin = (sect, W) => `<label style="display:inline-flex;align-items:center;gap:6px;cursor:pointer;font:600 var(--fs-sm) var(--mono);color:var(--dim)"><input type="checkbox" data-ds-origin="${sect}"${W[sect].origin ? ' checked' : ''}>Include Sparks from Origin Legacies</label>`;
  const dsChecks = (sect, labels, W) => `<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:7px 10px">${labels.map((l) =>
    `<label style="display:inline-flex;align-items:center;gap:6px;cursor:pointer;font:600 var(--fs-sm) var(--mono);color:var(--ink-2)"><input type="checkbox" data-ds-chk="${sect}" value="${esc(l)}"${W[sect].keys.includes(l) ? ' checked' : ''}>${esc(l)}</label>`).join('')}</div>`;
  const dsSection = (title, inner) => `<div style="border:1px solid var(--line-card);border-radius:8px;background:var(--card);padding:12px 14px;margin-bottom:12px">
      <div style="font:800 var(--fs-xs) var(--cond);letter-spacing:.18em;color:var(--green);margin-bottom:9px">${title}</div>${inner}</div>`;
  function dsFilterTab(W) {
    const cleanup = `<div style="border:1px solid var(--red-bd);border-radius:8px;padding:12px 14px;margin-top:4px">
        <div style="font:800 var(--fs-xs) var(--cond);letter-spacing:.18em;color:var(--red);margin-bottom:9px">CLEANUP (ICARUS)</div>
        <select id="ds-age" style="width:100%;background:var(--bar);border:1px solid var(--line-card);color:var(--ink-2);font:600 var(--fs-sm) var(--mono);padding:8px 10px;border-radius:5px;margin-bottom:9px">${PF_AGES.map(([v, l]) => `<option value="${v}"${Number(W.maxAgeH || 0) === Number(v) ? ' selected' : ''}>${esc(l)}</option>`).join('')}</select>
        <div style="display:flex;align-items:center;gap:10px"><button type="button" id="ds-cleanup" class="abtn danger">PREVIEW CLEANUP</button><span id="ds-cleanup-hint" style="font:500 var(--fs-xs) var(--mono);color:var(--label)"></span></div>
      </div>`;
    return dsSection('ATTRIBUTE SPARKS', dsChecks('attr', ATTR_KEYS, W) + dsStarRadio('attr', W) + dsOrigin('attr', W))
      + dsSection('APTITUDE SPARKS', dsChecks('apt', APT_LABELS, W) + dsStarRadio('apt', W) + dsOrigin('apt', W))
      + dsSection('UNIQUE SPARKS', `<label style="display:inline-flex;align-items:center;gap:6px;cursor:pointer;font:600 var(--fs-sm) var(--mono);color:var(--ink-2)"><input type="checkbox" data-ds-uniq-on${W.uniq.on ? ' checked' : ''}>Umamusume (has a unique spark)</label>` + dsStarRadio('uniq', W) + dsOrigin('uniq', W))
      + cleanup;
  }
  function openDisplaySettings(all) {
    const W = JSON.parse(JSON.stringify(PF));
    let tab = 'filter';
    const ov = document.createElement('div');
    ov.className = 'modal-overlay'; ov.style.zIndex = '80';
    const tabBtn = (id, label) => `<button type="button" class="ds-tab" data-ds-tab="${id}" style="flex:1;padding:11px;font:800 var(--fs-sm) var(--cond);letter-spacing:.18em;background:transparent;border:none;border-bottom:2px solid transparent;color:var(--dim);cursor:pointer">${label}</button>`;
    ov.innerHTML = `<div class="modal" style="width:470px;max-height:90vh;display:flex;flex-direction:column">
      <div class="modal-head"><span class="modal-mark"></span><span class="modal-title">DISPLAY SETTINGS</span><button class="modal-x" type="button" data-ds-close>\u00d7</button></div>
      <div style="display:flex;border-bottom:1px solid var(--line)">${tabBtn('sort', 'SORT')}${tabBtn('filter', 'FILTER')}</div>
      <div class="modal-body" id="ds-body" style="flex:1;overflow:auto"></div>
      <div class="modal-foot" style="justify-content:space-between"><button class="abtn danger" type="button" data-ds-reset>RESET</button><span style="display:flex;gap:8px"><button class="abtn" type="button" data-ds-cancel>CANCEL</button><button class="abtn amber" type="button" data-ds-ok>OK</button></span></div>
    </div>`;
    document.body.appendChild(ov);
    const $$ = (s) => ov.querySelector(s);
    const body = $$('#ds-body');
    function paintTabs() {
      ov.querySelectorAll('.ds-tab').forEach((b) => {
        const on = b.dataset.dsTab === tab;
        b.style.color = on ? 'var(--ink)' : 'var(--dim)';
        b.style.borderBottomColor = on ? 'var(--amber)' : 'transparent';
        if (b.dataset.dsTab === 'filter') b.innerHTML = 'FILTER' + (pfActiveCount(W) ? ' <span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--red);vertical-align:middle"></span>' : '');
      });
    }
    function refreshCleanupHint() {
      const hint = body.querySelector('#ds-cleanup-hint'); const btn = body.querySelector('#ds-cleanup');
      if (!hint || !btn) return;
      const maxH = Number(W.maxAgeH || 0);
      if (!maxH) { hint.textContent = 'Pick an age window; selected parents are protected.'; btn.disabled = true; btn.style.opacity = '.5'; }
      else { const n = all.filter((p) => Number(p.create_date || 0) >= (Date.now() / 1000 - maxH * 3600)).length; hint.textContent = `${n} recent parent(s) in window; selected are protected.`; btn.disabled = n === 0; btn.style.opacity = n === 0 ? '.5' : '1'; }
    }
    function wireTab() {
      body.querySelectorAll('[data-ds-chk]').forEach((el) => el.addEventListener('change', () => {
        const sec = el.dataset.dsChk; const arr = W[sec].keys; const i = arr.indexOf(el.value);
        if (el.checked) { if (i < 0) arr.push(el.value); } else if (i >= 0) arr.splice(i, 1);
        paintTabs();
      }));
      ['attr', 'apt', 'uniq'].forEach((sec) => body.querySelectorAll(`input[name="ds-${sec}-min"]`).forEach((el) => el.addEventListener('change', () => { if (el.checked) { W[sec].min = Number(el.value); paintTabs(); } })));
      body.querySelectorAll('[data-ds-origin]').forEach((el) => el.addEventListener('change', () => { W[el.dataset.dsOrigin].origin = el.checked; }));
      const uon = body.querySelector('[data-ds-uniq-on]'); if (uon) uon.addEventListener('change', () => { W.uniq.on = uon.checked; paintTabs(); });
      body.querySelectorAll('input[name="ds-sort"]').forEach((el) => el.addEventListener('change', () => { if (el.checked) W.sort = el.value; }));
      const age = body.querySelector('#ds-age'); if (age) age.addEventListener('change', () => { W.maxAgeH = Number(age.value); refreshCleanupHint(); });
      const cu = body.querySelector('#ds-cleanup'); if (cu) cu.addEventListener('click', () => { if (!online) { window.alert('Preview mode \u2014 start the server.'); return; } PF.maxAgeH = Number(W.maxAgeH || 0); pfCleanup(all); });
      refreshCleanupHint();
    }
    function renderTab() { body.innerHTML = tab === 'sort' ? dsSortTab(W) : dsFilterTab(W); wireTab(); paintTabs(); }
    ov.querySelectorAll('.ds-tab').forEach((b) => b.addEventListener('click', () => { tab = b.dataset.dsTab; renderTab(); }));
    const close = () => ov.remove();
    $$('[data-ds-close]').addEventListener('click', close);
    $$('[data-ds-cancel]').addEventListener('click', close);
    ov.addEventListener('mousedown', (e) => { if (e.target === ov) close(); });
    $$('[data-ds-reset]').addEventListener('click', () => { const d = defaultPF(); W.sort = d.sort; W.attr = d.attr; W.apt = d.apt; W.uniq = d.uniq; W.maxAgeH = d.maxAgeH; renderTab(); });
    $$('[data-ds-ok]').addEventListener('click', () => { PF.sort = W.sort; PF.attr = W.attr; PF.apt = W.apt; PF.uniq = W.uniq; PF.maxAgeH = W.maxAgeH; pfSave(); close(); renderLibBody(); });
    renderTab();
  }
  function pfRecentCount(all) {
    const maxH = Number(PF.maxAgeH || 0); if (!maxH) return 0;
    const cutoff = Date.now() / 1000 - maxH * 3600;
    return all.filter((p) => Number(p.create_date || 0) >= cutoff).length;
  }
  function pfRenderGrid(all) {
    const items = pfList(all);
    SPARK_ITEMS = items;
    const g = $('pf-grid');
    if (g) g.innerHTML = items.length ? grid(items.map((p, i) => gridCard({
      imgId: p.card_id, name: p.name, badge: RANK[p.rank], kicker: 'ID ' + (p.instance_id || '?'),
      selected: sel.veterans.some((v) => Number(v.instance_id) === Number(p.instance_id)),
      favIid: p.instance_id, favKind: 'parents', isFav: FAV.parents.has(String(p.instance_id)),
      attrs: `data-pick="parent" data-iid="${esc(String(p.instance_id))}" data-spark="${i}"`,
    })).join('')) : emptyTab('No parents match the filters.');
    const c = $('pf-count'); if (c) c.textContent = `${items.length}/${all.length} parents`;
  }
  async function pfCleanup(all) {
    const maxH = Number(PF.maxAgeH || 0); if (!maxH) return;
    try {
      const prev = await api('/api/parents/remove-recent', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ max_age_hours: maxH, dry_run: true }) });
      const parents = (prev && prev.parents) || [];
      if (!parents.length) { window.alert('No deletable parents found in that age window.'); return; }
      const sample = parents.slice(0, 10).map((p) => `${p.name || 'Unknown'} \u00b7 ID ${p.instance_id}`).join('\n');
      const extra = parents.length > 10 ? `\n\u2026and ${parents.length - 10} more` : '';
      if (!window.confirm(`Delete ${parents.length} parent(s) created in the last ${maxH}h?\n\n${sample}${extra}\n\nSelected/active parents are excluded. This cannot be undone.`)) return;
      const res = await api('/api/parents/remove-recent', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ max_age_hours: maxH, dry_run: false }) });
      window.alert(res && res.success ? `Deleted ${res.removed || 0} parent(s). Sync to refresh the list.` : `Delete failed: ${(res && res.detail) || 'unknown error'}`);
    } catch (e) { window.alert('Cleanup failed.'); }
  }
  function pfWire(all) {
    const btn = $('pf-display'); if (btn) btn.addEventListener('click', () => openDisplaySettings(all));
  }

  // ---- Decks: hover tooltip (per-card effects + score) and the always-on
  //      "Deck Bonuses" panel above the list. Both use /api/supports/details. ----
  const TYPE_COLOR = {
    speed: '#3b9cff', stamina: '#ff5d6c', power: '#ff9f1c', guts: '#ff6fae', wit: '#36c98f', friend: '#c98bff',
  };
  function typeChip(t) {
    const k = String(t || '').toLowerCase();
    const c = TYPE_COLOR[k] || 'var(--label)';
    return `<span style="font:800 var(--fs-2xs) var(--cond);letter-spacing:.08em;padding:2px 6px;border-radius:3px;color:#0b0d12;background:${c}">${esc(String(t || '?').toUpperCase())}</span>`;
  }
  function scoreColor(s) { return s >= 7.5 ? '#36c98f' : s >= 5.5 ? '#7bd06b' : s >= 3.5 ? '#f2a900' : '#ff5d6c'; }
  function scoreBadge(score, big) {
    const c = scoreColor(score);
    return `<span style="display:inline-flex;align-items:baseline;gap:1px;font:800 ${big ? 22 : 15}px var(--cond);color:${c}">${score.toFixed(1)}<span style="font:700 ${big ? 10 : 8}px var(--mono);color:var(--dim)">/10</span></span>`;
  }
  async function fetchDeckInfo(deck) {
    const ids = (deck.cards || []).map((c) => c.id || c.support_card_id || '').filter(Boolean).join(',');
    const lbs = (deck.cards || []).map((c) => Number(c.limit_break_count ?? 0)).join(',');
    const qs = new URLSearchParams({ ids, lbs });
    const tid = sel.trainee && sel.trainee.id;
    if (tid) qs.set('trainee_card_id', String(tid));
    return api('/api/supports/details?' + qs.toString());
  }
  function deckTooltipHtml(deck, p) {
    if (!p || !p.success) return `<div style="font:500 var(--fs-md)/1.6 var(--mono);color:var(--dim);padding:4px 2px">${esc((p && p.detail) || 'Master data not loaded \u2014 run a master data sync to see card bonuses.')}</div>`;
    const score = Number(p.deck_score || 0), verdict = String(p.deck_verdict || ''), bd = p.deck_breakdown || {};
    const cards = (p.cards || []).map((card) => {
      const eff = (card.effects_ordered || []).slice(0, 4).map((e) => `<span style="font:600 var(--fs-2xs) var(--mono);color:var(--ink-2);background:#11131a;border:1px solid var(--line-card);padding:1px 5px;border-radius:7px"><b style="color:var(--ink)">${esc(e.label)}</b> ${e.value > 0 ? '+' : ''}${esc(String(e.value))}${esc(e.unit || '')}</span>`).join('');
      return `<div style="border:1px solid var(--line-card);border-radius:6px;padding:7px 8px;background:var(--card)">
        <div style="display:flex;align-items:center;gap:5px;margin-bottom:4px">${typeChip(card.type_label)}<span style="font:700 var(--fs-2xs) var(--mono);color:var(--label)">${esc(card.rarity_label || '?')}</span><span style="font:700 var(--fs-2xs) var(--mono);color:var(--amber);margin-left:auto">LB${Math.max(0, Number(card.lb || 0))} \u00b7 Lv${esc(String(card.level || ''))}</span></div>
        <div style="font:700 var(--fs-sm) var(--cond);letter-spacing:.03em;color:var(--ink);margin-bottom:5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(card.name || '?')}</div>
        <div style="display:flex;flex-wrap:wrap;gap:3px">${eff || '<span style="font:500 var(--fs-2xs) var(--mono);color:var(--dim)">no bonuses at this level</span>'}</div>
      </div>`;
    }).join('');
    const typeChips = Object.keys(bd.type_counts || {}).sort().map((t) => `<span style="display:inline-flex;align-items:center;gap:3px">${typeChip(t)}<span style="font:700 var(--fs-2xs) var(--mono);color:var(--label)">\u00d7${bd.type_counts[t]}</span></span>`).join('');
    const tline = p.trainee_name ? `Scored against ${esc(p.trainee_name)} (${esc(bd.primary_growth_type || 'mixed')}-leaning)` : 'Select a trainee to refine the type-match score.';
    return `<div style="display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:8px">
        <div style="font:800 var(--fs-base) var(--cond);letter-spacing:.1em;color:var(--ink)">${esc((deck.name || 'Deck').toUpperCase())} <span style="font:600 var(--fs-2xs) var(--mono);color:var(--label)">SLOT ${esc(String(deck.id ?? '?'))}</span></div>
        <div style="display:flex;align-items:center;gap:8px">${scoreBadge(score)}<span style="font:700 var(--fs-xs) var(--cond);letter-spacing:.08em;color:${scoreColor(score)}">${esc(verdict.toUpperCase())}</span></div>
      </div>
      <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:6px">${typeChips}</div>
      <div style="font:500 var(--fs-xs) var(--mono);color:var(--dim);margin-bottom:9px">${tline}</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px">${cards}</div>
      <div style="font:500 var(--fs-2xs) var(--mono);color:var(--label);margin-top:9px;padding-top:8px;border-top:1px solid var(--line-card)">Total LB ${esc(String(bd.total_lb ?? '?'))} \u00b7 Type match ${(Number(bd.type_match || 0) * 100).toFixed(0)}% \u00b7 Bonus ${(Number(bd.effect_strength || 0) * 100).toFixed(0)}% \u00b7 LB density ${(Number(bd.lb_density || 0) * 100).toFixed(0)}%</div>`;
  }
  let _deckTip = null, _deckReq = 0;
  const _deckCache = new Map();
  function ensureDeckTip() {
    if (_deckTip) return _deckTip;
    _deckTip = document.createElement('div');
    _deckTip.style.cssText = 'position:fixed;z-index:9000;display:none;width:460px;max-width:94vw;background:#0b0d12;border:1px solid var(--line);border-radius:10px;box-shadow:0 18px 50px rgba(0,0,0,.6);padding:14px;pointer-events:none';
    document.body.appendChild(_deckTip);
    return _deckTip;
  }
  function placeDeckTip(x, y) {
    const t = _deckTip, w = t.offsetWidth, h = t.offsetHeight;
    let nx = x + 18, ny = y + 18;
    if (nx + w > window.innerWidth - 8) nx = x - w - 18;
    if (nx < 8) nx = 8;
    if (ny + h > window.innerHeight - 8) ny = window.innerHeight - h - 8;
    if (ny < 8) ny = 8;
    t.style.left = nx + 'px'; t.style.top = ny + 'px';
  }
  async function showDeckTip(deck, x, y) {
    const t = ensureDeckTip();
    const key = String(deck.id);
    t.style.display = 'block';
    if (_deckCache.has(key)) { t.innerHTML = deckTooltipHtml(deck, _deckCache.get(key)); placeDeckTip(x, y); return; }
    t.innerHTML = `<div style="font:600 var(--fs-sm) var(--mono);color:var(--dim);padding:4px 2px">Scoring ${esc(deck.name || 'deck')}\u2026</div>`;
    placeDeckTip(x, y);
    const req = ++_deckReq;
    let payload = null;
    try { payload = await fetchDeckInfo(deck); } catch (e) { payload = { success: false, detail: 'Could not load deck details.' }; }
    if (req !== _deckReq) return;
    _deckCache.set(key, payload);
    if (t.style.display === 'block') { t.innerHTML = deckTooltipHtml(deck, payload); placeDeckTip(x, y); }
  }
  function wireDeckHover() {
    if (document._deckWired) return;
    document._deckWired = true;
    document.addEventListener('mouseover', (e) => {
      const el = e.target.closest && e.target.closest('[data-deck-hover]');
      if (!el) return;
      const d = (lists().decks || []).find((x) => String(x.id) === el.dataset.deckHover);
      if (d) showDeckTip(d, e.clientX, e.clientY);
    });
    document.addEventListener('mousemove', (e) => { if (_deckTip && _deckTip.style.display === 'block') placeDeckTip(e.clientX, e.clientY); });
    document.addEventListener('mouseout', (e) => {
      const el = e.target.closest && e.target.closest('[data-deck-hover]');
      if (!el) return;
      const to = e.relatedTarget;
      if (to && to.closest && to.closest('[data-deck-hover]') === el) return;
      if (_deckTip) _deckTip.style.display = 'none';
    });
  }
  // The always-visible "Deck Bonuses" panel above the deck list.
  function deckBonusesHtml(p) {
    const totals = {}, units = {};
    (p.cards || []).forEach((card) => (card.effects_ordered || []).forEach((e) => {
      if (!e || !e.label) return;
      totals[e.label] = (totals[e.label] || 0) + Number(e.value || 0);
      if (e.unit) units[e.label] = e.unit;
    }));
    const entries = Object.keys(totals).map((label) => ({ label, value: totals[label], unit: units[label] || '' })).filter((x) => x.value).sort((a, b) => b.value - a.value);
    const rows = entries.length ? entries.map((x) => `<div style="display:flex;align-items:center;justify-content:space-between;gap:8px;padding:6px 9px;border-radius:5px;background:var(--card);border:1px solid var(--line-card)"><span style="font:600 var(--fs-xs) var(--cond);letter-spacing:.04em;color:var(--ink-2)">${esc(x.label)}</span><span style="font:800 var(--fs-md) var(--mono);color:var(--amber)">${x.value > 0 ? '+' : ''}${esc(String(x.value))}${esc(x.unit)}</span></div>`).join('') : '<div style="font:500 var(--fs-sm) var(--mono);color:var(--dim)">No combined bonuses at the current card levels.</div>';
    const bd = p.deck_breakdown || {};
    const typeChips = Object.keys(bd.type_counts || {}).sort().map((t) => `<span style="display:inline-flex;align-items:center;gap:3px">${typeChip(t)}<span style="font:700 var(--fs-2xs) var(--mono);color:var(--label)">\u00d7${bd.type_counts[t]}</span></span>`).join('');
    const score = Number(p.deck_score || 0), verdict = String(p.deck_verdict || '');
    return `<div style="display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:11px">
        <div style="display:flex;align-items:center;gap:9px">${scoreBadge(score, true)}<span style="font:700 var(--fs-sm) var(--cond);letter-spacing:.06em;color:${scoreColor(score)}">${esc(verdict.toUpperCase())}</span></div>
        <div style="display:flex;flex-wrap:wrap;gap:7px">${typeChips}</div>
      </div>
      <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:7px">${rows}</div>
      ${p.trainee_name ? `<div style="font:500 var(--fs-xs) var(--mono);color:var(--dim);margin-top:9px">Scored vs ${esc(p.trainee_name)} \u00b7 combined effect values across the deck at each card's current limit-break.</div>` : '<div style="font:500 var(--fs-xs) var(--mono);color:var(--dim);margin-top:9px">Combined effect values across the deck at each card\'s current limit-break.</div>'}`;
  }
  async function renderDeckBonusesPanel() {
    const el = $('deck-bonuses-body');
    if (!el) return;
    const deck = sel.deck;
    if (!deck || !Array.isArray(deck.cards) || !deck.cards.length) { el.innerHTML = '<div style="font:500 var(--fs-sm) var(--mono);color:var(--dim)">Select a deck below to see its combined bonuses.</div>'; return; }
    el.innerHTML = '<div style="font:600 var(--fs-sm) var(--mono);color:var(--dim)">Computing combined bonuses\u2026</div>';
    const reqDeck = deck;
    try {
      const payload = _deckCache.get(String(deck.id)) || await fetchDeckInfo(deck);
      _deckCache.set(String(deck.id), payload);
      if (sel.deck !== reqDeck) return;
      el.innerHTML = (payload && payload.success) ? deckBonusesHtml(payload) : `<div style="font:500 var(--fs-sm) var(--mono);color:var(--dim)">${esc((payload && payload.detail) || 'Master data not loaded \u2014 run a master data sync.')}</div>`;
    } catch (e) { if (sel.deck === reqDeck) el.innerHTML = '<div style="font:500 var(--fs-sm) var(--mono);color:var(--dim)">Could not load deck bonuses.</div>'; }
  }

  function renderLibBody(q) {
    const host = $('setup-libbody');
    if (!host) return;
    const L = lists();
    const match = (name) => !q || String(name || '').toLowerCase().includes(q);

    // server up but no session yet → user hasn't logged into the game
    if (!online && serverUp) {
      host.innerHTML = `<div style="border:1px solid var(--line-card);border-radius:6px;background:var(--card);padding:26px 22px;text-align:center">
        <div style="font:700 var(--fs-lg) var(--cond);letter-spacing:.14em;color:var(--amber);margin-bottom:8px">NOT LOGGED IN</div>
        <div style="font:500 var(--fs-md)/1.7 var(--mono);color:var(--mut);max-width:440px;margin:0 auto">No account session yet. Complete the in-game login (the bot console is waiting for you to enter the game menu). Once you're in, your trainees, parents, decks, and cards load here automatically.</div>
      </div>`;
      return;
    }

    // backend unreachable → offline state (no simulated catalog)
    if (!online) {
      host.innerHTML = `<div style="border:1px solid var(--line-card);border-radius:6px;background:var(--card);padding:26px 22px;text-align:center">
        <div style="font:700 var(--fs-lg) var(--cond);letter-spacing:.14em;color:var(--amber);margin-bottom:8px">OFFLINE</div>
        <div style="font:500 var(--fs-md)/1.7 var(--mono);color:var(--mut);max-width:440px;margin:0 auto">Backend not reached. Run <code>python main.py</code> and reload — your ${esc(libTab)} load here from your account once the server is up and you're in the game.</div>
      </div>`;
      return;
    }

    if (libTab === 'trainees') {
      const items = L.trainees.filter((u) => match(u.name));
      host.innerHTML = items.length ? grid(items.map((u) => gridCard({
        imgId: u.id, name: u.name, selected: sel.trainee && String(sel.trainee.id) === String(u.id),
        art: true, h: 150,   // full standing illustration in the trainee picker
        attrs: `data-pick="trainee" data-id="${esc(String(u.id))}"`,
      })).join('')) : emptyTab('No trainees found in your account.');
    } else if (libTab === 'parents') {
      const all = L.parents.filter((p) => match(p.name));
      host.innerHTML = pfBarHtml() + '<div id="pf-grid"></div>';
      pfWire(all);
      pfRenderGrid(all);
    } else if (libTab === 'guests') {
      if (online && guestsState === 'idle') { host.innerHTML = loadPanel('Guest / followed parents load from your follow list, separately from your own parents.'); return; }
      if (guestsState === 'loading') { host.innerHTML = emptyTab('Loading guest parents…'); return; }
      const items = favFirst(L.guests.filter((p) => match(p.name)), 'guests');
      SPARK_ITEMS = items;
      host.innerHTML = items.length ? grid(items.map((p, i) => gridCard({ imgId: p.card_id, name: p.name, badge: RANK[p.rank], kicker: 'ID ' + (p.instance_id || '?'),
        selected: (sel.guestParents || []).some((g) => Number(g.instance_id) === Number(p.instance_id)),
        favIid: p.instance_id, favKind: 'guests', isFav: FAV.guests.has(String(p.instance_id)),
        attrs: `data-pick="guest" data-iid="${esc(String(p.instance_id))}" data-spark="${i}"` })).join(''))
        : refreshPanel(guestsState === 'error' ? (data._guestErr || 'Guest parent load failed.') : 'No guest parents found on your follow list.');
    } else if (libTab === 'decks') {
      const items = L.decks;
      const panel = `<div style="border:1px solid var(--line);border-radius:9px;background:var(--bar);padding:14px 15px;margin-bottom:14px">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">
          <span style="font:800 var(--fs-sm) var(--cond);letter-spacing:.2em;color:var(--amber)">DECK BONUSES</span>
          <div style="display:flex;gap:7px">
            <button class="abtn" type="button" data-modal="recSupports" style="font-size:var(--fs-xs);padding:6px 11px">RECOMMENDED</button>
            <button class="abtn" type="button" data-modal="customDeck" style="font-size:var(--fs-xs);padding:6px 11px">BUILD DECK</button>
          </div>
        </div>
        <div id="deck-bonuses-body"></div>
      </div>`;
      host.innerHTML = items.length ? (panel + items.map((d) => {
        const on = sel.deck && Number(sel.deck.id) === Number(d.id);
        const cards = (d.cards || []).map((c) => gridCard({ imgId: c.id, name: c.name, kicker: `${c.type || '?'} | ${c.rarity || '?'}`, rarity: c.rarity, h: 64 })).join('');
        return `<div data-pick="deck" data-id="${esc(String(d.id))}" data-deck-hover="${esc(String(d.id))}" style="border:1px solid ${on ? 'var(--amber)' : 'var(--line-card)'};border-radius:6px;padding:11px;margin-bottom:12px;cursor:pointer;background:${on ? '#15120a' : 'var(--card)'}">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:9px"><span style="font:700 var(--fs-md) var(--cond);letter-spacing:.12em;color:${on ? 'var(--amber)' : 'var(--ink)'}">${esc((d.name || 'Deck').toUpperCase())}</span><span style="font:500 var(--fs-xs) var(--mono);color:var(--label)">SLOT ${esc(String(d.id))}${on ? ' · SELECTED' : ''}</span></div>
          ${grid(cards, 6)}</div>`;
      }).join('')) : emptyTab('No decks loaded from your account.');
      if (items.length) { renderDeckBonusesPanel(); wireDeckHover(); }
    } else if (libTab === 'friends') {
      if (online && friendsState === 'idle') { host.innerHTML = loadPanel('Friend support cards load from the game on demand (and are blocked while a career is running).'); return; }
      if (friendsState === 'loading') { host.innerHTML = emptyTab('Loading friend supports…'); return; }
      const items = L.friends.filter((f) => match(f.name));
      host.innerHTML = items.length ? grid(items.map((f) => {
        const id = String(f.support_card_id || f.card_id || f.id || '');
        const lb = (f.limit_break_count ?? f.lb);
        const key = friendKey(f);
        return gridCard({ imgId: id, name: f.support_name || f.name || ('Friend ' + (f.viewer_id || '')), kicker: String(f.type || '?').toUpperCase(), rarity: f.rarity, star: true, lb: (lb ?? ''), isSupport: true,
          selected: sel.friend && friendKey(sel.friend) === key,
          attrs: `data-pick="friend" data-id="${esc(key)}"` });
      }).join('')) : refreshPanel(friendsState === 'error' ? (data._friendErr || 'Friend load failed.') : 'No friend supports found (the endpoint is blocked during an active career).');
    } else if (libTab === 'cards') {
      const items = L.cards.filter((c) => match(c.name));
      host.innerHTML = items.length ? grid(items.map((c) => gridCard({ imgId: c.id, name: c.name, kicker: String(c.type || '?').toUpperCase(), rarity: c.rarity, star: true, h: 64, lb: (c.limit_break ?? c.limit_break_count ?? ''), isSupport: true })).join(''), 6) : emptyTab('No owned cards found.');
    }
  }

  // Parse a race's "Junior Year Late Jun" date string into a grid cell coordinate.
  function parseRaceDate(date) {
    const s = String(date || '');
    const ym = s.match(/(Junior|Classic|Senior)/i);
    const half = /\bLate\b/i.test(s) ? 1 : (/\bEarly\b/i.test(s) ? 0 : -1);
    const mm = s.match(/\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b/i);
    if (!ym || half < 0 || !mm) return null;
    return { yearKey: ym[1].toUpperCase() + ' YEAR', mi: (MONTH_NUM[mm[1].toUpperCase()] - 1) * 2 + half };
  }
  function buildRaceCells(cal) {
    const out = {};
    (cal || []).forEach((r) => {
      const p = parseRaceDate(r.date);
      if (!p) return;
      (out[p.yearKey] = out[p.yearKey] || {});
      (out[p.yearKey][p.mi] = out[p.yearKey][p.mi] || []).push(r);
    });
    const pri = { G1: 4, G2: 3, G3: 2, OP: 1 };
    Object.values(out).forEach((mo) => Object.entries(mo).forEach(([mi, arr]) => {
      arr.sort((a, b) => (pri[b.grade] || 0) - (pri[a.grade] || 0));
      // BUG #2: a single race recurs under several program_ids at the same turn
      // (e.g. Late December shows Arima Kinen 4x). Collapse to ONE entry per race
      // name — keep the highest-graded (already sorted first).
      const seen = new Set();
      mo[mi] = arr.filter((r) => { const k = String(r.name || r.id).toLowerCase(); if (seen.has(k)) return false; seen.add(k); return true; });
    }));
    return out;
  }
  // Persist the current race selection + mode onto the active preset.
  async function saveRaces(source) {
    if (!online) return;
    try {
      await api('/api/presets/save_races', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ races: [...selectedRaceIds], source }),
      });
    } catch (e) { /* best effort */ }
  }
  function applyModeButtons() {
    const bs = $('tb-mode-smart'), bm = $('tb-mode-manual');
    if (bs) bs.classList.toggle('amber', raceMode === 'smart');
    if (bm) bm.classList.toggle('amber', raceMode === 'manual');
    const meta = $('setup-sched-meta'); if (meta) meta.textContent = raceMode === 'manual' ? 'manual selection — click a box' : 'smart race solver';
  }
  function setRaceMode(m) {
    raceMode = (m === 'manual') ? 'manual' : 'smart';
    applyModeButtons();
    renderSchedule();
    saveRaces(raceMode);
  }
  function setShowOP(v) {
    showOP = !!v;
    try { localStorage.setItem('icarus_show_op', showOP ? '1' : '0'); } catch (e) {}
    const b = $('tb-op-toggle'); if (b) b.classList.toggle('amber', showOP);
    renderSchedule();
  }
  // Selected races for a turn-cell, in pick order (insertion order of the Set):
  // index 0 = MAIN race, 1+ = RIVAL OVERWRITES (run when the rival appears).
  // A race is selected if its precise per-occurrence id (occ) OR its bare
  // program_id (legacy presets / smart mode) is in the set. Returned in selection
  // order (first = MAIN, rest = rival overwrites).
  function cellSelected(yr, mi) {
    const races = (raceByCell[yr] && raceByCell[yr][mi]) || [];
    const byKey = new Map();
    races.forEach((r) => { byKey.set(r.occ, r); byKey.set(r.id, r); });
    const out = [];
    selectedRaceIds.forEach((k) => { const r = byKey.get(k); if (r && !out.includes(r)) out.push(r); });
    return out;
  }
  // Toggle a race in a turn-cell. Trackblazer allows MULTIPLE per turn: the first
  // picked is the MAIN race, extras are RIVAL OVERWRITES. Picking by hand flips the
  // schedule to manual mode.
  function toggleRaceInCell(occStr, key) {
    if (!online) return;
    const occ = Number(occStr);
    if (!occ) return;
    const parts = String(key).split('|');
    const cell = (raceByCell[parts[0]] && raceByCell[parts[0]][+parts[1]]) || [];
    const r = cell.find((x) => x.occ === occ) || cell.find((x) => x.id === occ);
    if (!r) return;
    // BUG #1: key by per-occurrence id so picking a recurring race in one year
    // does NOT toggle the other year. Toggle-off clears occ- AND pid-based keys
    // (a pid key may be present from an old preset or a smart plan).
    if (selectedRaceIds.has(r.occ) || selectedRaceIds.has(r.id)) {
      selectedRaceIds.delete(r.occ); selectedRaceIds.delete(r.id);
    } else {
      selectedRaceIds.add(r.occ);   // insertion order = main-first per cell
    }
    if (raceMode !== 'manual') { raceMode = 'manual'; applyModeButtons(); }
    renderSchedule();
    saveRaces('manual');
  }
  function clearCell(key) {
    const parts = String(key).split('|');
    const cell = (raceByCell[parts[0]] && raceByCell[parts[0]][+parts[1]]) || [];
    cell.forEach((r) => { selectedRaceIds.delete(r.occ); selectedRaceIds.delete(r.id); });
    if (raceMode !== 'manual') { raceMode = 'manual'; applyModeButtons(); }
    renderSchedule();
    saveRaces('manual');
  }
  // Modal popup listing a turn-cell's races. Multi-select: first pick = MAIN, extras
  // = RIVAL OVERWRITE 1/2… The bot runs a rival-overwrite race when the game presents
  // that rival on the turn; otherwise it runs the main. Stays open so you can stack
  // overwrites; shows ALL races (incl. hidden OP) so rivals are always pickable.
  function openRacePicker(key) {
    if (!online) return;
    const parts = String(key).split('|');
    const yr = parts[0], mi = +parts[1];
    const races = (raceByCell[yr] && raceByCell[yr][mi]) || [];
    if (!races.length) return;
    const monthLbl = MONTHS[mi] || '';
    const fmt = (n) => (I.fmtCompact ? I.fmtCompact(n) : String(n));
    function rowsHtml() {
      const sel = cellSelected(yr, mi);   // race objects, main-first
      return races.map((r) => {
        const idx = sel.indexOf(r);
        const on = idx >= 0;
        const col = gradeColor[r.grade] || 'cyan';
        const meta = [r.distance, r.fans ? (fmt(r.fans) + ' fans') : ''].filter(Boolean).join(' · ');
        const badge = !on ? ''
          : (idx === 0
            ? '<span style="flex-shrink:0;font:800 var(--fs-2xs) var(--cond);letter-spacing:.1em;color:#06121a;background:var(--amber);padding:2px 6px;border-radius:3px">MAIN</span>'
            : `<span style="flex-shrink:0;font:800 var(--fs-2xs) var(--cond);letter-spacing:.08em;color:var(--amber);background:rgba(242,169,0,.16);border:1px solid var(--amber-bd);padding:1px 5px;border-radius:3px">RIVAL OVERWRITE ${idx}</span>`);
        return `<button type="button" class="race-pick-row" data-pick-occ="${r.occ}" data-pick-key="${esc(key)}"
          style="display:flex;align-items:center;gap:10px;width:100%;text-align:left;padding:8px 12px;border:1px solid ${on ? 'var(--amber)' : 'var(--line-card)'};background:${on ? 'rgba(242,169,0,.14)' : 'var(--card)'};border-radius:6px;margin-bottom:7px;cursor:pointer">
          <img src="/races/${encodeURIComponent(r.name)}.png" alt="" style="flex-shrink:0;width:84px;height:30px;object-fit:cover;border-radius:4px;border:1px solid var(--line-card)" onerror="this.style.display='none'">
          <span style="flex-shrink:0;font:800 var(--fs-xs) var(--mono);color:#fff;background:var(--${col});padding:2px 6px;border-radius:4px">${esc(r.grade)}</span>
          <span style="flex:1;min-width:0;font:700 var(--fs-base) var(--cond);letter-spacing:.02em;color:${on ? 'var(--amber)' : 'var(--ink)'};overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(r.name)}</span>
          <span style="flex-shrink:0;font:500 var(--fs-sm) var(--mono);color:var(--label)">${esc(meta)}</span>
          ${badge}
        </button>`;
      }).join('');
    }
    const body = `<div style="font:500 var(--fs-sm)/1.5 var(--mono);color:var(--dim);margin-bottom:12px">First pick = <b style="color:var(--amber)">MAIN</b> race. Add more as <b style="color:var(--amber)">RIVAL OVERWRITES</b> — the bot runs a rival-overwrite race when that rival challenges you this turn, otherwise the main. Click again to remove.</div>
      <div id="rp-rows">${rowsHtml()}</div>
      <button type="button" id="rp-clear" style="display:flex;align-items:center;justify-content:center;width:100%;padding:9px;border:1px dashed var(--line-card);background:none;border-radius:6px;margin-top:4px;cursor:pointer;font:600 var(--fs-sm) var(--cond);letter-spacing:.14em;color:var(--label)">CLEAR THIS TURN</button>`;
    I.modal({
      title: 'PICK RACES', sub: `${monthLbl} · ${yr}`, body,
      onMount: (ov) => {
        const host = ov.querySelector('#rp-rows');
        if (host) host.addEventListener('click', (e) => {
          const b = e.target.closest('.race-pick-row');
          if (!b) return;
          toggleRaceInCell(b.dataset.pickOcc, b.dataset.pickKey);
          host.innerHTML = rowsHtml();   // stay open; refresh badges
        });
        const clr = ov.querySelector('#rp-clear');
        if (clr) clr.addEventListener('click', () => { clearCell(key); if (host) host.innerHTML = rowsHtml(); });
      },
    });
  }
  // Schedule: one selected-race icon per turn-cell (clean, uncluttered). Every cell
  // with available races is clickable → openRacePicker. A new preset has no saved
  // races, so every cell shows the empty "+" state.
  function renderSchedule() {
    const host = $('setup-schedule');
    if (!host) return;
    host.innerHTML = RACE_YEARS.map((yr) => {
      const cells = MONTHS.map((m, i) => {
        const all = (raceByCell[yr] && raceByCell[yr][i]) || [];
        const races = all.filter((r) => showOP || r.grade !== 'OP' || selectedRaceIds.has(r.occ) || selectedRaceIds.has(r.id));
        const key = yr + '|' + i;
        const monthLbl = `<span style="font:700 var(--fs-xs) var(--cond);letter-spacing:.08em;color:var(--mut)">${esc(m)}</span>`;
        const sel = cellSelected(yr, i);   // [main, ...rival overwrites]
        const selected = sel[0];
        const overwrites = sel.length - 1;
        const clickable = races.length > 0;
        const cur = clickable ? 'pointer' : 'default';
        const attrs = clickable ? `data-race-cell="${esc(key)}" role="button" tabindex="0"` : '';
        let box;
        if (selected) {
          // Real race banner image (like the old UI) + a SCHEDULED ribbon; falls
          // back to a grade-tinted plate + grade chip if the banner is missing.
          const col = gradeColor[selected.grade] || 'cyan';
          box = `<div ${attrs} title="${esc(selected.name)} · ${esc(selected.grade)} · ${esc(selected.distance)} — click to change"
            style="position:relative;min-height:46px;border-radius:8px;border:1px solid var(--amber);overflow:hidden;cursor:${cur}">
            <img src="/races/${encodeURIComponent(selected.name)}.png" alt="" style="width:100%;height:46px;object-fit:cover;display:block"
              onerror="this.style.display='none';this.parentElement.style.background='rgba(242,169,0,.13)';this.nextElementSibling.style.display='block'">
            <span style="display:none;position:absolute;top:5px;left:5px;font:800 var(--fs-2xs) var(--mono);color:#fff;background:var(--${col});padding:1px 4px;border-radius:3px">${esc(selected.grade)}</span>
            ${overwrites > 0 ? `<span title="${overwrites} rival overwrite${overwrites === 1 ? '' : 's'}" style="position:absolute;top:4px;right:4px;font:800 var(--fs-2xs) var(--cond);letter-spacing:.06em;color:#06121a;background:var(--amber);padding:1px 5px;border-radius:3px;box-shadow:0 1px 2px rgba(0,0,0,.5)">RIVAL +${overwrites}</span>` : ''}
            <span style="position:absolute;left:0;right:0;bottom:0;text-align:center;font:800 var(--fs-2xs) var(--cond);letter-spacing:.12em;color:#06121a;background:var(--amber);padding:1px 0">SCHEDULED</span>
          </div>`;
        } else if (clickable) {
          box = `<div ${attrs} title="${races.length} race${races.length === 1 ? '' : 's'} available — click to pick"
            style="min-height:46px;border-radius:8px;border:1px dashed var(--line-card);background:var(--card);display:flex;align-items:center;justify-content:center;cursor:${cur}">
            <span style="color:var(--green);font:700 var(--fs-5xl) var(--sans);line-height:1">+</span>
          </div>`;
        } else {
          box = `<div style="min-height:46px;border-radius:8px;border:1px dashed var(--line-card);background:#0f1217;display:flex;align-items:center;justify-content:center;opacity:.45"><span style="color:#43506a;font:700 var(--fs-2xl) var(--sans);line-height:1">·</span></div>`;
        }
        return `<div style="display:flex;flex-direction:column;gap:5px">${box}${monthLbl}</div>`;
      }).join('');
      return `<div style="text-align:center;font:700 var(--fs-sm) var(--cond);letter-spacing:.22em;color:var(--amber);background:linear-gradient(#15120a,#0e0c08);border:1px solid var(--amber-dk);border-radius:4px;padding:8px;margin:0 0 10px">${yr}</div>
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:16px">${cells}</div>`;
    }).join('');
  }

  function wireGlobalClicks() {
    document.addEventListener('click', (e) => {
      const ld = e.target.closest('[data-load]');
      if (ld) { const force = ld.dataset.force === '1'; if (ld.dataset.load === 'friends') loadFriends(force); else loadGuests(force); return; }
      const m = e.target.closest('[data-modal]');
      if (m && I.Modals && I.Modals[m.dataset.modal]) { I.Modals[m.dataset.modal](); return; }
      const rc = e.target.closest('[data-race-cell]');
      if (rc) { openRacePicker(rc.dataset.raceCell); return; }
      // Favorite toggle (parents/guests) — handled before data-pick so toggling a
      // favorite never also selects/deselects the parent.
      const fav = e.target.closest('[data-fav-iid]');
      if (fav) { e.stopPropagation(); toggleFav(fav.dataset.favKind, fav.dataset.favIid); renderLibBody(); return; }
      const pick = e.target.closest('[data-pick]');
      if (!pick || !online) return;
      const L = lists();
      const kind = pick.dataset.pick;
      if (kind === 'trainee') { const u = L.trainees.find((x) => String(x.id) === pick.dataset.id); if (u) selectTrainee(u); }
      else if (kind === 'parent') { const p = L.parents.find((x) => String(x.instance_id) === pick.dataset.iid); if (p) toggleVeteran(p); }
      else if (kind === 'guest') { const p = L.guests.find((x) => String(x.instance_id) === pick.dataset.iid); if (p) toggleGuest(p); }
      else if (kind === 'deck') { const d = L.decks.find((x) => String(x.id) === pick.dataset.id); if (d) selectDeck(d); }
      else if (kind === 'friend') { const f = L.friends.find((x) => friendKey(x) === pick.dataset.id); if (f) selectFriend(f); }
    });
    // keyboard: Enter/Space on a focused race cell opens its picker
    document.addEventListener('keydown', (e) => {
      if (e.key !== 'Enter' && e.key !== ' ') return;
      const rc = e.target.closest && e.target.closest('[data-race-cell]');
      if (rc) { e.preventDefault(); openRacePicker(rc.dataset.raceCell); }
    });
  }

  async function boot() {
    I.mountChrome();
    wireGlobalClicks();
    const [sess, pres] = await Promise.all([api('/api/session'), api('/api/settings-presets')]);
    serverUp = !I.isMock;
    online = !I.isMock && sess && sess.success === true && Array.isArray(sess.umas);
    if (online) {
      data = sess;
      if (sess.selection) applyServerSelection(sess.selection);
      applyActiveCareerParents();   // a live in-progress career's parents override the saved picks
    }
    if (pres && Array.isArray(pres.presets) && pres.presets.length) presets = pres.presets.map((p) => p.name || p);
    // Keep the dropdown on the backend's ACTIVE preset (was defaulting to the first
    // option, so loading a preset looked like it reverted to default).
    activePreset = (pres && pres.active) ? pres.active : (presets[0] || '');
    // Race calendar + the active preset's saved race selection (per-preset schedule).
    if (online) {
      try {
        const [rc, sc] = await Promise.all([api('/api/trackblazer/races'), api('/api/smart-solver/config')]);
        if (rc && rc.success && Array.isArray(rc.races)) raceByCell = buildRaceCells(rc.races);
        selectedRaceIds.clear();
        ((sc && sc.config && sc.config.extra_race_list) || []).forEach((id) => selectedRaceIds.add(Number(id)));
        raceMode = (sc && sc.source === 'manual') ? 'manual' : 'smart';
      } catch (e) { /* schedule stays empty until the server is reachable */ }
    }
    renderSlots();
    renderControls();
    renderLibrary();
    // races_cache count, if present on the session payload
    if (online && data.counts && data.counts.races != null) {
      const cell = document.querySelector('#setup-tb-stats');
      if (cell) cell.lastElementChild.innerHTML = `<span class="c-mut">races_cache</span><span style="color:var(--ink-2)">${data.counts.races}</span>`;
    }
  }
  // Allow other modules (the Build Custom Deck modal) to push a selection into
  // the live Setup state and re-render immediately after persisting it.
  I.applyExternalSelection = (s) => {
    if (!s) return;
    applyServerSelection(s);
    renderSlots();
    if (typeof renderLibBody === 'function') renderLibBody();
  };
  boot();
})();
