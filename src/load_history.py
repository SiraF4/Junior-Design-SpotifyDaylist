"""
Load Spotify streaming history (real OR synthetic -- same format) into one
clean pandas DataFrame that the rest of the pipeline uses.

Handles both export layouts:
  Streaming_History_Audio_*.json  (Extended: has track IDs, skips, reasons)
  StreamingHistory_music_*.json   (Standard: names + msPlayed only)

Usage:
  from src.load_history import load_history
  plays = load_history("data/synthetic/user1")       # today
  plays = load_history("data/raw/my_spotify_data")   # when the real export arrives
"""

import json
from pathlib import Path

import pandas as pd

COLUMNS = ["played_at", "played_at_local", "track_id", "track_name", "artist_name",
           "album_name", "ms_played", "skipped", "reason_start", "reason_end",
           "shuffle", "platform"]


def _load_extended(files):
    rows = [r for f in files for r in json.loads(f.read_text(encoding="utf-8"))]
    df = pd.DataFrame(rows)
    df = df[df["spotify_track_uri"].notna()]          # drop podcasts / audiobooks
    return pd.DataFrame({
        "played_at": pd.to_datetime(df["ts"], utc=True),
        "track_id": df["spotify_track_uri"].str.replace("spotify:track:", "", regex=False),
        "track_name": df["master_metadata_track_name"],
        "artist_name": df["master_metadata_album_artist_name"],
        "album_name": df["master_metadata_album_album_name"],
        "ms_played": df["ms_played"],
        "skipped": df["skipped"].fillna(False).astype(bool),
        "reason_start": df["reason_start"],
        "reason_end": df["reason_end"],
        "shuffle": df["shuffle"],
        "platform": df["platform"],
    })


def _load_standard(files):
    rows = [r for f in files for r in json.loads(f.read_text(encoding="utf-8"))]
    df = pd.DataFrame(rows)
    return pd.DataFrame({
        "played_at": pd.to_datetime(df["endTime"], utc=True),
        "track_id": None,                                  # not in this format
        "track_name": df["trackName"],
        "artist_name": df["artistName"],
        "album_name": None,
        "ms_played": df["msPlayed"],
        "skipped": df["msPlayed"] < 30_000,                # best guess: <30s = skip
        "reason_start": None, "reason_end": None, "shuffle": None, "platform": None,
    })


def load_history(folder, tz="America/New_York", prefer="extended"):
    folder = Path(folder)
    ext = sorted(folder.glob("Streaming_History_Audio_*.json"))
    std = sorted(folder.glob("StreamingHistory_music_*.json"))
    if ext and (prefer == "extended" or not std):
        df = _load_extended(ext)
    elif std:
        df = _load_standard(std)
    else:
        raise FileNotFoundError(f"No Spotify history JSON files found in {folder}")

    # Real exports are in UTC. Convert to local time, or your time-of-day
    # patterns will be shifted by 4-5 hours.
    df["played_at_local"] = df["played_at"].dt.tz_convert(tz)
    return df[COLUMNS].sort_values("played_at").reset_index(drop=True)


if __name__ == "__main__":
    import sys
    plays = load_history(sys.argv[1] if len(sys.argv) > 1 else "data/synthetic/user1")
    print(plays.head(10).to_string())
    print(f"\n{len(plays)} plays, skip rate {plays['skipped'].mean():.1%}")
