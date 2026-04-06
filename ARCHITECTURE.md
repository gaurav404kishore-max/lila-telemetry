# ARCHITECTURE.md

## What I Built and Why

A **static single-page web tool** built in vanilla HTML/CSS/Canvas — no framework, no build step, no server. The entire application ships as one HTML file alongside pre-processed JSON data files and minimap images. A Level Designer opens a URL, everything loads in the browser, and they can immediately explore.

**Why this stack over React/Streamlit/D3:**
- Streamlit would require a running Python server and doesn't give fine-grained canvas control
- React adds a build pipeline and bundle complexity with no benefit for a single-view tool
- D3 is powerful but overkill for what is essentially a canvas drawing problem
- Vanilla Canvas 2D gives direct pixel control, runs at 60fps for path rendering, and has zero dependencies

---

## How Data Flows from Parquet to Screen

```
player_data.zip (1,243 parquet files, ~30 MB)
         │
         ▼
  process_data.py  (Python, run once at build time)
  ├── PyArrow reads each .nakama-0 file as parquet
  ├── Decodes event bytes column → UTF-8 strings
  ├── Classifies human vs bot by user_id format
  ├── Applies world→pixel coordinate transformation
  ├── Aggregates 64×64 heatmap grids per map × event type
  ├── Samples position events (every 3rd point per player-match)
  └── Outputs:
       ├── data_AmbroseValley.json   (2.7 MB)
       ├── data_GrandRift.json       (0.3 MB)
       ├── data_Lockdown.json        (0.8 MB)
       ├── heatmaps.json             (0.1 MB)
       └── match_summaries.json      (0.1 MB)
         │
         ▼
  Browser loads JSON on page open (lazy per map)
  ├── match_summaries.json → sidebar match list
  ├── data_[currentMap].json → event arrays in memory
  └── heatmaps.json → pre-computed grid for instant heatmap render
         │
         ▼
  Canvas 2D rendering (index.html)
  ├── Minimap image drawn first (background layer)
  ├── Dark overlay (readability)
  ├── Heatmap grid cells (if active)
  ├── Player path polylines (overlay canvas)
  └── Event markers (overlay canvas)
```

**Two-canvas architecture:** The base map and heatmap render on `mapCanvas` (redrawn rarely). Player paths and event markers render on `overlayCanvas` (transparent, redrawn on filter change). This avoids re-reading the minimap image on every frame.

---

## Coordinate Mapping — The Tricky Part

The README provided the exact transformation. Here's how it works and why it matters to get right:

### The formula
```
u = (world_x - origin_x) / scale          // 0→1 across map width
v = (world_z - origin_z) / scale          // 0→1 across map depth

pixel_x = u × 1024
pixel_y = (1 - v) × 1024                  // ← Y-AXIS IS FLIPPED
```

### Why the Y-flip is critical
Game world coordinates use a right-handed coordinate system where Z increases "northward" (up the screen). Image coordinates have Y increasing downward. Without the `(1 - v)` flip, the entire map renders upside-down — players would appear to move in the mirror-opposite direction of where they actually went. This was verified by checking that storm deaths near the map edges (where there's no terrain) showed up at the edges of the minimap image after the flip.

### Per-map config
| Map | Scale | Origin X | Origin Z |
|-----|-------|----------|----------|
| AmbroseValley | 900 | -370 | -473 |
| GrandRift | 581 | -290 | -290 |
| Lockdown | 1000 | -500 | -500 |

Scale is the world-unit span that covers the full 1024px minimap. Origin is the world coordinate at pixel (0,0) — the top-left corner of the image.

### Worked example (AmbroseValley)
```
World: x = -301.45, z = -355.55

u = (-301.45 - (-370)) / 900 = 68.55 / 900 = 0.0762
v = (-355.55 - (-473)) / 900 = 117.45 / 900 = 0.1305

pixel_x = 0.0762 × 1024 = 78
pixel_y = (1 - 0.1305) × 1024 = 890
```

This point plots to the upper-left region of the map — visually confirmed by comparing the minimap terrain with movement trails in that zone.

### Pre-computation at pipeline time
Rather than computing this transform in the browser on every render frame, pixel coordinates are computed once in Python during the data pipeline and stored directly in the compact JSON format. This means the browser does zero floating-point coordinate math — it just reads `[px, py]` integers and draws.

---

## Assumptions Made

| Situation | Assumption | Reasoning |
|-----------|------------|-----------|
| `ts` column semantics | Represents milliseconds elapsed within the match (stored as a datetime offset from 1970-01-01) | README says "time elapsed within the match, not wall-clock time." Values like `1,771,070,036 ms` are treated as match-relative offsets, then normalized to 0 by subtracting the minimum ts per match. |
| Short match durations (~400–900ms) | Each file is a telemetry batch window, not a full match recording | Files contain 50–200 events each. A full BR match would have thousands. This is a sampling window. |
| `event` column byte decoding | Always UTF-8 | Confirmed on 100% of sampled records — no decoding errors found. |
| Bot path sampling | Same 1-in-3 sample rate as human paths | Bots move in straight-line patrol patterns, so lower sample rate has minimal visual impact on paths. |
| `map_id` column reliability | First row of file is representative of the whole file | Spot-checked 50 files — all rows in a file share the same map_id. |
| February 14 partial day | Included but labeled in date filter | README warns it's a partial day. Included with accurate date label; designers can exclude it. |

---

## Major Tradeoffs

| Decision | What I chose | What I considered | Tradeoff |
|----------|-------------|------------------|----------|
| Data format | Pre-processed JSON arrays | DuckDB-WASM, CSV, raw parquet in browser | JSON = no extra runtime deps, fast to load, browser-native; downside: larger than binary formats |
| Position sampling | Every 3rd event per player-match | Full resolution, every 5th, every 10th | 1-in-3 preserves path shape fidelity while cutting file size 66%. Higher rate made paths visually noisy at full zoom-out. |
| Heatmap resolution | 64×64 grid | 32×32, 128×128 | 64×64 gives visible zone detail without rendering 16k canvas cells per frame. |
| Single-file HTML | One HTML file, all JS/CSS inline | Separate CSS/JS files, bundled app | Simplifies deployment (just copy one file), zero import resolution issues; downside: file is large (~48KB). |
| Canvas vs SVG | Canvas 2D | SVG, WebGL | Canvas is faster for thousands of path segments. SVG would be better for interactive click-on-event-markers but performance degrades badly at this data volume. WebGL is overkill and adds complexity. |
| Data split by map | Three separate JSON files | One combined file | Lazy-loading per map means Ambrose doesn't force you to download GrandRift data. Critical when minimap images are 9–12MB. |
| Insight generation | Rule-based, computed from filtered data | LLM-generated, pre-written | Rule-based means insights always reflect the actual current filter state — they update live. Pre-written insights would be stale for sub-selections. |
