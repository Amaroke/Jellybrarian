import re
import sys
from collections import Counter
from datetime import date

import languages
import tmdb_checks
import mal
import tmdb


def is_anime(work):
    genres = {g["id"] for g in work.details.get("genres") or []}
    return 16 in genres and work.details.get("original_language") == "ja"


def mal_id(work):
    year = (work.details.get("first_air_date") or "")[:4]
    alternatives = work.details.get("alternative_titles") or {}
    alternatives = [t["title"] for t in alternatives.get("results") or alternatives.get("titles") or []]
    for types in (("tv", "ona"), ("ova",)):
        for query in dict.fromkeys([work.original, work.title, *alternatives]):
            for r in mal.search(query):
                if r["media_type"] in types and (r.get("start_date") or "")[:4] == year:
                    return r["id"]
    return None


def proximity(a, b):
    a, b = Counter(tmdb_checks.key(a)), Counter(tmdb_checks.key(b))
    total = sum(a.values()) + sum(b.values())
    return 2 * sum((a & b).values()) / total if total else 0


def other_tmdb_show(entry, work):
    year = (entry.get("start_date") or "")[:4]
    names = mal.titles(entry)
    sanitize = max(proximity(work.original, t) for t in names)
    for query in dict.fromkeys(names):
        for r in (tmdb_checks.call("search/tv", query=query) or {}).get("results") or []:
            if (
                (r.get("first_air_date") or "")[:4] == year
                and r["id"] != work.details["id"]
                and max(proximity(r.get("original_name"), t) for t in names) > sanitize
            ):
                return True
    return False


def excluded(identifier, work):
    entry_point = mal.anime(identifier)["media_type"]
    return {
        e["id"]
        for e in mal.franchise(identifier)
        if e["id"] != identifier and e["media_type"] == entry_point and other_tmdb_show(e, work)
    }


def movie_title(entry):
    year = (entry.get("start_date") or "")[:4]
    names = mal.titles(entry)
    candidates = {}
    for query in dict.fromkeys(names):
        for r in (tmdb_checks.call("search/movie", query=query) or {}).get("results") or []:
            if (r.get("release_date") or "")[:4] == year:
                candidates[r["id"]] = r
    if not candidates:
        return None
    best = max(candidates.values(), key=lambda r: max(proximity(r.get("original_title"), t) for t in names))
    return best["title"]


def mal_title(entry):
    return (entry.get("alternative_titles") or {}).get("en") or entry["title"]


def episodes(work, tmdb_list, identifier=None):
    identifier = identifier or mal_id(work)
    if not identifier:
        return None, None
    seasons, specials = mal.structure(identifier, excluded(identifier, work))
    order = [tmdb_list[n] for n in sorted(tmdb_list) if n[0] > 0]
    tmdb_specials = [tmdb_list[n] for n in sorted(tmdb_list) if n[0] == 0]
    total_mal = sum(p["num_episodes"] or 0 for parts in seasons for p in parts)
    moved = {}
    for entry in specials:
        if len(order) <= total_mal:
            break
        if (entry["num_episodes"] or 1) == 1:
            same_day = [e for e in order if e.get("air_date") and e["air_date"] == entry.get("start_date")]
            if len(same_day) == 1:
                moved[entry["id"]] = same_day[0]
                order.remove(same_day[0])
    catalog, position = {}, 0
    for number, parts in enumerate(seasons, 1):
        episode = 0
        for i, part in enumerate(parts):
            count_ = part["num_episodes"] or (max(0, len(order) - position) if number == len(seasons) and i == len(parts) - 1 else 0)
            finished = part.get("status") == "finished_airing"
            for _ in range(count_):
                episode += 1
                tmdb = order[position] if position < len(order) else {}
                position += 1
                catalog[(number, episode)] = {
                    "name": tmdb.get("name") or "",
                    "air_date": tmdb.get("air_date") or (part.get("end_date") if finished else None),
                    "mal": part["id"],
                }
    number = 0
    for entry in specials:
        count_ = entry["num_episodes"] or 1
        movie = movie_title(entry) if entry["media_type"] == "movie" else None
        start, end = entry.get("start_date") or "", entry.get("end_date") or entry.get("start_date") or ""
        in_span = sorted(
            (e for e in tmdb_specials if e.get("air_date") and start <= e["air_date"] <= end),
            key=lambda e: e["air_date"],
        )
        if len(in_span) != count_:
            in_span = []
        for k in range(count_):
            number += 1
            tmdb = moved.get(entry["id"]) or (in_span[k] if in_span else {})
            name = movie or tmdb.get("name") or ""
            if languages.DEFAULT_TITLE.match(name):
                name = ""
            catalog[(0, number)] = {
                "name": name,
                "mal_title": mal_title(entry) + (f" {k + 1}" if count_ > 1 else ""),
                "air_date": entry.get("start_date") if entry.get("status") == "finished_airing" else None,
                "mal": entry["id"],
            }
    return identifier, catalog


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2:
        print("usage: anime.py <TMDB identifier> [MAL identifier]")
        sys.exit(2)
    languages.use("anime")
    work = tmdb_checks.details("tv", sys.argv[1])
    identifier, catalog = episodes(work, tmdb_checks.tmdb_episodes(work), int(sys.argv[2]) if len(sys.argv) > 2 else None)
    if not catalog:
        print("No MAL match")
        sys.exit(1)
    print(f"{work.title}: MAL {identifier}")
    today = date.today().isoformat()
    for (s, e), ep in sorted(catalog.items()):
        marker = "" if ep["air_date"] and ep["air_date"] <= today else " (not aired)"
        name = ep["name"] or (f"(no Localized title, MAL: {ep['mal_title']})" if "mal_title" in ep else f"{languages.episode_word(tmdb.LANGUAGE)} {e}")
        print(f"S{s:02d}E{e:02d} | {name} | MAL {ep['mal']}{marker}")


if __name__ == "__main__":
    main()
