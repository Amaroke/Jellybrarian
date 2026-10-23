import json
import sys
import urllib.parse

import api

key = api.Key("TMDB key missing", "tmdb", "key")
LANGUAGE = "en"


def get(path, **params):
    params = {"api_key": key(), "language": LANGUAGE, **params}
    url = f"https://api.themoviedb.org/3/{path.strip('/')}?{urllib.parse.urlencode(params)}"
    return api.read(url)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2:
        print("usage: tmdb.py <path> [key=value ...]")
        sys.exit(2)
    if not key():
        print(key.message())
        sys.exit(2)
    params = dict(a.split("=", 1) for a in sys.argv[2:])
    print(json.dumps(get(sys.argv[1], **params), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
