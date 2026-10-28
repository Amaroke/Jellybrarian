import argparse
import re
import sys
from datetime import date, datetime
from pathlib import Path

import anime
import config
import languages
import storage
import tmdb_checks
import mal
import prowlarr
import qbittorrent
import scan
import tmdb

RESOLUTIONS = {"1080": 2, "720": 1}
RESOLUTION = re.compile(r"(?i)\b(\d{3,4})p\b")
SXE = re.compile(r"(?i)\bS(\d{1,2})\s?E(\d{1,4})(?:v\d)?(?:\s?[-~]\s?(?:E|S\d{1,2}E)?(\d{1,4}))?\b")
SEASON = re.compile(r"(?i)\bS(\d{1,2})\b|\bseason\s?(\d{1,2})\b|\b(\d{1,2})(?:st|nd|rd|th)\s+season\b")
SPAN = re.compile(r"\s-\s(\d{1,4})(?:v\d)?\s?[~-]\s?(\d{1,4})(?:v\d)?\b")
UNIQUE = re.compile(r"\s-\s(\d{1,4})(?:v\d)?\b")
NUMBER = re.compile(r"^S(\d{2})E(\d{2,4})$")
FORBIDDEN = re.compile(r'[<>:"/\\|?*]')
TYPE = "anime"


def episodes_of(text):
    numbers = []
    for part in text.split(", "):
        bounds = [NUMBER.match(b.strip()) for b in part.split(" to ")]
        if not all(bounds):
            return None
        (s, a), (_, b) = [(int(m[1]), int(m[2])) for m in (bounds[0], bounds[-1])]
        numbers += [(s, e) for e in range(a, b + 1)]
    return numbers


def span_label(season, numbers, complete):
    if complete:
        return f"S{season:02d}"
    return tmdb_checks.spans([(season, e) for e in sorted(numbers)])


class Season:
    def __init__(self, number, entries, episodes):
        self.number = number
        self.entries = entries
        self.episodes = episodes
        self.keys = {}
        for entry in entries:
            for title in mal.titles(entry):
                if title.isascii() and tmdb_checks.key(title):
                    self.keys[tmdb_checks.key(title)] = entry["id"]

    def relatives(self, entry):
        return [e for e, m in self.episodes if m == entry]

    def all_items(self):
        return {e for e, _ in self.episodes}


def read_title(release, seasons):
    head = re.split(r"\s\(", release["title"])[0]
    key = tmdb_checks.key(head)
    entry, season = None, None
    found_entries = [(len(k), s, m) for s in seasons for k, m in s.keys.items() if k and k in key]
    if found_entries:
        _, season, entry = max(found_entries, key=lambda t: t[0])
    m = SXE.search(head)
    if m:
        number = int(m[1])
        start, end = int(m[2]), int(m[3] or m[2])
        target = next((s for s in seasons if s.number == number), None)
        return target, set(range(start, end + 1)), False
    m = SEASON.search(head)
    if m:
        number = int(next(g for g in m.groups() if g))
        season = next((s for s in seasons if s.number == number), None)
        entry = None
    if season is None and len(seasons) == 1:
        season = seasons[0]
    if season is None:
        return None, set(), False
    relatives = season.relatives(entry) if entry else sorted(season.all_items())
    m = SPAN.search(head)
    if m:
        start, end = int(m[1]), int(m[2])
        return season, {relatives[i - 1] for i in range(start, end + 1) if 0 < i <= len(relatives)} or {-1}, False
    m = UNIQUE.search(head)
    if m and not re.search(r"(?i)\b(?:batch|complete|int[ée]grale)\b", head):
        i = int(m[1])
        return season, {relatives[i - 1]} if 0 < i <= len(relatives) else {-1}, False
    return season, set(relatives), not entry or len(season.entries) == 1


def acceptable(release):
    m = RESOLUTION.search(release["title"])
    wanted = languages.release_filter(TYPE)
    return (wanted is None or wanted.search(release["title"])) and m and m[1] in RESOLUTIONS and release["seeders"] >= 1


def score(release):
    return (RESOLUTIONS[RESOLUTION.search(release["title"])[1]], release["trusted"], release["seeders"])


def queries(season, base):
    titles = [t for e in season.entries for t in mal.titles(e)[:2] if t.isascii()]
    titles.append(f"{base} S{season.number:02d}")
    tags = languages.release_keywords(TYPE)[:1]
    return list(dict.fromkeys(t for title in titles for t in (title, *(f"{title} {tag}" for tag in tags))))


