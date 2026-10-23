import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from functools import lru_cache

import anime
import languages
import mal
import tmdb

DEFAULT_TITLE = languages.DEFAULT_TITLE
COLLECTION_SUFFIX = re.compile(r"(?i)\s*(?:\(.*?\)|- saga|- collection|collection)\s*$")


def key(text):
    return "".join(c for c in (text or "").casefold() if c.isalnum())


@lru_cache(maxsize=None)
def _call(path, params):
    return tmdb.get(path, **dict(params))


def call(path, **params):
    return _call(path, tuple(sorted(params.items())))


class Work:
    def __init__(self, genre, details):
        self.genre = genre
        self.details = details
        title_field = "title" if genre == "movie" else "name"
        self.title = details.get(title_field) or ""
        self.original = details.get(f"original_{title_field}") or ""
        alternatives = details.get("alternative_titles") or {}
        alternatives = alternatives.get("titles") or alternatives.get("results") or []
        self.localized = {key(self.title)} | {
            key(t["title"]) for t in alternatives if t.get("iso_3166_1") in languages.countries(tmdb.LANGUAGE)
        }

    def matching(self, name, subtitle_allowed):
        k = key(name)
        if k in self.localized:
            return "ok"
        if subtitle_allowed and any(f.endswith(k) for f in self.localized):
            return "ok"
        if k == key(self.original) and self.details.get("original_language") != tmdb.LANGUAGE:
            if any(f and (f in k or k in f) for f in self.localized):
                return "partial"
            return "original"
        if k and any(f and (f in k or k in f) for f in self.localized):
            return "partial"
        return "different"


def details(genre, identifier):
    storage = call(f"{genre}/{identifier}", append_to_response="alternative_titles")
    return Work(genre, storage) if storage else None


def title_deviations(work, state):
    if state == "original":
        return [("title", f"original title instead of the Localized title « {work.title} »")]
    if state == "different":
        return [("title", f"name unrelated to the TMDB Localized title « {work.title} »")]
    return []


def check_movies(report, movies):
    if movies:
        print(f"{len(movies)} Movie(s) to check on TMDB", file=sys.stderr, flush=True)
    with ThreadPoolExecutor(8) as pool:
        work_list = list(pool.map(lambda movie: details("movie", movie[2]), movies))

    by_collection = {}
    present_ones = set()
    for (file, title, identifier, in_collection), work in zip(movies, work_list):
        if not work:
            report.add(file, "title", f"TMDB identifier {identifier} unknown")
            continue
        present_ones.add(identifier)
        for kind, message in title_deviations(work, work.matching(title, in_collection)):
            report.add(file, kind, message)
        collection = work.details.get("belongs_to_collection")
        if collection:
            by_collection.setdefault((collection["id"], collection["name"]), []).append(file)

    missing = {}
    for (identifier, name), files in by_collection.items():
        folders = [f.parent for f in files if f.parent != report.root]
        media = max(set(folders), key=folders.count).name if folders else collection_name(name)
        for movie in released(identifier):
            if movie["id"] not in present_ones:
                missing.setdefault(media, []).append(movie["title"])

    for (_, name), files in by_collection.items():
        if len(files) < 2:
            continue
        folders = [f.parent for f in files]
        filed = [d for d in folders if d != report.root]
        if not filed:
            for f in files:
                report.add(f, "location", f"TMDB Collection « {name} » of {len(files)} Movies left at the root")
            continue
        entry_point = max(set(filed), key=filed.count)
        for f in files:
            if f.parent != entry_point:
                report.add(f, "location", f"TMDB Collection « {name} »: join « {entry_point.name} »")
    return {media: ", ".join(titles) for media, titles in missing.items()}


def collection_name(name):
    while (short := COLLECTION_SUFFIX.sub("", name)) != name:
        name = short
    return name


def released(identifier):
    today = date.today().isoformat()
    parts = (call(f"collection/{identifier}") or {}).get("parts") or []
    parts = [p for p in parts if p.get("release_date") and p["release_date"] <= today]
    return sorted(parts, key=lambda p: p["release_date"])


def check_shows(report, series):
    missing = {}
    for n, (folder, series_title, identifier, episodes) in enumerate(series, 1):
        print(f"{n}/{len(series)} {series_title}", file=sys.stderr, flush=True)
        work = details("tv", identifier)
        if not work:
            report.add(folder, "title", f"TMDB identifier {identifier} unknown")
            continue
        if report.type in ("show", "anime") and anime.is_anime(work) != (report.type == "anime"):
            report.other_type(folder, "anime" if report.type == "show" else "show")
            continue
        for kind, message in title_deviations(work, work.matching(series_title, False)):
            report.add(folder, kind, message)
        catalog = tmdb_episodes(work)
        if anime.is_anime(work) and mal.key():
            catalog = anime.episodes(work, catalog)[1] or catalog
        covered = set()
        split_files = {n for n in [(e[1], e[2]) for e in episodes] if [(x[1], x[2]) for x in episodes].count(n) > 1}
        for file, season, first, second, title in episodes:
            numbers = [(season, first)] + ([(season, n) for n in range(first + 1, second + 1)] if second else [])
            covered.update(numbers)
            known = [catalog.get(n) for n in numbers]
            if not all(known):
                report.add(file, "title", "Episode missing from the TMDB list")
                continue
            names = [e.get("name") or "" for e in known]
            if any(not n or DEFAULT_TITLE.match(n) for n in names):
                continue
            expected = key("".join(names))
            k = key(title)
            if (season, first) in split_files:
                expected, k = expected.rstrip("0123456789"), k.rstrip("0123456789")
            if not (k.startswith(expected) or (k and k in expected)):
                report.add(file, "title", f"title different from the TMDB title « {' & '.join(names)} »")
        absent = sorted(aired(catalog) - covered)
        if absent:
            missing[series_title] = spans(absent)
    return missing


def tmdb_episodes(work):
    catalog = {}
    for season in work.details.get("seasons") or []:
        path = f"tv/{work.details['id']}/season/{season['season_number']}"
        episodes = (call(path) or {}).get("episodes") or []
        if any(not e.get("name") or DEFAULT_TITLE.match(e["name"]) for e in episodes):
            english = {e["episode_number"]: e.get("name") for e in (call(path, language="en-US") or {}).get("episodes") or []}
            for e in episodes:
                name = english.get(e["episode_number"])
                if (not e.get("name") or DEFAULT_TITLE.match(e["name"])) and name and not DEFAULT_TITLE.match(name):
                    e["name"] = name
        for e in episodes:
            catalog[(e["season_number"], e["episode_number"])] = e
    return catalog


def aired(catalog):
    today = date.today().isoformat()
    return {n for n, e in catalog.items() if n[0] > 0 and e.get("air_date") and e["air_date"] <= today}


def spans(numbers):
    groups = []
    for season, episode in numbers:
        if groups and groups[-1][0] == season and groups[-1][2] == episode - 1:
            groups[-1][2] = episode
        else:
            groups.append([season, episode, episode])
    return ", ".join(
        f"S{s:02d}E{a:02d}" if a == b else f"S{s:02d}E{a:02d} to S{s:02d}E{b:02d}" for s, a, b in groups
    )
