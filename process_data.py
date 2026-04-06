"""
process_data.py
---------------
Reads player_data.zip and outputs all JSON files needed by the web tool.

Usage:
    python3 process_data.py [--input player_data.zip] [--output ./]

Requirements:
    pip install pyarrow pandas
"""

import argparse
import io
import json
import os
import zipfile
from collections import defaultdict

import pyarrow.parquet as pq
import pandas as pd

MAP_CONFIG = {
    "AmbroseValley": {"scale": 900, "origin_x": -370, "origin_z": -473},
    "GrandRift": {"scale": 581, "origin_x": -290, "origin_z": -290},
    "Lockdown": {"scale": 1000, "origin_x": -500, "origin_z": -500},
}

GRID = 64
ACTION_EVENTS = {"Kill", "Killed", "BotKill", "BotKilled", "KilledByStorm", "Loot"}


def is_bot(user_id: str) -> bool:
    return user_id.strip().isdigit()


def get_date(filepath: str) -> str:
    return filepath.split("/")[1]  # e.g. February_10


def parse_filename(filepath: str):
    basename = filepath.split("/")[-1].replace(".nakama-0", "")
    if basename.split("_")[0].isdigit():
        user_id = basename.split("_")[0]
        match_id = "_".join(basename.split("_")[1:])
    else:
        idx = basename.index("_")
        user_id = basename[:idx]
        match_id = basename[idx + 1:]
    return user_id, match_id


def world_to_pixel(x: float, z: float, map_id: str):
    cfg = MAP_CONFIG.get(map_id)
    if not cfg:
        return -1, -1
    u = (x - cfg["origin_x"]) / cfg["scale"]
    v = (z - cfg["origin_z"]) / cfg["scale"]
    px = round(u * 1024)
    py = round((1 - v) * 1024)
    return px, py


def world_to_cell(x: float, z: float, map_id: str):
    px, py = world_to_pixel(x, z, map_id)
    if px < 0 or py < 0:
        return None, None
    cx = min(GRID - 1, max(0, int(px / 1024 * GRID)))
    cy = min(GRID - 1, max(0, int(py / 1024 * GRID)))
    return cx, cy


