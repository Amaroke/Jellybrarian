import re
import sys
import urllib.request
from functools import cache

import config

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



def scanner():
    url = config.optional("jellyfin", "url")
    if not url:
        print("jellyfin.url missing from the config: start the library scan in Jellyfin")
        return
    query = urllib.request.Request(f"{url.rstrip('/')}/Library/Refresh", b"", {"Authorization": f'MediaBrowser Token="{config.value("jellyfin", "key")}"'}, method="POST")
    with urllib.request.urlopen(query, timeout=30):
        pass
    print("Jellyfin library scan started.")


def main():
    if sys.argv[1:] != ["scan"]:
        print("usage: jellyfin.py scan")
        sys.exit(2)
    scanner()


if __name__ == "__main__":
    config.run_main(main)
