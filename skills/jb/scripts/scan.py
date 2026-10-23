import argparse
from datetime import datetime
import re
import sys
from collections import defaultdict
from pathlib import Path

import archives
import config
import storage
import tmdb_checks
import genres
import jellyfin
import languages
import metadata
import names
import scan_readings
import scan_music
import tmdb

IDENTIFIER = re.compile(r"^(?P<title>.+?) \[tmdbid-(?P<id>\d+)\]$")
RANK = re.compile(r"^(?P<rank>\d+) - (?P<title>.+)$")
EPISODE = re.compile(
    r"^(?P<series>.+?) - S(?P<season>\d{2})E(?P<ep>\d{2,4})(?:-E(?P<ep2>\d{2,4}))? - (?P<title>.+)\.[^.]+$"
)
EPISODE_MARKER = re.compile(r"(?i)\bS\d{1,2}\s?E\d{1,4}\b|\b\d{1,2}x\d{2,3}\b|\b(?:saison|season) \d+|\b[ée]pisode\s*\(?\d+")
RAW_NAME = re.compile(
    r"(?i)\b(?:\d{3,4}p|[xh]\.?26[45]|hevc|web(?:-?dl|rip)?|bluray|bdrip|dvdrip|hdtv|multi|vostfr|truefrench|vff)\b|\w\.\w+\.\w"
)


class Report:
    def __init__(self, root, type_):
        self.root = root
        self.type = type_
        self.other_types = set()
        self.deviations = defaultdict(list)
        self.accepted = []
        self.accepted_list = storage.accepted(type_)
        self.movies = []
        self.series = []
        self.mangas = []
        self.books = []
        self.tracks = []
        self.files = []
        self.to_convert = []
        self.fixed_extensions = {}

    def relative(self, path):
        return path.relative_to(self.root).as_posix()

    def media(self, path):
        relative = path.relative_to(self.root)
        media = relative.parts[0] if len(relative.parts) > 1 or (relative.parts and path.is_dir()) else "(root)"
        return media

    def add(self, path, kind, message):
        relative = self.relative(path)
        if relative in self.accepted_list:
            self.accepted.append(relative)
            return
        self.deviations[self.media(path)].append((kind, relative, message))

    def other_type(self, path, work_type):
        if path in self.other_types:
            return
        self.other_types.add(path)
        media, relative = self.media(path), self.relative(path)
        kept_elements = [e for e in self.deviations.get(media, []) if media == "(root)" and e[1] != relative]
        if kept_elements:
            self.deviations[media] = kept_elements
        else:
            self.deviations.pop(media, None)
        self.add(path, "file", f"{genres.LABELS[work_type]} in a root of {genres.ROOTS[self.type]}, to handle by hand")

    def in_other_type(self, path):
        return any(h == path or h in path.parents for h in self.other_types)

    def compliant(self, path):
        media = self.media(path)
        targets = {self.relative(path)} if media == "(root)" else None
        return not any(
            kind in ("name", "location") and (targets is None or relative in targets)
            for kind, relative, _ in self.deviations.get(media, [])
        )


def separate(name):
    m = IDENTIFIER.match(name)
    return (m["title"], int(m["id"])) if m else (name, None)


def check_extension(report, file):
    if archives.is_reading(file):
        report.add(file, "file", "reading in a video root, to handle by hand")
        return False
    if not jellyfin.is_video(file):
        report.add(file, "file", "neither a video nor a Jellyfin file")
        return False
    if file.suffix != file.suffix.lower():
        report.add(file, "name", "uppercase extension")
    if file.suffix.lower() != ".mp4":
        report.to_convert.append(report.relative(file))
    report.files.append(file)
    return True


def useful_content(folder):
    return [c for c in jellyfin.content(folder) if not jellyfin.sidecar(c)]


def check_episode(report, file, series_title):
    m = EPISODE.match(file.name)
    names.check(report, file, Path(file.name).stem)
    if m["series"] != series_title:
        report.add(file, "name", f"prefix « {m['series']} » different from the folder « {series_title} »")
    if m["ep2"] and int(m["ep2"]) <= int(m["ep"]):
        report.add(file, "name", "second episode lower than the first")
    return file, int(m["season"]), int(m["ep"]), int(m["ep2"]) if m["ep2"] else None, m["title"]


def check_movie(report, file, stem=None):
    title, identifier = separate(stem or Path(file.name).stem)
    if not identifier:
        report.add(file, "name", "TMDB identifier missing")
    if EPISODE_MARKER.search(title):
        report.add(file, "name", "episode number outside the convention")
    elif RAW_NAME.search(title):
        report.add(file, "name", "raw download name")
    names.check(report, file, title)
    return title, identifier


def check_folder(report, folder):
    if folder != report.root:
        names.check(report, folder, folder.name)
    title, identifier = separate(folder.name)

    content = useful_content(folder)
    if not content:
        report.add(folder, "location", "empty folder")
        return

    for subparsers in (c for c in content if c.is_dir()):
        files = [f for f in subparsers.rglob("*") if f.is_file()]
        if not files:
            report.add(subparsers, "location", "empty subfolder")
        for f in files:
            report.add(f, "location", "file in a subfolder")

    videos = [c for c in content if c.is_file() and check_extension(report, c)]
    episodes = [v for v in videos if EPISODE.match(v.name)]
    movies = [v for v in videos if not EPISODE.match(v.name)]

    if episodes:
        if not identifier:
            report.add(folder, "name", "TMDB identifier missing")
        report.series.append((folder, title, identifier, [check_episode(report, e, title) for e in episodes]))
        for f in movies:
            report.add(f, "name", "non compliant file in a show folder")
        return

    check_collection(report, movies)


