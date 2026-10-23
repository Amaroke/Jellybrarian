import argparse
import sys
from datetime import date, datetime

import anime
import config
import storage
import tmdb_checks
import genres
import languages
import mal
import music_wanted
import scan
import tmdb

ANIME_LINKS = {"spin_off", "alternative_setting", "alternative_version"}
MANGA_LINKS = {"sequel", "prequel", "side_story", "parent_story", "spin_off", "alternative_setting", "alternative_version"}


class FollowUps:
    def __init__(self):
        self.catalog = []
        self.to_search = []

    def add(self, media, name, detail, source):
        if not any(s["media"] == media and s["follow_up"] == name for s in self.catalog):
            self.catalog.append({"media": media, "follow_up": name, "detail": detail, "source": source})


def title_key(title):
    return "".join(c for c in title.casefold() if c.isalnum())


def series(report, follow_ups):
    animes, present_ones = [], set()
    spin_offs = storage.read_cache(storage.cache("spin_offs"))
    titles = {title_key(t) for _, t, _, _ in report.series}
    for n, (folder, title, identifier, _) in enumerate(report.series, 1):
        if not identifier or not report.compliant(folder / "_"):
            continue
        print(f"Franchise {n}/{len(report.series)} {title}", file=sys.stderr, flush=True)
        work = tmdb_checks.details("tv", identifier)
        if not work:
            continue
        if (report.type == "anime" or anime.is_anime(work)) and mal.key():
            malid = anime.mal_id(work)
            if malid:
                entries = mal.franchise(malid)
                present_ones |= {e["id"] for e in entries}
                animes.append((title, entries))
                continue
        entry = spin_offs.get(title)
        if not storage.fresh(entry):
            follow_ups.to_search.append(f"Spin-off Show: {title}")
            continue
        for name in entry["follow_ups"]:
            if title_key(name) not in titles:
                follow_ups.add(title, name, "spin-off show", entry["source"])
    for n, (title, entries) in enumerate(animes, 1):
        print(f"Follow-ups {n}/{len(animes)} {title}", file=sys.stderr, flush=True)
        for e in entries:
            for link in (mal.anime(e["id"]) or {}).get("related_anime") or []:
                if link["relation_type"] in ANIME_LINKS and link["node"]["id"] not in present_ones and (mal.anime(link["node"]["id"]) or {}).get("status") != "not_yet_aired":
                    follow_ups.add(title, link["node"]["title"], link["relation_type"], f"MAL {link['node']['id']}")


def readings(report, follow_ups):
    present_ones = {identifier for _, _, identifier, *_ in report.mangas if identifier}
    for n, (folder, title, identifier, *_) in enumerate(report.mangas, 1):
        if not identifier or not report.compliant(folder / "_"):
            continue
        print(f"Follow-ups {n}/{len(report.mangas)} {title}", file=sys.stderr, flush=True)
        entry = mal.manga(identifier) or {}
        for link in entry.get("related_manga") or []:
            if link["relation_type"] in MANGA_LINKS and link["node"]["id"] not in present_ones and (mal.manga(link["node"]["id"]) or {}).get("status") != "not_yet_published":
                follow_ups.add(title, link["node"]["title"], link["relation_type"], f"MAL {link['node']['id']}")
    spin_offs = storage.read_cache(storage.cache("spin_offs"))
    titles = {title_key(t) for _, t, _, _ in report.books}
    for file, title, identifier, book_series in report.books:
        if not identifier or book_series or not report.compliant(file):
            continue
        entry = spin_offs.get(title)
        if not storage.fresh(entry):
            follow_ups.to_search.append(f"Follow-up of the Book: {title}")
            continue
        for name in entry["follow_ups"]:
            if title_key(name) not in titles:
                follow_ups.add(title, name, "follow_up", entry["source"])


