# Readings

Rules shared by Mangas and Books, on top of [common.md](common.md). Each Type has its own in [manga.md](manga.md) and [book.md](book.md). A reading Root only holds readings: a video in it is a Deviation to handle by hand.

## Titles

The title follows the language of the content: the title of the French edition for a reading in French (`L'Attaque des Titans`, but `One Piece`), the title of the English edition for a reading in English (`Attack on Titan`), the original title otherwise. A reading without an established title in its language is asked to the user, with the original title by default.

## Formats

The format is kept, except for comic archives: a `.cbr`, a `.cb7`, a `.rar` or a `.zip` of images is repacked as `.cbz` by rename, without touching the images, so that its metadata can be written. 7-Zip is needed to read a `.cbr` or a `.cb7`. An extension that does not match the content (an EPUB named `.cbz`) is fixed from the content: the file is a Fixed extension, listed in the Corrections. A `.mobi`, `.azw`, `.azw3`, `.fb2` or `.djvu` is To convert: Jellyfin reads neither its metadata nor its cover, the user converts it themselves to `.epub`.

## Sidecar files and metadata

Only readings stay. Covers, Calibre `.opf` files, `ComicInfo.xml`, `details.json` and other images, XML or JSON files next to the readings are deleted by rename: an external `metadata.opf` or `ComicInfo.xml` would apply to every book of its folder.

The reader is Jellyfin, which reads the embedded metadata before the file name. It reads no identifier in names, and groups a series from this metadata, otherwise from the folder. Cleaning rewrites the archive:

- `.cbz`: only the images stay, with a `ComicInfo.xml` that gives the title, the series and the number of a Volume,
- `.epub`: only the title (rewritten from the final name), the author, the language, the identifier, the modification date and the cover stay, plus `calibre:series` and `calibre:series_index` for a Book of a Series (rank in release order) or a Volume (its number), and for a Book its Google Books identifier (`opf:scheme="GOOGLE"`) and its ISBN (`opf:scheme="ISBN"`), which Jellyfin links to their listings,
- other formats are not touched.

Jellyfin does not read the reading direction: a Manga is read right to left by setting it in the reader.
