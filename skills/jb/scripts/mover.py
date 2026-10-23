import argparse
import os
import re
import sys
from collections import defaultdict

import apply_plan
import config
import storage
import tmdb_checks
import genres
import jellyfin
import languages
import music_wanted
import music
import releases
import music_releases
import scan
import scan_readings
import scan_music
import slskd
import tmdb

TMDBID = re.compile(r"\[tmdbid-(\d+)\]")
BLOCKING = ("name", "location", "file")


def examine(root, type_):
    report = scan.Report(root, type_)
    genre = genres.TYPES[type_]
    episodes = set()
    if genre is genres.MUSIC:
        scan_music.check(report)
    elif genre is genres.READINGS:
        scan_readings.check(report)
    else:
        episodes = scan.check_root(report, free_episodes=True)
    scan.exclude_other_types(report, episodes)
    if type_ == "movie":
        episodes = set()
    return report, genre, episodes


def non_compliant(report):
    works, files = {}, {}
    for media, deviations in report.deviations.items():
        for kind, path, message in deviations:
            if kind not in BLOCKING:
                continue
            if media == "(root)":
                files.setdefault(path, f"{kind}: {message}")
            else:
                works.setdefault(media, f"{kind}: {message}")
    return works, files


def index(videos):
    ids, series = {}, defaultdict(set)
    for f in videos:
        m = TMDBID.search(f.name)
        if m:
            ids[int(m[1])] = f.parent
        if scan.EPISODE.match(f.name):
            series[f.parent].add(f)
    titles = defaultdict(set)
    for folder in series:
        title, identifier = scan.separate(folder.name)
        if identifier:
            titles[title].add(folder)
    return ids, titles


def episode_slot(episode, destination, series):
    title = scan.EPISODE.match(episode.name)["series"]
    folders = series.get(title, set())
    if len(folders) == 1:
        return next(iter(folders)) / episode.name, None
    if folders:
        return None, f"name: Show « {title} » found in several folders of the destination"
    return None, f"name: Show « {title} » missing from the destination"


def movie_slot(movie, destination, ids, warnings):
    m = TMDBID.search(movie.name)
    if not m or not tmdb.key():
        return destination / movie.name
    work = tmdb_checks.details("movie", int(m[1]))
    collection = work and work.details.get("belongs_to_collection")
    if not collection:
        return destination / movie.name
    parts = {p["id"] for p in (tmdb_checks.call(f"collection/{collection['id']}") or {}).get("parts") or []}
    folders = [ids[i] for i in parts if i in ids]
    filed = [d for d in folders if d != destination]
    if filed:
        return max(set(filed), key=filed.count) / movie.name
    if folders:
        warnings.append(f"{movie.name}: TMDB Collection « {collection['name']} » already at the root of the destination, without a folder")
    return destination / movie.name


def moves(source, destination, report, genre, episodes, videos):
    works, files = non_compliant(report)
    ids, series = index(videos)
    warnings = []
    ops = []
    for d in sorted(c for c in jellyfin.content(source) if c.is_dir()):
        if d.name in works or jellyfin.sidecar(d) or not genres.contains(d, genre):
            continue
        ops += [(f, destination / f.relative_to(source)) for f in sorted(d.rglob("*")) if f.is_file()]
    for f in sorted(c for c in jellyfin.content(source) if c.is_file()):
        relative = f.relative_to(source).as_posix()
        if relative in files or not genre.owns_file(f):
            continue
        if f in episodes:
            target, reason = episode_slot(f, destination, series)
            if not target:
                files[relative] = reason
                continue
        elif genre is genres.VIDEOS:
            target = movie_slot(f, destination, ids, warnings)
        else:
            target = destination / f.name
        ops += genre.with_companions([(f, target)])
    left = [f"{m}: {r}" for m, r in sorted(works.items())] + [f"{f}: {r}" for f, r in sorted(files.items())]
    return ops, left, warnings


def collisions(ops):
    errors = []
    targets = set()
    for source, target in ops:
        key = os.path.normcase(str(target))
        if key in targets:
            errors.append(f"duplicate target: {target}")
        targets.add(key)
        if target.exists():
            errors.append(f"already in the destination: {target}")
    return errors


def work_of(destination, target):
    relative = target.parent.relative_to(destination)
    return relative.as_posix() if relative.parts else "(root)"


def forget_grabbed(type_):
    if type_ == "anime":
        return releases.forget_grabbed()
    if type_ == "music":
        if slskd.key() and slskd.reachable():
            before = len(storage.grabbed(type_))
            music_releases.active_grabbed()
            return before - len(storage.grabbed(type_))
    return 0


def main():
    parser = argparse.ArgumentParser()
    config.arguments(parser, target=False)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    languages.use(args.type)

    source, destination = config.folder(args.type, "incoming"), config.folder(args.type, "root")
    if source == destination or destination in source.parents or source in destination.parents:
        print("The source and the destination must not be nested.")
        sys.exit(2)

    report, genre, episodes = examine(source, args.type)
    existing = jellyfin.walk(destination)
    if any(g.owns_file(f) for g in genres.ALL for f in existing):
        genre_target = genres.detect(destination)
        if genre_target is not genre:
            print(f"Source of {genre.name}, destination of {genre_target.name}: move refused.")
            sys.exit(2)
    if genre is genres.VIDEOS and not tmdb.key():
        print(tmdb.key.message(", the Movies at the root are moved to the root of the destination"))

    videos = [f for f in existing if genre.owns_file(f)]
    ops, left, warnings = moves(source, destination, report, genre, episodes, videos)
    errors = collisions(ops)
    if errors:
        scan.show("Move refused:", errors)
        sys.exit(3)

    by_work = defaultdict(list)
    for s, c in ops:
        by_work[work_of(destination, c)].append(f"{s.relative_to(source).as_posix()}  →  {c.relative_to(destination).as_posix()}")
    for media in sorted(by_work):
        state = "" if media == "(root)" else " (merge)" if (destination / media).is_dir() else " (new)"
        scan.show(f"{media}{state}:", by_work[media])
    scan.show("Left in the source, non compliant:", left)
    scan.show("Collections to redo, /jb-movie-check root recommended:", warnings)
    print(f"{len(ops)} file(s) to move")

    if not args.apply:
        print("Dry run: nothing was changed.")
        return
    blocked = []
    for s, c in ops:
        try:
            apply_plan.move(s, c)
        except OSError as error:
            blocked.append(f"{s.relative_to(source)}: {error.strerror}")
    remaining = apply_plan.clean(source, ops, genre)
    for folder in remaining:
        content = ", ".join(f.name for f in folder.iterdir())
        print(f"Folder kept in the source: {folder.relative_to(source)} ({content})")
    if genre is genres.MUSIC:
        present_ones = {m for f in jellyfin.walk(destination) if f.is_file() and (m := music.from_name(f))}
        migrated = music_wanted.migrate(present_ones)
        if migrated:
            print(f"{migrated} Track(s) migrated, removed from the Spotify snapshot and the Wanted list")
    forgotten = forget_grabbed(args.type)
    if forgotten:
        print(f"{forgotten} Grabbed item(s) filed, forgotten")
    if blocked:
        scan.show("Locked files, run again to move them:", blocked)
        sys.exit(4)
    print("Move finished.")


if __name__ == "__main__":
    config.run_main(main)