def check_collection(report, movies):
    if not movies:
        return
    if len(movies) == 1:
        report.add(movies[0], "location", "Collection of a single Movie")
        return
    folder = movies[0].parent
    titles = []
    for f in movies:
        m = RANK.match(Path(f.name).stem)
        if m:
            report.add(f, "name", "order number to remove")
        title, identifier = check_movie(report, f, m["title"] if m else Path(f.name).stem)
        titles.append(title)
        report.movies.append((f, title, identifier, True))
    if all(jellyfin_version(folder.name, title) for title in titles):
        report.add(folder, "name", f"Jellyfin would group these Movies as versions of one, « {folder.name} - » to remove from the file names")


def jellyfin_version(folder, stem):
    if not stem.casefold().startswith(folder.casefold()):
        return False
    rest = stem[len(folder):].strip()
    return not rest or rest[0] in "-_."


def check_root(report, free_episodes=False):
    content = useful_content(report.root)
    files = sorted(c for c in content if c.is_file())
    if not free_episodes and any(EPISODE.match(f.name) for f in files):
        check_folder(report, report.root)
        return set()
    episodes = set()
    for f in files:
        if not check_extension(report, f):
            continue
        m = EPISODE.match(f.name)
        if m:
            check_episode(report, f, m["series"])
            episodes.add(f)
        else:
            title, identifier = check_movie(report, f)
            report.movies.append((f, title, identifier, False))
    for d in sorted(c for c in content if c.is_dir()):
        check_folder(report, d)
    return episodes


def exclude_other_types(report, free_episodes):
    if report.type == "movie":
        for folder, *_ in report.series:
            report.other_type(folder, "show")
        for f in free_episodes:
            report.other_type(f, "show")
        report.series = []
    elif report.type in ("show", "anime"):
        for f, _, identifier, in_collection in report.movies:
            if identifier:
                report.other_type(f.parent if in_collection else f, "movie")
        report.movies = [f for f in report.movies if not f[2]]
    elif report.type == "manga":
        for f, _, identifier, book_series in report.books:
            if identifier:
                report.other_type(f.parent if book_series else f, "book")
        report.books = [l for l in report.books if not l[2]]
    elif report.type == "book":
        for folder, *_ in report.mangas:
            report.other_type(folder, "manga")
        report.mangas = []


def check_metadata(report):
    if not metadata.available():
        print(f"mutagen not found: metadata not checked. Install it with: {metadata.INSTALLATION}")
        return
    for f in (f for f in report.files if not report.in_other_type(f)):
        for default in metadata.flaws(f):
            report.add(f, "metadata", default)


def show(title, values):
    if values:
        print(title)
        for value in values:
            print(f"  {value}")


def examine(root, with_tmdb, type_):
    report = Report(root, type_)
    genre = genres.TYPES[type_]
    missing, to_look_up = {}, []
    if genre is genres.MUSIC:
        scan_music.check(report)
        scan_music.check_musicbrainz(report, with_tmdb)
    elif genre is genres.READINGS:
        scan_readings.check(report)
        exclude_other_types(report, set())
        missing, to_look_up = scan_readings.missing(report)
        scan_readings.check_metadata(report)
    else:
        exclude_other_types(report, check_root(report, free_episodes=type_ == "movie"))
        if with_tmdb and not tmdb.key():
            print(tmdb.key.message(", identification not checked"))
        elif with_tmdb:
            missing = tmdb_checks.check_movies(report, [f for f in report.movies if f[2] and report.compliant(f[0])])
            missing |= tmdb_checks.check_shows(report, [s for s in report.series if s[2] and report.compliant(s[0] / "_")])
        check_metadata(report)
    report.to_convert = [r for r in report.to_convert if not report.in_other_type(root / r)]
    return report, genre, missing, to_look_up


def main():
    parser = argparse.ArgumentParser()
    config.arguments(parser)
    parser.add_argument("--online", dest="tmdb", action="store_true")
    parser.add_argument("--draft", action="store_true")
    args = parser.parse_args()
    languages.use(args.type)

    root = config.folder(args.type, args.target)
    report, genre, _, _ = examine(root, args.tmdb, args.type)

    print(f"Root of {genres.ROOTS[args.type]}")
    total = sum(len(e) for e in report.deviations.values())
    for media in sorted(report.deviations):
        print(f"{media}")
        for kind, path, message in report.deviations[media]:
            print(f"  [{kind}] {path}: {message}")
    print(f"{total} Deviation(s) in {len(report.deviations)} Work(s)")
    if report.accepted:
        print(f"{len(set(report.accepted))} file(s) with Accepted deviations")
    delete = genre.sidecars(root)
    if delete:
        print(f"{len(delete)} {genre.sidecars_label} to delete")
    show("Extensions to fix:", [f"{f} → {e}" for f, e in report.fixed_extensions.items()])
    show("To convert:", report.to_convert)

    plan = {
        "folder": str(root),
        "genre": genre.name,
        "type": args.type,
        "files": sorted(report.relative(f) for f in report.files),
        "deviations": [
            {"media": media, "kind": kind, "path": path, "message": message}
            for media in sorted(report.deviations)
            for kind, path, message in report.deviations[media]
        ],
        "to_convert": report.to_convert,
        "fixed_extensions": report.fixed_extensions,
    }
    if args.draft:
        plan |= {"operations": [], "set_aside": [], "responses": []}
        file = storage.in_progress(args.type, "check", args.target)
        old = storage.read_cache(file)
        if old.get("step", "check") != "check":
            print(f"Check progress kept, at step {old['step']}: {file}")
        else:
            storage.write_json(file, old | {"start": datetime.now().isoformat(timespec="seconds"), "step": "check", "works": {}, "corrections": plan})
            print(f"Check progress: {file}")
    sys.exit(1 if total else 0)


if __name__ == "__main__":
    config.run_main(main)
