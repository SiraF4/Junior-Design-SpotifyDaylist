"""
Smoke test for every Spotify Web API call this project depends on.
 
Run this FIRST (task T1). It tells you in ~1 minute whether your app, account,
and the endpoints you need actually work, before you build anything on them.
 
Uses plain `requests` for the API calls (spotipy is used only to log in and
cache your token), so it does not depend on whether your spotipy version has
been updated for Spotify's February 2026 endpoint changes
(e.g. /playlists/{id}/tracks was renamed /playlists/{id}/items).
 
Setup:
  pip install spotipy requests
  export SPOTIPY_CLIENT_ID="..."          # from the developer dashboard
  export SPOTIPY_CLIENT_SECRET="..."
  export SPOTIPY_REDIRECT_URI="http://127.0.0.1:8888/callback"   # must match the dashboard exactly
  python scripts/spotify_smoke_test.py            # read/write checks
  python scripts/spotify_smoke_test.py --skip     # also tests 'skip to next' (needs a playing device)
 
Windows PowerShell: use  $env:SPOTIPY_CLIENT_ID="..."  instead of export.
First run opens a browser to log in; the token is cached in .spotify_token_cache
(keep it out of Git).
"""
 
import os
import sys
import time
 
import requests
from spotipy.oauth2 import SpotifyOAuth
 
BASE = "https://api.spotify.com/v1"
SCOPES = " ".join([
    "user-read-recently-played",
    "user-read-currently-playing",
    "user-read-playback-state",
    "user-modify-playback-state",
    "playlist-modify-private",
    "playlist-read-private",
])
 
 
def get_token():
    auth = SpotifyOAuth(
        client_id="46564aea502a40e6a230e96b0c1146e8",
        client_secret="991609d490104a1584a6d80be3c5e84b",
        redirect_uri=os.environ.get("SPOTIPY_REDIRECT_URI", "http://127.0.0.1:8888/callback"),
        scope=SCOPES,
        cache_path=".spotify_token_cache",
    )
    info = auth.get_access_token(as_dict=True)
    return info["access_token"] if isinstance(info, dict) else info
 
 
def call(method, path, token, **kw):
    return requests.request(method, BASE + path, timeout=15,
                            headers={"Authorization": f"Bearer {token}"}, **kw)
 
 
results = []
 
 
def check(name, r, ok=(200, 201, 202, 204), note=""):
    passed = r.status_code in ok
    results.append((name, passed))
    msg = f"[{'PASS' if passed else 'FAIL'}] {name}: HTTP {r.status_code}"
    if note and passed:
        msg += f"  ({note})"
    if not passed:
        msg += f"\n        {r.text[:300]}"
    print(msg)
    return passed
 
 
def main():
    do_skip = "--skip" in sys.argv
    token = get_token()
 
    r = call("GET", "/me", token)
    check("GET /me (who am I)", r, note=r.json().get("display_name", "") if r.ok else "")
 
    r = call("GET", "/me/player/recently-played", token, params={"limit": 20})
    uris = []
    if check("GET /me/player/recently-played", r):
        items = r.json().get("items", [])
        uris = list(dict.fromkeys(i["track"]["uri"] for i in items))[:5]
        print(f"        got {len(items)} recent plays")
 
    if not uris:  # fall back to search (limit max is 10 now)
        r = call("GET", "/search", token, params={"q": "love", "type": "track", "limit": 5})
        if check("GET /search (fallback for track URIs)", r):
            uris = [t["uri"] for t in r.json()["tracks"]["items"]]
 
    r = call("GET", "/me/player/devices", token)
    if check("GET /me/player/devices", r):
        devs = r.json().get("devices", [])
        print("        devices:", [d["name"] for d in devs] or
              "NONE - open Spotify on your phone/computer and play something")
 
    r = call("POST", "/me/playlists", token,
             json={"name": "Daylist smoke test", "public": False,
                   "description": "Safe to delete - created by my project's smoke test"})
    pid = r.json().get("id") if check("POST /me/playlists (create)", r) else None
 
    if pid and uris:
        r = call("POST", f"/playlists/{pid}/items", token, json={"uris": uris})
        check("POST /playlists/{id}/items (add)", r)
        r = call("PUT", f"/playlists/{pid}/items", token, json={"uris": list(reversed(uris))})
        check("PUT /playlists/{id}/items (replace)", r)
        print(f"        playlist: https://open.spotify.com/playlist/{pid}  (delete it in the app when done)")
 
    r = call("GET", "/me/player/currently-playing", token)
    check("GET /me/player/currently-playing", r, ok=(200, 204),
          note="204 = nothing playing right now" if r.status_code == 204 else "")
 
    if do_skip:
        t0 = time.time()
        r = call("POST", "/me/player/next", token)
        check("POST /me/player/next (skip)", r, note=f"{time.time() - t0:.2f}s round trip")
    else:
        print("[ -- ] skip test not run (start music on a device, then use --skip)")
 
    failed = [n for n, ok in results if not ok]
    print("\nALL CHECKS PASSED" if not failed else f"\n{len(failed)} FAILED: {failed}")
    print("Tip: 403 on everything usually means the account isn't allowed to use this app "
          "(not added under User Management, or the app owner's Premium lapsed). "
          "404 on /player calls usually means no active device.")
 
 
if __name__ == "__main__":
    main()