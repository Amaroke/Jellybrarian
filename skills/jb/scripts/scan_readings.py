import re
import urllib.error
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path

import archives
import storage
import jellyfin
import books
import names

MANGA = re.compile(r"^(?P<title>.+?) \[malid-(?P<id>\d+)\]$")
VOLUME = re.compile(r"^(?P<title>.+?) - (?:T(?P<volume>\d{2,})|HS(?P<extra>\d{2,})|C(?P<chapter>\d{2,})(?P<half>\.\d+)?)(?: - (?P<subtitle>.+))?$")
BOOK = re.compile(r"^(?P<title>.+?) \[gbid-(?P<id>[\w-]+)\]$")


def key(text):
    return "".join(c for c in (text or "").casefold() if c.isalnum())


def classify(report, file, allowed_sidecars):
    if archives.tolerated(file) or (allowed_sidecars and archives.to_delete(file)):
        return False
    if jellyfin.is_video(file):
        report.add(file, "file", "video in a reading root, to handle by hand")
        return False
    if not archives.is_reading(file):
        report.add(file, "file", "neither a reading nor a sidecar file")
        return False
    actual = archives.wrong_extension(file)
    if actual and archives.to_repack(file):
        report.add(file, "name", f"archive {archives.real_format(file)[1:].upper()} to repack as {actual}")
        report.fixed_extensions[report.relative(file)] = actual
    elif actual:
        report.add(file, "name", f"content {actual[1:].upper()} under the extension {file.suffix}, extension to fix to {actual}")
        report.fixed_extensions[report.relative(file)] = actual
    if file.suffix.lower() in archives.TO_CONVERT:
        report.to_convert.append(report.relative(file))
    elif file.suffix != file.suffix.lower():
        report.add(file, "name", "uppercase extension")
    report.files.append(file)
    return True


def check(report):
    root = report.root
    content = sorted(jellyfin.content(root))
    for f in (c for c in content if c.is_file()):
        if classify(report, f, True):
            check_book(report, f, None)
    for d in (c for c in content if c.is_dir()):
        check_folder(report, d)


def check_book(report, file, book_series):
    m = BOOK.match(file.stem)
    if m:
        title, identifier = m["title"], m["id"]
    else:
        title, identifier = file.stem, None
        if book_series is None and VOLUME.match(file.stem):
            report.add(file, "location", "Volume outside the folder of its Manga")
        else:
            report.add(file, "name", "Google Books identifier missing")
    names.check(report, file, title)
    report.books.append((file, title, identifier, book_series))
    return title


def check_folder(report, folder):
    names.check(report, folder, folder.name)
    files = [c for c in folder.iterdir() if c.is_file()]
    subfolders = [c for c in folder.iterdir() if c.is_dir()]
    allowed_sidecars = any(archives.is_reading(f) for f in files)
    for subparsers in subfolders:
        content = [f for f in subparsers.rglob("*") if f.is_file()]
        if not content:
            report.add(subparsers, "location", "empty subfolder")
        for f in content:
            report.add(f, "location", "file in a subfolder")
    readings = [f for f in sorted(files) if classify(report, f, allowed_sidecars)]
    if not readings and not subfolders:
        report.add(folder, "location", "folder without a reading")
        return
    m = MANGA.match(folder.name)
    if m:
        check_manga(report, folder, m["title"], int(m["id"]), readings)
    elif any(VOLUME.match(f.stem) for f in readings):
        report.add(folder, "name", "MAL identifier missing")
        check_manga(report, folder, folder.name, None, readings)
    elif readings:
        check_series(report, folder, readings)


def check_manga(report, folder, title, identifier, readings):
    volumes = []
    for f in readings:
        t = VOLUME.match(f.stem)
        if not t:
            report.add(f, "name", "Volume name outside the convention")
            continue
        names.check(report, f, f.stem)
        if t["title"] != title:
            report.add(f, "name", f"prefix « {t['title']} » different from the folder « {title} »")
        sort_kind = "T" if t["volume"] else "HS" if t["extra"] else "C"
        number = t["volume"] or t["extra"] or t["chapter"]
        volumes.append((f, int(number) if sort_kind == "T" else None, number, (sort_kind, number + (t["half"] or "")), bool(t["subtitle"])))
    for f, _, number, _, _ in volumes:
        if len(number) < 3:
            report.add(f, "name", "number on fewer than three digits")
    sort_kinds = {key[0] for _, _, _, key, _ in volumes}
    if "C" in sort_kinds and "T" in sort_kinds:
        report.add(folder, "name", "Volumes and chapters mixed")
    titles = any(title for *_, title in volumes)
    duplicates = Counter((sort_kind, float(number)) for _, _, _, (sort_kind, number), _ in volumes)
    for f, _, _, (sort_kind, number), subtitle in volumes:
        if duplicates[(sort_kind, float(number))] > 1:
            report.add(f, "name", "duplicate Volume")
        if titles and not subtitle:
            report.add(f, "name", "Volume title missing while other Volumes of the folder have one")
    report.mangas.append((folder, title, identifier, [(f, n) for f, n, *_ in volumes], "C" in sort_kinds))


