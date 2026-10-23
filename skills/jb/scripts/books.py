import json
import sys
import urllib.error
import urllib.parse

import api
import config
import storage

key = api.Key("Google Books key missing", "google_books", "key")
CACHE = storage.cache("books")


def get(path, **params):
    if key():
        params["key"] = key()
    url = f"https://www.googleapis.com/books/v1/{path.strip('/')}?{urllib.parse.urlencode(params)}"
    return api.read(url, timeout=15, attempts=3)


def summary(volume):
    info = volume.get("volumeInfo") or {}
    title = info.get("title") or ""
    if info.get("subtitle"):
        title += f" - {info['subtitle']}"
    return {
        "title": title,
        "authors": info.get("authors") or [],
        "date": info.get("publishedDate") or "",
        "language": info.get("language") or "",
        "series": ((info.get("seriesInfo") or {}).get("volumeSeries") or [{}])[0].get("seriesId"),
        "isbn": next((i["identifier"] for i in info.get("industryIdentifiers") or [] if i.get("type") == "ISBN_13"), None),
    }


def cache():
    return storage.read_json(CACHE) if CACHE.is_file() else {}


def volume(identifier):
    known = cache()
    if identifier not in known:
        content = get(f"volumes/{identifier}")
        if not content:
            return None
        known[identifier] = summary(content)
        storage.write_json(CACHE, known)
    return known[identifier]


def search(query, language=None):
    params = {"q": query, "maxResults": 10, "printType": "books"}
    if language:
        params["langRestrict"] = language
    return [(v["id"], summary(v)) for v in (get("volumes", **params) or {}).get("items") or []]


def main():
    try:
        command()
    except urllib.error.HTTPError as error:
        if error.code != 429:
            raise
        print(key.message(", Google Books refuses repeated calls"))
        sys.exit(config.MISSING_CONFIG)


def command():
    if len(sys.argv) < 3 or sys.argv[1] not in ("search", "volume"):
        print("usage: books.py search <title> [--language fr] | books.py volume <identifier>")
        sys.exit(2)
    if sys.argv[1] == "volume":
        print(json.dumps(volume(sys.argv[2]), ensure_ascii=False, indent=1))
        return
    arguments = sys.argv[2:]
    language = None
    if "--language" in arguments:
        i = arguments.index("--language")
        language = arguments[i + 1]
        arguments = arguments[:i] + arguments[i + 2:]
    for identifier, r in search(" ".join(arguments), language):
        print(f"{identifier} | {r['title']} | {', '.join(r['authors'])} | {r['date']} | {r['language']}")


if __name__ == "__main__":
    config.run_main(main)
