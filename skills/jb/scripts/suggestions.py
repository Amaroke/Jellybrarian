import argparse
import random
import sys
import urllib.parse
from collections import defaultdict
from datetime import datetime

import api
import config
import storage
import jellyfin
import music_wanted
import musicbrainz
import music
import spotify

TYPE = "music"
SOURCES = {"albums": "album", "artists": "artist", "new": "new"}
ACTIONS = {"albums": "find-missing-album", "artists": "find-missing-artist", "new": "find-new-song"}
LASTFM = "https://ws.audioscrobbler.com/2.0/"
lastfm_key = api.Key("Last.fm API key missing", "lastfm", "key")


def progress(source):
    return storage.in_progress(TYPE, ACTIONS[source])


def present_ones():
    root = config.folder(TYPE, "root")
    mbids = {m for d in (root, config.folder(TYPE, "incoming")) for f in jellyfin.walk(d) if f.is_file() and (m := music.from_name(f))}
    return mbids


def discarded():
    mbids = present_ones()
    mbids |= {m["mbid"] for m in (storage.wanted(TYPE) or {}).get("tracks", [])}
    mbids |= {l["mbid"] for l in storage.grabbed(TYPE)}
    return mbids


def ignore(artist, title, ignored):
    return artist in ignored or f"{artist} : {title}" in ignored


def entry(mbid, duration, reason, source, source_title=None):
    f = music.listing(mbid)
    if not f:
        return None
    artist = music.artist_name(f["folder"])
    title = music.title_of(f)
    return {
        "mbid": mbid,
        "artist": artist,
        "title": title,
        "artists": [music.artist_name(i, n) for i, n in f["artists"]],
        "spotify_title": source_title or title,
        "duration": duration,
        "path": music.final_path(mbid, f, ".flac"),
        "origin": SOURCES[source],
        "reason": reason,
    }


def albums(state, ignored):
    listings = storage.read_cache(music.TRACKS)
    all_albums = storage.read_cache(music.ALBUMS)
    threshold = config.value(TYPE, "album_threshold", 50) / 100
    here = present_ones()
    excluded = discarded() | {s["mbid"] for s in state["suggestions"]}
    by_album = defaultdict(set)
    for mbid in here:
        f = listings.get(mbid)
        if f and f.get("album_mbid") in all_albums:
            by_album[f["album_mbid"]].add(mbid)
    retained = []
    for album, mbids in by_album.items():
        album_tracks = all_albums[album]["album_tracks"]
        if len(mbids) / len(album_tracks) >= threshold and len(mbids) < len(album_tracks):
            retained.append((album, mbids, album_tracks))
    for n, (album, mbids, album_tracks) in enumerate(retained, 1):
        print(f"Album {n}/{len(retained)} {all_albums[album]['title']}", file=sys.stderr, flush=True)
        reason = f"{all_albums[album]['title']}, {len(mbids)} Tracks out of {len(album_tracks)}"
        for mbid, title, duration in album_tracks:
            if mbid in excluded:
                continue
            e = entry(mbid, duration, reason, "albums", title)
            if e and not ignore(e["artist"], e["title"], ignored):
                state["suggestions"].append(e)
                excluded.add(mbid)
        storage.write_json(progress("albums"), state)


def artists(state, ignored):
    listings = storage.read_cache(music.TRACKS)
    minimum = config.value(TYPE, "min_artist", 3)
    excluded = discarded() | {s["mbid"] for s in state["suggestions"]}
    tally = defaultdict(int)
    for mbid in present_ones():
        f = listings.get(mbid)
        if f:
            tally[f["folder"]] += 1
    retained = sorted((music.artist_name(a), a) for a, n in tally.items() if n >= minimum and a not in state.get("done", []))
    for n, (name, identifier) in enumerate(retained, 1):
        print(f"Artist {n}/{len(retained)} {name}", file=sys.stderr, flush=True)
        if name in ignored:
            continue
        found_items = (spotify.get("search", q=f'artist:"{name}"', type="artist", limit=5) or {}).get("artists", {}).get("items") or []
        artist = next((a for a in found_items if musicbrainz.key(a["name"]) == musicbrainz.key(name)), None)
        for album_track in (spotify.get(f"artists/{artist['id']}/top-tracks", market=config.value("spotify", "market", "US")) or {}).get("tracks") or [] if artist else []:
            isrc = ((album_track.get("external_ids") or {}).get("isrc") or "").upper()
            duration = round((album_track.get("duration_ms") or 0) / 1000)
            mbid = musicbrainz.recording(isrc, duration) if isrc else None
            if not mbid or mbid in excluded:
                continue
            e = entry(mbid, duration, f"popular with {name}", "artists", album_track["name"])
            if e and e["artist"] == name and not ignore(e["artist"], e["title"], ignored):
                state["suggestions"].append(e)
                excluded.add(mbid)
        state.setdefault("done", []).append(identifier)
        storage.write_json(progress("artists"), state)


def lastfm(method, **params):
    url = f"{LASTFM}?{urllib.parse.urlencode({'method': method, 'api_key': lastfm_key(), 'format': 'json', **params})}"
    return api.read(url) or {}


