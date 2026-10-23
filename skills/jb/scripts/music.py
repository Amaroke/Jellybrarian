import argparse
import json
import re
import sys
import unicodedata
import urllib.error
import urllib.request

import config
import storage
import jellyfin
import musicbrainz
import names

try:
    import mutagen
    from mutagen.easyid3 import EasyID3
    from mutagen.flac import FLAC, Picture
    from mutagen.id3 import APIC, ID3
except ImportError:
    mutagen = None

AUDIO = {".flac", ".mp3", ".m4a", ".ogg", ".opus", ".wav", ".aac", ".wma", ".alac", ".aiff", ".ape"}
WRITTEN = {".flac", ".mp3"}
SIDECARS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".cue", ".log", ".m3u", ".m3u8", ".nfo", ".txt", ".sfv", ".md5", ".accurip", ".pls"}
ARTIST = re.compile(r"^(?P<name>.+?) \[mbid-(?P<id>[0-9a-f-]{36})\]$")
TRACK = re.compile(r"^(?P<title>.+?) \[mbid-(?P<id>[0-9a-f-]{36})\]$")
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
VARIOUS = "89ad4ac3-39f7-470e-963a-56509c546377"
EXCLUDED = {"Compilation", "DJ-mix"}
LEVELS = {"Album": 0, "EP": 1, "Single": 2}
KEYS = ("title", "artist", "albumartist", "album", "tracknumber", "date", "musicbrainz_trackid", "musicbrainz_albumid", "musicbrainz_releasegroupid", "musicbrainz_artistid", "musicbrainz_albumartistid")
TRACKS = storage.cache("tracks")
ARTISTS = storage.cache("artists")
ALBUMS = storage.cache("albums")


def is_audio(path):
    return path.is_file() and path.suffix.lower() in AUDIO


def to_delete(path):
    return path.is_file() and path.suffix.lower() in SIDECARS


def to_delete_under(root):
    return sorted(f for f in jellyfin.walk(root) if to_delete(f) and f.name.lower() not in jellyfin.TOLERATED)


def latin(text):
    return all(not c.isalpha() or "LATIN" in unicodedata.name(c, "") for c in text)


def credits(catalog):
    return [(c["artist"]["id"], c["artist"]["name"], c.get("joinphrase", "")) for c in catalog or []]


def rank(r):
    group = r.get("release-group") or {}
    is_excluded = set(group.get("secondary-types") or []) & EXCLUDED
    return (3 if is_excluded else LEVELS.get(group.get("primary-type"), 3), r.get("date") or "9999")


def output(releases):
    official = [r for r in releases if r.get("status") in (None, "Official")] or releases
    return min(official, key=rank) if official else None


def releases_out(mbid, firsts):
    if len(firsts) < 25:
        return firsts
    all_entries, shift = [], 0
    while True:
        page = musicbrainz.get("release", recording=mbid, inc="release-groups", limit=100, offset=shift) or {}
        all_entries += page.get("releases") or []
        shift += 100
        if shift >= page.get("release-count", 0):
            return all_entries


def compute(mbid):
    r = musicbrainz.get(f"recording/{mbid}", inc="releases+release-groups+artist-credits")
    if not r:
        return None
    artists = credits(r.get("artist-credit"))
    chosen = output(releases_out(mbid, r.get("releases") or []))
    old_value = storage.read_cache(TRACKS).get(mbid) or {}
    listing = {
        "title": r["title"],
        "artists": [[i, n] for i, n, _ in artists],
        "album": None, "album_mbid": None, "group_mbid": None,
        "album_artists": [], "album_track": None, "date": r.get("first-release-date"),
        "rank": rank(chosen)[0] if chosen else 4,
    }
    if chosen and old_value.get("album_mbid") == chosen["id"] and chosen["id"] in storage.read_cache(ALBUMS):
        listing |= {k: old_value[k] for k in ("album", "album_mbid", "group_mbid", "album_artists", "album_track", "date")}
    elif chosen:
        detail = musicbrainz.get(f"release/{chosen['id']}", inc="artist-credits+recordings") or {}
        album = credits(detail.get("artist-credit")) or artists
        album_tracks = [[t["recording"]["id"], t["recording"]["title"], round((t.get("length") or 0) / 1000)] for media in detail.get("media") or [] for t in media.get("tracks") or []]
        storage.record(ALBUMS, chosen["id"], {"title": chosen["title"], "album_tracks": album_tracks})
        listing |= {
            "album": chosen["title"],
            "album_mbid": chosen["id"],
            "group_mbid": (chosen.get("release-group") or {}).get("id"),
            "album_artists": [[i, n, j] for i, n, j in album],
            "album_track": next((t.get("position") for media in detail.get("media") or [] for t in media.get("tracks") or [] if t["recording"]["id"] == mbid), None),
            "date": chosen.get("date") or listing["date"],
        }
    album = [a for a in listing["album_artists"] if a[0] != VARIOUS]
    listing["folder"] = album[0][0] if album and len(album) == len(listing["album_artists"]) else artists[0][0]
    for i, n, _ in artists + [tuple(a) for a in listing["album_artists"]]:
        if i != VARIOUS and not storage.read_cache(ARTISTS).get(i):
            storage.record(ARTISTS, i, {"name": n})
    return listing


