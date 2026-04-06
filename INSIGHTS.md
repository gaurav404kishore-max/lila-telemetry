# INSIGHTS.md

Three findings from the data that a Level Designer should act on.

---

## Insight 1 — AmbroseValley's Northwest Is a Gravity Well

### What caught my eye
When I rendered the traffic heatmap for AmbroseValley (the most-played map, 566 of 796 matches), the northwest quadrant lit up immediately. I expected some imbalance, but not this extreme.

### The data
Counting position events per map quadrant across all human movement on AmbroseValley:

| Quadrant | Events | Share |
|----------|--------|-------|
| Northwest | 14,215 | **39.3%** |
| Southwest | 11,413 | 31.5% |
| Northeast | 6,814 | 18.8% |
| Southeast | 3,747 | **10.4%** |

The NW quadrant sees **3.8× more human traffic than SE**. This isn't a slight skew — it's a consistent pattern across 5 days and hundreds of matches.

### Why a Level Designer should care
If this distribution is unintentional, it means roughly 60% of the map is absorbing 90% of player attention. Players aren't experiencing the full designed space. Loot placed in the SE sector is effectively wasted — it's not being reached. Encounter design in the west corridors will be overloaded.

If it *is* intentional (e.g., the storm consistently pushes from east to west), that's fine — but then the SE quadrant should be validated as a "passthrough only" zone, not a designed engagement area.

### Actionable next steps
1. **Map overlay check:** Overlay loot spawn locations on the traffic heatmap. If high-value loot exists in SE, it's not being found — consider relocating or adding breadcrumb loot trails to pull players east.
2. **Storm path audit:** Check if storm collapse direction is consistently driving players northwest. If so, consider rotating storm direction in some match variants.
3. **POI placement:** The SE quadrant needs a reason to exist — a high-value extraction point, a unique mechanic, or a distinctive visual landmark that registers on the minimap.

**Metrics to watch:** Zone entry rate by quadrant (% of matches where ≥1 player enters SE), average loot pickups per zone, player-minutes spent per quadrant.

---

## Insight 2 — GrandRift Is Statistically Invisible

### What caught my eye
Sorting the match list by volume and switching between maps made the disparity obvious. AmbroseValley had hundreds of matches — GrandRift had tens. I initially assumed it was a data issue, but it's real.

### The data
| Map | Matches | % of Total | Avg Humans/Match | Avg Bots/Match | Bot Ratio |
|-----|---------|-----------|-----------------|---------------|-----------|
| AmbroseValley | 566 | **71.1%** | 1.0 | 0.5 | 34% |
| Lockdown | 171 | **21.5%** | 1.0 | 0.7 | 42% |
| GrandRift | 59 | **7.4%** | 1.0 | 0.9 | **49%** |

GrandRift is in **7.4% of matches** while having the **highest bot ratio** of any map. Every match averages 1.0 humans — but nearly 1.0 bots. The map is essentially a bot playground. Human players are nearly absent.

Additionally: GrandRift has only 5 storm deaths total (vs 17 each for the other maps), 880 loot pickups (vs 9,955 for Ambrose), and essentially zero human-vs-human kills recorded.

### Why a Level Designer should care
A map that sees 7% of sessions either has a matchmaking/rotation problem (the map isn't entering rotation) or a player preference problem (players are leaving when they land on it). Either way, design investment in GrandRift is currently seeing almost no return. The high bot ratio is a red flag — real players aren't staying.

The low loot pickup count confirms players aren't completing their intended gameplay loop on this map. They're either extracting early or dying before reaching loot zones.

### Actionable next steps
1. **Retention check:** Instrument match duration on GrandRift vs other maps. If sessions are significantly shorter, players are either dying fast or voluntarily extracting early.
2. **Loot density review:** 880 loot pickups across 59 matches = ~15 per match vs ~17 for Lockdown and ~17 for Ambrose. Loot density isn't dramatically different — the problem may be map flow, not loot spawn rates.
3. **Map layout audit:** With the tool's path overlay, compare bot patrol routes vs human movement paths on GrandRift. If they diverge significantly, the map may be routing humans into dead zones or poor sightlines that feel unfair, driving early abandonment.
4. **Rotation change:** Temporarily force GrandRift into heavier rotation with a structured playtest session and compare metrics before/after.

**Metrics to watch:** GrandRift session completion rate, average match duration by map, player return rate after a GrandRift match, human-vs-bot kill ratio on GrandRift.

---

## Insight 3 — Storm Deaths on Lockdown Cluster Near Center-East, Suggesting Insufficient Warning Time

### What caught my eye
Filtering to Lockdown and enabling the Storm Deaths heatmap showed a clear spatial cluster rather than random scatter. Storm deaths weren't happening uniformly at the map edge — they were happening in a specific interior zone.

### The data
Storm deaths by map:
- Lockdown: **17 deaths** (0.099 per match) — highest per-match rate
- AmbroseValley: **17 deaths** (0.030 per match)
- GrandRift: **5 deaths** (0.085 per match)

On Lockdown specifically, storm death coordinates cluster with an average pixel position near the center-east of the minimap (average u ≈ 0.55, average v ≈ 0.54). Storm deaths are not happening at the map edges — they're happening in interior zones where players presumably felt safe.

On AmbroseValley, storm deaths cluster in the center-west (average u ≈ 0.43) — consistent with the northwest traffic gravity described in Insight 1, where players congregate and get caught by late-closing storm.

### Why a Level Designer should care
Interior storm deaths (not at the edge) almost always mean one of three things:
1. The storm's visual/audio warning wasn't visible or legible from that position
2. The safe zone is contracting faster than the terrain allows players to traverse
3. Players were engaged in combat and couldn't disengage in time — which could be a design feature, but at 0.1 deaths/match it may be creating unavoidable situations

Lockdown's confined geometry means the storm can cross a lot of navigable space quickly. A player in a building in center-east may have a full storm circle visible 10 seconds earlier, then be inside the storm 10 seconds later if there's no direct exit route.

### Actionable next steps
1. **Storm VFX audit:** Walk the center-east zone on Lockdown in spectator mode. Is the storm boundary clearly visible from inside buildings? Consider adding storm-audio directional cues (wind direction sound design).
2. **Timing review:** Measure the delta between "storm enters player's visible range" and "storm damage begins" for deaths in this zone. If it's under 5 seconds, the warning window is too short for Lockdown's building density.
3. **Exit route mapping:** Overlay storm death positions against the building/obstacle layout. If deaths cluster at specific chokepoints, add secondary exits or reduce obstruction.
4. **AmbroseValley cross-reference:** Storm deaths on Ambrose cluster near the NW traffic concentration zone (matching Insight 1). Players gathering in NW are being caught by storm late-game — this may be intentional end-game pressure, but worth validating.

**Metrics to watch:** Average time between storm warning and player death, storm death rate by match phase (early/mid/late), storm death rate change after any VFX or timing adjustments.