def resolve_tracks(artist, title):
    query = f'recording:"{title.replace(chr(34), " ")}" AND artist:"{artist.replace(chr(34), " ")}"'
    for r in (musicbrainz.get("recording", query=query, limit=10) or {}).get("recordings") or []:
        c = musicbrainz.candidate(r)
        if musicbrainz.key(c["title"]) == musicbrainz.key(title) and musicbrainz.key(artist) in {musicbrainz.key(a) for a in c["artists"]}:
            return c
    return None


def seeds(since):
    listings = storage.read_cache(music.TRACKS)
    known = [(music.artist_name(f["folder"]), music.title_of(f)) for m in present_ones() if (f := listings.get(m))]
    if since:
        artist, _, title = since.partition(" - ")
        picked = [(a, t) for a, t in known if musicbrainz.key(a) == musicbrainz.key(artist) and (not title or musicbrainz.key(t) == musicbrainz.key(title))]
        return picked or [(artist, title)]
    random.shuffle(known)
    return known


def new_ones(state, ignored, count_, since):
    excluded = discarded() | {s["mbid"] for s in state["suggestions"]}
    seen = set(state.get("seen", []))
    for artist, title in seeds(since):
        if len(state["suggestions"]) >= count_:
            break
        print(f"Seed {len(state['suggestions'])}/{count_} {artist} - {title}", file=sys.stderr, flush=True)
        if title:
            similar = (lastfm("track.getsimilar", artist=artist, track=title, limit=10, autocorrect=1).get("similartracks") or {}).get("track") or []
            pairs = [(t["artist"]["name"], t["name"], f"close to {artist} - {title}") for t in similar]
        else:
            neighbours = (lastfm("artist.getsimilar", artist=artist, limit=10, autocorrect=1).get("similarartists") or {}).get("artist") or []
            pairs = [(a["name"], t["name"], f"artist close to {artist}") for a in neighbours for t in ((lastfm("artist.gettoptracks", artist=a["name"], limit=2).get("toptracks") or {}).get("track") or [])]
        for other, name, reason in pairs:
            key = musicbrainz.key(f"{other} {name}")
            if key in seen or ignore(other, name, ignored) or len(state["suggestions"]) >= count_:
                continue
            seen.add(key)
            c = resolve_tracks(other, name)
            if not c or c["mbid"] in excluded:
                continue
            e = entry(c["mbid"], c["duration"], reason, "new", name)
            if e and not ignore(e["artist"], e["title"], ignored):
                state["suggestions"].append(e)
                excluded.add(c["mbid"])
        state["seen"] = sorted(seen)
        storage.write_json(progress("new"), state)


def show(state):
    by_artist = defaultdict(list)
    for n, s in enumerate(state["suggestions"], 1):
        decision = {True: " [accepted]", False: " [declined]"}.get(s.get("accepted"), "")
        by_artist[s["artist"]].append(f"{n}. {s['title']} ({s['reason']}){decision}")
    for artist in sorted(by_artist, key=str.casefold):
        print(artist)
        for line in by_artist[artist]:
            print(f"  {line}")
    print(f"{len(state['suggestions'])} Suggestion(s)")


def save(source):
    file = progress(source)
    state = storage.read_json(file)
    approved = [s for s in state["suggestions"] if s.get("accepted") is True]
    declined = [s for s in state["suggestions"] if s.get("accepted") is False]
    if declined:
        storage.modify(TYPE, "ignored", additions=[f"{s['artist']} : {s['title']}" for s in declined])
    wanted = storage.wanted(TYPE) or {"type": TYPE, "genre": "music", "missing": {}, "follow_ups": []}
    tracks = wanted.get("tracks", []) + [{k: v for k, v in s.items() if k not in ("accepted", "reason")} for s in approved if s["mbid"] not in {m["mbid"] for m in wanted.get("tracks", [])}]
    wanted |= {"tracks": tracks, "missing": music_wanted.summary(tracks), "date": datetime.now().date().isoformat()}
    storage.write_wanted(TYPE, wanted)
    file.unlink()
    print(f"Accepted, added to the Wanted list: {len(approved)}")
    print(f"Declined, now Ignored: {len(declined)}")
    print(f"Unanswered, forgotten: {len(state['suggestions']) - len(approved) - len(declined)}")


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("search").add_argument("source", choices=SOURCES)
    p = subparsers.choices["search"]
    p.add_argument("--count", type=int, default=50)
    p.add_argument("--since")
    subparsers.add_parser("show").add_argument("source", choices=SOURCES)
    subparsers.add_parser("save").add_argument("source", choices=SOURCES)
    args = parser.parse_args()

    file = progress(args.source)
    if args.command == "save":
        save(args.source)
        return
    if args.command == "show":
        show(storage.read_json(file))
        return
    if args.source == "new" and not lastfm_key():
        print(lastfm_key.message())
        sys.exit(config.MISSING_CONFIG)
    state = storage.read_cache(file) or {"start": datetime.now().isoformat(timespec="seconds"), "step": "lookup", "suggestions": []}
    ignored = storage.ignored(TYPE)
    if args.source == "albums":
        albums(state, ignored)
    elif args.source == "artists":
        artists(state, ignored)
    else:
        new_ones(state, ignored, args.count, args.since)
    state["step"] = "questions"
    storage.write_json(file, state)
    show(state)
    print(f"Progress: {file}")


if __name__ == "__main__":
    config.run_main(main)
