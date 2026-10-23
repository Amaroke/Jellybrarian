import re
import sys
import time
import urllib.parse

import api
import storage

URL = "https://musicbrainz.org/ws/2"
AGENT = "Jellybrarian/1.0 ( https://github.com/Amaroke/jellybrarian )"
INTERVAL = 1.1
TOLERANCE = 3
VERSION = re.compile(r"(?i)\s+-\s+.*$|\s*[(\[](?:feat|ft|with)\b[^)\]]*[)\]]")
_last = 0.0


def get(path, **params):
    global _last
    pending = _last + INTERVAL - time.monotonic()
    if pending > 0:
        time.sleep(pending)
    _last = time.monotonic()
    url = f"{URL}/{path.strip('/')}?{urllib.parse.urlencode({'fmt': 'json', **params})}"
    return api.read(url, {"User-Agent": AGENT, "Accept": "application/json"}, codes=(429, 500, 502, 503, 504))


def key(text):
    return "".join(c for c in (text or "").casefold() if c.isalnum())


def recording(isrc, duration):
    candidates = [r for r in (get(f"isrc/{isrc}") or {}).get("recordings") or []]
    if not candidates:
        return None
    return min(candidates, key=lambda r: abs((r.get("length") or 0) / 1000 - duration))["id"]


def candidate(r):
    return {
        "mbid": r["id"],
        "title": r.get("title"),
        "artists": [c.get("name") for c in r.get("artist-credit") or []],
        "duration": round(r["length"] / 1000) if r.get("length") else None,
    }


def search(track):
    title = VERSION.sub("", track["title"]).strip() or track["title"]
    query = f'recording:"{title.replace(chr(34), " ")}" AND artist:"{track["artists"][0].replace(chr(34), " ")}"'
    artists = {key(a) for a in track["artists"]}
    sure, doubtful = [], []
    for r in (get("recording", query=query, limit=25) or {}).get("recordings") or []:
        found = candidate(r)
        if not artists & {key(a) for a in found["artists"]}:
            continue
        close = found["duration"] is not None and abs(found["duration"] - track["duration"]) <= TOLERANCE
        if close and key(found["title"]) in (key(title), key(track["title"])):
            sure.append(found["mbid"])
        elif len(doubtful) < 3:
            doubtful.append(found)
    return sure, doubtful


def look_up(track):
    if not track["title"] or not track["artists"]:
        return {"mbid": None, "doubtful": []}
    sure, doubtful = search(track)
    return {"mbid": sure[0], "doubtful": []} if sure else {"mbid": None, "doubtful": doubtful}


def resolve_tracks():
    snapshot = storage.read_cache(storage.spotify())
    if not snapshot:
        raise RuntimeError("No Spotify snapshot: run spotify.py snapshot")
    tracks = snapshot["tracks"]
    cache = storage.read_cache(storage.cache("musicbrainz"))
    to_search = sorted({m["isrc"] for m in tracks.values() if m["isrc"] and not storage.fresh(cache.get(m["isrc"]))})
    print(f"ISRC to search on MusicBrainz: {len(to_search)}, about {round(len(to_search) * INTERVAL / 60)} min")
    for n, isrc in enumerate(to_search, 1):
        duration = next(m["duration"] for m in tracks.values() if m["isrc"] == isrc)
        storage.record(storage.cache("musicbrainz"), isrc, {"mbid": recording(isrc, duration)})
        if n % 100 == 0:
            print(f"  {n}/{len(to_search)}")
    cache = storage.read_cache(storage.cache("musicbrainz"))
    without_isrc = [i for i, m in tracks.items() if not (cache.get(m["isrc"]) or {}).get("mbid") and not storage.fresh(cache.get(f"spotify:{i}"))]
    print(f"Tracks to search by artist and title: {len(without_isrc)}, about {round(len(without_isrc) * INTERVAL / 60)} min")
    for n, identifier in enumerate(without_isrc, 1):
        storage.record(storage.cache("musicbrainz"), f"spotify:{identifier}", look_up(tracks[identifier]))
        if n % 100 == 0:
            print(f"  {n}/{len(without_isrc)}")
    cache = storage.read_cache(storage.cache("musicbrainz"))
    for identifier, track in tracks.items():
        lookup = cache.get(f"spotify:{identifier}") or {}
        track["mbid"] = (cache.get(track["isrc"]) or {}).get("mbid") or lookup.get("mbid")
        track["doubtful"] = [] if track["mbid"] else lookup.get("doubtful") or []
    storage.write_json(storage.spotify(), snapshot)
    return [m for m in tracks.values() if not m["mbid"]]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    if sys.argv[1:] != ["resolve"]:
        print("usage: musicbrainz.py resolve")
        sys.exit(2)
    outside = resolve_tracks()
    doubtful = [m for m in outside if m["doubtful"]]
    print(f"Doubtful, to ask the user: {len(doubtful)}")
    print(f"Not on MusicBrainz: {len(outside) - len(doubtful)}")


if __name__ == "__main__":
    main()
