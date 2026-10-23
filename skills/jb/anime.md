# Animes

Convention of the Anime Root, on top of [common.md](common.md) and [videos.md](videos.md). An Anime is a Show that TMDB classifies as Animation with Japanese as original language: a donghua or a Korean animation is a Show. It follows the tree and names of [show.md](show.md), but its split comes from MyAnimeList, not TMDB (see [mal.md](mal.md)):

- **Seasons**: one season per MAL entry of the main type of the Anime (TV, or ONA for an Anime streamed online), in release order. The parts of a same season (`Part 2`, `2nd Cour`, `Zenpen`, `Kouhen`) stay in that season: `Shingeki no Kyojin Season 3` and `Season 3 Part 2` form season 03.
- **Season 00**: the MAL Movies, OVAs, ONAs and specials, sequels or side stories of the Anime, are Episodes of season 00 in the folder of the Anime. They are numbered in the release order of all these MAL entries, including those absent from the folder, an entry of several episodes taking as many numbers. A Movie in several files is an Episode spread over several files. The Movies of an Anime therefore never go into the Movie Root.
- **Titles**: always the TMDB Localized title. The Episodes of the seasons take the TMDB Episodes outside season 0 in order. A Movie takes the Localized title of its TMDB Movie. A special takes the one of the TMDB season 0 Episode aired on the same date, otherwise it is asked to the user with the MAL title by default.
- **Without a MAL Client ID**: the split falls back on the TMDB one, and Follow-ups are searched on the web.
- **Preferred language**: `audio_language` and `subtitle_language` of `[anime]`, usually the original audio with subtitles. Between two files of the same Episode, the one in the Preferred language wins.

## Preparation

`/jb-anime-download` puts each Release in a range folder (`S04E25`, `S03`, `S02E01 to S02E12`) under the folder of its Anime. Move the files out of it:

```
python <scripts>/unfold.py
```

Each file goes up into the folder of its Anime, then the emptied folders are deleted. A range folder still used by a qBittorrent torrent is left as is, as is a file whose name is already taken: the script lists them, pass them on. For the Root, nothing to do.

## Check

The online check reports as `title` a name no TMDB Work carries, an original title instead of the Localized title, an Episode missing from the `anime.py` list or whose title differs. Without a TMDB key, the script says so: ask for it as in [workflow.md](workflow.md#config).

### Inventory

Each direct subfolder is a candidate Anime. A subfolder that only holds Anime subfolders is undone: each Anime becomes a candidate, moved into its own folder. Each video placed directly in the target is a candidate Episode, attached to the Anime of its name. A subfolder that directly mixes several Works is a question: separate folders, or Set aside.

### Identification

Infer a title from the folder or file name, then search it on TMDB (`search/tv`, as in [tmdb.md](tmdb.md)). Accept the match without asking when the first result has exactly this title and nothing else makes it ambiguous. The TMDB identifier, added to the final name, tells homonyms apart. Also determine its Localized title, or its absence, fixed as in [videos.md](videos.md#titles).

A file filed with an Anime that TMDB classifies as a Movie stays in its folder as a season 00 Episode. A candidate that TMDB does not classify as an Anime is Set aside, with the reason "Show, to move to the Show Root".

### Matching Episodes

Take the `anime.py` list, which follows MAL (see [mal.md](mal.md)). Match each file to its Episode from the number found in its name (`S01E03`, `1x03`, `E03`, `- 03 -`, `Season 1 - Episode (3)`, absolute number). An absolute number is converted as in [tmdb.md](tmdb.md#absolute-numbering). A file covering two Episodes takes the two-Episode format.

When the name also carries a title, compare it with the TMDB titles of the season and of season 0:

- a title that clearly points to another Episode (two Episodes swapped, a special filed in a season) matches the file by its title,
- a title that matches the next season (a season 5 named season 4) fixes the season,
- a title that is only translated differently changes nothing: the TMDB title wins.

Cases with their default answer:

- **TMDB Episode spread over two files**: both files keep the same number, each with the title of its part,
- **file with two numbers that TMDB counts as one Episode**: it takes that single number,
- **two files for the same Episode**: compare their size and audio language with `python <scripts>/languages.py <file> ...`. An identical copy, a version outside the Preferred language when one in it exists, or an interrupted download (`.stopped`, a few MB) are Set aside.

### Questions

- each ambiguous Anime, with the 3 best results (title, year, one-line synopsis), the user answering with a number or a TMDB identifier,
- each obviously wrong Localized title, Anime or Episode, with the title offered by default. A missing Localized title takes its fallback without a question,
- each special without a TMDB Localized title, with the MAL title by default, as in [mal.md](mal.md#to-check),
- doubtful matches: no number found, two files for the same Episode, number outside the list,
- subfolders that mix several Works.

In the summary, also report the absolute number conversions, for example `1015 → S21E1015`.

## Missing

Missing items come from the `anime.py` list: Episodes already aired that are absent from the folder, season 00 included. Follow-ups come from MAL: spin-offs, alternative settings and remakes already aired, absent from the Root. An Anime is never linked to a Manga.

Without a MAL Client ID, `to_search` lists the Animes whose Follow-ups could not be followed: search and save their spin-offs, alternative settings and remakes already released like the spin-off Shows of [show.md](show.md#missing).

The name of a Work to ignore is the title of the Anime without its identifier.

## Download

The source is Prowlarr, which queries its indexers (Nyaa.si and its Trusted instance, see the README), and the qBittorrent client. Releases arrive in the Anime Incoming folder, under `<Anime>/<range>`.

```
python <scripts>/releases.py search
```

The script reads the Wanted list, without the Ignored items, and skips the Grabbed ones. For each season, it searches with the MAL titles of its entries and only keeps the Releases:

- with subtitles in `subtitle_language`, recognised by the keywords of that language (`VOSTFR`, `SUBFRENCH` or listed `FRE` subtitles for `fr`), never a MULTi or MultiSub without them. `release_keywords` in `[anime]` replaces these keywords, and an empty `subtitle_language` drops the filter,
- in 1080p, or in 720p otherwise,
- with at least one seeder,
- that only hold missing Episodes: a season pack only when the whole season is missing.

It prefers a complete season pack, then the resolution, the number of Episodes covered, a Trusted Release and the number of seeders. It writes the progress with `step` set to `review` and, under `releases`, `proposals` (each with `media`, `group`, `elements`, `release`, `path`), `not_found`, `out_of_scope` and `grabbed`.

**Review**: Release numbering does not always follow the MAL split. For each proposal, check that the Release title really points to the season and Episodes of `group`. Remove a doubtful proposal from the progress and add its `elements` to `not_found`. Set `step` to `approval`.

**Approval**: one line per Release with its size, its seeders and the Trusted mark. By default, every proposal.

**Grab**:

```
python <scripts>/releases.py grab
```

Each Release goes into the qBittorrent category of the config, which removes it as soon as the download is done, and becomes Grabbed. The script deletes the progress.
