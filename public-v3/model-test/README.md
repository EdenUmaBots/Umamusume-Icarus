# Seiun Sky PMX Preview

This folder contains the standalone web preview for the chibi Seiun Sky PMX model.

## Files

- `mini.html` - browser preview / renderer
- `seiun_sky.pmx` - PMX model
- `Texture2D/` - required model textures
- `start-preview.bat` - Windows launcher for local preview

## Requirements

- Windows with Chrome, Edge, or another modern browser
- Python installed and available as `py` or `python`
- Internet access, because `mini.html` loads Three.js from jsDelivr

## Run

Double-click `start-preview.bat`.

Or run this from the `model-test` folder:

```bat
py -3 -m http.server 8765 --bind 127.0.0.1
```

Then open:

```text
http://127.0.0.1:8765/mini.html?v=5
```

Do not open `mini.html` directly from the file system. Browser module/CORS rules can prevent the PMX and textures from loading correctly unless it is served over HTTP.

## QA URLs

- Normal spinning preview: `http://127.0.0.1:8765/mini.html?v=5`
- Frozen front view: `http://127.0.0.1:8765/mini.html?v=5&spin=0&angle=0`
