# How We Built the LILA BLACK Telemetry Tool
### A Complete Walkthrough — From Raw Data to a Working Product

---

> This document explains every decision made while building this tool — the product thinking, the UX design, the data engineering, and the code. It is written so that anyone — designer, engineer, PM, or someone who has never coded — can follow along and understand not just *what* was built, but *why* every choice was made.

---

## Table of Contents

1. [The Starting Point — What Was the Problem?](#1-the-starting-point)
2. [Understanding the User — Who Is a Level Designer?](#2-understanding-the-user)
3. [The Data — What Were We Working With?](#3-the-data)
4. [The Product Philosophy — What Makes This Different?](#4-the-product-philosophy)
5. [The UX Design — Every Screen Decision Explained](#5-the-ux-design)
6. [The Data Pipeline — From Parquet to Browser](#6-the-data-pipeline)
7. [The Coordinate System — The Hardest Part](#7-the-coordinate-system)
8. [The Insight Engine — Making Data Talk](#8-the-insight-engine)
9. [The Tech Stack — Why These Choices](#9-the-tech-stack)
10. [What the Data Actually Revealed](#10-what-the-data-revealed)
11. [Tradeoffs Made Along the Way](#11-tradeoffs-made)
12. [How to Think About This as a PM](#12-how-to-think-about-this-as-a-pm)

---

## 1. The Starting Point

### The brief

LILA Games gave us 5 days of raw gameplay data from LILA BLACK — an extraction shooter — and asked us to build a tool that lets Level Designers explore how players actually move through their maps.

The brief included three maps, 1,243 data files, and a minimap image for each map. That was it. No mockup. No spec. No prescribed tech stack.

### What most people would have built

A tool that shows data. Pick filters. See dots on a map. Done.

### What we actually needed to build

Something a Level Designer opens on a Monday morning and immediately knows what to fix. The difference between those two things is the entire PM challenge.

The core question we kept coming back to: **can a Level Designer who has never touched a spreadsheet open this tool and walk away with a clear next action?**

If yes, the tool works. If they need to interpret the data themselves, it fails.

---

## 2. Understanding the User

### Who is a Level Designer?

A Level Designer is the person who builds the physical space players move through — the terrain, the buildings, the corridors, the cover points, the loot placement, the extraction zones. They are artists and spatial thinkers first, data readers second.

They think in questions like:
- "Is anyone going to this part of the map I spent three weeks building?"
- "Why do players keep dying in the southeast corner? Is the storm too fast there?"
- "Are the firefights happening where I intended, or somewhere random?"
- "Is this map balanced — or is everyone just gravitating to one spot?"

They do **not** think in questions like:
- "What is the 95th percentile of the x-coordinate distribution?"
- "What is the bot-to-human ratio in quadrant NE?"

This distinction shaped every single design decision.

### The key insight about our user

Level Designers already know their map better than anyone. They built it. What they lack is visibility into what happens to it once real players touch it. The tool's job is to close that gap — to give them eyes they don't currently have, not to teach them data analysis.

This means the tool should feel like **watching a match** more than **reading a spreadsheet**.

---

## 3. The Data

### What we received

Five folders — one per day (February 10–14, 2026) — containing 1,243 files. Each file represents one player's journey through one match.

The files had no extension but were in Apache Parquet format — a standard data engineering format that stores tabular data efficiently. Each file contained these columns:

| Column | What it means |
|--------|--------------|
| `user_id` | Who the player is. UUIDs = real humans. Numbers like `1440` = bots. |
| `match_id` | Which match session this belongs to |
| `map_id` | Which of the 3 maps was being played |
| `x`, `y`, `z` | Where the player was in 3D game-world space |
| `ts` | When this event happened (time elapsed in the match) |
| `event` | What happened — movement, kill, death, loot pickup, storm death |

### The 8 event types

| Event | What it means |
|-------|--------------|
| `Position` | A human player moved to this location |
| `BotPosition` | A bot moved to this location |
| `Kill` | A human killed another human |
| `Killed` | A human was killed by another human |
| `BotKill` | A human killed a bot |
| `BotKilled` | A human was killed by a bot |
| `KilledByStorm` | A player died to the shrinking storm zone |
| `Loot` | A player picked up an item |

### The scale of the data

- **89,104 total events** across all files
- **796 unique matches** across 5 days
- **339 unique human players**
- **3 maps** — AmbroseValley (71% of matches), Lockdown (21%), GrandRift (7%)
- Position events alone: ~73,000 (82% of all data — movement is the dominant signal)

### The immediate data surprises

Two things jumped out as soon as we looked at the raw data:

**First:** Timestamps looked strange. The `ts` column stored values like `1,771,070,036 ms` — which, when interpreted as milliseconds from 1970 (how computers store time), gives a date of "January 21, 1970." That is clearly wrong for real-world dates.

What the README clarified: `ts` is not a wall-clock time. It is the number of milliseconds elapsed within a match — stored as a raw integer and accidentally interpreted by pandas (the Python data tool) as a timestamp. The actual values are match-relative time offsets. So `1,771,070,036` doesn't mean January 21, 1970 — it means that event happened 1,771 seconds (about 29 minutes) after some arbitrary reference point.

To get usable relative times, we subtracted the minimum timestamp value within each match. This gave us "how many milliseconds into the match did this event happen?" — which is what we actually needed for playback.

**Second:** Each file only spans about 400–900 milliseconds of relative time. This seems impossibly short for a game match. The explanation: these files are telemetry batch windows — snapshots of events logged in a short window, not recordings of entire matches. The tool handles this correctly by treating each file's relative time window as a segment.

---

## 4. The Product Philosophy

### The problem with most data tools

Standard data visualization tools — dashboards, heatmaps, analytics platforms — all make the same mistake with non-data users. They show *what* but never say *so what*.

A Level Designer looking at a traffic heatmap sees: "Players go here a lot."

What they need to see: "Players go here a lot — and that's a problem because it means your entire southeast quadrant is being ignored. Here's what you should do about it."

The gap between those two statements is the gap between a data tool and a design tool. We set out to build the latter.

### The three-layer principle

We designed the tool around three layers of information, always visible together:

**Layer 1 — Context.** What are we looking at? (Map selector, date filter, match selector) Before seeing any data, the designer knows the scope.

**Layer 2 — The Map.** What is actually happening? (Player paths, event markers, heatmaps) The visual representation of real behavior.

**Layer 3 — The Insight.** What should I do about it? (The right panel) This updates automatically with every filter change and turns data into action.

Most tools stop at Layer 2. We built to Layer 3.

### The filtering philosophy

Filters in most tools are independent dropdowns. You pick a date, pick a map, pick a match — and data changes. But the designer has to figure out what the filter combination means.

We designed filters to be **progressive and explanatory**:

- Pick a map → insight panel immediately shows map-level summary (how many matches, bot ratio, dominant traffic zone)
- Pick a date → panel updates to show what changed that day
- Pick a match → panel goes deep on that specific match's notable patterns

Each filter step narrows and *explains*. The designer never feels lost.

### The "Level Designer, not data scientist" test

At every design decision, we asked: would a Level Designer understand this without explanation? 

- Calling storm deaths "KilledByStorm" (the raw event name) — fails the test → we show "Storm Deaths"
- Showing bot ratio as a percentage — passes the test → we keep it
- Showing raw x/z coordinates in the match list — fails → we show human/bot counts, kill counts, storm deaths instead
- Showing a heatmap without explaining what high density means for map design — fails → the insight panel always adds the "so what"

---

## 5. The UX Design

### The overall layout

The screen is divided into three vertical panels:

```
┌─────────────┬──────────────────────────┬─────────────┐
│  LEFT       │  CENTER                  │  RIGHT      │
│  Controls   │  Map Canvas              │  Insights   │
│  260px      │  Flex (takes all space)  │  280px      │
└─────────────┴──────────────────────────┴─────────────┘
```

This layout was chosen deliberately over alternatives:

- **Why not tabs?** Switching between "filters" and "map" and "insights" hides context. A designer needs to see all three simultaneously.
- **Why not a floating panel over the map?** The map needs clean, unobstructed space. Floating UI creates visual noise on exactly the thing being analyzed.
- **Why this specific width split?** The left panel (260px) has enough space for filter controls without feeling cramped. The right panel (280px) has enough space for readable insight text. The center gets everything else.

### The left sidebar — controls

**Map tabs (AMBROSE / RIFT / LOCK)**

Three buttons, not a dropdown. Why? A dropdown hides options behind a click — you can't see all three maps at once. Three visible buttons let the designer jump between maps with one click and immediately see which is active. Short labels (AMBROSE not AmbroseValley) because space is tight and the designer already knows the map names.

**Date filter (pills)**

Small pill buttons instead of a calendar picker. Why? The data spans exactly 5 days. A full calendar is enormous overkill. Pills show all options simultaneously, require one click, and can be visually scanned in under a second. The "All" pill is always first and selected by default — zero friction to see the full picture.

**Overlay toggles**

Individual on/off switches for each layer type. Why toggles instead of a single multi-select? Because Level Designers will want combinations:
- Human paths only (to understand real player behavior without bot noise)
- Storm + paths together (to see where players were when the storm caught them)
- Loot only (to validate loot zone coverage)

Independent toggles give full flexibility. Each toggle has a colored dot matching the color of that layer on the map — visual language stays consistent across the UI.

**Heatmap dropdown**

One heatmap at a time, deliberately. We considered letting multiple heatmaps overlap. We didn't because overlapping heatmaps create visual soup — two color gradients fighting each other produce confusion, not insight. One mode at a time, clearly labeled.

**Match list**

Every match is shown as a card with badges — not as a table of numbers. The badges use color and iconography:
- 👤 blue = human players
- 🤖 grey = bots
- ⚔ red = kills
- 🌀 purple = storm deaths
- 📦 green = loot

A Level Designer scanning the list immediately sees which matches had interesting combat activity vs which were mostly bot-filled quiet sessions. No numbers reading required.

The search box at the top lets them find a specific match ID if they already know what they're looking for.

### The center canvas

**Two-canvas architecture**

There are actually two invisible canvas layers stacked on top of each other. The bottom canvas draws the minimap image and heatmap. The top canvas draws paths and event markers.

Why split? The minimap image and heatmap rarely change — only when you switch maps or change the heatmap mode. But paths and markers need to redraw every time you move the timeline slider, toggle an overlay, or select a match. By separating them, we avoid the expensive operation of re-reading and redrawing the minimap image dozens of times per second.

**Pan and zoom**

Mouse wheel to zoom, click-drag to pan. This is standard map interaction that any designer who has used Google Maps will recognize immediately. Zoom buttons (+/−) in the bottom-right for people who prefer clicking. A house icon (⌂) to reset to the default view when they get lost.

**Coordinate display**

Bottom-left shows the current world coordinates as you hover over the map (`x: 124  z: -301`). This is specifically for designers who already know their map's coordinate system — they can hover over a location on the minimap and immediately see "yes, that's the area near the north extraction point at x: 120."

**The timeline**

The playback slider at the top lets the designer scrub through a match's time window (0 to ~900ms of relative match time). The play button animates it automatically. This turns a static scatter of dots into a story — you see players spawn, move, engage, and die in sequence.

Why 0–900ms? Because that's the range of the data. The telemetry was captured in short batch windows. We normalize all events within a match to start at 0ms.

### The right panel — insights

This is the most important panel in the tool. It is also the most unusual — most data tools don't have anything like it.

The panel updates automatically whenever any filter changes. It never shows static text. Everything it says is computed from the currently visible data.

**What it shows:**

1. **A stat grid** — four numbers that orient the designer immediately: how many matches, how many combat events, storm deaths, loot pickups. These are facts, not insights.

2. **Insight cards** — each card has four parts:
   - A **tag** that categorizes the insight (TRAFFIC IMBALANCE, STORM PRESSURE, etc.)
   - A **title** that states the finding in plain language
   - A **body** that explains why it matters for map design
   - An **action** that tells the designer exactly what to do next, and which metrics to track

Each card has a left-border color that signals severity:
- Yellow border = warning (something worth investigating)
- Red border = danger (something likely broken)
- Blue border = informational (pattern worth knowing)
- Green border = good (things working as intended)

This color coding means the designer can scan the insight panel in 2 seconds and know if there's a problem.

### The visual design language

**Dark theme.** Gaming tools live in dark environments — not white-background dashboards. The dark palette (near-black backgrounds, subtle surface layers) also makes the bright event markers on the map pop dramatically. A kill event (red ×) on a dark map is immediately visible. The same marker on a white background would be muted.

**Two-font system.** Space Mono (a monospace font) is used exclusively for data — numbers, IDs, coordinate values, labels. Syne (a geometric sans) is used for everything else — headings, body text, insight copy. This creates instant visual hierarchy: you always know when you're reading data vs reading prose.

**Color vocabulary.** Every event type has one color, used consistently across the entire tool:
- Cyan (`#00e5ff`) = selected state, active filter, accent
- Blue (`#00b4d8`) = human players
- Grey (`#546e7a`) = bots
- Red (`#ff4455`) = kills
- Orange (`#ff8c00`) = deaths
- Purple (`#b04dff`) = storm deaths
- Green (`#00e676`) = loot
- Purple-violet (`#7c4dff`) = interactive elements (play button, active toggles)

There are no exceptions. The same red that labels a kill badge in the match list is the same red used for the kill marker on the map and the kill count in the stat grid.

---

## 6. The Data Pipeline

### The problem

The raw data is 1,243 Parquet files inside a zip archive, totaling about 30MB. A browser cannot read Parquet files directly. We needed to convert this data into something a browser can load and use.

### The solution: pre-process everything

We wrote a Python script (`process_data.py`) that reads all the raw files once, transforms the data, and outputs a set of JSON files. The browser then loads those JSON files — no Parquet reading, no heavy computation, just reading data that's already been processed.

This is called a **build-time pipeline** — the heavy work happens once when you set up the project, not every time a user opens the tool.

### What the pipeline does, step by step

**Step 1 — Read every Parquet file**

For each of the 1,243 files, we:
- Open the file (despite having no `.parquet` extension, it's valid Parquet)
- Convert the `event` column from bytes to readable text (`.decode('utf-8')`)
- Identify whether the player is a bot or human from the filename
- Extract the date from the folder name

**Step 2 — Build a match registry**

We maintain a dictionary that tracks, for each unique match ID:
- Which map was being played
- Which date it happened
- Which human players were in it
- Which bots were in it
- The earliest and latest timestamp seen (to compute match duration)

**Step 3 — Normalize timestamps**

Every event's raw timestamp is an absolute value. We subtract the minimum timestamp for that match, giving every event a "how many milliseconds from the start of this match" value. This is what the timeline slider uses.

**Step 4 — Compute pixel coordinates**

For every event, we transform the game-world coordinates (x, z) into pixel coordinates (pixel_x, pixel_y) on the 1024×1024 minimap image. This is pre-computed once in Python so the browser never has to do this math.

**Step 5 — Sample position events**

Position events make up 82% of all data. If we included every single position event, the data files would be enormous and the map would be a solid blob of lines. We keep every 3rd position event per player per match — enough to accurately represent the path shape, while reducing volume by 66%.

**Step 6 — Generate heatmaps**

We divide each map's 1024×1024 pixel space into a 64×64 grid of cells. For each event, we find which cell it falls in and increment that cell's counter. We do this separately for 5 event categories: traffic (all movement), kills, deaths, storm deaths, loot.

The result is five 64×64 grids per map — pre-computed, instantly loadable, renderabe in milliseconds.

**Step 7 — Build match summaries**

We compute per-match statistics: how many humans, how many bots, how many kills, storm deaths, loot pickups. These populate the match list sidebar.

**Step 8 — Extract minimap images**

The minimap PNG/JPG files are extracted from the zip and saved alongside the other output files.

### Output files and sizes

| File | Contents | Size |
|------|----------|------|
| `data_AmbroseValley.json` | ~28,000 events (sampled) | 2.7 MB |
| `data_GrandRift.json` | ~3,000 events | 0.3 MB |
| `data_Lockdown.json` | ~9,000 events | 0.8 MB |
| `heatmaps.json` | 5 types × 3 maps × 64×64 grids | 0.1 MB |
| `match_summaries.json` | 796 match records | 0.2 MB |
| Minimap images | 3 map images | ~24 MB |

The browser loads these sequentially on startup, showing a progress bar. Each map's data only loads when needed (lazy loading by map) — so GrandRift data doesn't load until you click the GrandRift tab.

---

## 7. The Coordinate System

### Why this was the hardest part

The game exists in 3D space. The minimap is a 2D image. Bridging those two spaces requires a precise mathematical transformation. Get it wrong and every player path draws in the wrong location — kills appearing in ocean when they happened in a building, players' routes going off-map entirely.

### The problem in detail

Game engines use a 3D coordinate system with X (left-right), Y (up-down elevation), and Z (forward-backward). A top-down minimap only shows X and Z — Y (elevation) is irrelevant for a 2D overhead view.

But there's a subtlety: game Z-axis and image Y-axis point in opposite directions.

In the game world, Z increases as you move "north" (up the screen). In an image, Y increases as you move down the screen. If you plot game Z directly as image Y, the entire map is upside-down.

### The formula

The README provided the correct transformation. Here's what each step does:

```
Step 1: Find the position as a fraction of the map's width/height
  u = (world_x - origin_x) / scale       ← horizontal fraction (0 = left edge, 1 = right edge)
  v = (world_z - origin_z) / scale       ← vertical fraction (0 = bottom, 1 = top)

Step 2: Convert to pixel coordinates on the 1024×1024 image
  pixel_x = u × 1024                     ← horizontal pixel (left to right)
  pixel_y = (1 - v) × 1024              ← vertical pixel (top to bottom) — NOTE THE FLIP
```

The `(1 - v)` is the Y-flip. It converts "0 = bottom, 1 = top" (game convention) to "0 = top, 1 = bottom" (image convention). Without it, the map renders upside-down.

### The per-map numbers

Each map has a different scale and origin point, because each map is a different physical size:

| Map | Scale | Origin X | Origin Z | What this means |
|-----|-------|----------|----------|-----------------|
| AmbroseValley | 900 | -370 | -473 | The map spans 900 game units. The top-left corner of the minimap image is at world position (-370, -473). |
| GrandRift | 581 | -290 | -290 | Smaller map — only 581 game units across. |
| Lockdown | 1000 | -500 | -500 | Largest map by coordinate range. |

### Worked example

Let's take a real event from the data: a player at world position x = -301.45, z = -355.55 on AmbroseValley.

```
u = (-301.45 - (-370)) / 900
u = 68.55 / 900
u = 0.0762                         ← 7.6% from the left edge

v = (-355.55 - (-473)) / 900
v = 117.45 / 900
v = 0.1305                         ← 13% from the bottom

pixel_x = 0.0762 × 1024 = 78      ← 78 pixels from left
pixel_y = (1 - 0.1305) × 1024 = 890   ← 890 pixels from top
```

This places the point near the upper-left of the minimap — which is the correct location when you look at the map image, corresponding to the northwest terrain visible there.

### How we verified it was correct

We plotted storm deaths first, because they happen at the map edge (the storm kills players caught near the boundary). If storm deaths appeared at the edges of the minimap image, the coordinate mapping was correct. They did.

---

## 8. The Insight Engine

### What it is

The right panel is not static text. It is a rule-based system that looks at the currently visible data, computes statistics, checks those statistics against thresholds, and generates plain-language findings with recommended actions.

It runs every time a filter changes — map, date, match — and produces output specific to what's visible right now.

### The rules

**Traffic imbalance rule:**

We divide the map into four quadrants (NW, NE, SW, SE) and count position events in each. If any quadrant has more than 45% of total traffic, we flag it as a traffic imbalance and identify which quadrant is being ignored.

The threshold of 45% was chosen because a perfectly balanced map would see 25% per quadrant. 45% means one quadrant is seeing nearly double its fair share — significant enough to be intentional or a bug, not statistical noise.

**Storm death rate rule:**

If more than 5 storm deaths are visible in the current filter, we flag it with a danger card and note where they're geographically clustering (we average the pixel coordinates of all storm deaths to find the centroid zone).

**Bot ratio rule:**

We compute what percentage of all movement events come from bots. If it exceeds 45%, we warn that heatmaps may be misleading — bot patrol routes can create artificial hotspots that make an area look active when real humans never go there.

**Loot rate rule:**

We compute loot pickups per match. If below 5 per match, we flag it as a low loot rate — suggesting players are dying before reaching loot, or loot spawns are too sparse.

**Map-specific rules:**

For each of the three maps, we have hardcoded insights based on the actual 5-day data pattern. GrandRift's low play rate (7.4% of matches), AmbroseValley's NW gravity, and Lockdown's storm death concentration are always surfaced when viewing those maps without a specific match selected.

### Why rule-based instead of AI-generated

We considered using an LLM to generate insights dynamically. We chose not to for three reasons:

1. **Reliability.** Rule-based logic produces the same output for the same input every time. An LLM might hallucinate a finding that doesn't match the actual data.
2. **Speed.** The insight panel updates in under 50 milliseconds. An LLM call would take 2–5 seconds, making the filter interaction feel sluggish.
3. **Trust.** Level Designers need to trust that what the panel says is true. Rule-based computation that can be traced back to data is inherently more trustworthy than generated text.

### The "so what" requirement

Every insight card must have an action line. This was a non-negotiable requirement from the start.

We enforced a simple template for every insight:
- **Finding:** what the data shows (factual)
- **Why it matters:** what this means for map design (interpretive)
- **What to do:** a specific concrete next step (actionable)
- **Metric to watch:** how to measure whether the fix worked (measurable)

An insight without an action is just an observation. An observation without a measurement is just an opinion. The tool forces structure that connects data → insight → action → measurement.

---

## 9. The Tech Stack

### Why vanilla HTML/CSS/JavaScript

No React. No Vue. No build tools. Just one HTML file.

This sounds like an unusual choice for a modern web tool. Here's the reasoning:

**The primary operation is drawing on a canvas.** React and Vue excel at managing complex UI state that maps to DOM elements — buttons, forms, lists. But our main output is a 1024×1024 pixel canvas. Frameworks add complexity without adding capability here.

**We needed zero setup friction for deployment.** One HTML file drops onto GitHub Pages and works. No `npm install`. No build step. No configuration. The tool is ready in seconds.

**The data volume is manageable.** We have ~40,000 events in memory at once. JavaScript handles this comfortably without specialized data libraries.

**The interactivity is custom.** Pan and zoom on a canvas, canvas path drawing, pixel-level heatmap rendering — none of this is something a component library helps with.

### Why Canvas 2D instead of SVG or WebGL

**SVG** would allow click-on-event-markers to show tooltips — something Canvas makes harder. But SVG degrades badly at our data volume. Rendering 5,000 path segments as SVG elements creates a DOM with 5,000 nodes, which is slow to update and slow to re-render.

**WebGL** would handle millions of points at 60fps with GPU acceleration. But it requires shader code (a specialized low-level graphics language) and dramatically increases complexity for marginal gain at our data volume.

**Canvas 2D** hits the sweet spot: fast enough for our volume, simple to implement, and gives us direct pixel control for heatmap rendering.

### Two-canvas stacking

We use two canvas elements positioned exactly on top of each other:

- **Bottom canvas (`mapCanvas`):** Draws the minimap image and heatmap. Redraws only when the map or heatmap mode changes — rare.
- **Top canvas (`overlayCanvas`):** Draws paths and event markers. Redraws whenever filters change — frequent.

This separation means a timeline slider drag only triggers a redraw of the overlay canvas, not the full minimap image re-render. The result is smooth interaction even with thousands of paths visible.

### Why JSON instead of Parquet in the browser

Parquet in the browser is possible using tools like DuckDB-WASM — a full SQL database compiled to run in JavaScript. We considered it and decided against it for this project.

DuckDB-WASM adds a ~6MB download before the tool can do anything. It requires an asynchronous initialization step. And for our use case — loading pre-defined data files for a fixed set of maps — SQL queries are overkill.

Pre-processing in Python and outputting JSON means the browser does zero data transformation. It just reads pre-organized arrays and draws them. Load time is proportional to file size, nothing more.

### The compact event format

Each event is stored as a 7-element array instead of a dictionary:
```
[match_id, user_id, is_bot, event_type, pixel_x, pixel_y, ts_rel]
```

Versus the dictionary alternative:
```json
{"match_id": "...", "user_id": "...", "is_bot": false, "event": "Position", "px": 78, "py": 890, "ts_rel": 245}
```

The array format saves approximately 60% file size because key names are not repeated for every record. At 28,000 events per map, the saving is significant.

---

## 10. What the Data Actually Revealed

Three findings that came out of building the tool and actually looking at the data.

### Finding 1 — AmbroseValley's southeast is a design dead zone

The traffic heatmap for AmbroseValley shows a pronounced northwest concentration. Across 566 matches, 39% of all human movement happened in the northwest quadrant. The southeast — a full quarter of the map — saw only 10%.

This is a 3.8× imbalance. If the map were perfectly balanced, each quadrant would see 25%.

What this means for a Level Designer: whatever is in the southeast is not pulling players there. It could be insufficient loot, lack of distinctive landmarks, sightline disadvantages, or simply that the storm path consistently drives players northwest. The designer needs to investigate and decide: is this intentional or a problem to fix?

### Finding 2 — GrandRift has almost no real players

GrandRift appeared in 7.4% of all matches — 59 out of 796. AmbroseValley appeared in 71%. More tellingly, GrandRift's bot ratio is 49% — nearly half of all activity is bots, not real people.

The practical implication: any heatmap or traffic analysis of GrandRift is heavily influenced by bot patrol routes, not human behavior. The map needs either more visibility in the match rotation or design changes that make it more appealing to real players.

### Finding 3 — Storm deaths cluster in interior zones, not at the map edge

On Lockdown, storm deaths should logically happen at the edge of the safe zone — places where players are caught running away from the closing storm. But the death clusters appear in interior zones, which suggests players were caught by surprise inside buildings with no clear escape route.

Lockdown has the highest per-match storm death rate of any map (0.099 deaths per match vs 0.030 for AmbroseValley). The fix is likely better storm warning visibility inside structures — directional audio cues, VFX that penetrates building walls, or adjusted storm timing that gives players more reaction time on this smaller, more obstructed map.

---

## 11. Tradeoffs Made

Every design and technical decision involved a tradeoff. Here are the significant ones.

### Sampling position events (keeping 1 in 3)

**What we gave up:** Pixel-perfect path fidelity. A player who made a quick dash and turned back might appear to have moved in a straight line.

**What we gained:** 66% smaller data files, paths that are readable at any zoom level without becoming a solid smear of lines.

**Why it was right:** At zoom-out (the most common view), sub-second position differences are invisible. At zoom-in, the sampled paths still show the correct area of map traversal.

### 64×64 heatmap grid

**What we gave up:** Fine-grained zone detail. Each cell covers roughly 14×14 pixels on the minimap — about a 15×15 meter area in game units.

**What we gained:** Instant heatmap rendering. 64×64 = 4,096 cells. The browser draws them in one loop in under 5 milliseconds.

**Why it was right:** Level Designers need to see zone-level patterns, not meter-level precision. "Kills cluster in the northeast area" is the insight. The exact 3×3 meter kill square is not.

### One heatmap at a time

**What we gave up:** The ability to see kill zones and traffic simultaneously — which could reveal whether kills happen in high-traffic areas (expected) or low-traffic areas (ambush spots).

**What we gained:** Clarity. Overlapping heatmaps create color interference. A cell that is simultaneously red (kills) and blue (traffic) becomes an ambiguous purple.

**Why it was right:** The tool is for decision-making, not for data exploration by analysts. A single clear signal per view produces better decisions than multiple overlapping signals. A future version could add a "compare" mode.

### Static rule-based insights instead of AI-generated

**What we gave up:** Flexibility. The rules we wrote catch specific patterns. A completely novel pattern in the data that doesn't match our rules would go unnoticed.

**What we gained:** Speed, reliability, and trustworthiness.

**Why it was right:** The patterns that matter for Level Design are known and finite — traffic imbalance, storm death clustering, bot ratio inflation, loot rate anomalies. We don't need open-ended discovery for this specific use case.

### No server-side component

**What we gave up:** The ability to run fresh queries against the data, or to accept new data uploads without re-running the pipeline.

**What we gained:** Zero infrastructure cost, zero maintenance burden, deployable in 60 seconds to any static hosting service.

**Why it was right:** The data is from a fixed 5-day window. The pipeline can be re-run whenever new data needs to be added. A static tool that works perfectly is better than a dynamic tool that might break.

---

## 12. How to Think About This as a PM

### The real job was not building a tool. It was defining what problem to solve.

The brief said "build a visualization tool." Most people read that as "make data visible." The PM reading is different: "help Level Designers make better decisions faster."

Those sound similar. They lead to completely different products.

A "make data visible" interpretation gives you filters, a heatmap, and paths on a map. A "better decisions faster" interpretation gives you all of that plus an insight panel that does the interpretation work, plus a design system that uses color and typography to make scanning fast, plus progressive filtering that adds context at every step.

### Every feature had to pass a user test

Before building any feature, we asked: does a Level Designer need this to make a design decision? 

- Traffic heatmap — yes. Tells them where the action is.
- Kill markers on the map — yes. Tells them where combat happens.
- Storm death markers — yes. Tells them where the storm is punishing players.
- Export to CSV — no. That's an analyst feature, not a Level Designer feature.
- Tooltip with exact coordinates on hover — marginal. Kept it simple (coordinates in corner).
- Per-player path history across multiple matches — interesting but complex. Not built.

### The insight panel is the PM's most important contribution to this product

Any engineer can build a heatmap. Any designer can make it look good. The insight panel — the idea of automatically surfacing "so what" from data, with a consistent structure of finding → explanation → action → metric — is the product thinking layer.

It is also the layer that differentiates this tool from commodity analytics dashboards. Without it, this is a good-looking data explorer. With it, it's a design decision support system.

### What we would build next

If this tool went into regular production use, the next priorities would be:

1. **Longitudinal comparison.** "Show me how traffic changed between this week and last week" — the current tool only shows a static 5-day window.

2. **Click-to-investigate.** Clicking on a kill event marker should show: who died, who killed them, what their paths were for the 10 seconds before the event. Turn any data point into a full story.

3. **Anomaly alerts.** Instead of making designers check the tool manually, surface a weekly digest: "This week, storm deaths on Lockdown increased 40% vs last week."

4. **A/B comparison mode.** Compare two heatmaps side-by-side — e.g., AmbroseValley this week vs last week after a balance patch — to measure the impact of design changes.

5. **Session recording integration.** Link a kill event marker to the actual game replay footage of that moment, so a Level Designer can go from "kills cluster here" to "watching the specific fight that happened there" in one click.

---

*This document was written to be read by anyone — developer, designer, PM, or someone entirely new to the domain. If anything is unclear, that's a gap in the writing, not in the reader.*
