import argparse
import re
import sys
import time
import urllib.error
import urllib.parse
from datetime import datetime
from pathlib import Path

import anime
import api
import config
import languages
import mal
import prowlarr
import qbittorrent
import releases
import scan
import storage
import tmdb
import tmdb_checks

TYPE = "anime"
ACTION = "mal-download"
TARGET = "mal"
STATUSES = {"1": "watching", "2": "completed", "3": "on_hold", "4": "dropped", "6": "plan_to_watch", "7": None}
MAIN_TYPES = ("tv", "ona")
EPISODE = re.compile(r" - S(\d{2})E(\d{2,4})(?:-E(\d{2,4}))? - ")
PERIOD = 300


def parse(url):
    parts = urllib.parse.urlsplit(url.strip())
    m = re.match(r"^/animelist/([^/]+)/?$", parts.path)
    if parts.netloc.removeprefix("www.") != "myanimelist.net" or not m:
        print(f"Not a MyAnimeList anime list: {url}. Expected https://myanimelist.net/animelist/<user>?status=<n>")
        sys.exit(2)
    query = urllib.parse.parse_qs(parts.query)
    status = query.pop("status", ["7"])[0]
    if status not in STATUSES:
        print(f"Unknown status {status}: expected one of {', '.join(STATUSES)}")
        sys.exit(2)
    return m[1], STATUSES[status], sorted(query)


def listed(user, status):
    params = {"limit": 1000, "nsfw": "true"} | ({"status": status} if status else {})
    try:
        page = mal.get(f"users/{urllib.parse.quote(user)}/animelist", **params)
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            print(f"The list of {user} is private: MAL refuses to read it")
            sys.exit(2)
        raise
    if page is None:
        print(f"MAL user not found: {user}")
        sys.exit(2)
    identifiers = []
    while page:
        identifiers += [d["node"]["id"] for d in page.get("data", [])]
        following = (page.get("paging") or {}).get("next")
        page = api.read(following, {"X-MAL-CLIENT-ID": mal.key()}) if following else None
    return identifiers


def main_entry(identifier):
    entries = list(mal.franchise(identifier))
    for link in mal.anime(identifier).get("related_anime") or []:
        if link["relation_type"] == "parent_story":
            entries += mal.franchise(link["node"]["id"])
    for kind in MAIN_TYPES:
        found = sorted((e for e in entries if e["media_type"] == kind), key=lambda e: e.get("start_date") or "9999")
        if found:
            return found[0]["id"]
    return identifier


def placement(identifier):
    main = main_entry(identifier)
    seasons, specials = mal.structure(main)
    if not any(e["id"] == identifier for parts in seasons for e in parts) and not any(e["id"] == identifier for e in specials):
        main = identifier
        seasons, specials = mal.structure(main)
    number = 0
    for entry in specials:
        count_ = entry["num_episodes"] or 1
        if entry["id"] == identifier:
            return main, releases.mal_seasons(main), {(0, number + k) for k in range(1, count_ + 1)}
        number += count_
    built = releases.mal_seasons(main)
    return main, built, {(s.number, e) for s in built for e in s.relatives(identifier)}


def present(destination):
    found, folders = {}, {}
    for folder in sorted(d for d in destination.iterdir() if d.is_dir()):
        m = scan.IDENTIFIER.match(folder.name)
        work = m and tmdb_checks.details("tv", m["id"])
        if not work or not anime.is_anime(work):
            continue
        _, catalog = anime.episodes(work, tmdb_checks.tmdb_episodes(work))
        if not catalog:
            continue
        files = {
            (int(s), e)
            for f in folder.rglob("*")
            for s, a, b in EPISODE.findall(f.name)
            for e in range(int(a), int(b or a) + 1)
        }
        for n in files & catalog.keys():
            found.setdefault(catalog[n]["mal"], set()).add(n)
        for episode in catalog.values():
            folders.setdefault(episode["mal"], folder.name)
    return found, folders


def special_releases(media, entry, numbers, folder, destination):
    keys = [k for t in mal.titles(entry) if t.isascii() and (k := tmdb_checks.key(t))]
    titles = [t for t in mal.titles(entry)[:2] if t.isascii()]
    tags = languages.release_keywords(TYPE)[:1]
    candidates = {}
    for query in dict.fromkeys(q for t in titles for q in (t, *(f"{t} {tag}" for tag in tags))):
        for release in prowlarr.search(query):
            head = tmdb_checks.key(re.split(r"\s\(", release["title"])[0])
            if release["hash"] not in candidates and releases.acceptable(release) and any(k in head for k in keys):
                candidates[release["hash"]] = release
    elements = [f"{media} : S00E{e:02d}" for _, e in sorted(numbers)]
    if not candidates:
        return [], elements
    release = max(candidates.values(), key=releases.score)
    group = releases.span_label(0, {e for _, e in numbers}, False)
    return [{
        "media": media,
        "group": group,
        "elements": elements,
        "release": release,
        "path": str(destination / releases.name_on(folder) / releases.name_on(group)),
    }], []


