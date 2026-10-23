import argparse
import re
import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
FILE = REPO / "config.toml"
TYPES = ("anime", "show", "movie", "manga", "book", "music")
TARGETS = ("incoming", "root")
SECRETS = {
    ("tmdb", "key"),
    ("mal", "client_id"),
    ("google_books", "key"),
    ("spotify", "client_id"),
    ("prowlarr", "key"),
    ("qbittorrent", "password"),
    ("slskd", "key"),
    ("jellyfin", "key"),
    ("lastfm", "key"),
}
MISSING_CONFIG = 3


class MissingConfig(Exception):
    def __init__(self, section, key):
        self.section, self.key = section, key
        super().__init__(f"{section}.{key}")

    def message(self):
        if (self.section, self.key) in SECRETS:
            return f"Missing config (secret): {self.section}.{self.key}, for the user to paste into {FILE}"
        return f"Missing config: {self.section}.{self.key}, ask the user then save it with config.py write {self.section}.{self.key} <value>"


def read():
    return tomllib.loads(FILE.read_text(encoding="utf-8")) if FILE.is_file() else {}


def value(section, key, default=None):
    found_value = read().get(section, {}).get(key)
    if found_value in (None, ""):
        if default is not None:
            return default
        raise MissingConfig(section, key)
    return found_value


def optional(section, key):
    try:
        return value(section, key)
    except MissingConfig:
        return None


def absolute(text):
    path = Path(text)
    return path if path.is_absolute() else REPO / path


def folder(type_, target):
    path = absolute(value(type_, target))
    if target == "incoming":
        path.mkdir(parents=True, exist_ok=True)
    if not path.is_dir():
        print(f"{type_}.{target} is {path}, folder not found: create it, plug in its drive or fix the config")
        sys.exit(2)
    return path.resolve()


def data_folder():
    return absolute(value("data", "folder", "data"))


def set_aside():
    return absolute(value("set_aside", "folder", "set_aside"))


def ignored():
    return set(value("ignored", "names", []))


def write(section, key, new_value):
    if (section, key) in SECRETS:
        raise ValueError(f"{section}.{key} is a secret: the user pastes it themselves into {FILE}")
    line = f"{key} = {toml(new_value)}"
    lines = FILE.read_text(encoding="utf-8").splitlines() if FILE.is_file() else []
    start = next((i for i, l in enumerate(lines) if l.strip() == f"[{section}]"), None)
    if start is None:
        lines += ["", f"[{section}]", line]
    else:
        end = next((i for i in range(start + 1, len(lines)) if lines[i].lstrip().startswith("[")), len(lines))
        existing_index = next((i for i in range(start + 1, end) if re.match(rf"\s*{re.escape(key)}\s*=", lines[i])), None)
        if existing_index is None:
            while end > start + 1 and not lines[end - 1].strip():
                end -= 1
            lines.insert(end, line)
        else:
            lines[existing_index] = line
    FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def toml(value_):
    if isinstance(value_, bool):
        return "true" if value_ else "false"
    if isinstance(value_, int):
        return str(value_)
    if isinstance(value_, list):
        return "[" + ", ".join(toml(v) for v in value_) + "]"
    text = str(value_)
    return f"'{text}'" if "'" not in text else '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def parse_value(text):
    if text in ("true", "false"):
        return text == "true"
    if text.isdigit():
        return int(text)
    return text


def arguments(parser, target=True):
    parser.add_argument("type", choices=TYPES)
    if target:
        parser.add_argument("target", nargs="?", default="incoming", choices=TARGETS)


def run_main(entry_point):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    try:
        entry_point()
    except MissingConfig as gap:
        print(gap.message())
        sys.exit(MISSING_CONFIG)


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("read").add_argument("key")
    p = subparsers.add_parser("write")
    p.add_argument("key")
    p.add_argument("value")
    subparsers.add_parser("check").add_argument("keys", nargs="+")
    args = parser.parse_args()

    if args.command == "write":
        section, key = args.key.split(".", 1)
        write(section, key, parse_value(args.value))
        print(f"{args.key} written to {FILE}")
        return
    keys = [args.key] if args.command == "read" else args.keys
    missing_keys = []
    for name in keys:
        section, key = name.split(".", 1)
        try:
            found_value = value(section, key)
            if args.command == "read":
                print("(secret set)" if (section, key) in SECRETS else found_value)
        except MissingConfig as gap:
            missing_keys.append(gap)
    for gap in missing_keys:
        print(gap.message())
    if missing_keys:
        sys.exit(MISSING_CONFIG)
    if args.command == "check":
        print("Config complete.")


if __name__ == "__main__":
    run_main(main)
