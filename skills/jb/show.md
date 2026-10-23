# Shows

Convention of the Show Root, on top of [common.md](common.md) and [videos.md](videos.md). Animes follow the same names, with the split of [anime.md](anime.md).

## Tree

```text
<root>/
├── Breaking Bad [tmdbid-1396]/
│   ├── Breaking Bad - S01E01 - Pilot.mp4
│   └── Breaking Bad - S00E01 - Special title.mp4
├── The Boys [tmdbid-76479]/
│   └── The Boys - S01E01 - The Name of the Game.mp4
└── Gen V [tmdbid-205715]/
    └── Gen V - S01E01 - God U.mp4
```

- Each Show has a folder `<Title> [tmdbid-<id>]`, which directly holds all its Episodes, without season subfolders.
- **Shows of a same universe**: each Show has its own folder at the Root, under its own TMDB title, even a spin-off or a sequel that TMDB counts as another Show (The Boys and Gen V). Jellyfin takes each Root folder for a single Show: a folder gathering several would mix them like seasons. They are never merged into seasons of a single Show.
- **Movies of a Show**: a Movie that TMDB attaches to a Show (special, TV movie, movie of the show) belongs to the Movie Root, in the Collection `<Show> - Movies` of [movie.md](movie.md#collections). It is Set aside, with this reason.

## Names

| Item | Format |
| --- | --- |
| Show folder | `<Title> [tmdbid-<id>]` |
| Episode | `<Title> - S<SS>E<EE> - <Episode title>.mp4` |
| File with two Episodes | `<Title> - S<SS>E<EE>-E<EE> - <Title 1> & <Title 2>.mp4` |

- `<SS>` on two digits. `<EE>` on at least two digits (`E07`, `E1015`).
- Special episodes are in season `00`.
- A TMDB Episode spread over two files keeps the same `S<SS>E<EE>` in both, each file carrying the title of its part.
- **Preferred language**: `audio_language` and `subtitle_language` of `[show]`. Between two files of the same Episode, the one in the Preferred language wins.

## Check

The online check reports as `title` a name no TMDB Work carries, an original title instead of the Localized title, an Episode missing from the TMDB list or whose title differs. Without a TMDB key, the script says so: ask for it as in [workflow.md](workflow.md#config).

### Inventory

Each direct subfolder is a candidate Show. A subfolder that only holds Show subfolders (`The Boys/The Boys`, `The Boys/Gen V`) is undone: each Show becomes a candidate, moved into its own folder. Each video placed directly in the target is a candidate Episode, attached to the Show of its name. A subfolder that directly mixes several Shows is a question: separate folders, or Set aside.

### Identification

Infer a title from the folder or file name, then search it on TMDB (`search/tv`, as in [tmdb.md](tmdb.md)). Accept the match without asking when the first result has exactly this title and nothing else makes it ambiguous. The TMDB identifier, added to the final name, tells homonyms apart. Also determine its Localized title, or its absence, fixed as in [videos.md](videos.md#titles).

A file filed with a Show but that TMDB classifies as a Movie (special, TV movie, movie of the show) is Set aside, with the reason "Movie, to move to the Movie Root". A candidate that TMDB classifies as an Anime is Set aside, with the reason "Anime, to move to the Anime Root".

### Matching Episodes

Get the TMDB list of the Episodes of every season, season 0 included. Match each file to its Episode from the number found in its name (`S01E03`, `1x03`, `E03`, `- 03 -`, `Season 1 - Episode (3)`, absolute number). An absolute number is converted as in [tmdb.md](tmdb.md#absolute-numbering). A file covering two Episodes takes the two-Episode format.

When the name also carries a title, compare it with the TMDB titles of the season and of season 0:

- a title that clearly points to another Episode (two Episodes swapped, a special filed in a season) matches the file by its title,
- a title that matches the next season (a season 5 named season 4) fixes the season,
- a title that is only translated differently changes nothing: the TMDB title wins.

Cases with their default answer:

- **TMDB Episode spread over two files** (a finale cut in two): both files keep the same number, each with the title of its part (`Exodus (2)`, `Exodus (3)`),
- **file with two numbers that TMDB counts as one Episode**: it takes that single number,
- **two files for the same Episode**: compare their size and audio language with `python <scripts>/languages.py <file> ...`, then apply [videos.md](videos.md#duplicates).

### Questions

- each ambiguous Show, with the 3 best results (title, year, one-line synopsis), the user answering with a number or a TMDB identifier,
- each obviously wrong Localized title, Show or Episode, with the title offered by default. A missing Localized title takes its fallback without a question,
- doubtful matches: no number found, two files for the same Episode, number outside the list,
- subfolders that mix several Shows.

In the summary, also report the absolute number conversions, for example `1015 → S21E1015`.

## Missing

Missing items come from TMDB: Episodes already aired that are absent from the folder, season 0 included.

Follow-ups are not known to TMDB. They come from a cache of web searches, valid for a month. `to_search` lists each Show absent from the cache or stale: search the web for all its spin-off Shows, sequels or prequels already released that TMDB counts as other Shows (Gen V for The Boys), present in the Root or not, then save them with the page visited, even when there is none:

```
python <scripts>/storage.py spin-offs "<Show>" <url> "<spin-off Show>" ...
```

The name of the Show is its title without identifier, the name of a spin-off Show is its Localized title. `wanted.py` only keeps as Follow-ups those absent from the Root. Once the whole list is saved, run `wanted.py search` again.

The name of a Work to ignore is the title of the Show without its identifier.
