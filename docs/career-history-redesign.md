# Desktop Career History Redesign

## Purpose

Pre Icarus v5.8 replaces the old session-only Career History table with a desktop-first, two-level modal that shows completed careers as rich summary cards and opens a full detail view for each run.

## Main History Modal

The main modal keeps the existing dashboard styling but renders career entries as cards instead of rows. Each card includes:

- trainee portrait, resolved through `/api/images/{card_id}.png` with `/sweep.png` fallback
- trainee name and optional title/outfit text when the run payload contains it
- career rank badge and numeric rating
- fans earned, final fans, race count, win count, and major-win summary
- final stat grade badges with numeric values
- track, distance, and style aptitude badges
- spark chips with one to three star indicators
- `VIEW DETAILS` action

The modal also adds desktop controls for search and sorting by newest, rating, fans, wins, or trainee name.

## Detail Modal

Clicking any career card opens a second modal above the history modal. The detail view preserves the history list behind it and includes:

- large trainee portrait
- rank and metadata summary
- final stats panel
- aptitude panel
- full spark list
- grouped skill snapshot when skill data is available

The detail modal can be closed with BACK to return to the history list or DONE to close the full history stack.

## Data Model

Career entries returned by `/api/career/history` now support the richer fields below when the runner snapshot provides them:

```json
{
  "run_id": "20260611-...",
  "trainee": "Taiki Shuttle",
  "title": "Wild Frontier",
  "card_id": "106001",
  "portrait_url": "/api/images/106001.png",
  "career_rank": "A+",
  "rating": 12999,
  "fans_gained": 570495,
  "fans_final": 570495,
  "races": 40,
  "wins": 33,
  "major_wins": "2 G1, 1 G2",
  "scenario": "Trackblazer: Start of the Climax",
  "stats": {
    "speed": 1200,
    "stamina": 650,
    "power": 920,
    "guts": 540,
    "wit": 900,
    "skill_point": 0
  },
  "aptitudes": {
    "track": { "turf": "A", "dirt": "B" },
    "distance": { "sprint": "A", "mile": "A", "medium": "B", "long": "G" },
    "style": { "front": "B", "pace": "A", "late": "D", "end": "G" }
  },
  "sparks": [
    { "name": "Sprint", "stars": 2, "category": "aptitude" }
  ],
  "skills_grouped": {
    "Unique": [{ "skill_id": 10071, "name": "Warning Shot!", "rarity": 3 }]
  }
}
```

Older session entries that lack sparks or skills still render with clear fallback text.

## Asset Strategy

- Portraits use the existing `/api/images/{image_name}` endpoint and the `data/images` folder.
- Grade and aptitude badges are CSS-rendered text badges for crisp scaling and to avoid depending on missing sprite files.
- Spark stars are CSS-rendered star glyphs with filled/empty states. This keeps the UI sharp while preserving the visual meaning from the game screens.

## Implementation Files

- `public/index.html` contains the redesigned modal shells.
- `public/app.js` renders cards, detail panels, grade badges, spark chips, and filters.
- `public/styles.css` contains the desktop-only card/detail modal styling.
- `main.py` enriches `/api/career/history` entries with normalized aptitudes, sparks, skills, rank, race/win totals, and portrait URLs.
- `career_bot/runner.py` preserves final career skill/factor/win arrays in the compact final snapshot when available.
