"""
Measure how many of YOUR plays get audio features from the 114K dataset (R2).

  python scripts/match_report.py --history data/raw/my_spotify_data
  python scripts/match_report.py --history data/synthetic/user1      # test run

Writes data/processed/matched_plays.csv for the next pipeline step.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.dataset import load_tracks          # noqa: E402
from src.load_history import load_history    # noqa: E402
from src.matching import match_plays, match_report  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--history", default="data/raw/my_spotify_data")
ap.add_argument("--dataset", default="data/raw/dataset.csv")
ap.add_argument("--min-ms", type=int, default=0,
                help="ignore plays shorter than this (30000 = counted listens only)")
ap.add_argument("--out", default="data/processed/matched_plays.csv")
args = ap.parse_args()

plays = load_history(args.history)
if args.min_ms:
    plays = plays[plays["ms_played"] >= args.min_ms]
tracks = load_tracks(args.dataset)
matched = match_plays(plays, tracks)
match_report(matched)

Path(args.out).parent.mkdir(parents=True, exist_ok=True)
matched.drop(columns=["genres"]).to_csv(args.out, index=False)
print(f"\nSaved {args.out}")