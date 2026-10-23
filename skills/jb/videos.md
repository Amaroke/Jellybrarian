# Videos

Rules shared by Movies, Shows and Animes, on top of [common.md](common.md). Each Type has its own in [movie.md](movie.md), [show.md](show.md) and [anime.md](anime.md). Checked by `scripts/scan.py`.

## Languages

Each video Type has three settings in its config section:

- `title_language`: the language of the Localized title, `en` by default,
- `audio_language`: the preferred audio, a language code or `original`,
- `subtitle_language`: the preferred subtitles, a language code or empty for none.

Read them with `python <scripts>/config.py read <type>.title_language`, and the same for the two others. Below, "the title language" and "the Preferred language" mean these values.

## Identifier

Each Show or Anime folder and each Movie carries its TMDB identifier, `[tmdbid-<id>]`. Jellyfin uses it to identify the Work without a name search, and it tells homonyms apart. Episodes do not carry one: they start with the bare `<Title>` of their Show. A Collection folder does not carry one.

## Titles

- Always the Localized title. A title is never translated: when the Localized title does not exist, the English TMDB title is used as is, otherwise the original title. An Episode without a title anywhere (TMDB in the title language, in English, in the original language, file name) is called `<Episode> <n>`, with the word for Episode in the title language (`Episode 3`, `Épisode 3`).
- For an Episode, the TMDB title wins over the one in the file name, even when the latter looks better.
- The TMDB title is the base, fixed when it is off:
  - **wrong case**: `The salvation` becomes `The Salvation`,
  - **truncated form or competing with a title in use**: `Usual Suspects` becomes `The Usual Suspects`, `Marvel's Daredevil` becomes `Daredevil`,
  - **title isolated in its Collection**: every Movie of a Collection follows the same pattern and case. `Star Wars` becomes `Star Wars - Episode IV - A New Hope` like the other episodes, `Guardians of the Galaxy Vol. 2` becomes `Guardians of the Galaxy - Vol. 2` like volume 3,
  - **obviously wrong title**: a title unrelated to the Movie is asked to the user, with the title of the file offered by default.

## Extensions

In the end, the library only holds `.mp4`, with a lowercase extension. The skills never convert nor remux a video: a video in another format is To convert, reported by `scan.py`, in the Corrections and at rename, then renamed and moved like the others. The user converts it themselves. A file that is neither a video, a subtitle nor a Jellyfin file is a Deviation, handled by hand.

## Subtitles

An external subtitle (`.srt`, `.ass`, `.ssa`, `.vtt`) carries the name of its video followed by its language and markers, `<name>.<language>[.forced].<ext>` (`Jujutsu Kaisen - S01E01 - Ryomen Sukuna.eng.ass`), which Jellyfin reads. It follows its video when renamed. A subtitle without a video is deleted by rename.

## Duplicates

Between two files of the same Episode or Movie, an identical copy and an interrupted download are Set aside. For two languages, the Preferred language of the Type wins, and the other version is Set aside. `python <scripts>/languages.py <file> ...` lists the audio and subtitle tracks of an `.mp4`. When no file has the preferred audio, the original audio is kept.

## Jellyfin

Jellyfin identifies each Work by the TMDB identifier of its name and keeps its metadata and images in its own database. No NFO nor image is kept next to the videos: `<name>.nfo`, `<name>-thumb.jpg`, `<name>-poster.jpg`…, where `<name>` is the name of the video without its extension, and `tvshow.nfo`, `poster.jpg`, `logo.svg`, `season<SS>-poster.jpg`… in a folder. Rename deletes them. Only the `<name>.trickplay` folders stay and follow their video when renamed.

## Metadata

An `.mp4` carries no tag (title, comment, encoder, artist, cover…): these are the properties that can be removed from Windows Properties → Details. They are removed in place, instantly. Chapters, track names and creation dates stay, since removing them would mean rewriting the whole file.
