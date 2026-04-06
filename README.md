# LILA BLACK — Level Designer Telemetry Tool

A browser-based visualization tool for exploring player behavior across LILA BLACK's three maps. Built for Level Designers — shows where players move, fight, loot, and die to the storm, with actionable insights surfaced automatically on every filter change.

**Live URL:** _[deploy and paste here]_

---

## Tech Stack

| Layer | Choice | Why |
|-------|--------|-----|
| Frontend | Vanilla HTML/CSS/JS (single file) | Zero build tooling, instant deploy, no framework overhead for a canvas-heavy app |
| Rendering | Canvas 2D API | Direct pixel control for paths, heatmaps, and event markers at 1024×1024 resolution |
| Data pipeline | Python + PyArrow + pandas | Parquet reading, coordinate transformation, heatmap pre-aggregation |
| Data format | JSON (per-map compact arrays) | Browser-native, no WASM or additional parsers needed |
| Hosting | GitHub Pages / Vercel (static) | No server required — all data is pre-processed at build time |
| Fonts | Space Mono + Syne (Google Fonts) | Monospace for data readability; geometric sans for UI labels |

---

## Setup & Running Locally

### Prerequisites
- Python 3.9+
- Node.js not required (static site)

### Install Python deps
```bash
pip install pyarrow pandas
```

### Data pipeline (already pre-run — outputs committed to repo)
```bash
python3 process_data.py   # reads player_data.zip, outputs data_*.json + heatmaps.json + match_summaries.json
```

### Run locally
```bash
# Any static file server works
python3 -m http.server 8080
# then open http://localhost:8080
```

### Deploy to GitHub Pages
```bash
git init
git add .
git commit -m "init"
git remote add origin https://github.com/YOUR_USERNAME/lila-telemetry.git
git push -u origin main
# Enable Pages in repo settings → Source: main branch
```

### Deploy to Vercel
```bash
npx vercel --prod
# Set output directory to . (root)
```

---

## Environment Variables

None required. All data is static JSON served alongside the HTML file.

---

## File Structure

```
lila-telemetry/
├── index.html                  # Complete application (single file)
├── match_summaries.json        # Match metadata: map, date, player counts, event counts
├── data_AmbroseValley.json     # Compact event arrays for AmbroseValley
├── data_GrandRift.json         # Compact event arrays for GrandRift
├── data_Lockdown.json          # Compact event arrays for Lockdown
├── heatmaps.json               # Pre-aggregated 64×64 heatmap grids (all maps × all types)
├── AmbroseValley_Minimap.png   # 1024×1024 minimap image
├── GrandRift_Minimap.png       # 1024×1024 minimap image
├── Lockdown_Minimap.jpg        # 1024×1024 minimap image
├── README.md
├── ARCHITECTURE.md
└── INSIGHTS.md
```

---

## Features

- **Map viewer** — Switch between AmbroseValley, GrandRift, and Lockdown with per-map minimap background
- **Player paths** — Human (blue) and bot (grey) movement trails, toggleable independently
- **Event markers** — Kills (red ×), deaths (orange ○), storm deaths (purple ◆), loot (green dot)
- **5 heatmap modes** — Traffic density, kill zones, death zones, storm death zones, loot hotspots
- **Match sidebar** — All matches listed with human/bot/kill/storm/loot badges, searchable
- **Date filter** — Filter to any of the 5 days of data
- **Timeline playback** — Scrub or auto-play through a match's event sequence
- **Insight panel** — Automatically surfaces actionable observations (traffic imbalance, storm clustering, bot ratio warnings, loot rate flags) on every filter change
- **Pan & zoom** — Mouse wheel zoom, click-drag pan, reset button

---

## Data Format Notes

### Compact event array schema
Each `data_[Map].json` is a JSON array of arrays:
```
[match_id, user_id, is_bot(0/1), event_type, pixel_x, pixel_y, ts_rel_ms]
```
Pixel coordinates are pre-computed from world coordinates using the map config (see ARCHITECTURE.md).

### Heatmap schema
`heatmaps.json` structure:
```json
{
  "AmbroseValley": {
    "traffic": [[int, ...], ...],   // 64×64 grid, row-major (y first)
    "kills": [[...]],
    "deaths": [[...]],
    "storm_deaths": [[...]],
    "loot": [[...]]
  },
  ...
}
```
