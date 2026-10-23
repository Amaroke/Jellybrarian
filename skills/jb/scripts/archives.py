import os
import re
import shutil
import io
import subprocess
import tempfile
import zipfile
import zlib
from pathlib import Path

import jellyfin

READINGS = {".epub", ".pdf", ".cbz", ".cbr", ".cb7", ".cbt", ".zip", ".rar", ".mobi", ".azw", ".azw3", ".fb2", ".djvu"}
TO_CONVERT = {".mobi", ".azw", ".azw3", ".fb2", ".djvu"}
SEVEN_ZIP = [r"C:\Program Files\7-Zip\7z.exe", "7z"]
IMAGES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".avif"}
SIDECARS = IMAGES | {".opf", ".xml", ".json", ".nfo"}
EPUB_JUNK = {"itunesmetadata.plist", "meta-inf/calibre_bookmarks.txt"}
ELEMENT = re.compile(r"<(?P<name>dc:\w+|meta)\b(?P<attributes>[^>]*?)(?:/>|>(?P<text>.*?)</(?P=name)\s*>)", re.S)
METADATA = re.compile(r"(<(?:opf:)?metadata\b[^>]*>)(.*?)(</(?:opf:)?metadata\s*>)", re.S)
ROOTFILE = re.compile(r"full-path=\"([^\"]+)\"")
UNIQUE = re.compile(r"unique-identifier=\"([^\"]+)\"")
ITEM = re.compile(r"<(?:opf:)?item\b(?P<attributes>[^>]*?)/?>", re.S)


def is_reading(path):
    return path.is_file() and path.suffix.lower() in READINGS


def tolerated(path):
    return path.name.lower() in jellyfin.TOLERATED


def real_format(file):
    try:
        with zipfile.ZipFile(file) as archive:
            names = archive.namelist()
            if "mimetype" in names and archive.read("mimetype").strip() == b"application/epub+zip":
                return ".epub"
            return ".cbz"
    except (zipfile.BadZipFile, OSError):
        pass
    try:
        with open(file, "rb") as f:
            head = f.read(8)
    except OSError:
        return None
    if head.startswith(b"%PDF"):
        return ".pdf"
    if head.startswith(b"Rar!"):
        return ".cbr"
    if head.startswith(bytes.fromhex("377abcaf")):
        return ".cb7"
    return None


def wrong_extension(file):
    current_suffix = file.suffix.lower()
    if current_suffix not in (".epub", ".cbz", ".cbr", ".cb7", ".zip", ".rar", ".pdf"):
        return None
    actual = real_format(file)
    if actual in (".cbr", ".cb7"):
        actual = ".cbz"
    if actual is None or actual == current_suffix or (actual == ".cbz" and current_suffix == ".epub"):
        return None
    return actual


def to_repack(file):
    return real_format(file) in (".cbr", ".cb7")


def seven_zip():
    return next((c for c in SEVEN_ZIP if shutil.which(c)), None)


def repack(file):
    tool = seven_zip()
    if not tool:
        raise RuntimeError("7-Zip not found, archive not repacked")
    with tempfile.TemporaryDirectory() as folder:
        result = subprocess.run([tool, "x", "-y", f"-o{folder}", str(file)], capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"7-Zip failed: {result.stderr.strip() or result.stdout.strip()}")
        images = sorted(f for f in Path(folder).rglob("*") if f.is_file() and f.suffix.lower() in IMAGES)
        if not images:
            raise RuntimeError("no image in the archive")
        temp = file.with_name(file.name + ".jb-tmp")
        with zipfile.ZipFile(temp, "w", zipfile.ZIP_STORED) as target:
            for image in images:
                target.write(image, image.relative_to(folder).as_posix())
    os.replace(temp, file)


def to_delete(path):
    return path.is_file() and path.suffix.lower() in SIDECARS


def to_delete_under(root):
    folders = [root] + [d for d in jellyfin.content(root) if d.is_dir()]
    return sorted(
        f for d in folders for f in (jellyfin.content(root) if d == root else d.iterdir())
        if to_delete(f) and (d == root or any(is_reading(x) for x in d.iterdir()))
    )


def attribute(attributes, name):
    m = re.search(rf"\b{re.escape(name)}=\"([^\"]*)\"", attributes)
    return m[1] if m else None


