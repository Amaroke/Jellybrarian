import argparse
import os
import shutil
import sys
from collections import defaultdict
from pathlib import Path

import config
import storage
import genres
import jellyfin


def same_file(a, b):
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def set_aside_folder(type_):
    return config.set_aside() / type_


def operations(root, corrections):
    ops = [(root / op["from"], root / op["to"]) for op in corrections.get("operations", [])]
    ops += [(root / m["from"], set_aside_folder(corrections["type"]) / Path(m["from"]).name) for m in corrections.get("set_aside", [])]
    return ops


def record_reasons(type_, set_aside):
    if set_aside:
        log = set_aside_folder(type_) / "reasons.txt"
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as f:
            for m in set_aside:
                print(f"{Path(m['from']).name}: {m['reason']}", file=f)


def check(root, ops, elsewhere=()):
    errors = []
    targets = set()
    for source, target in ops:
        if not source.exists():
            errors.append(f"source not found: {source.relative_to(root)}")
        key = os.path.normcase(str(target))
        if key in targets:
            errors.append(f"duplicate target: {target}")
        targets.add(key)
        if target.exists() and not same_file(source, target):
            errors.append(f"target already exists: {target}")
        if not any(target.resolve().is_relative_to(d) for d in (root, *elsewhere)):
            errors.append(f"target outside the root: {target}")
    return errors


def move(source, target):
    if str(source) == str(target):
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if not target.samefile(source):
            raise FileExistsError(target)
        temp = source.with_name(source.name + ".jb-tmp")
        source.rename(temp)
        temp.rename(target)
    else:
        shutil.move(source, target)


def clean(root, ops, genre):
    folders = set()
    for source, _ in ops:
        parent = source.parent
        while parent != root and root in parent.parents:
            folders.add(parent)
            parent = parent.parent
    remaining = []
    for folder in sorted(folders, key=lambda d: len(d.parts), reverse=True):
        if not folder.exists():
            continue
        if not any(folder.iterdir()):
            folder.rmdir()
        elif not genres.contains(folder, genre):
            remaining.append(folder)
    return [d for d in remaining if d.parent not in remaining]


def is_excluded(relative, exclusions):
    stem = (jellyfin.companion(Path(relative)) or [Path(relative).stem])[0]
    return any(relative.startswith(f"{e}/") or stem == e for e in exclusions)


def current_files(root, genre):
    return {f.relative_to(root).as_posix() for f in jellyfin.walk(root) if genre.owns_file(f) and ".trickplay" not in f.as_posix().lower()}


def clean_metadata(root, relatives, genre):
    failures = []
    for n, (r, expected) in enumerate(relatives, 1):
        print(f"Cleaning {n}/{len(relatives)} {r}", file=sys.stderr, flush=True)
        try:
            genre.clean(root / r, expected)
        except Exception as error:
            failures.append(f"{r}: {error}")
    return failures


def show(title, lines):
    if lines:
        print(title)
        for line in lines:
            print(f"  {line}")


