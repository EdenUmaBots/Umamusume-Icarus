/* Career History — fetches /api/career/history, renders each completed run as a
   champion profile (final stats, aptitudes, sparks) + full race history.
   Renders an empty state when the backend is unreachable (api() returns null). */
(() => {
  'use strict';
  const I = window.Icarus;
  const { api, fmtCompact, esc, pad2 } = I;
  const $ = (id) => document.getElementById(id);
  const fmtNum = (n) => (n || 0).toLocaleString('en-US');

  const gradeBg = (g) => ({ URA: 'bg-amber', WIN: 'bg-green', FAIL: 'bg-red' }[g] || 'bg-mut');

  // ---- final-stat value -> letter grade ------------------------------------
  function statGrade(v) {
    if (v >= 1100) return 'SS';
    if (v >= 1000) return 'A+';
    if (v >= 850)  return 'A';
    if (v >= 800)  return 'B+';
    if (v >= 600)  return 'B';
    if (v >= 500)  return 'C';
    if (v >= 450)  return 'D+';
    if (v >= 350)  return 'D';
    if (v >= 300)  return 'E';
    if (v >= 100)  return 'F';
    return 'G';
  }
  // letter -> tone class (S A B C D E F G)
  const gradeTone = (letter) => {
    const c = (letter || '')[0];
    return c === 'S' ? 'g-s' : c === 'A' ? 'g-a' : c === 'B' ? 'g-b'
         : c === 'C' ? 'g-c' : c === 'D' ? 'g-d' : 'g-g';
  };
  const gradeBadgeCls = (g) => {
    const k = (g || '').toUpperCase();
    if (k === 'CLIMAX') return 'gb-climax';
    if (k === 'G1') return 'gb-g1';
    if (k === 'G2') return 'gb-g2';
    if (k === 'G3') return 'gb-g3';
    return 'gb-op';
  };
  const placeCls = (p) => p === 1 ? 'pl-1' : p === 2 ? 'pl-2' : p === 3 ? 'pl-3' : 'pl-x';
  const placeLbl = (p) => p === 1 ? '1st' : p === 2 ? '2nd' : p === 3 ? '3rd' : (p ? p + 'th' : '—');
  const hpToneCls = (r) => { const f = (r.hp / (r.hpmax || 100)); return f <= 0.18 ? 'hp-red' : f <= 0.42 ? 'hp-amber' : 'hp-green'; };

  let careers = [];
  let activeIdx = null;

  // ---- profile model -------------------------------------------------------
  // real runs supply `profile`; otherwise derive a plausible one from c.stats.
  function profileFor(c) {
    if (c.profile) return c.profile;
    const st = c.stats || {};
    const fs = [st.speed, st.stamina, st.power, st.guts, st.wit].map((v) => v || 0);
    const sum = fs.reduce((a, b) => a + b, 0);
    const seed = c.index || 1;
    const apt = (i) => ['A', 'B', 'C', 'A', 'B', 'S', 'C', 'D'][(seed + i) % 8];
    // a representative race set derived from the career
    const names = [
      ['G1', 'Arima Kinen', 'Nakayama', 2500, 'Long'], ['G1', 'Japan Cup', 'Tokyo', 2400, 'Medium'],
      ['G1', 'Tenno Sho (Autumn)', 'Tokyo', 2000, 'Medium'], ['G1', 'Osaka Hai', 'Hanshin', 2000, 'Medium'],
      ['G2', 'Kyoto Kinen', 'Kyoto', 2200, 'Medium'], ['G3', 'Aichi Hai', 'Chukyo', 1600, 'Mile'],
    ];
    const wins = c.wins || 0;
    const races = names.map(([grade, name, venue, dist, cat], i) => {
      const f = 1 - i * 0.06;
      return {
        grade, name, venue, surface: 'Turf', dist, cat,
        when: ['Senior Year Late Dec', 'Senior Year Late Nov', 'Senior Year Late Oct', 'Senior Year Early Apr', 'Classic Year Mid Feb', 'Junior Year Late Aug'][i],
        style: 'Late Surger', plan: i % 3 === 0 ? 'mandatory' : 'solver-planned',
        hp: 30 + ((seed * 7 + i * 11) % 50), hpmax: 108,
        spd: Math.round(fs[0] * f), sta: Math.round(fs[1] * f), pwr: Math.round(fs[2] * f),
        gut: Math.round(fs[3] * f), wit: Math.round(fs[4] * f),
        place: i < Math.max(1, Math.round(wins / 4)) ? 1 : (i % 2 ? 2 : 3),
        fans: [30000, 20000, 20000, 12000, 9000, 5000][i],
      };
    });
    return {
      rating: Math.round(sum * 3.1), rank: c.index, career_grade: Math.max(1, Math.min(12, Math.round(sum / 280))),
      date: '—', scenario_label: (c.scenario || 'Trackblazer') + ': Career Complete',
      win_rate: c.races ? Math.round((wins / c.races) * 100) : 0,
      race_fans: Math.round((c.fans_final || 0) * 0.62),
      major_wins: races.filter((r) => r.place === 1).slice(0, 5).map((r) => r.name),
      aptitudes: {
        TRACK: [['Turf', apt(0)], ['Dirt', apt(1)]],
        DISTANCE: [['Sprint', apt(2)], ['Mile', apt(3)], ['Medium', apt(4)], ['Long', apt(5)]],
        STYLE: [['Front', apt(6)], ['Pace', apt(7)], ['Late', apt(0)], ['End', apt(1)]],
      },
      sparks: [['Speed', 3, 12], ['Turf', 2, 5], ['Late Surger', 2, 5], [c.scenario + ' Scenario', 3, 5]],
      races,
    };
  }

  function renderList() {
    const host = $('ch-list');
    $('ch-count').textContent = careers.length;
    host.innerHTML = '';
    careers.forEach((c, i) => {
      const row = document.createElement('div');
      row.className = 'listrow' + (i === activeIdx ? ' is-active' : '');
      row.innerHTML = `
        <div class="listrow-top">
          <span class="listrow-title">RUN #${c.index} · ${esc((c.trainee || '').toUpperCase())}</span>
          <span class="tagbadge ${gradeBg(c.grade || c.career_rank)}">${esc(c.grade || c.career_rank || '—')}</span>
        </div>
        <div class="listrow-meta">${esc(c.scenario || 'Trackblazer')} · ${c.turn || 0} turns · ${esc(c.runtime || '')}</div>
        <div class="listrow-kv">
          <span class="mut">FANS <span class="${i === activeIdx ? 'c-amber' : 'c-mut'}">${fmtCompact(c.fans_final)}</span></span>
          <span class="mut">RACES <span class="c-mut">${c.races || 0}</span></span>
          <span class="mut">WINS <span class="${(c.wins >= 18) ? 'c-green' : 'c-mut'}">${c.wins || 0}</span></span>
        </div>`;
      row.addEventListener('click', () => { activeIdx = i; renderList(); renderReport(); });
      host.appendChild(row);
    });
  }

  function aptSetHtml(pairs) {
    return pairs.map(([k, g]) =>
      `<span class="aptchip">${esc(k)}<b class="${gradeTone(g)}">${esc(g)}</b></span>`).join('');
  }

  function raceRowHtml(r) {
    const venue = r.venue ? esc(r.venue) + ' · ' : '';
    return `
      <div class="racerow${r.place === 1 ? ' win' : ''}">
        <div class="gradebadge ${gradeBadgeCls(r.grade)}">${esc(r.grade)}</div>
        <div>
          <div class="race-name">${esc(r.name)}</div>
          <div class="race-dist">${venue}${esc(r.surface)} ${r.dist}m <span style="color:var(--label)">(${esc(r.cat)})</span></div>
          <div class="race-meta">${esc(r.when)} · ${esc(r.style)} · <span class="plan">${esc(r.plan)}</span></div>
          <div class="race-stats"><span class="hpbadge ${hpToneCls(r)}">HP ${r.hp}/${r.hpmax}</span>SPD ${r.spd} · STA ${r.sta} · PWR ${r.pwr} · GUT ${r.gut} · WIT ${r.wit}</div>
        </div>
        <div class="race-right">
          <span class="placebadge ${placeCls(r.place)}">${placeLbl(r.place)}</span>
          ${winprobChip(r)}
          <span class="race-fans">${fmtNum(r.fans)} fans</span>
        </div>
      </div>`;
  }

  // ---- real-data adapters (prefer the backend's per-career fields; the mock
  //      profileFor() is only a fallback for older/partial history rows) --------
  // Sparks: backend sends objects {name, stars, initial_points}; mock sends [name,stars,pts] tuples.
  function sparkTuples(c, p) {
    if (c.sparks && c.sparks.length) {
      return c.sparks.map((s) => Array.isArray(s)
        ? s
        : [s.name || s.label || 'Spark', Number(s.stars || s.star || 0), Number(s.initial_points ?? s.points ?? s.pts ?? 0)]);
    }
    return p.sparks || [];
  }
  // Aptitudes: backend sends {track:{turf,dirt}, distance:{...}, style:{...}}; render wants
  // {TRACK:[[k,g]], DISTANCE:[...], STYLE:[...]}.
  function aptFromBackend(c) {
    const a = c.aptitudes;
    if (!a || !a.distance) return null;
    const U = (s) => String(s == null ? '' : s).toUpperCase();
    return {
      TRACK: [['Turf', U(a.track && a.track.turf)], ['Dirt', U(a.track && a.track.dirt)]],
      DISTANCE: [['Sprint', U(a.distance.sprint)], ['Mile', U(a.distance.mile)], ['Medium', U(a.distance.medium)], ['Long', U(a.distance.long)]],
      STYLE: [['Front', U(a.style && a.style.front)], ['Pace', U(a.style && a.style.pace)], ['Late', U(a.style && a.style.late)], ['End', U(a.style && a.style.end)]],
    };
  }
  // Real race row (runner _race_program_summary shape) -> raceRowHtml shape.
  function adaptRace(r) {
    const rank = Number(r.final_rank ?? r.rank ?? 0);
    const st = r.stat_snapshot || {};
    const md = r.master_metadata || {};
    return {
      grade: r.grade || '',
      name: r.name || ('Race ' + (r.program_id || '')),
      venue: md.venue || r.venue || '',
      surface: r.terrain || r.surface || '',
      dist: r.distance_m || r.dist || '',
      cat: r.distance_type || r.cat || '',
      when: md.date || (r.turn ? 'Turn ' + r.turn : ''),
      style: r.running_style || (r.style_adaptation && r.style_adaptation.base_user_style) || '',
      plan: r.race_type || 'race',
      hp: Number(st.hp ?? st.vital ?? 0), hpmax: Number(st.max_hp ?? st.max_vital ?? 100),
      spd: Number(st.speed ?? 0), sta: Number(st.stamina ?? 0), pwr: Number(st.power ?? 0),
      gut: Number(st.guts ?? 0), wit: Number(st.wit ?? st.wiz ?? 0),
      place: (rank > 0 && rank < 90) ? rank : 0,
      fans: Number(r.fans ?? 0),
      winprob: r.win_probability || null,   // read-only pre-race estimate (may be null/unavailable)
    };
  }

  // Pre-race win-probability chip (read-only). Hidden when no named-rival field
  // was known for the race, so it never shows a misleading 100%.
  function winprobChip(r) {
    const w = r.winprob;
    if (!w || !w.available || w.p_win == null) return '';
    const pct = Math.round(w.p_win * 100);
    const top3 = Math.round((w.p_top3 || 0) * 100);
    const tone = pct >= 50 ? 'c-green' : pct >= 20 ? 'c-amber' : 'c-mut';
    // "~" marks this as a PRELIMINARY, uncalibrated estimate (default logistic
    // scale, pending backtest calibration). It is computed vs the NAMED rivals
    // only — the full starting gate is larger — so it is an optimistic upper bound.
    return `<span class="winprob ${tone}" style="font-size:var(--fs-md);font-weight:600" `
      + `title="Preliminary (uncalibrated) pre-race estimate vs the ${(w.field_size || 1) - 1} named rival(s) only — the full gate is larger, so this is optimistic. Top-3 ~${top3}%. Read-only, does not affect play.">`
      + `~P(win) ${pct}%</span>`;
  }

  function renderReport() {
    const c = careers[activeIdx];
    const host = $('ch-report');
    if (!c) { host.innerHTML = ''; return; }
    const p = profileFor(c);
    const st = c.stats || {};
    const FS = [['SPD', st.speed], ['STA', st.stamina], ['POW', st.power], ['GUT', st.guts], ['WIT', st.wit]];
    const aptOrder = ['TRACK', 'DISTANCE', 'STYLE'];

    // Prefer real per-career data; fall back to the mock for older/partial rows.
    const aptitudes = aptFromBackend(c) || p.aptitudes;
    const sparkRows = sparkTuples(c, p);
    const skillGroups = c.skills_grouped && typeof c.skills_grouped === 'object' ? c.skills_grouped : null;
    const realRaces = (c.race_results && c.race_results.length) ? c.race_results.map(adaptRace) : null;
    const races = realRaces || p.races;
    const ratingNum = Number(c.rating) || Number(p.rating) || 0;
    const careerGrade = (c.career_grade != null && c.career_grade !== '') ? c.career_grade : p.career_grade;
    const majorWins = c.major_wins
      ? (Array.isArray(c.major_wins) ? c.major_wins.join(', ') : String(c.major_wins))
      : (p.major_wins || []).join(', ');
    const raceCount = c.races || races.length;
    const winRate = raceCount ? Math.round(((c.wins || 0) / raceCount) * 100) : p.win_rate;
    const raceFans = realRaces ? realRaces.reduce((s, r) => s + (r.fans || 0), 0) : p.race_fans;

    host.className = 'col bordered prof';
    host.innerHTML = `
      <div class="prof-scroll">
        <!-- header -->
        <div class="prof-hd">
          <div class="prof-av">${(c.card_id || c.portrait_url) ? `<img src="${c.card_id ? '/api/card-art/' + esc(String(c.card_id)) + '.png?v=2' : esc(c.portrait_url)}" alt="${esc(c.trainee || 'trainee')}" onerror="this.remove()">` : '<span>TRAINEE</span>'}</div>
          <div class="prof-id">
            <div class="prof-name">${esc(c.trainee)}</div>
            <div class="prof-sub">${esc(c.scenario || p.scenario_label)}${p.date && p.date !== '—' ? ' · ' + esc(p.date) : ''}</div>
          </div>
          <div class="prof-rate">
            <div class="prof-circle">${c.index ?? p.rank}</div>
            <div class="prof-rate-v">${fmtNum(ratingNum)}</div>
            <div class="prof-rate-k">RATING</div>
          </div>
        </div>

        <!-- stat cards -->
        <div class="scards">
          <div class="scard"><div class="scard-v">${fmtNum(c.fans_final)}</div><div class="scard-k">FANS</div></div>
          <div class="scard"><div class="scard-v">${c.races || 0}</div><div class="scard-k">RACES</div></div>
          <div class="scard"><div class="scard-v">${c.wins || 0}</div><div class="scard-k">WINS</div></div>
          <div class="scard"><div class="scard-v amber">${esc(String(c.career_rank || careerGrade || '—'))}</div><div class="scard-k">RATING RANK</div></div>
          ${majorWins ? `<div class="scard wide"><div class="scard-v">${esc(majorWins)}</div><div class="scard-k">MAJOR WINS</div></div>` : ''}
        </div>

        <!-- final stats + aptitudes -->
        <div class="prof-sec">
          <div class="prof-split">
            <div>
              <div class="prof-sec-t">FINAL STATS</div>
              <div class="fstats">
                ${FS.map(([k, v]) => { const g = statGrade(v || 0); return `
                  <div class="fstat"><div class="fstat-k">${k}</div><div class="fstat-g ${gradeTone(g)}">${g}</div><div class="fstat-v">${v || 0}</div></div>`; }).join('')}
              </div>
            </div>
            <div>
              <div class="prof-sec-t">APTITUDES</div>
              ${aptOrder.map((k) => aptitudes[k] ? `
                <div class="aptrow"><div class="aptrow-k">${k}</div><div class="aptset">${aptSetHtml(aptitudes[k])}</div></div>` : '').join('')}
            </div>
          </div>
        </div>

        <!-- sparks -->
        ${sparkRows && sparkRows.length ? `
        <div class="prof-sec">
          <div class="prof-sec-t">SPARKS</div>
          <div class="sparks">
            ${sparkRows.map(([name, stars, pts]) => `
              <span class="sparkchip">${esc(name)} <span class="stars">${'★'.repeat(stars)}${'☆'.repeat(Math.max(0, 3 - stars))}</span> <span class="pts">+${pts} pts</span></span>`).join('')}
          </div>
        </div>` : ''}

        <!-- skills gained -->
        ${skillGroups && Object.keys(skillGroups).length ? `
        <div class="prof-sec">
          <div class="prof-sec-t">SKILLS GAINED</div>
          ${Object.entries(skillGroups).map(([label, arr]) => (arr && arr.length) ? `
            <div class="aptrow"><div class="aptrow-k">${esc(String(label).toUpperCase())}</div><div class="sparks">${arr.map((sk) => `<span class="skillchip">${esc(sk && (sk.name || sk.skill_name) || sk)}</span>`).join('')}</div></div>` : '').join('')}
        </div>` : ''}

        <!-- race history -->
        <div class="rh-head">
          <span class="t">RACE HISTORY</span>
          <span class="rh-stat"><b>${raceCount}</b> races</span>
          <span class="rh-stat"><b>${c.wins || 0}</b> wins</span>
          <span class="rh-stat"><b>${winRate}%</b> win rate</span>
          <span class="rh-stat"><b>${fmtNum(raceFans)}</b> race fans</span>
        </div>
        <div class="rh-list">
          ${races.map(raceRowHtml).join('')}
        </div>
      </div>`;
  }

  async function boot() {
    I.mountChrome();
    const data = await api('/api/career/history');
    careers = (data && data.careers) || [];
    careers.forEach((c) => {
      if (c.grade == null) c.grade = c.career_rank;
      if (c.fans_final == null) c.fans_final = c.fans_gained || 0;
    });
    activeIdx = careers.length ? 0 : null;
    renderList(); renderReport();

    $('ch-filter').addEventListener('input', (e) => {
      const q = e.target.value.toLowerCase();
      [...$('ch-list').children].forEach((row, i) => {
        const c = careers[i];
        row.style.display = (!q || (c.trainee || '').toLowerCase().includes(q) || String(c.index).includes(q)) ? '' : 'none';
      });
    });
  }
  boot();
})();
