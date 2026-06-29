/* Pre Icarus Parent Spark Filter
   Filters existing parent and guest-parent grids without changing DOM order.
   Selection in app.js still uses original indices/data attributes, so this
   module only toggles display/CSS order and never removes nodes during
   filtering or sorting. Explicit cleanup is the only deletion path. */
(() => {
    'use strict';

    const STORE_KEY = 'sweepy_parent_filter_v1';
    const CATEGORIES = ['stat', 'aptitude', 'unique', 'skill', 'race', 'scenario'];
    const RANK_ORDER = { 'SS+': 13, 'SS': 12, 'S+': 11, 'S': 10, 'A+': 9, 'A': 8, 'B+': 7, 'B': 6, 'C+': 5, 'C': 4, 'D+': 3, 'D': 2, 'E': 1 };
    const state = { search: '', cats: [], factor: '', minStars: 0, scope: 'lineage', sort: 'none', maxAgeH: 0 };
    try { Object.assign(state, JSON.parse(localStorage.getItem(STORE_KEY) || '{}')); } catch (e) {}

    let cards = [];
    let bar = null;
    let observer = null;
    let timer = 0;

    function esc(value) {
        return String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    }
    function save() { try { localStorage.setItem(STORE_KEY, JSON.stringify(state)); } catch (e) {} }
    async function postJson(url, payload) {
        const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' }, body: JSON.stringify(payload || {}) });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
        return data;
    }

    function parseCard(el) {
        const factors = new Map();
        let totalStars = 0;
        el.querySelectorAll('.spark-node').forEach((node, nodeIdx) => {
            const isSelf = node.classList.contains('spark-node-self') || nodeIdx === 0;
            node.querySelectorAll('.factor-badge').forEach(badge => {
                const starsEl = badge.querySelector('.stars');
                const stars = starsEl ? (starsEl.textContent.match(/★/g) || []).length : 0;
                const label = badge.textContent.replace(/★/g, '').trim();
                if (!label) return;
                const key = label.toLowerCase();
                let cat = 'other';
                badge.classList.forEach(c => { if (c.startsWith('f-')) cat = c.slice(2); });
                if (!factors.has(key)) factors.set(key, { label, cat, total: 0, self: 0 });
                const row = factors.get(key);
                row.total += stars;
                if (isSelf) row.self += stars;
                totalStars += stars;
            });
        });
        const nameEl = el.querySelector('.grid-card-name');
        const rankEl = el.querySelector('.rank-badge');
        return { el, name: nameEl ? nameEl.textContent.trim() : '', rank: rankEl ? rankEl.textContent.trim() : '', factors, totalStars };
    }

    function reindex() {
        const grids = ['parent-grid', 'guest-parent-grid']
            .map(id => document.getElementById(id))
            .filter(Boolean);
        if (!grids.length) return;
        cards = grids.flatMap(grid => Array.from(grid.querySelectorAll(':scope > .grid-card')).map(parseCard));
        rebuildFactorOptions();
    }
    function factorScore(card) {
        if (!state.factor) return card.totalStars;
        const row = card.factors.get(state.factor);
        if (!row) return 0;
        return state.scope === 'self' ? row.self : row.total;
    }
    function passes(card) {
        if (state.search) {
            const q = state.search.toLowerCase();
            let hit = card.name.toLowerCase().includes(q);
            if (!hit) for (const row of card.factors.values()) if (row.label.toLowerCase().includes(q)) { hit = true; break; }
            if (!hit) return false;
        }
        if (state.cats.length) {
            let hit = false;
            for (const row of card.factors.values()) if (state.cats.includes(row.cat)) { hit = true; break; }
            if (!hit) return false;
        }
        if (state.factor && factorScore(card) < (state.minStars || 1)) return false;
        return true;
    }
    function applyAgeFilter() {
        const maxH = Number(state.maxAgeH || 0);
        const cutoff = Date.now() / 1000 - maxH * 3600;
        ['parent-grid', 'guest-parent-grid']
            .map(id => document.getElementById(id))
            .filter(Boolean)
            .forEach(grid => grid.querySelectorAll('.grid-card[data-create-date]').forEach(card => {
                if (!maxH) { card.dataset.ageHidden = '0'; return; }
                const created = Number(card.dataset.createDate || 0);
                card.dataset.ageHidden = (created > 0 && created >= cutoff) ? '0' : '1';
            }));
    }
    function apply() {
        if (!cards.length) reindex();
        applyAgeFilter();
        let shown = 0;
        cards.forEach(card => {
            const ok = card.el.dataset.ageHidden !== '1' && passes(card);
            card.el.style.display = ok ? '' : 'none';
            if (ok) shown += 1;
            let order = 0;
            if (state.sort === 'factor') order = -factorScore(card);
            else if (state.sort === 'stars') order = -card.totalStars;
            else if (state.sort === 'rank') order = -(RANK_ORDER[card.rank] || 0);
            card.el.style.order = String(order);
        });
        const count = bar && bar.querySelector('#parent-filter-count');
        if (count) count.textContent = `${shown}/${cards.length} parents`;
        updateAutodelHint();
        save();
    }
    function rebuildFactorOptions() {
        const select = bar && bar.querySelector('#parent-filter-factor');
        if (!select) return;
        const names = new Map();
        cards.forEach(card => card.factors.forEach((row, key) => { if (!names.has(key)) names.set(key, row); }));
        const current = state.factor;
        const sorted = Array.from(names.entries()).sort((a, b) => a[1].cat === b[1].cat ? a[1].label.localeCompare(b[1].label) : a[1].cat.localeCompare(b[1].cat));
        select.innerHTML = '<option value="">Any factor</option>' + sorted.map(([key, row]) => `<option value="${esc(key)}">[${esc(row.cat)}] ${esc(row.label)}</option>`).join('');
        if (current && names.has(current)) select.value = current;
        else state.factor = '';
    }
    function recentCount(maxH) {
        if (!maxH) return 0;
        const cutoff = Date.now() / 1000 - maxH * 3600;
        return cards.filter(c => Number(c.el.dataset.createDate || 0) >= cutoff).length;
    }
    function updateAutodelHint() {
        if (!bar) return;
        const hint = bar.querySelector('#parent-autodel-hint');
        const btn = bar.querySelector('#parent-autodel-btn');
        const maxH = Number(state.maxAgeH || 0);
        if (!hint || !btn) return;
        if (!maxH) { hint.textContent = 'Select age window to preview cleanup'; btn.disabled = true; return; }
        const n = recentCount(maxH);
        hint.textContent = `${n} recent parent(s) in window; selected parents are protected`;
        btn.disabled = n === 0;
    }
    async function previewAndDeleteRecentParents(maxH) {
        const preview = await postJson('/api/parents/remove-recent', { max_age_hours: maxH, dry_run: true });
        const parents = preview.parents || [];
        if (!parents.length) { alert('No deletable parents found in that age window.'); return; }
        const sample = parents.slice(0, 10).map(p => `${p.name || 'Unknown'} · ID ${p.instance_id}`).join('\n');
        const extra = parents.length > 10 ? `\n...and ${parents.length - 10} more` : '';
        if (!confirm(`Preview: delete ${parents.length} parent(s) created in the last ${maxH}h?\n\n${sample}${extra}\n\nSelected/active parents are excluded. This cannot be undone.`)) return;
        const result = await postJson('/api/parents/remove-recent', { max_age_hours: maxH, dry_run: false });
        alert(result.success ? `Deleted ${result.removed || 0} parent(s). Click Sync to refresh the list.` : `Delete failed: ${result.detail || 'unknown error'}`);
        if (result.success) {
            (result.ids || []).forEach(id => {
                const node = document.querySelector(`#parent-grid .grid-card[data-instance-id="${CSS.escape(String(id))}"]`);
                if (node) node.remove();
            });
            reindex(); apply();
        }
    }
    function buildBar() {
        bar = document.createElement('div');
        bar.id = 'parent-filter-bar';
        bar.className = 'parent-filter-bar';
        bar.innerHTML = `
            <div class="pf-row">
                <input type="text" id="parent-filter-search" class="form-input pf-search" placeholder="Search parent / spark...">
                <div class="pf-chips">${CATEGORIES.map(c => `<button type="button" class="pf-chip" data-cat="${c}">${c.toUpperCase()}</button>`).join('')}</div>
            </div>
            <div class="pf-row">
                <select id="parent-filter-factor" class="form-input pf-select"></select>
                <select id="parent-filter-stars" class="form-input pf-select pf-select-sm">${[1,2,3,4,5,6,7,8,9].map(n => `<option value="${n}">≥ ${n}★</option>`).join('')}</select>
                <select id="parent-filter-scope" class="form-input pf-select pf-select-sm"><option value="lineage">Full lineage</option><option value="self">Self only</option></select>
                <select id="parent-filter-sort" class="form-input pf-select pf-select-sm"><option value="none">Sort: default</option><option value="factor">Sort: factor ★</option><option value="stars">Sort: total ★</option><option value="rank">Sort: rank</option></select>
                <button type="button" id="parent-filter-clear" class="btn btn-sm pf-clear">CLEAR</button>
                <span class="pf-count" id="parent-filter-count"></span>
            </div>
            <div class="pf-row pf-row-autodel">
                <select id="parent-filter-age" class="form-input pf-select pf-select-sm"><option value="0">Cleanup age...</option><option value="1">Created &lt; 1h ago</option><option value="6">Created &lt; 6h ago</option><option value="12">Created &lt; 12h ago</option><option value="24">Created &lt; 24h ago</option><option value="48">Created &lt; 48h ago</option><option value="72">Created &lt; 3d ago</option><option value="168">Created &lt; 7d ago</option></select>
                <button type="button" id="parent-autodel-btn" class="btn btn-sm btn-danger pf-autodel" title="Preview and delete recent trained parents">PREVIEW CLEANUP</button>
                <span class="pf-autodel-hint" id="parent-autodel-hint"></span>
            </div>`;
        const search = bar.querySelector('#parent-filter-search');
        search.value = state.search;
        search.addEventListener('input', () => { state.search = search.value.trim(); apply(); });
        bar.querySelectorAll('.pf-chip').forEach(chip => {
            const cat = chip.dataset.cat;
            chip.classList.toggle('active', state.cats.includes(cat));
            chip.addEventListener('click', () => { const i = state.cats.indexOf(cat); if (i >= 0) state.cats.splice(i, 1); else state.cats.push(cat); chip.classList.toggle('active', state.cats.includes(cat)); apply(); });
        });
        const factor = bar.querySelector('#parent-filter-factor');
        factor.addEventListener('change', () => { state.factor = factor.value; apply(); });
        const stars = bar.querySelector('#parent-filter-stars');
        stars.value = String(state.minStars || 1);
        stars.addEventListener('change', () => { state.minStars = Number(stars.value || 1); apply(); });
        const scope = bar.querySelector('#parent-filter-scope');
        scope.value = state.scope;
        scope.addEventListener('change', () => { state.scope = scope.value; apply(); });
        const sort = bar.querySelector('#parent-filter-sort');
        sort.value = state.sort;
        sort.addEventListener('change', () => { state.sort = sort.value; apply(); });
        const age = bar.querySelector('#parent-filter-age');
        age.value = String(state.maxAgeH || 0);
        age.addEventListener('change', () => { state.maxAgeH = Number(age.value || 0); apply(); });
        bar.querySelector('#parent-filter-clear').addEventListener('click', () => { state.search = ''; state.cats = []; state.factor = ''; state.minStars = 0; state.scope = 'lineage'; state.sort = 'none'; state.maxAgeH = 0; save(); bar.remove(); buildAndMount(); });
        bar.querySelector('#parent-autodel-btn').addEventListener('click', () => previewAndDeleteRecentParents(Number(state.maxAgeH || 0)).catch(e => alert(`Cleanup failed: ${e.message || e}`)));
        return bar;
    }
    function buildAndMount() {
        const body = document.getElementById('parents-body');
        const grid = document.getElementById('parent-grid');
        if (!body || !grid) return false;
        if (document.getElementById('parent-filter-bar')) return true;
        const built = buildBar();
        body.insertBefore(built, grid);
        reindex(); apply();
        if (observer) observer.disconnect();
        observer = new MutationObserver((mutations) => {
            // Ignore tooltip relocations: hovering an owned-parent card moves its
            // .sparks-tooltip node out to <body>, which would otherwise trigger a
            // stale reindex that re-parses the card as empty (0 stars) and
            // reorders/hides it -- the "owned parent vanishes on hover when sorted"
            // bug. Only react to real card add/removes.
            const relevant = mutations.some((m) =>
                [...m.addedNodes, ...m.removedNodes].some((n) =>
                    n.nodeType === 1 && !(n.classList && n.classList.contains('sparks-tooltip'))
                )
            );
            if (!relevant) return;
            clearTimeout(timer);
            timer = setTimeout(() => { reindex(); apply(); }, 120);
        });
        observer.observe(grid, { childList: true, subtree: true });
        return true;
    }
    function init() {
        if (buildAndMount()) return;
        const retry = setInterval(() => { if (buildAndMount()) clearInterval(retry); }, 500);
        setTimeout(() => clearInterval(retry), 10000);
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
})();
// test contract: id="parent-filter-bar"