def listing(mbid, network=True):
    if not mbid or not UUID.match(mbid):
        return None
    cache = storage.read_cache(TRACKS)
    if mbid in cache or not network:
        return cache.get(mbid)
    value = compute(mbid)
    if value:
        storage.record(TRACKS, mbid, value)
    return storage.read_cache(TRACKS).get(mbid)


def to_compute(mbid):
    f = storage.read_cache(TRACKS).get(mbid)
    return not f or "rank" not in f or (f["album_mbid"] and f["album_mbid"] not in storage.read_cache(ALBUMS))


def substitute(identifier, track):
    current = listing(track["mbid"])
    best, best_rank = track["mbid"], current["rank"] if current else 4
    sure, _ = musicbrainz.search(track) if track["title"] and track["artists"] else ([], [])
    for other in [s for s in sure if s != track["mbid"]][:5]:
        f = listing(other)
        if f and f["rank"] < best_rank:
            best, best_rank = other, f["rank"]
    if best == track["mbid"]:
        return None
    cache = storage.read_cache(storage.cache("musicbrainz"))
    key = track["isrc"] if (cache.get(track["isrc"]) or {}).get("mbid") == track["mbid"] else f"spotify:{identifier}"
    cache[key] = {"mbid": best, "doubtful": [], "replaces": track["mbid"], "checked": "9999-12-31"}
    storage.write_json(storage.cache("musicbrainz"), cache)
    snapshot = storage.read_cache(storage.spotify())
    snapshot["tracks"][identifier]["mbid"] = best
    storage.write_json(storage.spotify(), snapshot)
    return best


def compute_all(tracks):
    remaining = [m for m in sorted({m["mbid"] for m in tracks.values()}) if to_compute(m)]
    print(f"Listings to compute: {len(remaining)}, about {round(len(remaining) * 2 * musicbrainz.INTERVAL / 60)} min")
    for n, mbid in enumerate(remaining, 1):
        value = compute(mbid)
        if value:
            storage.record(TRACKS, mbid, value)
        if n % 50 == 0:
            print(f"  {n}/{len(remaining)}", flush=True)
    listings = storage.read_cache(TRACKS)
    weak = {i: m for i, m in tracks.items() if (listings.get(m["mbid"]) or {}).get("rank", 4) >= 3}
    print(f"Tracks without Album, EP or single, other recording searched: {len(weak)}", flush=True)
    replaced = [i for i, m in weak.items() if substitute(i, m)]
    print(f"Replaced by a recording on an Album, an EP or a single: {len(replaced)}")


def choose(identifier, mbid):
    snapshot = storage.read_cache(storage.spotify())
    track = snapshot["tracks"][identifier]
    track["mbid"] = None if mbid == "not_found" else mbid
    track["doubtful"] = []
    cache = storage.read_cache(storage.cache("musicbrainz"))
    cache[f"spotify:{identifier}"] = {"mbid": track["mbid"], "doubtful": [], "chosen": True, "checked": "9999-12-31"}
    storage.write_json(storage.cache("musicbrainz"), cache)
    storage.write_json(storage.spotify(), snapshot)
    if track["mbid"]:
        listing(track["mbid"])
    return track


def artist_name(identifier, name=None):
    return (storage.read_cache(ARTISTS).get(identifier) or {}).get("name") or name


def title_of(f):
    return f.get("latin_title") or f["title"]


