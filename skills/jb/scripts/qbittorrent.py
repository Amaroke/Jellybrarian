import http.cookiejar
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

import config

REMOVE = 1

_session = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
_connected = False


def url():
    return config.value("qbittorrent", "url")


def category():
    return config.value("qbittorrent", "category")


def incoming():
    return config.folder("anime", "incoming")


def identifiers():
    user = config.optional("qbittorrent", "user")
    return (user, config.value("qbittorrent", "password")) if user else None


def call(path, storage=None):
    global _connected
    if not _connected:
        _connected = True
        if identifiers():
            user, password = identifiers()
            if call("auth/login", {"username": user, "password": password}) != "Ok.":
                raise RuntimeError("qBittorrent credentials refused")
    body = urllib.parse.urlencode(storage).encode() if storage is not None else None
    query = urllib.request.Request(f"{url()}/api/v2/{path}", data=body, headers={"Referer": url()})
    with _session.open(query, timeout=30) as response:
        text = response.read().decode("utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def reachable():
    try:
        call("app/version")
        return True
    except (urllib.error.URLError, RuntimeError, OSError):
        return False


def prepare():
    categories = call("torrents/categories")
    action = "torrents/editCategory" if category() in categories else "torrents/createCategory"
    call(action, {"category": category(), "savePath": str(incoming())})
    call("app/setPreferences", {"json": json.dumps({"max_ratio_act": REMOVE})})


def torrents():
    return {t["hash"].lower(): t for t in call("torrents/info", {"category": category()})}


def add(url, folder):
    response = call("torrents/add", {
        "urls": url,
        "category": category(),
        "savepath": str(folder),
        "autoTMM": "false",
        "ratioLimit": 0,
        "seedingTimeLimit": -2,
    })
    if response != "Ok.":
        raise RuntimeError(f"qBittorrent refused the torrent: {response}")


def main():
    if not reachable():
        print(f"qBittorrent unreachable at {url()}: start qBittorrent and enable its web UI")
        sys.exit(2)
    if sys.argv[1:] == ["prepare"]:
        prepare()
        print(f"Category {category()} to {incoming()}, torrent removed as soon as ratio 0 is reached")
        return
    for t in torrents().values():
        print(f"{t['progress']:>6.1%} | {t['state']} | {t['name']}")


if __name__ == "__main__":
    config.run_main(main)