def escape_xml(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def opf_path(archive):
    m = ROOTFILE.search(archive.read("META-INF/container.xml").decode("utf-8"))
    return m[1]


def cover(opf, elements):
    images = [m["attributes"] for m in ITEM.finditer(opf) if (attribute(m["attributes"], "media-type") or "").startswith("image/")]
    declared = next((attribute(e["attributes"], "content") for e in elements if e["name"] == "meta" and attribute(e["attributes"], "name") == "cover"), None)
    if declared and any(attribute(a, "id") == declared for a in images):
        return declared
    for criterion in (
        lambda a: "cover-image" in (attribute(a, "properties") or ""),
        lambda a: (attribute(a, "id") or "").lower() in ("cover", "cover-image", "coverimage"),
        lambda a: "cover" in (attribute(a, "id") or "").lower() or "cover" in (attribute(a, "href") or "").lower(),
    ):
        found_value = next((attribute(a, "id") for a in images if criterion(a) and attribute(a, "id")), None)
        if found_value:
            return found_value
    return None


def to_add(identifier, expected):
    file_isbn = identifier is not None and (attribute(identifier["attributes"], "opf:scheme") or "").upper() == "ISBN"
    return [("GOOGLE", expected.get("google"))] + ([] if file_isbn else [("ISBN", expected.get("isbn"))])


def epub_metadata(opf, expected):
    block = METADATA.search(opf)
    if not block:
        raise ValueError("OPF without metadata")
    unique = (UNIQUE.search(opf) or [None, None])[1]
    elements = list(ELEMENT.finditer(block[2]))
    identifiers = [e for e in elements if e["name"] == "dc:identifier"]
    identifier = next((e for e in identifiers if attribute(e["attributes"], "id") == unique), identifiers[0] if identifiers else None)
    language = next((e for e in elements if e["name"] == "dc:language"), None)
    kept_elements = [e[0] for e in (identifier, language) if e is not None]
    for schema, value in to_add(identifier, expected):
        if value:
            kept_elements.append(f'<dc:identifier opf:scheme="{schema}">{escape_xml(value)}</dc:identifier>')
    kept_elements += [e[0] for e in elements if e["name"] == "dc:creator"]
    kept_elements += [e[0] for e in elements if e["name"] == "meta" and attribute(e["attributes"], "property") == "dcterms:modified"]
    cover_identifier = cover(opf, elements)
    if cover_identifier:
        kept_elements.append(f'<meta name="cover" content="{escape_xml(cover_identifier)}"/>')
    kept_elements.insert(0, f"<dc:title>{escape_xml(expected['title'])}</dc:title>")
    if expected.get("series"):
        kept_elements.append(f'<meta name="calibre:series" content="{escape_xml(expected["series"])}"/>')
        if expected.get("rank") is not None:
            kept_elements.append(f'<meta name="calibre:series_index" content="{expected["rank"]}"/>')
    removed = [e for e in elements if e[0] not in kept_elements]
    opening = block[1]
    if "xmlns:opf=" not in opf:
        opening = opening[:-1] + ' xmlns:opf="http://www.idpf.org/2007/opf">'
    new_text = opf[:block.start(1)] + opening + "\n    " + "\n    ".join(kept_elements) + "\n  " + opf[block.end(2):]
    return new_text, elements, removed


def epub_flaws(archive, expected):
    flaws = []
    names = archive.namelist()
    junk = [n for n in names if n.lower() in EPUB_JUNK]
    if junk:
        flaws.append("internal files: " + ", ".join(junk))
    if expected is None:
        return flaws
    opf = archive.read(opf_path(archive)).decode("utf-8")
    _, elements, removed = epub_metadata(opf, expected)
    declared = next((attribute(e["attributes"], "content") for e in elements if e["name"] == "meta" and attribute(e["attributes"], "name") == "cover"), None)
    if cover(opf, elements) and declared != cover(opf, elements):
        flaws.append("cover not declared")
    titles = [(e["text"] or "").strip() for e in elements if e["name"] == "dc:title"]
    if titles != [escape_xml(expected["title"])]:
        flaws.append(f"internal title « {' / '.join(titles)} »")
    current_values = {attribute(e["attributes"], "name"): attribute(e["attributes"], "content") for e in elements if e["name"] == "meta"}
    if current_values.get("calibre:series") != (escape_xml(expected["series"]) if expected.get("series") else None):
        flaws.append(f"internal series « {current_values.get('calibre:series') or 'none'} »")
    rank = str(expected["rank"]) if expected.get("series") and expected.get("rank") is not None else None
    if rank and (current_values.get("calibre:series_index") or "").rstrip("0").rstrip(".") != rank:
        flaws.append(f"internal rank « {current_values.get('calibre:series_index') or 'none'} »")
    schemas = {(attribute(e["attributes"], "opf:scheme") or "").upper(): (e["text"] or "").strip() for e in elements if e["name"] == "dc:identifier"}
    unique = (UNIQUE.search(opf) or [None, None])[1]
    identifiers = [e for e in elements if e["name"] == "dc:identifier"]
    entry_point = next((e for e in identifiers if attribute(e["attributes"], "id") == unique), identifiers[0] if identifiers else None)
    for schema, value in to_add(entry_point, expected):
        if value and schemas.get(schema) != value:
            flaws.append(f"identifier {schema} missing internally")
    others = sorted({e["name"] if e["name"] != "meta" else attribute(e["attributes"], "name") or attribute(e["attributes"], "property") or "meta" for e in removed} - {"dc:title", "calibre:series", "calibre:series_index", "cover"})
    if others:
        flaws.append("internal metadata: " + ", ".join(others))
    return flaws


def comic_info(expected):
    fields = [("Title", expected["title"]), ("Series", expected.get("series"))]
    if expected.get("rank") is not None:
        fields.append(("Number", f"{expected['rank']:g}" if isinstance(expected["rank"], float) else str(expected["rank"])))
    lines = [f"  <{k}>{escape_xml(str(v))}</{k}>" for k, v in fields if v]
    return '<?xml version="1.0" encoding="utf-8"?>\n<ComicInfo>\n' + "\n".join(lines) + "\n</ComicInfo>\n"


def cbz_flaws(archive, expected):
    names = archive.namelist()
    others = [n for n in names if not n.endswith("/") and Path(n).suffix.lower() not in IMAGES and n != "ComicInfo.xml"]
    flaws = ["internal files: " + ", ".join(others)] if others else []
    if expected and ("ComicInfo.xml" not in names or archive.read("ComicInfo.xml").decode("utf-8", "replace") != comic_info(expected)):
        flaws.append("ComicInfo.xml missing or different")
    return flaws


def flaws(file, expected):
    extension = wrong_extension(file) or file.suffix.lower()
    if extension not in (".epub", ".cbz"):
        return []
    if to_repack(file):
        return ["archive to repack as .cbz"]
    try:
        with zipfile.ZipFile(file) as archive:
            return epub_flaws(archive, expected) if extension == ".epub" else cbz_flaws(archive, expected)
    except (zipfile.BadZipFile, KeyError, ValueError, UnicodeDecodeError) as error:
        return [f"unreadable archive: {error}"]


def corrupted_page(name):
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        raise RuntimeError("Pillow not found: python -m pip install --user pillow")
    image = Image.new("RGB", (1200, 1800), "white")
    drawing = ImageDraw.Draw(image)
    drawing.rectangle((40, 40, 1160, 1760), outline="black", width=8)
    drawing.text((600, 900), "Corrupted page", fill="black", anchor="mm", font_size=110)
    output = io.BytesIO()
    format_ = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP", ".gif": "GIF", ".bmp": "BMP"}.get(Path(name).suffix.lower(), "JPEG")
    image.save(output, format_)
    return output.getvalue()


def read_entry(source, info, corrupted):
    try:
        return source.read(info.filename)
    except (zipfile.BadZipFile, zlib.error, EOFError):
        if Path(info.filename).suffix.lower() not in IMAGES:
            raise
        corrupted.append(info.filename)
        return corrupted_page(info.filename)


def rewrite(file, keep, substitute):
    temp = file.with_name(file.name + ".jb-tmp")
    corrupted = []
    try:
        with zipfile.ZipFile(file) as source, zipfile.ZipFile(temp, "w") as target:
            infos = sorted(source.infolist(), key=lambda i: i.filename != "mimetype")
            for info in infos:
                if not keep(info.filename):
                    continue
                storage = substitute.get(info.filename) or read_entry(source, info, corrupted)
                target.writestr(info, storage, compress_type=zipfile.ZIP_STORED if info.filename == "mimetype" else info.compress_type)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise
    os.replace(temp, file)
    if corrupted:
        print(f"Corrupted page(s) replaced in {file.name}: {', '.join(corrupted)}", flush=True)


def clean(file, expected):
    extension = wrong_extension(file) or file.suffix.lower()
    if extension == ".cbz":
        if to_repack(file):
            repack(file)
        rewrite(file, lambda n: n.endswith("/") or Path(n).suffix.lower() in IMAGES, {})
        if expected:
            with zipfile.ZipFile(file, "a") as archive:
                archive.writestr("ComicInfo.xml", comic_info(expected))
    elif extension == ".epub":
        with zipfile.ZipFile(file) as archive:
            path = opf_path(archive)
            opf = archive.read(path).decode("utf-8")
        substitute = {path: epub_metadata(opf, expected)[0].encode("utf-8")} if expected else {}
        rewrite(file, lambda n: n.lower() not in EPUB_JUNK, substitute)
