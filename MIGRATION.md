# Applying the public-v3 redesign to IcarusDev

The redesign is **frontend-only**. It calls the same API endpoints your backend
already serves, so the only backend change needed is to **serve the new folder**.
Your `main.py` hand-routes individual files today (`/`, `/styles.css`, `/app.js`,
`/css/*`, `/js/*`, image routes) — the redesign's extra pages (`setup.html`,
`accounts.html`, `core.js`, `setup.js`, `modals.js`, …) have no routes, so they
must be served by one static mount.

This migration is **parallel and reversible**: the old UI stays at `/`, the new
UI lives at `/v3/`. Flip the default only when you're happy.

---

## Step 1 — Copy the redesign into the Dev folder

Place it as a sibling of `public/` (do NOT overwrite `public/`):

```
IcarusDev/
  main.py
  public/        <- old UI, untouched
  public-v3/     <- drop the redesign here
```

Files in `public-v3/`:
index.html, setup.html, accounts.html, events.html, history.html, diag.html,
help.html, core.js, app.js, setup.js, modals.js, accounts.js, events.js,
history.js, diag.js, styles.css

(The `public-v3/model-test/` folder is an experimental 3D viewer and is optional.)

---

## Step 2 — Add ONE static mount to main.py

`from fastapi.staticfiles import StaticFiles` is already imported in your file
(top of main.py), so no new import is needed.

Find this block (near the bottom of main.py, the root route):

```python
@app.get("/", response_class=HTMLResponse)
async def root():
    index_path = base_dir / "public" / "index.html"
    if index_path.exists():
        return FileResponse(
            index_path, media_type="text/html", headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"}
        )
    return "index.html not found"
```

Add the mount **immediately AFTER** that function (mounts must be registered
after the `@app` routes; `/v3` cannot shadow `/api`):

```python
# --- Redesign (public-v3): served in parallel with the old UI at /v3/ ---
# Old UI stays at "/". Visit http://localhost:<port>/v3/ for the new one.
app.mount(
    "/v3",
    StaticFiles(directory=base_dir / "public-v3", html=True),
    name="v3",
)
```

That's the whole backend change.

---

## Step 3 — Run and compare

Start the server as you normally do, then open:

* Old UI:  `http://localhost:<port>/`
* New UI:  `http://localhost:<port>/v3/`

Both share the same backend, the same live career, the same account data. Nothing
about the old UI changes. Click around `/v3/` (Setup, Decks, Parents, the CAREER
pill, etc.) against a live login to confirm everything wires up.

---

## Step 4 — Make the redesign the default (only when ready)

Change ONLY the root route to serve `public-v3/index.html`:

```python
@app.get("/", response_class=HTMLResponse)
async def root():
    index_path = base_dir / "public-v3" / "index.html"   # was: "public"
    if index_path.exists():
        return FileResponse(
            index_path, media_type="text/html", headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"}
        )
    return "index.html not found"
```

Keep the `/v3` mount in place — with the root now serving `public-v3/index.html`,
its relative refs (`styles.css`, `core.js`, …) resolve at the site root, and the
mount keeps `/v3/` working as a stable alias. Leave `public/` on disk until you're
fully confident; reverting is just changing `"public-v3"` back to `"public"`.

---

## Notes / gotchas

* **No API changes.** The redesign only calls endpoints IcarusDev already has:
  `/api/session`, `/api/selection`, `/api/skills`, `/api/skill-config`,
  `/api/career/runner`, `/api/career/delete`, `/api/supports/details`,
  `/api/trainee/support-setups`, `/api/trainee/recommended-supports`,
  `/api/parents/remove-recent`, `/api/settings-presets`, `/api/userdata/*`,
  plus the image/icon routes (`/api/images/<id>.png`, `/api/skill-icons/<id>.png`).

* **Don't repoint the old `/styles.css` and `/app.js` routes.** Those serve the
  OLD `public/` files. The redesign's own `styles.css`/`app.js` live under the
  mount and are referenced relatively, so there is no conflict — leave those
  routes alone.

* **Cache busting.** The redesign already uses `?v=` query strings on its CSS/JS
  (e.g. `core.js?v=4`, `styles.css?v=4`). When you edit one of those files later,
  bump its `?v=` number so browsers don't serve a stale copy.

* **Fonts** load from Google's CDN (same as today) — no local font files needed.
