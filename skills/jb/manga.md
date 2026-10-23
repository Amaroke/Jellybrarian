# Mangas

Convention and check of the Manga Root, on top of [common.md](common.md) and [readings.md](readings.md).

## Tree

```text
<root>/
├── One Piece [malid-13]/
│   ├── One Piece - T001 - Romance Dawn.cbz
│   ├── One Piece - T002 - Buggy the Clown.cbz
│   └── One Piece - HS001 - Color Walk 1.cbz
└── Attack on Titan [malid-23390]/
    ├── Attack on Titan - T000.cbz
    └── Attack on Titan - T001.cbz
```

| Item | Format |
| --- | --- |
| Manga folder | `<Title> [malid-<id>]` |
| Volume | `<Title> - T<NNN> - <Volume title>.<ext>` |
| Extra volume | `<Title> - HS<NNN> - <Extra volume title>.<ext>` |
| Chapter | `<Title> - C<NNN> - <Chapter title>.<ext>`, `C<NNN>.5` for an intermediate chapter |

- `malid` is the MyAnimeList identifier of the Manga. Jellyfin does not read it: it serves the skills, Jellyfin grouping the Volumes from their `ComicInfo.xml`.
- `<NNN>` on at least three digits, for every Volume, Extra volume and chapter. The official Volume 0 takes `T000`. Extra volumes (guides, artbooks, anthologies) are numbered `HS001`, `HS002` in release order.
- The Volume title is the one of the edition of the file, kept as it is in the current name except for the character rules. A Volume whose name has no title gets one, searched on the publisher's site or a reference site of the edition's language (Manga-News or Nautiljon in French, MangaUpdates in English). Only an edition that does not title its Volumes gives `<Title> - T<NNN>.<ext>`.
- One file per Volume. A chapter isolated among Volumes is Set aside.
- A Manga of which only chapters exist has its own folder `<Title> [malid-<id>]`, under the MAL identifier of the work in chapters. It keeps this folder even when another Work carries the same title, like the light novel it is adapted from: their identifiers tell them apart. Its files follow the Chapter format, with the same width rule as Volumes. Its Missing items are not computed, since they are counted in Volumes.

## Check

There is no online check for Mangas: the script only checks the form and the metadata.

### Inventory

Each direct subfolder is a candidate Manga. A reading placed at the target is a Volume outside its Manga, or a Book to handle by hand. Done when each reading concerned is attached to a candidate Manga or Set aside with its reason.

### Identification

On MAL with the Client ID of [mal.md](mal.md):

```
python <scripts>/mal.py manga-search "Shingeki no Kyojin"
python <scripts>/mal.py manga 23390
```

Done when each Manga has a `malid` or a pending question.

### Volumes

Match each file to its Volume from the number in its name (`Tome 3`, `T03`, `Vol. 3`, `v03`), and keep the Volume title the name carries. Search for the missing ones. Spot the edition: a Perfect, Deluxe or omnibus edition does not number like the regular edition. Two editions mixed in a folder, or two files for the same Volume, are asked to the user. Chapters filed with the Volumes of another Work (a manga with its light novel) go into their own Manga folder, as in [Tree](#tree).

### Questions

- each ambiguous Manga, with the 3 best MAL results, the user answering with a number or a MAL identifier,
- each title without an established form in the language of the content, with the original title by default,
- two editions mixed in a folder, two files for the same Volume.

## Missing

`wanted.py` computes Missing items from the Volume cache of `data/cache/`, valid for a month, and lists under "To look up on the web" the Mangas absent or stale. For each one, search the web for the last Volume released in the edition and language of the folder (publisher's site or a reference site of that language), then save it with the source:

```
python <scripts>/storage.py volumes <malid> "<Title>" <last Volume released> <url> [--zero]
```

`--zero` when an official Volume 0 exists. Extra volumes never count. Then run `wanted.py search` again to get the Missing items.
