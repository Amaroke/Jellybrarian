import argparse
import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path

import config

VALIDITY = 31


def folder():
    return config.data_folder()


def of_type(type_, name):
    return folder() / type_ / f"{name}.json"


def cache(name):
    return folder() / "cache" / f"{name}.json"


def corrections(type_, target):
    return of_type(type_, f"corrections-{target}")


def in_progress(type_, action, target="root"):
    return folder() / type_ / "in_progress" / f"{action}-{target}.json"


def spotify():
    return of_type("music", "spotify")


def spotify_token():
    return of_type("music", "spotify_token")


def read_json(file):
    return json.loads(Path(file).read_text(encoding="utf-8"))


def write_json(file, storage):
    file = Path(file)
    file.parent.mkdir(parents=True, exist_ok=True)
    temp = file.with_name(file.name + ".tmp")
    temp.write_text(json.dumps(storage, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(temp, file)


def read_cache(file):
    return read_json(file) if Path(file).is_file() else {}


def fresh(entry):
    return bool(entry) and entry.get("checked", "") >= (date.today() - timedelta(days=VALIDITY)).isoformat()


def record(file, key, values):
    content = read_cache(file)
    content[key] = values | {"checked": date.today().isoformat()}
    write_json(file, content)


def as_set(type_, name):
    file = of_type(type_, name)
    return set(read_json(file)) if file.is_file() else set()


def modify(type_, name, additions=(), removals=()):
    values = (as_set(type_, name) | set(additions)) - set(removals)
    write_json(of_type(type_, name), sorted(values, key=str.casefold))
    return values


def ignored(type_):
    return as_set(type_, "ignored")


def accepted(type_):
    return as_set(type_, "accepted")


def wanted(type_):
    file = of_type(type_, "wanted")
    return read_json(file) if file.is_file() else None


def write_wanted(type_, content):
    write_json(of_type(type_, "wanted"), content)


def grabbed(type_):
    file = of_type(type_, "grabbed")
    return read_json(file) if file.is_file() else []


def write_grabbed(type_, values):
    write_json(of_type(type_, "grabbed"), values)


def lock(type_, target):
    return folder() / type_ / "in_progress" / f"lock-{target}.json"


def acquire_lock(type_, targets, action, force=False):
    taken = [(c, read_json(lock(type_, c))) for c in targets if lock(type_, c).is_file()]
    others = [(c, v) for c, v in taken if v["action"] != action]
    if others and not force:
        return [f"{type_} {c} is locked by {v['action']} since {v['since']}" for c, v in others]
    for c in targets:
        write_json(lock(type_, c), {"action": action, "since": datetime.now().isoformat(timespec="seconds")})
    return []


def unlock(type_, targets):
    for c in targets:
        lock(type_, c).unlink(missing_ok=True)


def label(follow_up):
    return f"{follow_up['media']} : {follow_up['follow_up']}"


def follow_up_line(follow_up):
    details = " | ".join(x for x in (follow_up.get("detail"), follow_up.get("source")) if x)
    return label(follow_up) + (f" ({details})" if details else "")


def sections(missing, follow_ups, ignored_):
    lines = {"Missing": [], "Ignored": []}
    for media, spans in missing.items():
        lines["Ignored" if media in ignored_ else "Missing"].append(f"{media} : {spans}")
    for s in follow_ups:
        lines["Ignored" if label(s) in ignored_ else "Missing"].append(follow_up_line(s))
    return {title: sorted(l, key=str.casefold) for title, l in lines.items()}


def extension_lines(content, renamed):
    return [f"{f} → {renamed.get(f, f)}" for f in content.get("fixed_extensions", {})]


def extension_errors(content):
    fixed = content.get("fixed_extensions", {})
    renamed = {op["from"]: op["to"] for op in content.get("operations", [])}
    moved = {m["from"] for m in content.get("set_aside", [])}
    errors = []
    for source, target in renamed.items():
        expected_value = fixed.get(source, Path(source).suffix.lower())
        if Path(target).suffix != expected_value and Path(target).suffix.lower() != Path(source).suffix.lower():
            errors.append(f"extension changed: {source} → {target}")
    for source, extension in fixed.items():
        if source not in moved and Path(renamed.get(source, source)).suffix != extension:
            errors.append(f"extension to fix to {extension}: {source}")
    return errors


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("ignored", "accepted"):
        subparsers.add_parser(command).add_argument("type", choices=config.TYPES)
    for command in ("ignore", "keep", "accept", "restore"):
        p = subparsers.add_parser(command)
        p.add_argument("type", choices=config.TYPES)
        p.add_argument("names", nargs="+")
    p = subparsers.add_parser("lock")
    p.add_argument("type", choices=config.TYPES)
    p.add_argument("action")
    p.add_argument("targets", nargs="+", choices=config.TARGETS)
    p.add_argument("--force", action="store_true")
    p = subparsers.add_parser("unlock")
    p.add_argument("type", choices=config.TYPES)
    p.add_argument("targets", nargs="+", choices=config.TARGETS)
    p = subparsers.add_parser("in-progress")
    p.add_argument("type", choices=config.TYPES)
    p.add_argument("action")
    p.add_argument("target", nargs="?", default="root", choices=config.TARGETS)
    p.add_argument("--give-up", action="store_true")
    p = subparsers.add_parser("volumes")
    p.add_argument("malid")
    p.add_argument("title")
    p.add_argument("last", type=int)
    p.add_argument("source")
    p.add_argument("--zero", action="store_true")
    p = subparsers.add_parser("spin-offs")
    p.add_argument("media")
    p.add_argument("source")
    p.add_argument("follow_ups", nargs="*")
    p = subparsers.add_parser("series")
    p.add_argument("name")
    p.add_argument("source")
    p.add_argument("books", nargs="+")
    args = parser.parse_args()

    if args.command == "lock":
        refusal = acquire_lock(args.type, args.targets, args.action, args.force)
        for line in refusal:
            print(line)
        if refusal:
            raise SystemExit(4)
        print(f"Lock taken: {args.type} {' '.join(args.targets)} for {args.action}")
        return
    if args.command == "unlock":
        unlock(args.type, args.targets)
        print(f"Lock released: {args.type} {' '.join(args.targets)}")
        return
    if args.command == "in-progress":
        file = in_progress(args.type, args.action, args.target)
        if args.give_up:
            file.unlink(missing_ok=True)
            print("Progress dropped.")
        elif file.is_file():
            content = read_json(file)
            print(f"In progress since {content.get('start', '?')}, step {content.get('step', '?')}: {file}")
        else:
            print("Nothing in progress.")
        return
    if args.command == "volumes":
        record(cache("volumes"), args.malid, {"title": args.title, "last": args.last, "zero": args.zero, "source": args.source})
        print(f"{args.title}: {args.last} Volume(s) released" + (", Volume 0 included" if args.zero else ""))
        return
    if args.command == "spin-offs":
        record(cache("spin_offs"), args.media, {"follow_ups": args.follow_ups, "source": args.source})
        print(f"{args.media}: {len(args.follow_ups)} spin-off Show(s) released")
        return
    if args.command == "series":
        record(cache("series"), args.name, {"books": args.books, "source": args.source})
        print(f"{args.name}: {len(args.books)} Book(s) released")
        return
    name = "accepted" if args.command in ("accept", "restore", "accepted") else "ignored"
    if args.command in ("ignore", "accept"):
        values = modify(args.type, name, additions=args.names)
    elif args.command in ("keep", "restore"):
        values = modify(args.type, name, removals=args.names)
    else:
        values = as_set(args.type, name)
    empty = "No Accepted deviation." if name == "accepted" else "Nothing Ignored."
    print("\n".join(sorted(values, key=str.casefold)) or empty)


if __name__ == "__main__":
    config.run_main(main)
