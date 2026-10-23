from collections import defaultdict

import storage
import music


def artist_of(track, f):
    return music.artist_name(f["folder"]) if f else track["artists"][0]


def search(report):
    snapshot = storage.read_cache(storage.spotify())
    if not snapshot:
        return None
    listings = storage.read_cache(music.TRACKS)
    present_ones = {mbid for _, _, mbid, _ in report.tracks}
    tracks, doubtful, outside, without_listing = [], [], [], []
    for identifier, m in snapshot["tracks"].items():
        label = f"{', '.join(m['artists'])} - {m['title']}"
        if not m.get("mbid"):
            if m.get("doubtful"):
                doubtful.append({"spotify": identifier, "track": label, "duration": m["duration"], "candidates": m["doubtful"]})
            else:
                outside.append(label)
            continue
        if m["mbid"] in present_ones:
            continue
        f = listings.get(m["mbid"])
        if not f:
            without_listing.append(label)
        tracks.append({
            "mbid": m["mbid"],
            "artist": artist_of(m, f),
            "title": music.title_of(f) if f else m["title"],
            "artists": m["artists"],
            "spotify_title": m["title"],
            "duration": m["duration"],
            "isrc": m["isrc"],
            "path": music.final_path(m["mbid"], f, ".flac") if f else None,
            "origin": "spotify",
        })

    return tracks, doubtful, outside, without_listing


def summary(tracks):
    by_artist = defaultdict(list)
    for m in tracks:
        by_artist[m["artist"]].append(m["title"])
    return {a: ", ".join(sorted(t, key=str.casefold)) for a, t in sorted(by_artist.items(), key=lambda e: e[0].casefold())}


def filter_ignored(tracks, ignored):
    return [m for m in tracks if m["artist"] not in ignored and f"{m['artist']} : {m['title']}" not in ignored]


def migrate(present_ones):
    file = storage.spotify()
    snapshot = storage.read_cache(file)
    if not snapshot:
        return 0
    snapshot.setdefault("total", len(snapshot["tracks"]))
    remaining = {i: m for i, m in snapshot["tracks"].items() if not m.get("mbid") or m["mbid"] not in present_ones}
    migrated = len(snapshot["tracks"]) - len(remaining)
    snapshot["tracks"] = remaining
    storage.write_json(file, snapshot)
    wanted = storage.wanted("music")
    if wanted:
        wanted["tracks"] = [m for m in wanted.get("tracks", []) if m["mbid"] not in present_ones]
        wanted["missing"] = summary(wanted["tracks"])
        storage.write_wanted("music", wanted)
    return migrated


def progress():
    snapshot = storage.read_cache(storage.spotify())
    if not snapshot:
        return None
    total = snapshot.get("total", len(snapshot["tracks"]))
    removed = snapshot.get("removed", 0)
    return total - len(snapshot["tracks"]) - removed, removed, total


def remove(identifiers):
    file = storage.spotify()
    snapshot = storage.read_cache(file)
    snapshot.setdefault("total", len(snapshot["tracks"]))
    removed = [snapshot["tracks"].pop(i) for i in identifiers if i in snapshot["tracks"]]
    snapshot["removed"] = snapshot.get("removed", 0) + len(removed)
    storage.write_json(file, snapshot)
    return removed


def merge(old_values, new_ones, origin):
    kept_elements = [m for m in old_values if m.get("origin", "spotify") != origin]
    seen = {m["mbid"] for m in kept_elements}
    return kept_elements + [m for m in new_ones if m["mbid"] not in seen]
