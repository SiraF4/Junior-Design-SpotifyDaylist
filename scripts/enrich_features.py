"""
Fill in audio features for plays the 114K dataset could not match, using ReccoBeats.
Run scripts/match_report.py first (it writes data/processed/matched_plays.csv).

  python scripts/enrich_features.py --probe              # 1) look at the raw response (3 tracks)
  python scripts/enrich_features.py --validate 300       # 2) compare ReccoBeats vs the dataset
  python scripts/enrich_features.py --limit 500          # 3) small real run (most-played first)
  python scripts/enrich_features.py                      # 4) everything (resumable)
"""
import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.reccobeats import FEATURES, enrich, fetch_batch, load_cache  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--matched", default="data/processed/matched_plays.csv")
ap.add_argument("--cache", default="data/processed/reccobeats_features.csv")
ap.add_argument("--batch", type=int, default=20)
ap.add_argument("--delay", type=float, default=1.0, help="seconds between requests")
ap.add_argument("--limit", type=int, default=0, help="only the N most-played unmatched tracks")
ap.add_argument("--probe", action="store_true")
ap.add_argument("--validate", type=int, default=0, metavar="N")
args = ap.parse_args()

m = pd.read_csv(args.matched)

if args.probe:
    ids = m.loc[m["match_stage"] == "id", "track_id"].dropna().unique()[:3].tolist()
    print("Requesting:", ids)
    print(json.dumps(fetch_batch(ids), indent=2)[:3000])
    sys.exit()

if args.validate:
    known = m[m["match_stage"] == "id"].drop_duplicates("track_id")
    sample = known.sample(min(args.validate, len(known)), random_state=0)
    cache = enrich(sample["track_id"].tolist(), args.cache, args.batch, args.delay)
    got = pd.DataFrame([r for r in cache.values() if r["status"] == "ok"])
    if got.empty:
        sys.exit("No ReccoBeats results to compare.")
    for f in FEATURES:
        got[f] = got[f].astype(float)
    both = sample.merge(got, on="track_id", suffixes=("_dataset", "_recco"))
    print(f"\nCompared {len(both)} of {len(sample)} sampled tracks "
          f"({len(both) / len(sample):.0%} found in ReccoBeats)\n")
    print(f"{'feature':<17}{'corr':>7}{'mean(ds)':>10}{'mean(recco)':>13}{'mean abs diff':>15}")
    for f in FEATURES:
        a, b = both[f + "_dataset"], both[f + "_recco"]
        print(f"{f:<17}{a.corr(b):>7.2f}{a.mean():>10.3f}{b.mean():>13.3f}{(a - b).abs().mean():>15.3f}")
    print("\nRule of thumb: corr >= 0.8 and similar means -> safe to mix sources. "
          "Low corr or shifted means -> keep the sources separate or rescale.")
    sys.exit()

miss = m[(m["match_stage"] == "none") & m["track_id"].notna()]
order = miss.groupby("track_id").size().sort_values(ascending=False)
ids = order.index.tolist()[: args.limit or None]
share = order.iloc[: len(ids)].sum() / len(m)
print(f"Fetching {len(ids)} tracks covering {share:.1%} of all plays")
cache = enrich(ids, args.cache, args.batch, args.delay)
ok = sum(1 for r in cache.values() if r["status"] == "ok")
print(f"Tracks with features from ReccoBeats: {ok}")