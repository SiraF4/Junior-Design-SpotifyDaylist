"""
Small client for ReccoBeats' free audio-features endpoint (used to fill the gaps
left by the 114K dataset, since Spotify's own audio-features endpoint is closed
to new apps).

  GET https://api.reccobeats.com/v1/audio-features?ids=<spotify ids, comma separated>

Things I could NOT confirm from the docs, so this code is defensive:
  * the maximum batch size  -> keep --batch small (default 20)
  * the exact response shape -> parsed in parse_payload(); run `--probe` first
  * rate limits -> polite delay + retry/backoff on 429/5xx
Check ReccoBeats' site for current terms before relying on it, and cite it in your report.
"""

import csv
import re
import time
from pathlib import Path

import requests

BASE = "https://api.reccobeats.com/v1/audio-features"
FEATURES = ["acousticness", "danceability", "energy", "instrumentalness",
            "liveness", "loudness", "speechiness", "tempo", "valence"]
CACHE_COLS = ["track_id", "status"] + FEATURES
_SPOTIFY_ID = re.compile(r"track/([A-Za-z0-9]{22})")


def fetch_batch(ids, session=None, retries=5):
    """GET one batch. Returns parsed JSON, or {} if ReccoBeats has none of them."""
    s = session or requests
    for attempt in range(retries):
        r = s.get(BASE, params={"ids": ",".join(ids)}, timeout=30,
                  headers={"Accept": "application/json"})
        if r.status_code == 200:
            return r.json()
        if r.status_code in (400, 404):
            return {}
        if r.status_code in (429, 500, 502, 503, 504):
            wait = float(r.headers.get("Retry-After", 2 ** attempt * 2))
            print(f"  HTTP {r.status_code}, waiting {wait:.0f}s (attempt {attempt + 1}/{retries})")
            time.sleep(wait)
            continue
        r.raise_for_status()
    raise RuntimeError("ReccoBeats kept failing; try again later or lower the request rate")


def parse_payload(payload, requested):
    """Return ({spotify_id: {feature: value}}, n_items_seen)."""
    items = payload.get("content", payload) if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        items = []
    out = {}
    for it in items:
        if not isinstance(it, dict):
            continue
        m = _SPOTIFY_ID.search(str(it.get("href", "")))
        sid = m.group(1) if m else None
        if sid is None and len(requested) == 1 and len(items) == 1:
            sid = requested[0]          # unambiguous when we asked for exactly one
        if sid in requested and all(f in it for f in FEATURES):
            out[sid] = {f: float(it[f]) for f in FEATURES}
    return out, len(items)


def load_cache(path):
    path = Path(path)
    if not path.exists():
        return {}
    with open(path, newline="", encoding="utf-8") as f:
        return {row["track_id"]: row for row in csv.DictReader(f)}


def save_cache(cache, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CACHE_COLS)
        w.writeheader()
        for row in cache.values():
            w.writerow({c: row.get(c, "") for c in CACHE_COLS})


def enrich(ids, cache_path, batch=20, delay=1.0, session=None, save_every=10):
    """Fetch features for ids not already cached. Resumable: safe to stop and re-run."""
    cache = load_cache(cache_path)
    todo = [i for i in ids if i not in cache]
    print(f"{len(ids)} requested, {len(ids) - len(todo)} already cached, {len(todo)} to fetch")
    n_ok = n_missing = 0
    for b, start in enumerate(range(0, len(todo), batch), 1):
        chunk = todo[start:start + batch]
        payload = fetch_batch(chunk, session=session)
        found, seen = parse_payload(payload, set(chunk))
        if seen and not found:
            print("Got items back but could not match them to Spotify IDs.\n"
                  "Run with --probe and send the output so the parser can be fixed.")
            break
        for sid in chunk:
            if sid in found:
                cache[sid] = {"track_id": sid, "status": "ok", **found[sid]}
                n_ok += 1
            else:
                cache[sid] = {"track_id": sid, "status": "not_found"}
                n_missing += 1
        if b % save_every == 0:
            save_cache(cache, cache_path)
            print(f"  {start + len(chunk)}/{len(todo)} done  (ok {n_ok}, not found {n_missing})")
        time.sleep(delay)
    save_cache(cache, cache_path)
    print(f"Finished: ok {n_ok}, not found {n_missing}. Cache: {cache_path}")
    return cache