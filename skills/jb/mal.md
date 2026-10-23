# MyAnimeList

Source of the split of Animes (seasons and season 00), as in [anime.md](anime.md). Titles stay those of TMDB.

Official API v2, with the Client ID `mal.client_id` of the config, which the user creates at https://myanimelist.net/apiconfig (App Type `other`, URL `http://localhost`). The public Jikan API is not used: it is often down or rate limited.

## Scripts

Search an entry:

```
python <scripts>/mal.py search "Jujutsu Kaisen"
```

Show the split of an Anime from any of its TV entries:

```
python <scripts>/mal.py structure 40748
```

Show the full list of Episodes of an Anime, numbered according to MAL and titled according to TMDB, with the Episodes not aired yet marked:

```
python <scripts>/anime.py <TMDB identifier> [MAL identifier]
```

Without a MAL identifier, `anime.py` takes the MAL TV or ONA entry that started the same year as the TMDB Show. Pass it explicitly when this match fails or is wrong. `scan.py --online` uses the same list to check Animes.

## Franchise

`mal.py` follows the `sequel` and `prequel` relations from the given entry, then adds the `side_story` of these entries. `summary`, `spin_off`, `alternative_version`, `alternative_setting`, `character` and `other` are ignored: a spin-off with its own TMDB listing is another Show, in its own folder at the root.

## To check

- A special without a TMDB Localized title shows up in `anime.py` as "no Localized title", with its MAL title. `scan.py` does not check its title. Ask the user, with the Localized title of the file by default, otherwise the MAL title.
- When TMDB counts an episode 0 in a season (DxD Hero), `anime.py` removes it from the seasons and attaches it to the MAL special with the same air date.
- A season entry still airing can have `num_episodes` at 0. It then takes the rest of the TMDB Episodes.
- Parts are merged on the MAL title. Check the result of `mal.py structure` when a season looks too long or too short.

## Mangas

Mangas are identified with the same API, without a split: a Manga is a MAL entry, filed as in [manga.md](manga.md).

```
python <scripts>/mal.py manga-search "Shingeki no Kyojin"
python <scripts>/mal.py manga 23390
```

`manga` also shows the relations of the entry, which `wanted.py` follows for `/jb-manga-find-missing`.
