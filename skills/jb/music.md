# Music

Convention and check of the Music Root, on top of [common.md](common.md). Checked by `scripts/scan.py music`, identified on MusicBrainz by `scripts/music.py`.

## Tree

```text
<root>/
├── Orelsan [mbid-6cad3ce5-6380-4594-a8da-ae7d273b683d]/
│   ├── Suicide social [mbid-962f1cd3-7cf4-4fc0-be9f-941f13cbb1cc].flac
│   └── Plus rien ne m'étonne [mbid-<uuid>].flac
└── Vald [mbid-062ab94e-b7a5-47a9-b3f4-cc1750c3f859]/
    └── Eurotrap [mbid-d0e8240a-6a35-4d8e-85a3-37d7502f9a56].flac
```

| Item | Format |
| --- | --- |
| Artist folder | `<Artist> [mbid-<artist uuid>]` |
| Track | `<Title> [mbid-<recording uuid>].flac` |

- No Album folder: the Album only exists in the tags, Jellyfin groups by itself.
- **Folder Artist**: the album artist of the Track. When the Album is a various-artists release (`Various Artists`), the first credited artist of the Track.
- **Album**: the first official release of type Album that holds the recording, never a compilation nor a DJ-mix. Otherwise an EP, then a single. A soundtrack or a mixtape are Albums.
- **Title**: the MusicBrainz title of the recording, except for the character rules. The version is part of it (`Title (Live)`, `Title (Hardstyle Remix)`). The title is never translated.
- **Non-Latin script**: a title or an Artist name in Japanese, Korean, Cyrillic… is transliterated to Latin script, from a Latin alias on MusicBrainz when it exists, otherwise by the usual romanisation (Hepburn, Revised Romanization of Korean, common Russian transliteration). The transliterated title is used for the name and the tags.

## Format

FLAC only, lowercase extension. A Track in another format is a `file` Deviation: it is replaced by a FLAC, or kept as MP3 320 as an Accepted deviation when no FLAC exists. There is no To convert: converting does not restore lost quality.

## Tags

Jellyfin builds its Music library from the file tags only. Rename rewrites them from MusicBrainz and removes everything else:

- title, artists (one value per artist), album artist, Album, track number, release date,
- MusicBrainz identifiers of the recording, the release, the release group, the artists and the album artists,
- the artwork of the release, embedded in the file, taken from Cover Art Archive.

## Sidecar files

Only Tracks stay. Artwork, `.cue`, `.log`, `.m3u`, `.nfo`, `.txt`, `.sfv` and `.accurip` files next to them are deleted by rename.

## Check

`music.py` keeps in `data/cache/` a listing per recording (`tracks.json`), the Albums (`albums.json`) and the name of each Artist (`artists.json`), where transliterations are also written. The online check is long on a large Root: run it in the background.

The online check reports:

- `name`, `location`: a folder or a Track without `[mbid-…]` is a `name` Deviation, a Track outside an Artist folder or in a subfolder (an Album folder) a `location` Deviation,
- `file`: a format other than FLAC, a video, a reading, an unknown file,
- `title`: an unknown recording, a folder Artist that is not the album artist, a name or title different from MusicBrainz, a non-Latin script,
- `metadata`: tags that differ from the expected ones, missing artwork.

### Identification

For the Tracks to rename:

```
python <scripts>/music.py identify <target> [<relative file> ...]
```

Without a file, the script handles each Track without `[mbid-…]`. Pass as arguments the Tracks to rename that already have their identifier. It takes the identifier from the tags when it is there, otherwise it searches MusicBrainz by artist and title, from the tags or an `Artist - Title` name, and recognises an slskd Grabbed item by its file name. It only accepts a result by the same artist, with an identical title and within 3 seconds. It writes under `identification`, in the check progress, one proposal per Track: `from`, `mbid`, `to` (the final path), `non_latin` (the texts to transliterate), `doubtful` (up to 3 candidates when nothing is sure) and the `tags` read. A proposal without `mbid` nor `doubtful` is not found on MusicBrainz: it is Set aside.

In `works`, a Work is a final Artist: its `operations` are the `to` of the proposals kept.

### Transliteration