def final_path(mbid, f, extension):
    folder = f"{names.sanitize(artist_name(f['folder']))} [mbid-{f['folder']}]"
    return f"{folder}/{names.sanitize(title_of(f))} [mbid-{mbid}]{extension.lower()}"


def non_latin(f):
    texts = [title_of(f)] + [artist_name(i, n) for i, n in f["artists"]] + [artist_name(f["folder"])]
    return [t for t in texts if not latin(t)]


def expected_values(mbid, f):
    album = [a for a in f["album_artists"]] or [[i, n, ""] for i, n in f["artists"]]
    tags = {
        "title": [title_of(f)],
        "artist": [artist_name(i, n) for i, n in f["artists"]],
        "albumartist": ["".join(artist_name(i, n) + j for i, n, j in album)],
        "album": [f["album"]] if f["album"] else [],
        "tracknumber": [str(f["album_track"])] if f["album_track"] else [],
        "date": [f["date"]] if f["date"] else [],
        "musicbrainz_trackid": [mbid],
        "musicbrainz_albumid": [f["album_mbid"]] if f["album_mbid"] else [],
        "musicbrainz_releasegroupid": [f["group_mbid"]] if f["group_mbid"] else [],
        "musicbrainz_artistid": [i for i, _ in f["artists"]],
        "musicbrainz_albumartistid": [i for i, _, _ in album],
    }
    return {k: v for k, v in tags.items() if v}


def read(file):
    audio = mutagen.File(file, easy=True)
    if audio is None:
        raise ValueError("unreadable audio file")
    tags = {k.lower(): [str(x) for x in audio[k]] for k in audio.keys()} if audio.tags else {}
    if file.suffix.lower() == ".flac":
        artwork = bool(audio.pictures)
    elif file.suffix.lower() == ".mp3":
        try:
            artwork = bool(ID3(file).getall("APIC"))
        except Exception:
            artwork = False
    else:
        artwork = False
    return tags, artwork, round(audio.info.length) if audio.info else 0


def flaws(file, mbid, f):
    if file.suffix.lower() not in WRITTEN:
        return []
    try:
        tags, artwork, _ = read(file)
    except Exception as error:
        return [str(error)]
    desired_values = expected_values(mbid, f)
    different = sorted(k for k in set(tags) | set(desired_values) if tags.get(k) != desired_values.get(k))
    found_items = [f"tags: {', '.join(different)}"] if different else []
    if not artwork:
        found_items.append("artwork missing")
    return found_items


def artwork(f):
    for url in (f"https://coverartarchive.org/release/{f['album_mbid']}/front-1200", f"https://coverartarchive.org/release-group/{f['group_mbid']}/front-1200"):
        if "None" in url:
            continue
        try:
            query = urllib.request.Request(url, headers={"User-Agent": musicbrainz.AGENT})
            with urllib.request.urlopen(query, timeout=60) as response:
                return response.read(), response.headers.get_content_type()
        except (urllib.error.URLError, TimeoutError):
            continue
    return None


def write(file, mbid, f):
    desired_values = expected_values(mbid, f)
    image = artwork(f)
    if file.suffix.lower() == ".flac":
        audio = FLAC(file)
        audio.delete()
        audio.clear_pictures()
        for k, v in desired_values.items():
            audio[k] = v
        if image:
            p = Picture()
            p.type, p.data, p.mime = 3, image[0], image[1]
            audio.add_picture(p)
        audio.save()
    elif file.suffix.lower() == ".mp3":
        ID3().save(file)
        audio = EasyID3(file)
        for k, v in desired_values.items():
            audio[k] = v
        audio.save()
        if image:
            id3 = ID3(file)
            id3.add(APIC(encoding=3, mime=image[1], type=3, desc="", data=image[0]))
            id3.save()


def from_name(file):
    m = TRACK.match(file.stem)
    return m["id"] if m else None


def grabbed():
    return {l["filename"].replace("\\", "/").rsplit("/", 1)[-1]: l["mbid"] for l in storage.grabbed("music")}