def search(type_):
    root = config.folder(type_, "root")
    if storage.corrections(type_, "root").is_file():
        print(f"Corrections pending for {root}: their Works stay out of the Wanted list until /jb-{type_}-rename root has applied them")
    report, genre, missing, to_look_up = scan.examine(root, True, type_)
    follow_ups = FollowUps()
    music = {}
    if genre is genres.MUSIC:
        result = music_wanted.search(report)
        if result is None:
            print("No Spotify snapshot: run spotify.py snapshot then musicbrainz.py resolve")
            sys.exit(2)
        tracks, doubtful, outside, without_listing = result
        missing = music_wanted.summary(tracks)
        migrated, removed, total = music_wanted.progress()
        print(f"Spotify migration: {migrated} Track(s) migrated out of {total}, {removed} removed, {total - migrated - removed} remaining")
        music = {"tracks": tracks, "doubtful": doubtful, "not_on_musicbrainz": outside}
        scan.show("Without a MusicBrainz listing, run music.py listings:", without_listing)
        scan.show("Doubtful, to ask the user:", [f"{d['track']} ({len(d['candidates'])} candidate(s))" for d in doubtful])
        scan.show("Not on MusicBrainz, not downloaded:", outside)
    elif genre is genres.READINGS:
        if not mal.key():
            print(mal.key.message(", Manga relations not searched"))
        else:
            readings(report, follow_ups)
    else:
        if not tmdb.key():
            print(tmdb.key.message())
            sys.exit(2)
        series(report, follow_ups)

    non_compliant = sorted(m for m, deviations in report.deviations.items() if any(n in ("name", "location") for n, _, _ in deviations))
    scan.show(f"Non compliant, run /jb-{type_}-check root first:", non_compliant)
    for title, lines in storage.sections(missing, follow_ups.catalog, storage.ignored(type_)).items():
        scan.show(f"{title}:", lines)
    scan.show("To look up on the web for Missing items:", to_look_up)
    scan.show("To look up on the web for Follow-ups:", follow_ups.to_search)
    content = {
        "folder": str(root),
        "genre": genre.name,
        "type": type_,
        "missing": missing,
        "follow_ups": follow_ups.catalog,
        "to_look_up": to_look_up,
        "to_search": follow_ups.to_search,
    } | music
    file = storage.in_progress(type_, "find-missing")
    storage.write_json(file, {"start": datetime.now().isoformat(timespec="seconds"), "step": "lookup", "wanted": content})
    print(f"find-missing progress: {file}")


def save(type_):
    draft = storage.in_progress(type_, "find-missing")
    if not draft.is_file():
        print(f"No Wanted list draft: {draft}")
        sys.exit(2)
    content = storage.read_json(draft)["wanted"]
    ignored = storage.ignored(type_)
    missing = {m: p for m, p in content["missing"].items() if m not in ignored}
    follow_ups = [s for s in content["follow_ups"] if storage.label(s) not in ignored]
    music = {}
    if content["type"] == "music":
        tracks = music_wanted.filter_ignored(content["tracks"], ignored)
        tracks = music_wanted.merge((storage.wanted(type_) or {}).get("tracks", []), tracks, "spotify")
        missing = music_wanted.summary(tracks)
        follow_ups = []
        music = {"tracks": tracks, "not_on_musicbrainz": content["not_on_musicbrainz"]}
    storage.write_wanted(type_, {
        "date": date.today().isoformat(),
        "genre": content["genre"],
        "type": content["type"],
        "missing": missing,
        "follow_ups": follow_ups,
    } | music)
    print(f"Missing: {len(missing)}")
    print(f"Follow-ups: {len(follow_ups)}")
    print(f"Ignored removed: {len(content['missing']) - len(missing) + len(content['follow_ups']) - len(follow_ups)}")
    print(f"Wanted: {storage.of_type(type_, 'wanted')}")
    draft.unlink()


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("search").add_argument("type", choices=config.TYPES)
    subparsers.add_parser("save").add_argument("type", choices=config.TYPES)
    args = parser.parse_args()
    languages.use(args.type)

    if args.command == "save":
        save(args.type)
    else:
        search(args.type)


if __name__ == "__main__":
    config.run_main(main)
