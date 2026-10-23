import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

import api
import config

key = api.Key("slskd API key missing", "slskd", "key")


def url():
    return config.value("slskd", "url") + "/api/v0"


def call(method, path, body=None):
    storage = json.dumps(body).encode() if body is not None else None
    query = urllib.request.Request(f"{url()}/{path}", storage, {"X-API-Key": key(), "Content-Type": "application/json"}, method=method)
    with urllib.request.urlopen(query, timeout=60) as response:
        content = response.read()
    return json.loads(content) if content else None


def reachable():
    try:
        return bool((call("GET", "server") or {}).get("isLoggedIn"))
    except (urllib.error.URLError, OSError):
        return False


def search(text, delay=15, attempts=10):
    identifier = str(uuid.uuid4())
    for attempt in range(attempts):
        try:
            call("POST", "searches", {"id": identifier, "searchText": text, "searchTimeout": delay * 1000, "responseLimit": 100, "fileLimit": 10000, "filterResponses": True})
            break
        except urllib.error.HTTPError as error:
            if error.code != 429 or attempt == attempts - 1:
                raise
            time.sleep(5 * (attempt + 1))
    try:
        while not (call("GET", f"searches/{identifier}") or {}).get("isComplete"):
            time.sleep(1)
        return call("GET", f"searches/{identifier}/responses") or []
    finally:
        call("DELETE", f"searches/{identifier}")


def download(user, files):
    call("POST", f"transfers/downloads/{urllib.parse.quote(user)}", [{"filename": f["filename"], "size": f["size"]} for f in files])


def downloads():
    return [
        file | {"username": u["username"]}
        for u in call("GET", "transfers/downloads") or []
        for d in u.get("directories") or []
        for file in d.get("files") or []
    ]


def main():
    if not key():
        print(key.message())
        sys.exit(2)
    if not reachable():
        print(f"slskd unreachable or disconnected from Soulseek at {url()}: start slskd")
        sys.exit(2)
    if sys.argv[1:2] == ["search"]:
        print(json.dumps(search(" ".join(sys.argv[2:])), ensure_ascii=False, indent=1))
        return
    for t in downloads():
        print(f"{t.get('state')} | {t.get('percentComplete', 0):.0f}% | {t['username']} | {t['filename']}")


if __name__ == "__main__":
    config.run_main(main)