def cover_span(media, season, missing, seasons, base, folder, destination=None):
    candidates = {}
    for query in queries(season, base):
        for release in prowlarr.search(query):
            if release["hash"] in candidates or not acceptable(release):
                continue
            target, numbers, pack = read_title(release, seasons)
            if target is season and numbers and numbers <= missing:
                candidates[release["hash"]] = (release, numbers, pack and numbers == season.all_items())
    remaining, choice = set(missing), []
    while remaining:
        useful = [c for c in candidates.values() if c[1] <= remaining]
        if not useful:
            break
        release, numbers, complete = max(useful, key=lambda c: (c[2], score(c[0])[0], len(c[1]), score(c[0])[1:]))
        choice.append({
            "media": media,
            "group": span_label(season.number, numbers, complete),
            "elements": [f"{media} : S{season.number:02d}E{e:02d}" for e in sorted(numbers)],
            "release": release,
            "path": str((destination or qbittorrent.incoming()) / name_on(folder) / name_on(span_label(season.number, numbers, complete))),
        })
        remaining -= numbers
    choice.sort(key=lambda c: c["elements"][0])
    return choice, [f"{media} : S{season.number:02d}E{e:02d}" for e in sorted(remaining)]


def name_on(text):
    return FORBIDDEN.sub(" -", text).strip(" .")


def anime_seasons(folder):
    m = scan.IDENTIFIER.match(folder.name)
    work = m and tmdb_checks.details("tv", m["id"])
    if not work or not anime.is_anime(work):
        return None
    _, catalog = anime.episodes(work, tmdb_checks.tmdb_episodes(work))
    if not catalog:
        return None
    return build({(s, e): ep["mal"] for (s, e), ep in catalog.items() if s > 0})


def mal_seasons(identifier):
    parts, _ = mal.structure(identifier)
    numbers = {}
    for s, group in enumerate(parts, 1):
        e = 0
        for part in group:
            if part.get("status") == "not_yet_aired":
                continue
            for _ in range(part["num_episodes"] or 0):
                e += 1
                numbers[(s, e)] = part["id"]
    return build(numbers)


def build(numbers):
    seasons = []
    for s in sorted({s for s, _ in numbers}):
        episodes = sorted((e, m) for (n, e), m in numbers.items() if n == s)
        entries = [mal.anime(m) for m in dict.fromkeys(m for _, m in episodes)]
        seasons.append(Season(s, [e for e in entries if e], episodes))
    return seasons


def base_of(seasons):
    entry = seasons[0].entries[0]
    return (entry.get("alternative_titles") or {}).get("en") or entry["title"]


def active_grabbed(elements):
    in_progress = qbittorrent.torrents()
    kept_elements = []
    for grab in storage.grabbed(TYPE):
        folder = Path(grab["path"])
        present = grab["hash"] in in_progress or (folder.is_dir() and any(folder.iterdir()))
        if present and set(grab["elements"]) & elements:
            kept_elements.append(grab)
    storage.write_grabbed(TYPE, kept_elements)
    return kept_elements


def forget_grabbed():
    reachable = qbittorrent.reachable()
    in_progress = qbittorrent.torrents() if reachable else {}
    before = storage.grabbed(TYPE)
    kept_elements = []
    for grab in before:
        folder = Path(grab["path"])
        if grab["hash"] in in_progress or (folder.is_dir() and (not reachable or any(folder.iterdir()))):
            kept_elements.append(grab)
    storage.write_grabbed(TYPE, kept_elements)
    return len(before) - len(kept_elements)


def missing_of(wanted, ignored):
    missing, others = {}, []
    for media, spans in wanted["missing"].items():
        if media in ignored:
            continue
        numbers = episodes_of(spans)
        if numbers:
            missing[media] = numbers
        else:
            others.append(media)
    return missing, others


def follow_ups_of(wanted, ignored):
    mal, others = [], []
    for s in wanted.get("follow_ups", []):
        if storage.label(s) in ignored:
            continue
        if (s.get("source") or "").startswith("MAL "):
            mal.append(s)
        else:
            others.append(storage.label(s))
    return mal, others


