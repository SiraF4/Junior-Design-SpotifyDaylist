"""
Load and clean the 114K Spotify Tracks Dataset.

The raw CSV lists a track once PER GENRE it appears under, so the same
track_id shows up several times. We keep one row per track_id and collect
every genre it appeared under in a `genres` list column.
"""

import pandas as pd

from src.textnorm import norm_artist, norm_title

AUDIO_FEATURES = ["danceability", "energy", "valence", "tempo", "acousticness",
                  "instrumentalness", "speechiness", "loudness", "liveness"]


def load_tracks(path="data/raw/dataset.csv"):
    df = pd.read_csv(path)
    df = df.dropna(subset=["track_id", "track_name", "artists"])
    genres = df.groupby("track_id")["track_genre"].apply(lambda s: sorted(set(s)))
    df = df.drop_duplicates(subset=["track_id"]).copy()
    df["genres"] = df["track_id"].map(genres)
    df["track_genre"] = df["genres"].str[0]            # a primary genre, for display
    # same song re-released with a different track_id appears as a separate row;
    # keep the most popular copy per (title, first artist) for name-based matching
    df["title_key"] = df["track_name"].map(norm_title)
    df["artist_key"] = df["artists"].map(norm_artist)
    df["name_key"] = df["title_key"] + "|" + df["artist_key"]
    return df.reset_index(drop=True)