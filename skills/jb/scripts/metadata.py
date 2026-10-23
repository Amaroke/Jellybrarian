import argparse
import sys
from pathlib import Path

import jellyfin

try:
    from mutagen.mp4 import MP4
except ImportError:
    MP4 = None

INSTALLATION = "python -m pip install --user mutagen"


def available():
    return MP4 is not None


def flaws(file):
    if file.suffix.lower() != ".mp4":
        return []
    try:
        tags = MP4(file).tags
    except Exception:
        return ["unreadable MP4 file"]
    if not tags:
        return []
    return ["tags: " + ", ".join(sorted(tags.keys()))]


def clean(file):
    MP4(file).delete()


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("root")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    if not available():
        print(f"mutagen not found. Install it with: {INSTALLATION}")
        sys.exit(2)

    root = Path(args.root).resolve()
    videos = sorted(f for f in jellyfin.walk(root) if f.is_file() and f.suffix.lower() == ".mp4")
    to_process = [(f, d) for f in videos if (d := [x for x in flaws(f) if x.startswith("tags")])]
    failures = 0
    for file, found_items in to_process:
        relative = file.relative_to(root)
        if not args.apply:
            print(f"{relative}: {' ; '.join(found_items)}")
            continue
        try:
            clean(file)
            print(f"cleaned {relative}")
        except Exception as error:
            failures += 1
            print(f"FAILED {relative}: {error}")
    print(f"{len(to_process)} video(s) to clean out of {len(videos)}" + (f", {failures} failure(s)" if failures else ""))
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