def process(zip_path: str, output_dir: str):
    print(f"Reading {zip_path}...")
    z = zipfile.ZipFile(zip_path)
    all_files = [f for f in z.namelist() if f.endswith(".nakama-0")]
    print(f"Found {len(all_files)} player files")

    # -------------------------------------------------------
    # Pass 1: read all files, build events + match registry
    # -------------------------------------------------------
    all_events = []
    match_registry = defaultdict(
        lambda: {"map": "", "date": "", "humans": set(), "bots": set(),
                 "ts_min": None, "ts_max": None}
    )

    for i, fp in enumerate(all_files):
        try:
            data = z.read(fp)
            buf = io.BytesIO(data)
            df = pq.read_table(buf).to_pandas()
            df["event"] = df["event"].apply(
                lambda x: x.decode("utf-8") if isinstance(x, bytes) else x
            )

            user_id, match_id = parse_filename(fp)
            date = get_date(fp)
            bot = is_bot(user_id)
            map_id = df["map_id"].iloc[0] if len(df) > 0 else "Unknown"

            mr = match_registry[match_id]
            mr["map"] = map_id
            mr["date"] = date
            if bot:
                mr["bots"].add(user_id)
            else:
                mr["humans"].add(user_id)

            ts_ms = df["ts"].astype("int64")
            cur_min = int(ts_ms.min())
            cur_max = int(ts_ms.max())
            if mr["ts_min"] is None or cur_min < mr["ts_min"]:
                mr["ts_min"] = cur_min
            if mr["ts_max"] is None or cur_max > mr["ts_max"]:
                mr["ts_max"] = cur_max

            for _, row in df.iterrows():
                all_events.append({
                    "user_id": user_id,
                    "match_id": match_id,
                    "map_id": map_id,
                    "date": date,
                    "is_bot": bot,
                    "x": float(row["x"]),
                    "z": float(row["z"]),
                    "ts": cur_min,  # will be overridden below
                    "ts_abs": int(pd.Timestamp(row["ts"]).value // 1_000_000),
                    "event": row["event"],
                })

        except Exception as ex:
            print(f"  Warning: could not read {fp}: {ex}")

        if (i + 1) % 200 == 0:
            print(f"  Processed {i+1}/{len(all_files)} files...")

    print(f"Total events: {len(all_events)}")

    # -------------------------------------------------------
    # Compute relative timestamps per match
    # -------------------------------------------------------
    match_ts_min = {mid: m["ts_min"] for mid, m in match_registry.items()}
    for e in all_events:
        e["ts_rel"] = e["ts_abs"] - (match_ts_min.get(e["match_id"]) or e["ts_abs"])

    # -------------------------------------------------------
    # Build match summaries
    # -------------------------------------------------------
    print("Building match summaries...")
    match_event_map = defaultdict(list)
    for e in all_events:
        match_event_map[e["match_id"]].append(e)

    match_summaries = []
    for mid, mr in match_registry.items():
        m_evts = match_event_map[mid]
        match_summaries.append({
            "match_id": mid,
            "map": mr["map"],
            "date": mr["date"],
            "humans": list(mr["humans"]),
            "bots": list(mr["bots"]),
            "num_humans": len(mr["humans"]),
            "num_bots": len(mr["bots"]),
            "duration_ms": (mr["ts_max"] - mr["ts_min"]) if mr["ts_min"] else 0,
            "kills": sum(1 for e in m_evts if e["event"] in ("Kill", "BotKill")),
            "deaths": sum(1 for e in m_evts if e["event"] in ("Killed", "BotKilled")),
            "storm_deaths": sum(1 for e in m_evts if e["event"] == "KilledByStorm"),
            "loot_pickups": sum(1 for e in m_evts if e["event"] == "Loot"),
        })

    path = os.path.join(output_dir, "match_summaries.json")
    with open(path, "w") as f:
        json.dump(match_summaries, f, separators=(",", ":"))
    print(f"  Saved {path} ({os.path.getsize(path)//1024} KB)")

    # -------------------------------------------------------
    # Build per-map compact event files
    # -------------------------------------------------------
    print("Building per-map event files...")
    for map_id in ["AmbroseValley", "GrandRift", "Lockdown"]:
        map_evts = [e for e in all_events if e["map_id"] == map_id]

        actions = [e for e in map_evts if e["event"] in ACTION_EVENTS]
        positions = [e for e in map_evts if e["event"] not in ACTION_EVENTS]

        # Sample positions 1-in-3 per player-match to reduce size
        pos_by_pm = defaultdict(list)
        for e in positions:
            pos_by_pm[(e["match_id"], e["user_id"])].append(e)

        sampled = []
        for evts_list in pos_by_pm.values():
            evts_list.sort(key=lambda x: x["ts_abs"])
            sampled.extend(evts_list[::3])

        combined = actions + sampled

        # Compact format: [match_id, user_id, is_bot, event, px, py, ts_rel]
        compact = []
        for e in combined:
            px, py = world_to_pixel(e["x"], e["z"], map_id)
            compact.append([
                e["match_id"],
                e["user_id"],
                1 if e["is_bot"] else 0,
                e["event"],
                px, py,
                e["ts_rel"],
            ])

        path = os.path.join(output_dir, f"data_{map_id}.json")
        with open(path, "w") as f:
            json.dump(compact, f, separators=(",", ":"))
        print(f"  Saved {path} ({os.path.getsize(path)//1024} KB, {len(compact)} events)")

    # -------------------------------------------------------
    # Build heatmaps (64×64 grids)
    # -------------------------------------------------------
    print("Building heatmaps...")
    heatmaps = {}
    for map_id in ["AmbroseValley", "GrandRift", "Lockdown"]:
        heatmaps[map_id] = {
            "kills": [[0] * GRID for _ in range(GRID)],
            "deaths": [[0] * GRID for _ in range(GRID)],
            "storm_deaths": [[0] * GRID for _ in range(GRID)],
            "traffic": [[0] * GRID for _ in range(GRID)],
            "loot": [[0] * GRID for _ in range(GRID)],
        }

    for e in all_events:
        mid = e["map_id"]
        if mid not in heatmaps:
            continue
        evt = e["event"]
        cx, cy = world_to_cell(e["x"], e["z"], mid)
        if cx is None:
            continue

        if evt in ("Position", "BotPosition"):
            heatmaps[mid]["traffic"][cy][cx] += 1
        elif evt in ("Kill", "BotKill"):
            heatmaps[mid]["kills"][cy][cx] += 1
        elif evt in ("Killed", "BotKilled"):
            heatmaps[mid]["deaths"][cy][cx] += 1
        elif evt == "KilledByStorm":
            heatmaps[mid]["storm_deaths"][cy][cx] += 1
        elif evt == "Loot":
            heatmaps[mid]["loot"][cy][cx] += 1

    path = os.path.join(output_dir, "heatmaps.json")
    with open(path, "w") as f:
        json.dump(heatmaps, f, separators=(",", ":"))
    print(f"  Saved {path} ({os.path.getsize(path)//1024} KB)")

    # -------------------------------------------------------
    # Extract minimap images
    # -------------------------------------------------------
    print("Extracting minimap images...")
    minimap_files = [f for f in z.namelist()
                     if "minimaps" in f and (f.endswith(".png") or f.endswith(".jpg"))]
    for mp in minimap_files:
        name = mp.split("/")[-1]
        dest = os.path.join(output_dir, name)
        with open(dest, "wb") as f:
            f.write(z.read(mp))
        print(f"  Saved {dest} ({os.path.getsize(dest)//1024} KB)")

    print("\nDone. All output files written to:", output_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LILA BLACK data pipeline")
    parser.add_argument("--input", default="player_data.zip", help="Path to player_data.zip")
    parser.add_argument("--output", default=".", help="Output directory")
    args = parser.parse_args()
    process(args.input, args.output)
