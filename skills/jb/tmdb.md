# TMDB

API v3, with the `tmdb.key` key of the config. Always in the title language of the Type, see [videos.md](videos.md#languages).

Query it with `scripts/tmdb.py`, which adds the key and prints the JSON in UTF-8. Pass the title language, English otherwise:

```
python <scripts>/tmdb.py search/tv query="Breaking Bad" language=<title language>
```

For many calls, import `tmdb.get(path, **params)` from a Python script, after `languages.use(<type>)`. `scripts/tmdb_checks.py` gathers the TMDB checks of `scan.py --online`: matching a name with a Work, Localized title, Collections, Episodes, missing Episodes and Movies.

| Need | Path | Useful fields |
| --- | --- | --- |
| Search a show or an anime | `search/tv?query=<title>` | `id`, `name`, `original_name`, `first_air_date`, `overview` |
| Search a movie | `search/movie?query=<title>` | `id`, `title`, `original_title`, `release_date`, `overview` |
| Movie by identifier | `movie/<id>` | `title`, `release_date`, `belongs_to_collection` |
| Movies of a Collection | `collection/<id>` | `parts[].id`, `parts[].title`, `parts[].release_date` |
| Seasons of a show | `tv/<id>` | `seasons[].season_number`, `seasons[].episode_count` |
| Episodes of a season | `tv/<id>/season/<n>` | `episodes[].episode_number`, `episodes[].name` |

## Missing Localized title

A missing Localized title is never translated: the English TMDB title (`language=en`) replaces it as is, otherwise the original title. `tmdb_checks.tmdb_episodes`, used by `scan.py` and `anime.py`, applies this fallback to Episodes.

TMDB returns a fallback title when the translation is missing. The Localized title is considered missing when:

- the field is empty,
- or it is `<Episode> <n>` in any language (`Episode 3`, `Épisode 3`),
- or, for a Work, it is identical to the original title while the original language (`original_language`) is not the title language and a web search finds no other title in that language.

## Absolute numbering

To convert an absolute number `N`, add up the `episode_count` of the seasons in order, starting at season 1 (season 0 is left out). The Episode is the one where the sum reaches `N`.
