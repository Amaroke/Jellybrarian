import base64
import hashlib
import http.server
import json
import secrets
import sys
import time
import urllib.parse
import urllib.request
import webbrowser
from datetime import date

import api
import config
import music_wanted
import storage

key = api.Key("Spotify Client ID missing", "spotify", "client_id")
SCOPES = "user-library-read playlist-read-private playlist-read-collaborative"
ACCOUNTS = "https://accounts.spotify.com"
API = "https://api.spotify.com/v1"


def port():
    return config.value("spotify", "port", 8888)


def redirect():
    return f"http://127.0.0.1:{port()}/callback"


def request_token(content):
    query = urllib.request.Request(f"{ACCOUNTS}/api/token", urllib.parse.urlencode(content).encode(), {"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(query, timeout=30) as response:
        token = json.load(response)
    old = storage.read_cache(storage.spotify_token())
    token["refresh_token"] = token.get("refresh_token") or old.get("refresh_token")
    token["expire"] = time.time() + token["expires_in"] - 60
    storage.write_json(storage.spotify_token(), token)
    return token


def connect():
    checker = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(checker.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)
    received = {}

    class Callback(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            received.update(urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query))
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write("Login received, this page can be closed.".encode())

        def log_message(self, *args):
            pass

    params = {"client_id": key(), "response_type": "code", "redirect_uri": redirect(), "scope": SCOPES, "state": state, "code_challenge_method": "S256", "code_challenge": challenge}
    url = f"{ACCOUNTS}/authorize?{urllib.parse.urlencode(params)}"
    print(f"Login in the browser: {url}")
    webbrowser.open(url)
    with http.server.HTTPServer(("127.0.0.1", port()), Callback) as server:
        while "code" not in received and "error" not in received:
            server.handle_request()
    if "error" in received or received.get("state") != [state]:
        raise RuntimeError(f"Login refused: {received.get('error', ['unexpected state'])[0]}")
    request_token({"grant_type": "authorization_code", "code": received["code"][0], "redirect_uri": redirect(), "client_id": key(), "code_verifier": checker})


def access():
    token = storage.read_cache(storage.spotify_token())
    if not token:
        raise RuntimeError("No Spotify token: run spotify.py connect")
    if time.time() >= token["expire"]:
        token = request_token({"grant_type": "refresh_token", "refresh_token": token["refresh_token"], "client_id": key()})
    return token["access_token"]


def get(path, **params):
    url = path if path.startswith("http") else f"{API}/{path.strip('/')}?{urllib.parse.urlencode(params)}"
    return api.read(url, {"Authorization": f"Bearer {access()}"})


def pages(path, **params):
    page = get(path, limit=50, **params)
    while page:
        yield from page.get("items") or []
        page = get(page["next"]) if page.get("next") else None


def track_of(album_track):
    return {
        "title": album_track["name"],
        "artists": [a["name"] for a in album_track.get("artists") or []],
        "album": (album_track.get("album") or {}).get("name"),
        "isrc": ((album_track.get("external_ids") or {}).get("isrc") or "").upper() or None,
        "duration": round((album_track.get("duration_ms") or 0) / 1000),
        "sources": [],
    }


def snapshot():
    me = get("me")["id"]
    tracks, discarded = {}, {"podcasts": 0, "local": 0}

    def add(entry, source):
        album_track = entry.get("item") or entry.get("track")
        if not album_track:
            return
        if album_track.get("type") != "track":
            discarded["podcasts"] += 1
            return
        if album_track.get("is_local") or not album_track.get("id"):
            discarded["local"] += 1
            return
        track = tracks.setdefault(album_track["id"], track_of(album_track))
        if source not in track["sources"]:
            track["sources"].append(source)

    if config.value("spotify", "likes", True):
        for entry in pages("me/tracks"):
            add(entry, "Liked songs")
    desired = {n.casefold() for n in config.value("spotify", "playlists", [])}
    playlists = [p for p in pages("me/playlists") if (p.get("owner") or {}).get("id") == me and (not desired or p["name"].casefold() in desired)]
    for playlist in playlists:
        for entry in pages(f"playlists/{playlist['id']}/items"):
            add(entry, f"Playlist: {playlist['name']}")
    storage.write_json(storage.spotify(), {"date": date.today().isoformat(), "playlists": [p["name"] for p in playlists], "discarded": discarded, "tracks": tracks})
    return tracks, playlists, discarded


def main():
    if sys.argv[1:2] == ["remove"]:
        for m in music_wanted.remove(sys.argv[2:]):
            print(f"Removed from the migration: {', '.join(m['artists'])} - {m['title']}")
        return
    if sys.argv[1:] not in (["connect"], ["snapshot"]):
        print("usage: spotify.py connect | snapshot | remove <Spotify identifier> ...")
        sys.exit(2)
    if sys.argv[1] == "snapshot" and storage.spotify().is_file():
        print(f"Snapshot already taken, frozen for the migration: {storage.spotify()}")
        sys.exit(2)
    if not key():
        print(key.message())
        sys.exit(config.MISSING_CONFIG)
    if sys.argv[1] == "connect":
        connect()
        print(f"Connected, token in {storage.spotify_token()}")
        return
    tracks, playlists, discarded = snapshot()
    without_isrc = sum(1 for m in tracks.values() if not m["isrc"])
    print(f"Tracks: {len(tracks)}, including {without_isrc} without ISRC")
    print(f"Playlists: {len(playlists)}")
    print(f"Discarded: {discarded['podcasts']} podcast episode(s), {discarded['local']} local file(s)")
    print(f"Snapshot: {storage.spotify()}")


if __name__ == "__main__":
    config.run_main(main)
