import archives
import jellyfin
import metadata
import music
import scan_readings


class Videos:
    name = "videos"
    unit = "video"
    sidecars_label = "Jellyfin file(s) (NFO, images)"

    def owns_file(self, path):
        return jellyfin.is_video(path)

    def with_companions(self, ops):
        everything = []
        for source, target in ops:
            everything.append((source, target))
            if source.is_file() and source.parent.is_dir():
                everything += [(f, target.with_name(target.stem + follow_up)) for f, follow_up in jellyfin.companions(source)]
        return everything

    def sidecars(self, root):
        return jellyfin.to_delete_under(root)

    def to_clean(self, root, relatives, renamed):
        if not metadata.available():
            print(f"mutagen not found: metadata not cleaned. Install it with: {metadata.INSTALLATION}")
            return []
        return [(r, None) for r in relatives if (root / r).suffix.lower() == ".mp4" and any(d.startswith("tags") for d in metadata.flaws(root / r))]

    def clean(self, file, expected):
        metadata.clean(file)


class Readings:
    name = "readings"
    unit = "reading"
    sidecars_label = "sidecar file(s) (covers, OPF, ComicInfo…)"

    def owns_file(self, path):
        return archives.is_reading(path)

    def with_companions(self, ops):
        return list(ops)

    def sidecars(self, root):
        return archives.to_delete_under(root)

    def to_clean(self, root, relatives, renamed):
        expected_values = scan_readings.expected_values([renamed.get(r, r) for r in relatives])
        return [(r, expected_values.get(renamed.get(r, r))) for r in relatives if archives.flaws(root / r, expected_values.get(renamed.get(r, r)))]

    def clean(self, file, expected):
        archives.clean(file, expected)


class Music:
    name = "music"
    unit = "Track"
    sidecars_label = "sidecar file(s) (artwork, CUE, logs, playlists…)"

    def owns_file(self, path):
        return music.is_audio(path)

    def with_companions(self, ops):
        return list(ops)

    def sidecars(self, root):
        return music.to_delete_under(root)

    def to_clean(self, root, relatives, renamed):
        if music.mutagen is None:
            print(f"mutagen not found: tags not rewritten. Install it with: {metadata.INSTALLATION}")
            return []
        found_items = []
        for r in relatives:
            mbid = music.from_name(root / renamed.get(r, r))
            f = music.listing(mbid, False) if mbid else None
            if f and music.flaws(root / r, mbid, f):
                found_items.append((r, (mbid, f)))
        return found_items

    def clean(self, file, expected):
        music.write(file, *expected)


VIDEOS, READINGS, MUSIC = Videos(), Readings(), Music()
ALL = (VIDEOS, READINGS, MUSIC)


def by_name(name):
    return next((g for g in ALL if g.name == name), VIDEOS)


def detect(root):
    files = [f for f in jellyfin.walk(root) if ".trickplay" not in f.as_posix().lower()]
    return max(ALL, key=lambda g: sum(map(g.owns_file, files)))


def contains(folder, genre):
    return any(genre.owns_file(f) for f in folder.rglob("*"))


TYPES = {"anime": VIDEOS, "show": VIDEOS, "movie": VIDEOS, "manga": READINGS, "book": READINGS, "music": MUSIC}
LABELS = {"anime": "Anime", "show": "Show", "movie": "Movie", "manga": "Manga", "book": "Book", "music": "Track"}
ROOTS = {"anime": "Animes", "show": "Shows", "movie": "Movies", "manga": "Mangas", "book": "Books", "music": "Music"}
