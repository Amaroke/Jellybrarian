import json
import re
import sys
import time
import urllib.parse
import urllib.request
from functools import cache

import config

BATCH = 100
SCAN_TIMEOUT = 1800

VIDEOS = {
    ".mp4", ".mkv", ".avi", ".m4v", ".mov", ".wmv", ".ts", ".m2ts", ".webm",
    ".flv", ".mpg", ".mpeg", ".vob", ".divx", ".3gp", ".ogm", ".rmvb",
}
IMAGE = r"\.(?:jpg|jpeg|png|webp|tbn|svg)"
GENRES = r"(?:thumb|poster|fanart\d*|backdrop\d*|landscape|banner|logo|clearlogo|clearart|disc|discart|art|cover)"
COMPANION = re.compile(rf"(?i)^(?P<stem>.+?)(?P<suffix>\.nfo|-{GENRES}{IMAGE}|\.trickplay)$")
FROM_FOLDER = re.compile(
    rf"(?i)^(?:tvshow\.nfo|(?:poster|folder|cover|fanart\d*|backdrop\d*|landscape|banner|logo|clearlogo|clearart|disc|discart|art){IMAGE}"
    rf"|season(?:\d+|-specials|-all)-(?:poster|fanart|banner|landscape|thumb){IMAGE})$"
)
TOLERATED = {"desktop.ini", "thumbs.db"}
SUBTITLES = {".srt", ".ass", ".ssa", ".vtt"}


@cache
def ignored():
    return {n.casefold() for n in config.ignored()}


def outside_library(name):
    return name.startswith(".") or name.casefold() in ignored()


def content(root):
    return [c for c in root.iterdir() if not outside_library(c.name)]


def walk(root):
    return [f for c in content(root) for f in ([c, *c.rglob("*")] if c.is_dir() else [c])]


def is_video(path):
    return path.is_file() and path.suffix.lower() in VIDEOS


def companion(path):
    if path.suffix.lower() in VIDEOS:
        return None
    m = COMPANION.match(path.name)
    if not m or (m["suffix"].lower() == ".trickplay") != path.is_dir():
        return None
    return m["stem"], m["suffix"]


def folder_file(path):
    return path.is_file() and bool(FROM_FOLDER.match(path.name))


def is_subtitle(path):
    return path.is_file() and path.suffix.lower() in SUBTITLES


def subtitle_video(path):
    videos = [v for v in path.parent.iterdir() if is_video(v) and path.name.startswith(v.stem + ".")]
    return max(videos, key=lambda v: len(v.stem), default=None)


def sidecar(path):
    return path.name.lower() in TOLERATED or is_subtitle(path) or bool(companion(path)) or folder_file(path)


def to_delete(path):
    if is_subtitle(path):
        return subtitle_video(path) is None
    return path.is_file() and (bool(companion(path)) or folder_file(path))


def to_delete_under(root):
    return sorted(f for f in walk(root) if ".trickplay" not in f.as_posix().lower() and to_delete(f))


def companions(video):
    found_items = []
    for f in video.parent.iterdir():
        if is_subtitle(f):
            if subtitle_video(f) == video:
                found_items.append((f, f.name[len(video.stem):]))
            continue
        c = companion(f)
        if c and c[0] == video.stem and not to_delete(f):
            found_items.append((f, c[1]))
    return found_items



def call(method, path, body=None, **params):
    url = f"{config.value('jellyfin', 'url').rstrip('/')}/{path.lstrip('/')}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {"Authorization": f'MediaBrowser Token="{config.value("jellyfin", "key")}"', "Content-Type": "application/json"}
    data = json.dumps(body).encode() if body is not None else (b"" if method == "POST" else None)
    with urllib.request.urlopen(urllib.request.Request(url, data, headers, method=method), timeout=120) as response:
        text = response.read()
    return json.loads(text) if text else None


def scanner():
    if not config.optional("jellyfin", "url"):
        print("jellyfin.url missing from the config: start the library scan in Jellyfin")
        return
    call("POST", "Library/Refresh")
    print("Jellyfin library scan started.")


def owner():
    users = call("GET", "Users")
    name = config.optional("jellyfin", "user")
    if name:
        found_items = [u for u in users if u["Name"].casefold() == name.casefold()]
        if not found_items:
            raise SystemExit(f"Jellyfin user not found: {name}")
        return found_items[0]["Id"]
    return next((u for u in users if u["Policy"].get("IsAdministrator")), users[0])["Id"]


def wait_for_scan():
    deadline = time.monotonic() + SCAN_TIMEOUT
    while time.monotonic() < deadline:
        task = next((t for t in call("GET", "ScheduledTasks") if t.get("Key") == "RefreshLibrary"), None)
        if not task or task["State"] == "Idle":
            return
        time.sleep(10)
    print("The Jellyfin library scan is still running: the newest Tracks may be missing from the playlist")


def playlist():
    if not config.optional("jellyfin", "url"):
        print("jellyfin.url missing from the config: update the playlist in Jellyfin by hand")
        return
    wait_for_scan()
    name = config.value("jellyfin", "playlist", "Finamp")
    user = owner()
    tracks = [i["Id"] for i in call("GET", "Items", userId=user, IncludeItemTypes="Audio", Recursive="true", SortBy="SortName")["Items"]]
    found_items = [p for p in call("GET", "Items", userId=user, IncludeItemTypes="Playlist", Recursive="true")["Items"] if p["Name"] == name]
    if not found_items:
        identifier = call("POST", "Playlists", {"Name": name, "UserId": user, "MediaType": "Audio", "Ids": []})["Id"]
        present = set()
    else:
        identifier = found_items[0]["Id"]
        present = {i["Id"] for i in call("GET", f"Playlists/{identifier}/Items", userId=user)["Items"]}
    to_add = [t for t in tracks if t not in present]
    for start in range(0, len(to_add), BATCH):
        call("POST", f"Playlists/{identifier}/Items", userId=user, ids=",".join(to_add[start:start + BATCH]))
    print(f"Playlist {name}: {len(to_add)} Track(s) added, {len(present) + len(to_add)} in total")


def main():
    commands = {"scan": scanner, "playlist": playlist}
    if len(sys.argv) != 2 or sys.argv[1] not in commands:
        print("usage: jellyfin.py scan | playlist")
        sys.exit(2)
    commands[sys.argv[1]]()


if __name__ == "__main__":
    config.run_main(main)