def search(url, destination):
    user, status, ignored_params = parse(url)
    if ignored_params:
        print(f"Ignored URL parameters: {', '.join(ignored_params)}")
    found, folders = present(destination)
    proposals, not_found, skipped, airing = [], [], [], []
    for identifier in listed(user, status):
        entry = mal.anime(identifier)
        if not entry:
            continue
        if entry.get("status") == "not_yet_aired":
            skipped.append(f"{entry['title']} : not yet aired")
            continue
        main, seasons, numbers = placement(identifier)
        if not numbers:
            skipped.append(f"{entry['title']} : episode count unknown on MAL")
            continue
        numbers -= found.get(identifier, set())
        if not numbers:
            skipped.append(f"{entry['title']} : already in the folder")
            continue
        base = releases.base_of(seasons) if seasons else entry["title"]
        folder = folders.get(main) or folders.get(identifier) or base
        if entry.get("status") == "currently_airing":
            airing.append(entry["title"])
        if all(s == 0 for s, _ in numbers):
            choice, remaining = special_releases(base, entry, numbers, folder, destination)
        else:
            choice, remaining = [], []
            for season in seasons:
                wanted = {e for s, e in numbers if s == season.number}
                if wanted:
                    c, r = releases.cover_span(base, season, wanted, seasons, base, folder, destination)
                    choice += c
                    remaining += r
        proposals += choice
        not_found += remaining
    return {
        "folder": str(destination),
        "list": url,
        "proposals": proposals,
        "not_found": not_found,
        "skipped": skipped,
        "airing": airing,
    }


def launch(file):
    content = storage.read_json(file)
    for p in content["releases"]["proposals"]:
        if p.get("grabbed"):
            continue
        Path(p["path"]).mkdir(parents=True, exist_ok=True)
        qbittorrent.add(p["release"]["url"], p["path"])
        p["grabbed"] = True
        storage.write_json(file, content | {"step": "downloading"})
        print(f"Grabbed: {p['media']} {p['group']} → {p['path']}")
    storage.write_json(file, content | {"step": "downloading"})


def wait(file):
    content = storage.read_json(file)
    hashes = {p["release"]["hash"] for p in content["releases"]["proposals"] if p.get("grabbed")}
    while True:
        running = {h: t for h, t in qbittorrent.torrents().items() if h in hashes}
        done = len(hashes) - len(running)
        progress = sum(t["progress"] for t in running.values())
        print(f"Downloads: {done}/{len(hashes)} done, {progress + done:.1f}/{len(hashes)} overall", flush=True)
        if not running:
            return
        time.sleep(PERIOD)


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("folder").add_argument("path")
    subparsers.add_parser("search").add_argument("url")
    subparsers.add_parser("grab")
    subparsers.add_parser("wait")
    args = parser.parse_args()
    languages.use(TYPE)

    if args.command == "folder":
        destination = Path(args.path).expanduser().resolve()
        destination.mkdir(parents=True, exist_ok=True)
        storage.write_json(config.mal_folder(TYPE), {"folder": str(destination)})
        print(f"Destination folder: {destination}")
        return
    if not qbittorrent.reachable():
        print(f"qBittorrent unreachable at {qbittorrent.url()}: start qBittorrent and enable its web UI")
        sys.exit(2)
    file = storage.in_progress(TYPE, ACTION, TARGET)
    if args.command == "wait":
        wait(file)
        content = storage.read_json(file)
        storage.write_json(file, content | {"step": "check"})
        print("Downloads done")
        return
    if args.command == "grab":
        launch(file)
        return
    if not prowlarr.key():
        print(prowlarr.key.message())
        sys.exit(config.MISSING_CONFIG)
    if not tmdb.key() or not mal.key():
        print("TMDB key and MAL Client ID required to read the list and find the split of the Animes. " + (tmdb.key.message() if not tmdb.key() else mal.key.message()))
        sys.exit(config.MISSING_CONFIG)
    content = search(args.url, config.folder(TYPE, TARGET))
    scan.show("Proposals:", releases.grouped(content["proposals"]))
    scan.show("Not found:", releases.by_work(content["not_found"]))
    scan.show("Still airing, aired Episodes only:", content["airing"])
    scan.show("Skipped:", content["skipped"])
    storage.write_json(file, {"start": datetime.now().isoformat(timespec="seconds"), "step": "review", "releases": content})
    print(f"Progress: {file}")


if __name__ == "__main__":
    config.run_main(main)
