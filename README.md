# Jellybrarian

[Claude Code](https://claude.com/claude-code) skills that name, file and complete a [Jellyfin](https://jellyfin.org) library of animes, shows, movies, mangas, books and music, according to a single convention. Titles follow the language you choose.

Each Type (`anime`, `show`, `movie`, `manga`, `book`, `music`) has a Root, where its library lives, and an Incoming folder, where its downloads arrive. The `/jb-<type>-<action>` skills work on these two folders, set in `config.toml`, and take no path. The vocabulary is defined in [CONTEXT.md](CONTEXT.md), the decisions in [docs/adr/](docs/adr/).

## Skills

| Skill | Role |
| --- | --- |
| `/jb-<type>-check [incoming\|root]` | Checks the Incoming folder (default) or the Root, identifies each Work, asks the questions and writes the Corrections. |
| `/jb-<type>-rename [incoming\|root]` | Applies the Corrections after approval: renames, metadata, sidecar files, Set aside files. |
| `/jb-<type>-move` | Moves the Incoming folder into the Root and starts the Jellyfin scan. |
| `/jb-<type>-find-missing` | Searches for the Missing items and Follow-ups of the Root, asks which ones to ignore and writes the Wanted list. |
| `/jb-anime-download` | Searches the Wanted list on Prowlarr with the chosen subtitles and sends it to qBittorrent. |
| `/jb-music-migrate-spotify` | Lists the Spotify Tracks left to migrate to the Root and writes them to the Wanted list. |
| `/jb-music-find-missing-album`, `-artist`, `/jb-music-find-new-song` | Suggest Tracks: nearly complete Albums, popular tracks of an Artist, close Tracks through Last.fm. |
| `/jb-music-download` | Searches the Wanted list in FLAC on Soulseek, in batches, sends it to slskd, then fills the Jellyfin playlist `jellyfin.playlist` with every Track. |

Music has no `find-missing`: its four migration and Suggestion skills replace it.

To file downloads: `check`, `rename`, `move`. To complete the library: `find-missing` (or the Music skills), then `download` when the Type has one, otherwise a manual download into the Incoming folder.

Each skill takes a lock on its folders and saves its progress in `data/`: when interrupted, it resumes where it stopped. Questions are asked in batches of 10 Works.

## Languages

`general.conversation_language` sets the language the skills talk to you in. Each video Type has its own languages:

- `title_language`: the language of the titles, with the English title then the original title as fallbacks, never translated,
- `audio_language` and `subtitle_language`: the Preferred language, which decides between two versions of a file and which Releases are searched. For example original audio with French subtitles for Animes, French audio for Shows and Movies.

Release keywords are built in for French (`VOSTFR`, `SUBFRENCH`…). For another subtitle language, list its keywords in `release_keywords`. Mangas and Books follow the language of their text, Tracks and Artists keep their original title.

## Convention

The convention is in [skills/jb/](skills/jb/): [common.md](skills/jb/common.md) for every Type, [videos.md](skills/jb/videos.md) and [readings.md](skills/jb/readings.md) by family, then one file per Type. In short:

- **Shows and Animes**: `<Title> [tmdbid-<id>]/<Title> - S01E01 - <Episode title>.mp4`, the split of Animes following MyAnimeList.
- **Movies**: `<Title> [tmdbid-<id>].mp4`, in a Collection folder when there is one.
- **Mangas**: `<Title> [malid-<id>]/<Title> - T001 - <Volume title>.cbz`, with an embedded `ComicInfo.xml`.
- **Books**: `<Title> [gbid-<id>].epub`, in a Series folder, with the Google Books identifier and the ISBN in the OPF.
- **Music**: `<Artist> [mbid-<uuid>]/<Title> [mbid-<uuid>].flac`, tags and artwork rewritten from MusicBrainz.

The skills never convert a video nor a book: a file in another format is reported To convert, then filed like the others. Only comic archives are repacked as `.cbz`.

## Installation

Requirements: Windows, Python 3.11 or later, Claude Code, Jellyfin 12. Optional: 7-Zip (`.cbr` and `.cb7` archives), Prowlarr and qBittorrent (Anime download), slskd (Music download), a Spotify Premium account (Music migration).

```powershell
git clone https://github.com/Amaroke/jellybrarian.git
cd jellybrarian
.\install.ps1
```

`install.ps1` links each skill into `%USERPROFILE%\.claude\skills`, creates `config.toml` from [config.example.toml](config.example.toml) and installs mutagen and Pillow. Then fill in `config.toml`, which is never committed: the Root of each Type, the languages and the service keys, each explained in a comment. A missing value is asked for by the skill that needs it, except a secret, which you paste yourself.

`data/`, `incoming/` and `set_aside/` are created in the repository and are not committed: they hold the data specific to each library.

## Services

**Jellyfin**: `jellyfin.url` and `jellyfin.key` (Dashboard, API Keys) let the skills start the library scan. Jellyfin keeps its metadata in its database: in each library, untick **Save artwork into media folders** and the **Nfo** metadata saver. Mangas and Books go into a library of type Books.

**Prowlarr and qBittorrent**: Prowlarr with the Nyaa.si indexer, in two instances, one of them filtered on **Trusted only**, named in `prowlarr.trusted_indexers`. qBittorrent with its web UI enabled. Then:

```powershell
python skills\jb\scripts\qbittorrent.py prepare
```

creates the `qbittorrent.category` category pointing to the Anime Incoming folder, and removes each torrent as soon as its download is done.

**Spotify**: an app on <https://developer.spotify.com/dashboard> with **Web API** and the URI `http://127.0.0.1:8888/callback`, owned by a Premium account. Then, once:

```powershell
python skills\jb\scripts\spotify.py connect
python skills\jb\scripts\spotify.py snapshot
python skills\jb\scripts\musicbrainz.py resolve
```

The snapshot is the frozen list of Tracks to migrate, which empties as they arrive in the Root.

**slskd**: Soulseek client with a local API (<https://github.com/slskd/slskd>), its downloads pointed at the Music Incoming folder and its API key in `slskd.key`.

## Tests

```powershell
python -m unittest discover -s tests
```

## License

[MIT](LICENSE)