def search(root):
    wanted = storage.wanted(TYPE)
    if wanted is None:
        print("No Anime Wanted list: run /jb-anime-find-missing first")
        sys.exit(2)
    ignored = storage.ignored(TYPE)
    missing, others = missing_of(wanted, ignored)
    follow_ups, other_follow_ups = follow_ups_of(wanted, ignored)
    folders = {m["title"]: d for d in root.iterdir() if d.is_dir() and (m := scan.IDENTIFIER.match(d.name))}
    elements = {f"{media} : S{s:02d}E{e:02d}" for media, numbers in missing.items() for s, e in numbers}
    groups = []
    for follow_up in follow_ups:
        malid = int(follow_up["source"].split()[1])
        seasons = mal_seasons(malid)
        own = [s for s in seasons if any(e["id"] == malid for e in s.entries)]
        name = storage.label(follow_up)
        elements |= {f"{name} : S{s.number:02d}E{e:02d}" for s in own for e in s.all_items()}
        groups.append((name, seasons, {(s.number, e) for s in own for e in s.all_items()}, follow_up["follow_up"]))
    grabbed = active_grabbed(elements)
    already = {e for l in grabbed for e in l["elements"]}
    out_of_scope = sorted(others) + other_follow_ups
    for media, numbers in sorted(missing.items()):
        seasons = anime_seasons(folders[media]) if media in folders else None
        if not seasons:
            out_of_scope.append(media)
            continue
        groups.insert(0, (media, seasons, set(numbers), media))
    proposals, not_found = [], []
    for media, seasons, numbers, folder in groups:
        base = base_of(seasons)
        for season in seasons:
            desired_values = {e for s, e in numbers if s == season.number and f"{media} : S{s:02d}E{e:02d}" not in already}
            if not desired_values:
                continue
            choice, remaining = cover_span(media, season, desired_values, seasons, base, folder)
            proposals += choice
            not_found += remaining
    return {
        "folder": str(root),
        "proposals": proposals,
        "not_found": not_found,
        "out_of_scope": out_of_scope,
        "grabbed": [f"{l['media']} {l['group']} : {l['release']}" for l in grabbed],
    }


def launch(content):
    grabbed = storage.grabbed(TYPE)
    for p in content["proposals"]:
        Path(p["path"]).mkdir(parents=True, exist_ok=True)
        qbittorrent.add(p["release"]["url"], p["path"])
        grabbed.append({
            "media": p["media"],
            "group": p["group"],
            "elements": p["elements"],
            "release": p["release"]["title"],
            "hash": p["release"]["hash"],
            "path": p["path"],
            "date": date.today().isoformat(),
        })
        storage.write_grabbed(TYPE, grabbed)
        print(f"Grabbed: {p['media']} {p['group']} → {p['path']}")


def by_work(elements):
    numbers = {}
    for element in elements:
        media, _, number = element.rpartition(" : ")
        m = NUMBER.match(number)
        numbers.setdefault(media, []).append((int(m[1]), int(m[2])))
    return [f"{media} : {tmdb_checks.spans(sorted(n))}" for media, n in numbers.items()]


def grouped(proposals):
    lines = []
    for p in proposals:
        r = p["release"]
        lines.append(f"{p['media']} {p['group']} | {r['title']} | {r['seeders']} seeders{' | Trusted' if r['trusted'] else ''} | {r['size'] // 2**20} Mo")
    return lines


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("search", "grab"))
    args = parser.parse_args()
    languages.use(TYPE)

    if not prowlarr.key():
        print(prowlarr.key.message())
        sys.exit(config.MISSING_CONFIG)
    if not qbittorrent.reachable():
        print(f"qBittorrent unreachable at {qbittorrent.url()}: start qBittorrent and enable its web UI")
        sys.exit(2)
    file = storage.in_progress(TYPE, "download")
    if args.command == "grab":
        launch(storage.read_json(file)["releases"])
        file.unlink()
        return
    if not tmdb.key() or not mal.key():
        print("TMDB key and MAL Client ID required to find the split of the Animes. " + (tmdb.key.message() if not tmdb.key() else mal.key.message()))
        sys.exit(config.MISSING_CONFIG)
    content = search(config.folder(TYPE, "root"))
    scan.show("Proposals:", grouped(content["proposals"]))
    scan.show("Not found:", by_work(content["not_found"]))
    scan.show("Out of scope (not an Anime):", content["out_of_scope"])
    scan.show("Already Grabbed:", content["grabbed"])
    storage.write_json(file, {"start": datetime.now().isoformat(timespec="seconds"), "step": "review", "releases": content})
    print(f"Download progress: {file}")


if __name__ == "__main__":
    config.run_main(main)
