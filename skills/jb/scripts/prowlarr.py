import sys
import urllib.parse
from functools import lru_cache

import api
import config

key = api.Key("Prowlarr API key missing", "prowlarr", "key")


def get(path, params=()):
    url = f"{config.value('prowlarr', 'url')}/api/v1/{path.strip('/')}?{urllib.parse.urlencode(list(params))}"
    return api.read(url, {"X-Api-Key": key()}, timeout=120, attempts=1)


@lru_cache(maxsize=None)
def indexers():
    reliable = {n.casefold() for n in config.value("prowlarr", "trusted_indexers", [])}
    return tuple((i["id"], i["name"].casefold() in reliable) for i in get("indexer") if i.get("enable"))


@lru_cache(maxsize=None)
def search(query):
    active = indexers()
    params = [("query", query), ("type", "search"), ("limit", 100)] + [("indexerIds", i) for i, _ in active]
    results = get("search", params)
    reliable = {i for i, trusted in active if trusted}
    trusted = {r.get("infoHash") for r in results if r.get("indexerId") in reliable}
    seen = {}
    for r in results:
        fingerprint = (r.get("infoHash") or r.get("guid") or "").lower()
        if fingerprint in seen or not (r.get("magnetUrl") or r.get("downloadUrl")):
            continue
        seen[fingerprint] = {
            "title": r["title"],
            "seeders": r.get("seeders") or 0,
            "size": r.get("size") or 0,
            "trusted": r.get("infoHash") in trusted,
            "hash": fingerprint,
            "url": r.get("magnetUrl") or r.get("downloadUrl"),
            "page": r.get("infoUrl") or r.get("guid"),
        }
    return list(seen.values())


def main():
    if len(sys.argv) < 2:
        print("usage: prowlarr.py <query>")
        sys.exit(2)
    if not key():
        print(key.message())
        sys.exit(2)
    for r in sorted(search(" ".join(sys.argv[1:])), key=lambda r: -r["seeders"]):
        print(f"{r['seeders']:>5} | {'T' if r['trusted'] else ' '} | {r['size'] // 2**20:>6} Mo | {r['title']}")


if __name__ == "__main__":
    config.run_main(main)