def fix(root, plan, exclusions, apply_plan):
    genre = genres.by_name(plan.get("genre"))
    def keeps(op):
        return not (is_excluded(op["from"], exclusions) or is_excluded(op.get("to", op["from"]), exclusions))

    plan["operations"] = [op for op in plan.get("operations", []) if keeps(op)]
    plan["set_aside"] = [m for m in plan.get("set_aside", []) if keeps(m)]
    done = [op for op in plan["operations"] if not (root / op["from"]).exists() and (root / op["to"]).exists()]
    plan["operations"] = [op for op in plan["operations"] if op not in done]
    if done:
        print(f"{len(done)} rename(s) already done by an interrupted run")
    ops = genre.with_companions(operations(root, plan))
    errors = check(root, ops, [set_aside_folder(plan["type"]).resolve()])
    if errors:
        show(f"Corrections refused, run /jb-{plan['type']}-check again:", errors)
        return 3

    new_items = sorted(current_files(root, genre) - set(plan.get("files", [])) - {op["to"] for op in done})
    show("Files that appeared since the check, left untouched:", new_items)

    by_work = defaultdict(list)
    for op in plan["operations"]:
        target = Path(op["to"])
        by_work[target.parts[0] if len(target.parts) > 1 else "(root)"].append(f"{op['from']}  →  {op['to']}")
    for media in sorted(by_work):
        show(media, by_work[media])
    companions = len(ops) - len(plan["operations"]) - len(plan["set_aside"])
    if companions:
        print(f"{companions} companion(s) (subtitles, .trickplay) follow their video")
    delete = [f for f in genre.sidecars(root) if not is_excluded(f.relative_to(root).as_posix(), exclusions)]
    print(f"{len(delete)} {genre.sidecars_label} to delete")
    show(f"Set aside in {set_aside_folder(plan['type'])}:", [f"{m['from']}: {m['reason']}" for m in plan["set_aside"]])

    renamed = {op["from"]: op["to"] for op in plan["operations"]}
    moved = {m["from"] for m in plan["set_aside"]}
    kept = [v for v in plan.get("files", []) if v not in moved and not is_excluded(v, exclusions) and not is_excluded(renamed.get(v, v), exclusions)]
    tags = genre.to_clean(root, [v for v in kept if (root / v).exists()], renamed)
    print(f"{len(tags)} file(s) whose metadata will be cleaned")
    convert = [renamed.get(v, v) for v in plan.get("to_convert", []) if v not in moved and not is_excluded(v, exclusions)]
    show("To convert:", convert)
    extensions = storage.extension_lines(plan, renamed)
    show("Fixed extensions:", extensions)
    print(f"{len(plan['operations'])} rename(s), {len(plan['set_aside'])} Set aside")

    if not apply_plan:
        print("Dry run: nothing was changed.")
        return 0

    failures = clean_metadata(root, tags, genre)
    blocked = []
    for f in delete:
        try:
            f.unlink()
        except OSError as error:
            blocked.append(f"{f.relative_to(root)}: {error.strerror}")
    for source, target in ops:
        try:
            move(source, target)
        except OSError as error:
            blocked.append(f"{source.relative_to(root)}: {error.strerror}")
    record_reasons(plan["type"], [m for m in plan["set_aside"] if not (root / m["from"]).exists()])
    remaining = clean(root, ops + [(f, None) for f in delete] + [(root / op["from"], None) for op in done], genre)
    show("Metadata cleaning failures:", failures)
    for folder in remaining:
        content = ", ".join(f.name for f in folder.iterdir())
        print(f"Folder without {genre.unit} kept: {folder.relative_to(root)} ({content})")
    if blocked:
        show("Locked files, kept in the Corrections for a new run:", blocked)
        return 4
    print("Corrections applied.")
    return 1 if failures else 0


def remaining_items(root, plan):
    def rest(source, target):
        return source.exists() and not (target.exists() and same_file(source, target))
    return plan | {
        "operations": [op for op in plan.get("operations", []) if rest(root / op["from"], root / op["to"])],
        "set_aside": [m for m in plan.get("set_aside", []) if rest(root / m["from"], set_aside_folder(plan["type"]) / Path(m["from"]).name)],
    }


def main():
    parser = argparse.ArgumentParser()
    config.arguments(parser)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--exclude", nargs="*", default=[])
    args = parser.parse_args()

    root = config.folder(args.type, args.target)
    file = storage.corrections(args.type, args.target)
    if not file.is_file():
        print(f"No Corrections for {args.type} {args.target}. Run /jb-{args.type}-check {args.target}.")
        sys.exit(2)
    plan = storage.read_json(file)
    if Path(plan["folder"]).resolve() != root:
        print(f"The Corrections are about {plan['folder']}, but {args.type}.{args.target} is {root}: run /jb-{args.type}-check {args.target}.")
        sys.exit(2)
    print(f"Corrections used: {file}")

    code = fix(root, dict(plan), args.exclude, args.apply)
    if args.apply and code in (0, 1, 4):
        rest = remaining_items(root, plan)
        if rest["operations"] or rest["set_aside"] or args.exclude:
            storage.write_json(file, rest)
            print(f"Corrections left: {len(rest['operations'])} rename(s), {len(rest['set_aside'])} Set aside")
        else:
            file.unlink()
            print("Corrections empty, file deleted.")
    sys.exit(code)


if __name__ == "__main__":
    config.run_main(main)
