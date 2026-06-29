/* Pre Icarus Career Monitor — bottom drawer for live runner log, crash trace,
   and current-run stat chart.  Uses separate live_history endpoint so the
   existing Career History archive stays unchanged. */
// Shared coalescer for /api/career/runner — app.js + monitor.js poll this on
// separate timers; without coalescing that's 3 fetches of the same payload per
// ~2s. get() returns the in-flight promise or a sub-TTL cached result so
// near-simultaneous callers share one round-trip. (defined defensively so
// whichever file loads first creates it.)
window.SweepyRunnerFeed = window.SweepyRunnerFeed || (function () {
    let cache = null, ts = 0, inflight = null;
    const TTL = 900;
    // v2.1: a hung /api/career/runner fetch used to leave `inflight` set forever,
    // freezing EVERY runner-fed panel (status, action log, decision reasoning,
    // monitor) until a full page reload. An AbortController timeout now rejects a
    // stalled request so `.finally` clears `inflight` and the next tick recovers.
    const FETCH_TIMEOUT_MS = 8000;
    return {
        get(force) {
            const now = Date.now();
            if (!force && cache && (now - ts) < TTL) return Promise.resolve(cache);
            if (inflight) return inflight;
            const ctrl = (typeof AbortController !== 'undefined') ? new AbortController() : null;
            const timer = ctrl ? setTimeout(() => { try { ctrl.abort(); } catch (e) {} }, FETCH_TIMEOUT_MS) : null;
            inflight = fetch('/api/career/runner', { headers: { 'Accept': 'application/json' }, signal: ctrl ? ctrl.signal : undefined })
                .then(r => r.json().catch(() => ({})).then(d => { if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`); return d; }))
                .then(d => { cache = d; ts = Date.now(); return d; })
                .finally(() => { if (timer) clearTimeout(timer); inflight = null; });
            return inflight;
        },
        peek() { return cache; },
    };
})();
(() => {
    'use strict';
    if (window.SWEEPY_DISABLE_MONITOR) return;
    const POLL_LOG_MS = 2000;
    const POLL_CHART_MS = 5000;
    const SERIES = [
        { key: 'speed', label: 'SPD', color: '#4fc3f7' },
        { key: 'stamina', label: 'STA', color: '#ffb74d' },
        { key: 'power', label: 'PWR', color: '#e57373' },
        { key: 'guts', label: 'GUT', color: '#ba68c8' },
        { key: 'wit', alt: 'wiz', label: 'WIT', color: '#81c784' },
        { key: 'skill_point', label: 'SP', color: '#fff176' },
    ];
    // WIT arrives as either `wit` or legacy `wiz`; resolve from whichever the
    // row carries so the chart never renders a duplicate empty "WIT 0" series.
    const seriesVal = (row, s) => {
        const v = row[s.key];
        return Number((v === undefined || v === null || v === '') ? row[s.alt] : v) || 0;
    };
    const state = { open: false, filter: 'all', paused: false, crash: false, logTimer: 0, chartTimer: 0, lastKey: '', history: null, userClosed: false, wasRunning: false };
    function esc(value) { return String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }
    function el(tag, cls, html) { const n = document.createElement(tag); if (cls) n.className = cls; if (html !== undefined) n.innerHTML = html; return n; }
    async function getJson(url) { const r = await fetch(url, { headers: { 'Accept': 'application/json' } }); const d = await r.json().catch(() => ({})); if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`); return d; }
    function kind(action) {
        const a = String(action || '');
        if (/error|failed|blocked/.test(a)) return 'error';
        if (/recover|retry|reject|skip|warn/.test(a)) return 'warn';
        if (/race/.test(a)) return 'race';
        if (/skills|items|gain/.test(a)) return 'gain';
        return 'info';
    }
    const root = el('div', 'monitor-drawer collapsed');
    root.id = 'career-monitor';
    root.innerHTML = `
        <button class="monitor-handle" id="monitor-toggle" type="button" aria-expanded="false">
            <span class="monitor-dot" id="monitor-dot"></span> MONITOR <span id="monitor-status" class="monitor-status"></span><span class="monitor-chevron">▲</span>
        </button>
        <div class="monitor-body" id="monitor-body">
            <div class="monitor-split">
                <div class="monitor-col monitor-col-log"><div class="monitor-col-head"><span>LIVE LOG</span><div id="monitor-tools" class="monitor-tools"></div></div><div class="monitor-log" id="monitor-log"></div></div>
                <div class="monitor-col monitor-col-chart"><div class="monitor-col-head"><span id="monitor-chart-title">STATS</span><button id="monitor-crash-toggle" class="monitor-filter" type="button">CRASH TRACE</button></div><div id="monitor-chart-pane" class="monitor-chart-pane"><canvas id="monitor-chart" height="220"></canvas><div id="monitor-legend" class="monitor-legend"></div><div id="monitor-empty" class="monitor-empty">No current-run stat rows yet.</div></div><pre id="monitor-crash" class="monitor-crash" hidden>Loading...</pre></div>
            </div>
        </div>`;
    const filters = ['all', 'race', 'gain', 'info', 'warn', 'error'];
    const tools = root.querySelector('#monitor-tools');
    filters.forEach(f => { const b = el('button', `monitor-filter ${f === 'all' ? 'active' : ''}`, f.toUpperCase()); b.type = 'button'; b.dataset.filter = f; b.addEventListener('click', () => { state.filter = f; tools.querySelectorAll('[data-filter]').forEach(x => x.classList.toggle('active', x === b)); state.lastKey = ''; refreshLog(); }); tools.appendChild(b); });
    const pause = el('button', 'monitor-filter monitor-pause', 'PAUSE'); pause.type = 'button'; pause.addEventListener('click', () => { state.paused = !state.paused; pause.textContent = state.paused ? 'RESUME' : 'PAUSE'; pause.classList.toggle('active', state.paused); }); tools.appendChild(pause);
    function setOpen(open) { state.open = open; root.classList.toggle('collapsed', !open); root.querySelector('#monitor-toggle').setAttribute('aria-expanded', String(open)); if (open) startPolling(); else stopPolling(); }
    function stopPolling() { if (state.logTimer) clearInterval(state.logTimer); if (state.chartTimer) clearInterval(state.chartTimer); state.logTimer = state.chartTimer = 0; }
    function startPolling() { stopPolling(); refreshStatus(); refreshLog(); refreshChart(); state.logTimer = setInterval(() => { refreshStatus(); refreshLog(); }, POLL_LOG_MS); state.chartTimer = setInterval(refreshChart, POLL_CHART_MS); }
    async function refreshStatus() { try { const d = await window.SweepyRunnerFeed.get(); const r = d.runner || {}; const running = Boolean(r.running); root.querySelector('#monitor-dot').classList.toggle('live', running); root.querySelector('#monitor-dot').classList.toggle('error', Boolean(r.last_error)); root.querySelector('#monitor-status').textContent = running ? `turn ${r.turn ?? '?'} · ${r.last_action || 'running'}` : (r.last_error ? `stopped · ${String(r.last_error).slice(0, 60)}` : (r.finished ? 'finished' : 'idle')); if (running && !state.wasRunning && !state.open && !state.userClosed) setOpen(true); state.wasRunning = running; } catch (e) {} }
    async function refreshLog() { if (state.paused || !state.open) return; let r; try { r = (await window.SweepyRunnerFeed.get()).runner || {}; } catch (e) { return; } const rows = (r.log || []).map(x => ({ ...x, kind: kind(x.action) })).filter(x => state.filter === 'all' || x.kind === state.filter); const key = rows.length ? `${rows.length}:${rows[rows.length-1].id}:${state.filter}` : `0:${state.filter}`; if (key === state.lastKey) return; state.lastKey = key; const box = root.querySelector('#monitor-log'); const stick = box.scrollHeight - box.scrollTop - box.clientHeight < 40; box.innerHTML = rows.length ? rows.map(x => `<div class="monitor-log-row kind-${x.kind}"><span>${esc(x.time || '')}</span><span>T${esc(x.turn ?? 0)}</span><strong>${esc(x.action || '')}</strong><span>${esc(x.detail || '')}</span></div>`).join('') : '<div class="monitor-empty">No log rows for this filter.</div>'; if (stick) box.scrollTop = box.scrollHeight; }
    async function refreshCrash() { const pane = root.querySelector('#monitor-crash'); try { const d = await getJson('/api/career/crash_trace'); pane.textContent = (d.trace || '').trim() || 'No crash trace recorded.'; } catch (e) { pane.textContent = `Could not load crash trace: ${e.message}`; } }
    async function refreshChart() { if (!state.open || state.crash) return; try { state.history = await getJson('/api/career/live_history'); drawChart(); } catch (e) {} }
    function drawChart() { const canvas = root.querySelector('#monitor-chart'); const empty = root.querySelector('#monitor-empty'); const legend = root.querySelector('#monitor-legend'); const stats = (state.history && state.history.stats || []).filter(x => x && x.turn != null); if (!canvas || state.crash) return; if (!stats.length) { canvas.style.display = 'none'; empty.style.display = 'block'; legend.innerHTML = ''; return; } canvas.style.display = 'block'; empty.style.display = 'none'; const dpr = window.devicePixelRatio || 1; const host = canvas.parentElement; const w = Math.max(240, host.clientWidth - 20); const h = Math.max(160, host.clientHeight - 44); canvas.width = w * dpr; canvas.height = h * dpr; canvas.style.width = w + 'px'; canvas.style.height = h + 'px'; const ctx = canvas.getContext('2d'); ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0,0,w,h); const pad = {l:42,r:10,t:12,b:22}; const pw = w-pad.l-pad.r, ph = h-pad.t-pad.b; const turns = stats.map(x => Number(x.turn)||0); const minT = Math.min(...turns), maxT = Math.max(...turns, minT+1); let maxV = 100; stats.forEach(row => SERIES.forEach(s => { const v = seriesVal(row, s); if (v > maxV) maxV = v; })); maxV = Math.ceil(maxV/100)*100; const x = t => pad.l + ((t-minT)/(maxT-minT))*pw; const y = v => pad.t + ph - (v/maxV)*ph; ctx.strokeStyle = 'rgba(255,255,255,0.13)'; ctx.fillStyle = 'rgba(255,255,255,0.65)'; ctx.font = '10px system-ui'; for (let i=0;i<=4;i++){ const v=(maxV/4)*i, gy=y(v); ctx.beginPath(); ctx.moveTo(pad.l,gy); ctx.lineTo(w-pad.r,gy); ctx.stroke(); ctx.fillText(String(Math.round(v)),4,gy+3); } for (const s of SERIES.filter((v,i,a) => a.findIndex(x => x.key === v.key) === i)) { ctx.strokeStyle = s.color; ctx.lineWidth = 1.5; ctx.beginPath(); let started=false; stats.forEach(row => { const px=x(Number(row.turn)||0), py=y(seriesVal(row, s)); if (!started) { ctx.moveTo(px,py); started=true; } else ctx.lineTo(px,py); }); ctx.stroke(); } const last = stats[stats.length-1] || {}; legend.innerHTML = SERIES.filter((v,i,a) => a.findIndex(x => x.key === v.key) === i).map(s => `<span><i style="background:${s.color}"></i>${s.label} ${seriesVal(last, s)}</span>`).join(''); }
    function setCrash(visible) { state.crash = visible; root.querySelector('#monitor-chart-pane').hidden = visible; root.querySelector('#monitor-crash').hidden = !visible; root.querySelector('#monitor-crash-toggle').textContent = visible ? 'SHOW STATS' : 'CRASH TRACE'; root.querySelector('#monitor-chart-title').textContent = visible ? 'CRASH TRACE' : 'STATS'; if (visible) refreshCrash(); else drawChart(); }
    root.querySelector('#monitor-toggle').addEventListener('click', () => { if (state.open) state.userClosed = true; setOpen(!state.open); });
    root.querySelector('#monitor-crash-toggle').addEventListener('click', () => setCrash(!state.crash));
    window.addEventListener('resize', () => { if (state.open && !state.crash) drawChart(); });
    function mount(){ const host = document.getElementById('monitor-host'); if (host) { root.classList.add('inline'); host.appendChild(root); setOpen(true); } else { document.body.appendChild(root); } refreshStatus(); setInterval(() => { if (!state.open) refreshStatus(); }, 4000); }
    window.SweepyCareerMonitor = { refreshStatus, refreshLog, refreshChart, setOpen };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount); else mount();
})();