def check_series(report, folder, readings):
    titles = [check_book(report, f, folder.name) for f in readings]
    if len(readings) == 1:
        report.add(readings[0], "location", "Series of a single Book")
        return
    name = folder.name
    if all(t == name or t.startswith(f"{name} - ") for t in titles) and any(t != name for t in titles):
        report.add(folder, "name", f"every Book repeats the name of the Series, « {name} - » to remove from the file names")


@lru_cache(maxsize=None)
def date_of(identifier):
    try:
        return (books.volume(identifier) or {}).get("date") or "9999"
    except (urllib.error.URLError, OSError):
        return "9999"


def identifiers(identifier):
    try:
        isbn = (books.volume(identifier) or {}).get("isbn")
    except (urllib.error.URLError, OSError):
        isbn = None
    return {"google": identifier} | ({"isbn": isbn} if isbn else {})


def expected_values(relatives):
    result = {}
    book_series_list = defaultdict(list)
    for r in relatives:
        p = Path(r)
        manga = MANGA.match(p.parts[0]) if len(p.parts) == 2 else None
        book = BOOK.match(p.stem)
        if manga:
            t = VOLUME.match(p.stem)
            if t and t["title"] == manga["title"]:
                rank = int(t["volume"]) if t["volume"] else float(t["chapter"] + (t["half"] or "")) if t["chapter"] else None
                result[r] = {"title": p.stem, "series": manga["title"], "rank": rank}
        elif book and len(p.parts) == 1:
            result[r] = {"title": book["title"]} | identifiers(book["id"])
        elif book and len(p.parts) == 2:
            book_series_list[p.parts[0]].append((r, book["title"], book["id"]))
    known = storage.read_cache(storage.cache("series"))
    for name, members in book_series_list.items():
        series_books = [key(l) for l in (known.get(name) or {}).get("books", [])]
        known_rank = lambda x: series_books.index(key(x[1])) if key(x[1]) in series_books else len(series_books)
        order = sorted(members, key=lambda x: (known_rank(x), date_of(x[2]), x[1].casefold()))
        for rank, (r, title, identifier) in enumerate(order, 1):
            result[r] = {"title": title, "series": name, "rank": rank} | identifiers(identifier)
    return result


def check_metadata(report):
    files = [f for f in report.files if not report.in_other_type(f)]
    relatives = [report.relative(f) for f in files]
    expected = expected_values(relatives)
    for f, r in zip(files, relatives):
        for default in archives.flaws(f, expected.get(r)):
            report.add(f, "metadata", default)


def volume_spans(numbers, width):
    groups = []
    for n in numbers:
        if groups and groups[-1][1] == n - 1:
            groups[-1][1] = n
        else:
            groups.append([n, n])
    return ", ".join(f"T{a:0{width}d}" if a == b else f"T{a:0{width}d} to T{b:0{width}d}" for a, b in groups)


def missing(report):
    volumes = storage.read_cache(storage.cache("volumes"))
    book_series_list = storage.read_cache(storage.cache("series"))
    result, to_look_up = {}, []
    for folder, title, identifier, present_ones, in_chapters in report.mangas:
        if in_chapters or not identifier or not report.compliant(folder / "_"):
            continue
        entry = volumes.get(str(identifier))
        if not storage.fresh(entry):
            to_look_up.append(f"Manga: {folder.name}")
            continue
        numbers = {n for _, n in present_ones if n is not None}
        absent = sorted(set(range(0 if entry.get("zero") else 1, entry["last"] + 1)) - numbers)
        if absent:
            result[title] = volume_spans(absent, 3)
    by_series = defaultdict(list)
    for file, title, identifier, book_series in report.books:
        if book_series and identifier and report.compliant(file):
            by_series[book_series].append(key(title))
    for book_series, present_ones in sorted(by_series.items()):
        entry = book_series_list.get(book_series)
        if not storage.fresh(entry):
            to_look_up.append(f"Series: {book_series}")
            continue
        absent = [l for l in entry["books"] if not any(p and (key(l) == p or key(l).endswith(p)) for p in present_ones)]
        if absent:
            result[book_series] = ", ".join(absent)
    return result, to_look_up