For each text of `non_latin`, look for a Latin alias on MusicBrainz, otherwise transliterate as in [Tree](#tree), then save the Latin form. An Artist only gets one form, shared by all its Tracks.

```
python <scripts>/music.py title <recording mbid> "<Latin title>"
python <scripts>/music.py artist <artist mbid> "<Latin name>"
python <scripts>/music.py listing <recording mbid>
```

`listing` shows the identifiers of the artists. Then run the identification of these Tracks again to get their final path.

### Questions

- each doubtful Track, with its candidates (artists, title, duration against the file duration), the user answering with a number, a recording MBID or "not found",
- each uncertain transliteration, with the form offered,
- two files for the same recording: the FLAC is kept, the other Set aside,
- each Track in another format than FLAC: Set aside to be replaced, or kept as an Accepted deviation. For an accepted MP3, accept its final path.

For an MBID given by the user, pass it to `music.py listing` to get the final path. In the summary, report the transliterations.

## Missing

For `/jb-music-migrate-spotify`. The music leaves Spotify for the Root. The snapshot `data/music/spotify.json` is the migration list: the Liked songs and the playlists taken into account by the config (`spotify.likes`, `spotify.playlists`) when it was taken. It is frozen and never refreshes. It empties at `move`: each Track moved into the Root leaves it, and leaves the Wanted list. A Missing item is a Track of the snapshot absent from the Root. There are no Follow-ups: Albums and Artists go through Suggestions.

### Preparation

When the snapshot does not exist yet, take it once and for all, then find the MusicBrainz recordings:

```
python <scripts>/spotify.py snapshot
python <scripts>/musicbrainz.py resolve
```

Without a token, `spotify.py connect` opens the login in the browser. Without an active Premium, Spotify refuses: say so. Then compute the missing MusicBrainz listings (folder Artist, Album and its tracks), about two seconds per Track the first time, in the background:

```
python <scripts>/music.py listings
```

### Search

`wanted.py search music` gives the progress of the migration (Tracks migrated out of the snapshot total) and also lists the Tracks without a listing, when `music.py listings` did not finish, the doubtful Tracks with their MusicBrainz candidates, and the Tracks not on MusicBrainz, which will not be downloaded. The draft also holds `tracks` (each Missing item with its `mbid`, final `path`, duration and ISRC), `doubtful` and `not_on_musicbrainz`.

First ask about the doubtful ones in batches, each with its candidates (artists, title, duration against the Spotify duration), the default answer being the candidate with the same title closest in duration, otherwise "not found". Save each answer with the Spotify identifier of the Track, then run `wanted.py search music` again. A choice is final.

```
python <scripts>/music.py choose <spotify> <mbid>
python <scripts>/music.py choose <spotify> not_found
```

A doubtful Track decided "not found" or not on MusicBrainz cannot be migrated, but stays in the snapshot. Report them at each run and ask which ones to remove from the migration. Only on their answer:

```
python <scripts>/spotify.py remove <Spotify identifier> ...
```

### Ignored

An Artist is ignored under its name, the key in `missing`, a specific Track under `<Artist> : <Title>`.

## Suggestions

The three Suggestion skills add to the Wanted list, with their origin, the Tracks the user accepts:

- `/jb-music-find-missing-album`: for each Album of which the Root has at least `music.album_threshold` % of the tracks (50 by default) without having them all, the absent tracks. Only Tracks whose MusicBrainz listing is computed count (`music.py listings`, or the check of the Root).
- `/jb-music-find-missing-artist`: for each Artist with at least `music.min_artist` Tracks in the Root (3 by default), their most popular Tracks on Spotify in the `spotify.market` country, found on MusicBrainz by their ISRC. The Spotify token is needed (`spotify.py connect`).
- `/jb-music-find-new-song`: Tracks close to Tracks of the Root drawn at random, or to the Artist or Track given, from Last.fm (`lastfm.key` in the config), found on MusicBrainz by artist and title. 50 per run.

A Suggestion is only kept if its MusicBrainz listing gives its Artist and its final path.

## Download

The source is Soulseek, through the slskd API, which must be running and connected. Tracks arrive in the Music Incoming folder.

```
python <scripts>/music_releases.py search
```

Run it in the background: it searches batch after batch (100 Tracks, about 25 minutes per batch), every Track of the Wanted list whatever its origin, and saves each result in the progress. Run again, it resumes where it stopped. For each Track, it searches `<artist> <title>` and only keeps the files:

- in FLAC,
- whose duration is the Spotify one within 3 seconds,
- whose name holds the full title, version included (`Hardstyle Remix`, `Sped Up`).

It prefers a source with a free slot, then 16 bits, then the shortest queue and the speed. Without FLAC, it keeps an MP3 320 apart.

As soon as a batch is ready, show it while the next one searches:

```
python <scripts>/music_releases.py batches
```

One line per Track with its quality, size and source, then the MP3 320 and the items not found. By default, every FLAC proposal and no MP3. In the progress, remove the declined proposals from the batch and add the accepted MP3: their Track will become an Accepted deviation at check. Then grab the batch:

```
python <scripts>/music_releases.py grab <batch number>
```

Each Track goes into the slskd queue and becomes Grabbed, which the check uses to recognise the file. When the search is finished and every batch grabbed, the script deletes the progress.

**Playlist**: at the end of the download, even when nothing was grabbed, add every Track of the Jellyfin library to the playlist `jellyfin.playlist` (`Finamp` by default), created when missing:

```
python <scripts>/jellyfin.py playlist
```
