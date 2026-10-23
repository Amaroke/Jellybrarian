import sys

import archives
import jellyfin
import music
import names


def classify(report, file):
    if file.name.lower() in jellyfin.TOLERATED or music.to_delete(file):
        return False
    if jellyfin.is_video(file) or archives.is_reading(file):
        report.add(file, "file", "video or reading in a Music root, to handle by hand")
        return False
    if not music.is_audio(file):
        report.add(file, "file", "neither a Track nor a sidecar file")
        return False
    if file.suffix != file.suffix.lower():
        report.add(file, "name", "uppercase extension")
    if file.suffix.lower() != ".flac":
        report.add(file, "file", f"format {file.suffix[1:].upper()} instead of FLAC: replace it, or accept it for lack of FLAC")
    report.files.append(file)
    return True


def check_track(report, file, artist):
    m = music.TRACK.match(file.stem)
    if not m:
        report.add(file, "name", "MusicBrainz identifier missing")
        return
    names.check(report, file, m["title"])
    report.tracks.append((file, m["title"], m["id"], artist))


def check(report):
    for c in sorted(jellyfin.content(report.root)):
        if c.is_file():
            if classify(report, c):
                report.add(c, "location", "Track outside an Artist folder")
            continue
        m = music.ARTIST.match(c.name)
        names.check(report, c, m["name"] if m else c.name)
        if not m:
            report.add(c, "name", "MusicBrainz identifier of the Artist missing")
        for f in sorted(f for f in c.rglob("*") if f.is_file()):
            if not classify(report, f):
                continue
            if f.parent != c:
                report.add(f, "location", "file in a subfolder, Tracks sit directly in the Artist folder")
            else:
                check_track(report, f, m["id"] if m else None)
        if not any(music.is_audio(f) for f in c.rglob("*")):
            report.add(c, "location", "folder without a Track")


def check_musicbrainz(report, network):
    folders = set()
    for n, (file, title, mbid, artist) in enumerate(report.tracks, 1):
        if n % 50 == 0:
            print(f"{n}/{len(report.tracks)} Tracks", file=sys.stderr, flush=True)
        if not report.compliant(file):
            continue
        f = music.listing(mbid, network)
        if not f:
            if network:
                report.add(file, "title", f"MusicBrainz recording {mbid} unknown")
            continue
        expected = music.final_path(mbid, f, file.suffix)
        folder, name = expected.split("/")
        if artist and artist != f["folder"]:
            report.add(file, "location", f"Album artist: « {folder} »")
        elif file.parent.name != folder and file.parent not in folders:
            folders.add(file.parent)
            report.add(file.parent, "title", f"MusicBrainz name of the Artist: « {folder} »")
        if file.name != name:
            report.add(file, "title", f"MusicBrainz title: « {name} »")
        for text in music.non_latin(f):
            report.add(file, "title", f"non-Latin script to transliterate: « {text} »")
        for default in music.flaws(file, mbid, f):
            report.add(file, "metadata", default)
