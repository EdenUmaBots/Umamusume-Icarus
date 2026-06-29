/* Event Choices — fetches /api/events, renders the catalog + override editor.
   Forcing a choice POSTs /api/events/override {story_id, choice:<0-based index>};
   AUTO posts choice:-1; CLEAR ALL posts /api/events/overrides/clear.

   Mirrors the WORKING old-UI contract (public/app.js): the backend returns
   {success, events:[{story_id, event_name, category:'story'|'support_card',
   support_card_id, num_choices, choice_select_indices[], count, override:int|null,
   outcomes:{<select_index>:effectText}}]}. The override int is the 0-based CHOICE
   POSITION, not the game select_index. */
(() => {
  'use strict';
  const I = window.Icarus;
  const { api, esc } = I;
  const $ = (id) => document.getElementById(id);

  let events = [];
  let cat = 'Story';            // tab: 'Story' | 'Support' | 'Scenario'
  let activeId = null;

  const isSupport = (e) => !!(e && (e.category === 'support_card' || Number(e.support_card_id || 0) > 0));
  // Tab → predicate. The backend has no 'scenario' category, so that tab is empty.
  const inTab = (e) => cat === 'Support' ? isSupport(e) : cat === 'Story' ? !isSupport(e) : false;
  const evName = (e) => e.event_name || e.story_id || '(unnamed event)';
  const catLabel = (e) => isSupport(e) ? 'Support card' : 'Story';
  const catBadge = (e) => isSupport(e) ? 'bg-cyan' : 'bg-amber';

  // Effect text for the i-th choice (mirror of old UI eventChoiceEffect): the
  // game's select_index for position i is choice_select_indices[i] when present,
  // else i+1; outcomes are keyed by that select_index.
  function choiceEffect(e, i) {
    const out = (e && e.outcomes) || {};
    const idxList = Array.isArray(e && e.choice_select_indices) ? e.choice_select_indices : null;
    const sel = idxList && i < idxList.length ? Number(idxList[i]) : (i + 1);
    return String(out[String(sel)] ?? out[sel] ?? out[String(i + 1)] ?? out[i + 1] ?? '').trim();
  }
  function effTone(effect) {
    const s = String(effect || '').toLowerCase();
    if (s === 'bad' || /(^|[\s,])-\d|energy -|motivation -/.test(s)) return 'red';
    if (s === 'good' || /\+\d/.test(s)) return 'green';
    return 'mut';
  }
  function choicesOf(e) {
    const n = Math.max(0, Number(e.num_choices || 0));
    const out = [];
    const forced = e.override != null ? Number(e.override) : null;
    for (let i = 0; i < n; i++) {
      const eff = choiceEffect(e, i);
      out.push({ i, label: 'Choice ' + (i + 1), effect: eff, tone: effTone(eff), chosen: forced === i });
    }
    return out;
  }
  const isForced = (e) => e.override != null;
  function seenChoiceText(e) {
    if (e.override == null) return 'Auto';
    return 'Choice ' + (Number(e.override) + 1);
  }

  function visible() {
    const q = ($('ev-search').value || '').toLowerCase();
    return events.filter((e) => inTab(e) &&
      (!q || evName(e).toLowerCase().includes(q) || String(e.story_id).toLowerCase().includes(q)
        || String(e.source_name || '').toLowerCase().includes(q)));
  }

  function renderList() {
    const host = $('ev-list');
    const list = visible();
    if (!list.some((e) => e.story_id === activeId)) activeId = list.length ? list[0].story_id : null;
    host.innerHTML = '';
    if (!list.length) {
      host.innerHTML = '<div class="mon-empty" style="padding:18px">No events in this tab.</div>';
      return;
    }
    list.forEach((e, n) => {
      const row = document.createElement('div');
      const isActive = e.story_id === activeId;
      row.className = 'trow';
      row.style.cssText = 'grid-template-columns:64px 1fr 130px 110px;cursor:pointer;border-top:1px solid var(--line-row)' +
        (isActive ? ';background:#0d0b06;border-left:2px solid var(--amber)' : '') + ((e.count || 0) === 0 ? ';opacity:.7' : '');
      const mode = isForced(e)
        ? '<span class="tagbadge bg-amber">FORCED</span>'
        : '<span class="fbtn">AUTO</span>';
      row.innerHTML = `
        <span style="font:700 var(--fs-md) var(--mono);color:${isActive ? 'var(--amber)' : 'var(--ink-3)'}">${n + 1}</span>
        <div><div style="font:600 var(--fs-base) var(--mono);color:var(--ink-2);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(evName(e))}</div>
        <div style="font:500 var(--fs-xs) var(--mono);color:var(--label);margin-top:2px">${esc(catLabel(e))}${e.count ? ' · seen ' + e.count + '×' : ''}</div></div>
        <span style="font:500 var(--fs-sm) var(--mono);color:${isForced(e) ? 'var(--green)' : 'var(--label)'}">${esc(seenChoiceText(e))}</span>
        <span class="r">${mode}</span>`;
      row.addEventListener('click', () => { activeId = e.story_id; renderList(); renderDetail(); });
      host.appendChild(row);
    });
  }

  function renderDetail() {
    const e = events.find((x) => x.story_id === activeId);
    const host = $('ev-detail');
    if (!e) { host.innerHTML = '<p class="rcard-text is-mut">Select an event.</p>'; return; }
    const choices = choicesOf(e);
    const cards = choices.length ? choices.map((c) => {
      const eff = c.effect
        ? `<span class="chip c-${c.tone === 'mut' ? '' : c.tone}" style="border-color:${c.tone === 'green' ? 'var(--green-bd)' : c.tone === 'red' ? 'var(--red-bd)' : 'var(--line-card)'}">${esc(c.effect)}</span>`
        : '<span class="chip" style="color:var(--label)">no recorded effect</span>';
      return `
        <div class="card" style="margin-bottom:9px;${c.chosen ? 'border-color:var(--amber-dk);border-left:2px solid var(--amber);background:#0d0b06' : ''}">
          <div class="card-body">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
              <span style="font:700 var(--fs-base) var(--mono);color:${c.chosen ? 'var(--amber)' : 'var(--ink-2)'}">${esc(c.label)}</span>
              ${c.chosen ? '<span class="tagbadge bg-amber">FORCED ✓</span>' : '<button class="fbtn" data-force="' + c.i + '" type="button" style="border-color:var(--cyan-bd);color:var(--cyan)">FORCE THIS</button>'}
            </div>
            <div style="display:flex;flex-wrap:wrap;gap:6px">${eff}</div>
          </div>
        </div>`;
    }).join('') : '<p class="rcard-text is-mut">No recorded choices for this event.</p>';
    host.innerHTML = `
      <div style="display:flex;align-items:center;gap:9px;margin-bottom:5px">
        <span class="tagbadge ${catBadge(e)}" style="letter-spacing:.12em">${esc(catLabel(e).toUpperCase())}</span>
        ${e.auto_source ? `<span style="font:500 var(--fs-xs) var(--mono);color:var(--label)">src ${esc(e.auto_source)}</span>` : ''}
      </div>
      <div style="font:700 var(--fs-3xl) var(--cond);letter-spacing:.03em;color:#fff;margin-bottom:4px">${esc(evName(e))}</div>
      <div style="font:500 var(--fs-sm) var(--mono);color:var(--label);margin-bottom:16px">seen ${e.count || 0}× this profile</div>
      <div class="card-title" style="margin-bottom:10px;color:var(--label)">CHOICES</div>
      ${cards}
      <div style="border-top:1px solid var(--line);margin:16px 0 14px"></div>
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">
        <span style="font:600 var(--fs-sm) var(--cond);letter-spacing:.14em;color:var(--ink-2)">OVERRIDE MODE</span>
        <div style="display:flex;gap:6px">
          <button class="seg ${!isForced(e) ? 'is-active' : ''}" data-mode="auto" type="button">AUTO</button>
          <button class="seg ${isForced(e) ? 'is-active' : ''}" data-mode="force" type="button">FORCE</button>
        </div>
      </div>
      <div style="font:500 var(--fs-xs)/1.6 var(--mono);color:var(--label);background:var(--bar);border:1px solid var(--line);border-radius:4px;padding:10px 11px">Override is saved to the active preset and applied at the next career start. Auto lets the bot's advisor pick by current goals.</div>`;

    host.querySelectorAll('[data-force]').forEach((b) => b.addEventListener('click', () => setOverride(e, Number(b.dataset.force))));
    host.querySelectorAll('[data-mode]').forEach((b) => b.addEventListener('click', () => {
      if (b.dataset.mode === 'auto') setAuto(e); else { const c = choicesOf(e); if (c.length) setOverride(e, isForced(e) ? Number(e.override) : 0); }
    }));
  }

  async function setOverride(e, i) {
    e.override = i;                                   // 0-based choice position
    recountOverrides(); renderList(); renderDetail();
    await api('/api/events/override', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ story_id: e.story_id, choice: i }) });
  }
  async function setAuto(e) {
    e.override = null;
    recountOverrides(); renderList(); renderDetail();
    await api('/api/events/override', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ story_id: e.story_id, choice: -1 }) });
  }

  function recountOverrides() {
    const n = events.filter((e) => e.override != null).length;
    $('ev-ovr').textContent = n + ' override' + (n === 1 ? '' : 's') + ' active';
  }

  function renderCounts() {
    const story = events.filter((e) => !isSupport(e)).length;
    const support = events.filter((e) => isSupport(e)).length;
    $('ev-c-story').textContent = story;
    $('ev-c-support').textContent = support;
    $('ev-c-scenario').textContent = 0;
  }

  async function boot() {
    I.mountChrome();
    const data = await api('/api/events');
    events = (data && data.events) || (data && data.list) || [];
    renderCounts();
    recountOverrides();
    renderList(); renderDetail();

    document.querySelectorAll('.seg[data-cat]').forEach((s) => s.addEventListener('click', () => {
      document.querySelectorAll('.seg[data-cat]').forEach((x) => x.classList.remove('is-active'));
      s.classList.add('is-active');
      cat = s.dataset.cat; activeId = null; renderList(); renderDetail();
    }));
    $('ev-search').addEventListener('input', () => { activeId = null; renderList(); renderDetail(); });
    $('ev-clear').addEventListener('click', async () => {
      events.forEach((e) => { e.override = null; });
      recountOverrides(); renderList(); renderDetail();
      await api('/api/events/overrides/clear', { method: 'POST' });
    });
  }
  boot();
})();
