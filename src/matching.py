"""
Match your listening history to the 114K dataset to get audio features.

Three stages, cheapest first. Each play is labeled with the stage that matched it,
so you can report exactly how coverage was achieved (requirement R2):

  1. "id"         exact Spotify track_id
  2. "normalized" same title + first artist after cleaning
                  ("Song - Remastered 2011" == "Song", "(feat. X)" ignored)
  3. "fuzzy"      close spelling (rapidfuzz, score >= 90); skipped if rapidfuzz
                  is not installed
Anything left is "none" (usually newer releases or niche tracks not in the dataset).
"""

import pandas as pd

from src.dataset import AUDIO_FEATURES
from src.textnorm import norm_artist, norm_title

FEATURE_COLS = AUDIO_FEATURES + ["genres", "track_genre"]


def match_plays(plays, tracks, fuzzy_cutoff=90, use_fuzzy=True):
    """Return `plays` plus columns: match_stage, ds_track_id, audio features, genres."""
    out = plays.copy()
    out["match_stage"] = "none"
    out["ds_track_id"] = None

    # ---- stage 1: exact id
    by_id = tracks.set_index("track_id")
    hit = out["track_id"].isin(by_id.index)
    out.loc[hit, "match_stage"] = "id"
    out.loc[hit, "ds_track_id"] = out.loc[hit, "track_id"]

    # ---- stage 2: normalized name (one dataset row per name_key, most popular first)
    name_to_id = (tracks.sort_values("popularity", ascending=False)
                  .drop_duplicates("name_key").set_index("name_key")["track_id"])
    todo = out["match_stage"] == "none"
    keys = (out.loc[todo, "track_name"].map(norm_title) + "|" +
            out.loc[todo, "artist_name"].map(norm_artist))
    mapped = keys.map(name_to_id)
    ok = mapped.notna()
    out.loc[mapped[ok].index, "ds_track_id"] = mapped[ok]
    out.loc[mapped[ok].index, "match_stage"] = "normalized"

    # ---- stage 3: fuzzy, on UNIQUE leftover (title, artist) pairs only (fast)
    if use_fuzzy:
        try:
            from rapidfuzz import fuzz, process
        except ImportError:
            print("note: rapidfuzz not installed, skipping fuzzy stage "
                  "(pip install rapidfuzz)")
        else:
            todo = out["match_stage"] == "none"
            pairs = out.loc[todo, ["track_name", "artist_name"]].drop_duplicates()
            choices = tracks["name_key"].tolist()
            found = {}
            for t, a in pairs.itertuples(index=False):
                q = norm_title(t) + "|" + norm_artist(a)
                m = process.extractOne(q, choices, scorer=fuzz.ratio, score_cutoff=fuzzy_cutoff)
                if m:
                    found[(t, a)] = tracks.iloc[m[2]]["track_id"]
            if found:
                idx = out.index[todo]
                ids = [found.get((t, a)) for t, a in
                       zip(out.loc[idx, "track_name"], out.loc[idx, "artist_name"])]
                ids = pd.Series(ids, index=idx)
                ok = ids.notna()
                out.loc[ids[ok].index, "ds_track_id"] = ids[ok]
                out.loc[ids[ok].index, "match_stage"] = "fuzzy"

    # ---- attach features
    feats = tracks.set_index("track_id")[FEATURE_COLS]
    out = out.join(feats, on="ds_track_id")
    return out


def match_report(matched, top_unmatched=15):
    """Print coverage (R2) and which tracks failed, so you know what to fix."""
    n = len(matched)
    stage = matched["match_stage"].value_counts()
    print(f"\nPlays: {n}   Unique tracks: {matched['track_name'].nunique()}")
    print("\nCoverage by stage (share of PLAYS):")
    for s in ["id", "normalized", "fuzzy", "none"]:
        c = int(stage.get(s, 0))
        print(f"  {s:<11} {c:>7}  {c / n:6.1%}")
    covered = 1 - stage.get("none", 0) / n
    print(f"\nR2 coverage (plays with audio features): {covered:.1%}")
    uniq = matched.drop_duplicates(["track_name", "artist_name"])
    print(f"Coverage by UNIQUE track: {(uniq['match_stage'] != 'none').mean():.1%}")
    miss = matched[matched["match_stage"] == "none"]
    if len(miss):
        print(f"\nMost-played unmatched tracks (top {top_unmatched}):")
        top = (miss.groupby(["artist_name", "track_name"]).size()
               .sort_values(ascending=False).head(top_unmatched))
        for (a, t), c in top.items():
            print(f"  {c:>4}  {a} - {t}")
    return covered