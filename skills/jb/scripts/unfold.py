import re
import urllib.error
from pathlib import Path

import config
import qbittorrent

SPAN = re.compile(r"^S\d+(E\d+( to S\d+E\d+)?)?(, S\d+(E\d+( to S\d+E\d+)?)?)*$")


def busy():
    try:
        if not qbittorrent.reachable():
            return []
        return [Path(t["save_path"]).resolve() for t in qbittorrent.call("torrents/info")]
    except (urllib.error.URLError, RuntimeError, OSError):
        return []


def unfold(root):
    root = Path(root).resolve()
    active = busy()
    released, in_progress, blocked = [], [], []
    for media in sorted(d for d in root.iterdir() if d.is_dir()):
        for span in sorted(d for d in media.iterdir() if d.is_dir() and SPAN.match(d.name)):
            if any(p == span or span in p.parents for p in active):
                in_progress.append(span.relative_to(root))
                continue
            for file in sorted(f for f in span.rglob("*") if f.is_file()):
                target = media / file.name
                if target.exists():
                    blocked.append(file.relative_to(root))
                    continue
                file.rename(target)
                released.append(target.relative_to(root))
            for folder in sorted((d for d in span.rglob("*") if d.is_dir()), key=lambda d: len(d.parts), reverse=True) + [span]:
                if not any(folder.iterdir()):
                    folder.rmdir()
    return released, in_progress, blocked


def main():
    released, in_progress, blocked = unfold(config.folder("anime", "incoming"))
    print(f"Moved out of range folders: {len(released)}")
    for title, catalog in (("Still in qBittorrent:", in_progress), ("Name already taken, left in place:", blocked)):
        if catalog:
            print(title)
            print("\n".join(f"  {c}" for c in catalog))


if __name__ == "__main__":
    config.run_main(main)
