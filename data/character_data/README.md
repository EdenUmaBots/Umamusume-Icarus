# Character data — Android-bot origin

These two JSON files are direct ports of community-maintained data from the
`uma-android-automation` project:

  - `character_presets.json` — distance & surface aptitudes for 59 trainees,
    sourced from `src/data/characterPresets.json` upstream.
  - `epithets.json` — 217 epithets (titles), each tagged with the
    character(s) it can be earned by, sourced from `src/data/epithets.json`
    upstream.  Built by their `scripts/scrapers/epithet_scraper.py`.

We bundle them so Pre Icarus has a starting catalog without writing its own
scraper.  License & attribution as per the upstream repo.  Updating: copy
fresh versions from the upstream `src/data/` directory whenever they refresh.
