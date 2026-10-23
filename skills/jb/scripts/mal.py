import re
import sys
import urllib.parse
from functools import lru_cache

import api

key = api.Key("MAL Client ID missing", "mal", "client_id")
FIELDS = "alternative_titles,media_type,num_episodes,start_date,end_date,status,related_anime"
MANGA_FIELDS = "alternative_titles,media_type,num_volumes,start_date,end_date,status,related_manga"
FOLLOW_UP = {"sequel", "prequel"}
SIDECAR = {"side_story"}
PART = re.compile(r"(?i)[\s:-]*(?:part\s*\d+|\d+(?:st|nd|rd|th)\s+(?:part|cour)|cour\s*\d+|kouhen|zenpen|kanketsu-hen)$")


def get(path, **params):
    url = f"https://api.myanimelist.net/v2/{path.strip('/')}?{urllib.parse.urlencode(params)}"
    return api.read(url, {"X-MAL-CLIENT-ID": key()})


@lru_cache(maxsize=None)
def anime(identifier):
    return get(f"anime/{identifier}", fields=FIELDS)


@lru_cache(maxsize=None)
def manga(identifier):
    return get(f"manga/{identifier}", fields=MANGA_FIELDS)


def search_manga(title, limit=10):
    if len(title) < 3:
        return []
    results = get("manga", q=title[:64], limit=limit, nsfw="true", fields="alternative_titles,media_type,num_volumes,start_date,status")
    return [r["node"] for r in (results or {}).get("data", [])]


def search(title, limit=10):
    if len(title) < 3:
        return []
    try:
        results = get("anime", q=title[:64], limit=limit, nsfw="true", fields="alternative_titles,media_type,num_episodes,start_date")
    except urllib.error.HTTPError as error:
        if error.code == 400:
            return []
        raise
    return [r["node"] for r in (results or {}).get("data", [])]


def titles(entry):
    alternatives = entry.get("alternative_titles") or {}
    return [t for t in [entry.get("title"), alternatives.get("en"), alternatives.get("ja"), *(alternatives.get("synonyms") or [])] if t]


def franchise(identifier):
    seen, to_visit, sidecars = {}, [identifier], set()
    while to_visit:
        current_batch = to_visit.pop()
        if current_batch in seen:
            continue
        seen[current_batch] = anime(current_batch)
        for link in seen[current_batch].get("related_anime") or []:
            if link["relation_type"] in FOLLOW_UP:
                to_visit.append(link["node"]["id"])
            elif link["relation_type"] in SIDECAR:
                sidecars.add(link["node"]["id"])
    for identifier in sidecars - set(seen):
        seen[identifier] = anime(identifier)
    return sorted(seen.values(), key=lambda e: e.get("start_date") or "9999")


def season_root(title):
    return PART.sub("", title).strip()


def same_season(entry, previous):
    pairs = [(entry["title"], previous["title"])]
    pairs.append(((entry.get("alternative_titles") or {}).get("en"), (previous.get("alternative_titles") or {}).get("en")))
    return any(a and b and a != b and season_root(a) == season_root(b) for a, b in pairs)


def structure(identifier, excluded=()):
    entries = franchise(identifier)
    entry_point = anime(identifier)["media_type"]
    seasons, specials = [], []
    for entry in entries:
        if entry["id"] in excluded:
            continue
        if entry["media_type"] == entry_point:
            if seasons and same_season(entry, seasons[-1][-1]):
                seasons[-1].append(entry)
            else:
                seasons.append([entry])
        else:
            specials.append(entry)
    return seasons, specials


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    commands = ("search", "structure", "manga-search", "manga")
    if len(sys.argv) < 3 or sys.argv[1] not in commands:
        print("usage: mal.py search <title> | mal.py structure <identifier> [excluded identifiers ...] | mal.py manga-search <title> | mal.py manga <identifier>")
        sys.exit(2)
    if not key():
        print(key.message())
        sys.exit(2)
    if sys.argv[1] == "manga-search":
        for r in search_manga(" ".join(sys.argv[2:])):
            print(f"{r['id']} | {r['title']} | {(r.get('alternative_titles') or {}).get('en', '')} | {r['media_type']} | {r.get('start_date', '')} | {r.get('num_volumes')} volumes | {r.get('status')}")
        return
    if sys.argv[1] == "manga":
        r = manga(int(sys.argv[2]))
        print(f"{r['id']} | {r['title']} | {r['media_type']} | {r.get('start_date', '')} | {r.get('num_volumes')} volumes | {r.get('status')}")
        for link in r.get("related_manga") or []:
            print(f"  {link['relation_type']}: {link['node']['id']} {link['node']['title']}")
        return
    if sys.argv[1] == "search":
        for r in search(" ".join(sys.argv[2:])):
            print(f"{r['id']} | {r['title']} | {(r.get('alternative_titles') or {}).get('en', '')} | {r['media_type']} | {r.get('start_date', '')} | {r.get('num_episodes')} ep.")
        return
    seasons, specials = structure(int(sys.argv[2]), {int(x) for x in sys.argv[3:]})
    for number, parts in enumerate(seasons, 1):
        total = sum(p["num_episodes"] or 0 for p in parts)
        print(f"S{number:02d} ({total} ep.): " + " + ".join(f"{p['id']} {p['title']} [{p['num_episodes']}, {p.get('start_date', '')}]" for p in parts))
    number = 0
    for entry in specials:
        count_ = entry["num_episodes"] or 1
        span = f"S00E{number + 1:02d}" + (f" to S00E{number + count_:02d}" if count_ > 1 else "")
        number += count_
        print(f"{span}: {entry['id']} {entry['title']} | {(entry.get('alternative_titles') or {}).get('en', '')} | {entry['media_type']} | {entry.get('start_date', '')}")


if __name__ == "__main__":
    main()