def identify(root, files, save=None):
    proposals = []
    requested = grabbed()
    for n, file in enumerate(files, 1):
        if n % 25 == 0:
            print(f"Identification {n}/{len(files)}", file=sys.stderr, flush=True)
            if save:
                save(proposals)
        relative = file.relative_to(root).as_posix()
        try:
            tags, _, duration = read(file)
        except Exception as error:
            proposals.append({"from": relative, "mbid": None, "doubtful": [], "reason": str(error)})
            continue
        mbid = from_name(file) or requested.get(file.name) or (tags.get("musicbrainz_trackid") or [None])[0]
        if mbid and not UUID.match(mbid.strip().lower()):
            mbid = None
        mbid = mbid.strip().lower() if mbid else None
        doubtful = []
        if not mbid:
            title = (tags.get("title") or [None])[0]
            artists = tags.get("artist") or []
            if not title and " - " in file.stem:
                artist, title = file.stem.split(" - ", 1)
                artists = [artist]
            result = musicbrainz.look_up({"title": title or file.stem, "artists": artists, "duration": duration})
            mbid, doubtful = result["mbid"], result["doubtful"]
        f = listing(mbid) if mbid else None
        proposals.append({
            "from": relative,
            "mbid": mbid if f else None,
            "to": final_path(mbid, f, file.suffix) if f else None,
            "non_latin": non_latin(f) if f else [],
            "doubtful": doubtful,
            "tags": {k: tags.get(k) for k in ("artist", "title", "album") if tags.get(k)},
        })
    return proposals


def main():
    if mutagen is None:
        print("mutagen not found: python -m pip install --user mutagen")
        sys.exit(2)
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    p = subparsers.add_parser("identify")
    p.add_argument("target", choices=config.TARGETS)
    p.add_argument("files", nargs="*")
    p = subparsers.add_parser("listing")
    p.add_argument("mbid")
    subparsers.add_parser("listings")
    p = subparsers.add_parser("choose")
    p.add_argument("spotify")
    p.add_argument("mbid")
    p = subparsers.add_parser("title")
    p.add_argument("mbid")
    p.add_argument("title")
    p = subparsers.add_parser("artist")
    p.add_argument("mbid")
    p.add_argument("name")
    args = parser.parse_args()

    if args.command == "identify":
        root = config.folder("music", args.target)
        file = storage.in_progress("music", "check", args.target)
        already = [p for p in storage.read_cache(file).get("identification", []) if (root / p["from"]).is_file()]
        done = {p["from"] for p in already}
        requested = [root / f for f in args.files]
        if requested:
            already = [p for p in already if p["from"] not in set(args.files)]
            done = {p["from"] for p in already}
        files = requested or [f for f in jellyfin.walk(root) if is_audio(f) and not from_name(f) and f.relative_to(root).as_posix() not in done]
        if done and not requested:
            print(f"Resuming: {len(done)} Track(s) already identified, {len(files)} remaining")

        def save(new_items):
            storage.write_json(file, storage.read_cache(file) | {"identification": already + new_items})

        proposals = already + identify(root, files, save)
        storage.write_json(file, storage.read_cache(file) | {"identification": proposals})
        found_items = [p for p in proposals if p["mbid"]]
        print(f"Identified: {len(found_items)}, including {sum(1 for p in found_items if p['non_latin'])} in non-Latin script")
        print(f"Doubtful: {sum(1 for p in proposals if not p['mbid'] and p['doubtful'])}")
        print(f"Not found: {sum(1 for p in proposals if not p['mbid'] and not p['doubtful'])}")
        print(f"Proposals in the check progress: {file}")
    elif args.command == "listings":
        compute_all({i: m for i, m in storage.read_cache(storage.spotify())["tracks"].items() if m.get("mbid")})
    elif args.command == "choose":
        track = choose(args.spotify, args.mbid)
        print(f"{', '.join(track['artists'])} - {track['title']}: {track['mbid'] or 'not_found'}")
    elif args.command == "listing":
        print(json.dumps(listing(args.mbid), ensure_ascii=False, indent=1))
    elif args.command == "title":
        if not listing(args.mbid):
            print(f"Unknown recording: {args.mbid}")
            sys.exit(2)
        cache = storage.read_cache(TRACKS)
        cache[args.mbid]["latin_title"] = args.title
        storage.write_json(TRACKS, cache)
        print(f"{args.mbid}: {args.title}")
    else:
        storage.record(ARTISTS, args.mbid, {"name": args.name})
        print(f"{args.mbid}: {args.name}")


if __name__ == "__main__":
    config.run_main(main)
