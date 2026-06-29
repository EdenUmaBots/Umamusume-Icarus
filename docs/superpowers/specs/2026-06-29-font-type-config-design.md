# v3 Typographic Config + Runtime Font Controls

**Date:** 2026-06-29
**Status:** Approved (build)
**Scope:** v3 UI only (`public-v3/`). `log_viewer.html` is NOT an Icarus file (only the
Android app ships one, in `_analysis_tmp/`); the in-app log panels are already styled by
`styles.css`. Legacy `public/` UI is out of scope.

## Goal
Testers report the UI is hard to read. Give them (a) a global **font-size** control and
(b) **selectable fonts**, and give the maintainer a single **"type config"** block (the
native-CSS equivalent of a Tailwind `theme.fontFamily`/`theme.fontSize`) — no build tooling.

## Why not Tailwind
The v3 frontend is deliberately build-free, statically served, and runs offline at times
(same reason the 3D viewer's CDN breaks). Tailwind needs a build step or its CDN script.
What the user likes about Tailwind — one config controlling all type tokens — is exactly
what CSS custom properties in `:root` provide. So we use those.

## Decisions (locked with the user)
- **Font source:** more Google Fonts via CDN (large curated pick-list). *Accepted caveat:*
  selections load only when online; offline they fall back to system fonts (unchanged from
  today, where the 3 defaults already come from the Google CDN).
- **Pickers:** three independent dropdowns — **Body**, **Heading**, **Numeric** — mapping to
  the existing `--sans`, `--cond`, `--mono` variables.

## Design

### 1. Type config (`:root` in `styles.css`) — the single source of truth
```css
--fs-scale: 1;                        /* global multiplier driven by the size control */
--fs-2xs … --fs-6xl: calc(Npx * var(--fs-scale));   /* 12 rungs: 8,9,10,11,12,13,14,15,16,18,22,26 */
```
Font *families* stay as `--sans` / `--cond` / `--mono` (already the body/heading/numeric
roles). The pickers override these three vars.

### 2. Tokenize every hardcoded size
All `font-size:` and `font:`-shorthand pixel values in `styles.css` (~152) and inline in
`app/history/diag/modals/setup/core.js` (~48) are rewritten to `var(--fs-*)` by a
deterministic script. Mapping is nearest-rung; the 5 sub-pixel decimals (10.5/12.5/…) snap
≤0.5px (imperceptible). **At "Normal" scale nothing changes size.** Shorthands keep the
token in place, e.g. `font: 400 var(--fs-base)/1.6 var(--sans)`.

### 3. DISPLAY control (global, injected by `core.js`)
A `DISPLAY` button added to `.rail-toggles` (present on every page) opens an Appearance
modal (`Icarus.modal`) with:
- **Font size:** segmented Small / Normal / Large / X-Large → `--fs-scale` = 0.9 / 1 / 1.1 / 1.2
- **Body / Heading / Numeric font:** three `<select>` dropdowns from curated Google-Font lists
- **Accent theme:** the 6 themes (bonus — currently only reachable via the hidden logo-click)

Controls apply **live** and persist immediately (like the existing theme) — no Save/dirty
guard.

### 4. Persistence + load (mirrors `icarus_theme`)
localStorage keys: `icarus_fs_scale` (small|normal|large|xlarge), `icarus_font_body`,
`icarus_font_head`, `icarus_font_num` (font label). Applied on every page in `mountChrome()`:
set `--fs-scale`, override the 3 family vars, and **lazily inject** a Google-Fonts `<link>`
only for non-default selections (defaults already load via the HTML `<link>`).

### 5. Cache-bust
Bump `?v=` on `styles.css` + every changed JS across all 7 v3 HTML pages.

## Risk / verify-live
- `calc()` font-size inside the `font:` shorthand (`var(--fs-base)/1.6 …`) is standard and
  supported in modern browsers; the few `/line-height` shorthands are the one thing to eyeball
  on a real page. Fallback if any misbehaves: split that rule into longhand.
- Google Fonts only load online (accepted).

## Out of scope
Tailwind/build tooling; legacy `public/`; self-hosting the default fonts.
