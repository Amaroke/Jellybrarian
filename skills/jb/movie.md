# Movies

Convention of the Movie Root, on top of [common.md](common.md) and [videos.md](videos.md).

## Tree

Every Movie is filed one level deep at most, without exception:

```text
<root>/
├── Harry Potter/
│   ├── Harry Potter and the Philosopher's Stone [tmdbid-671].mp4
│   └── Harry Potter and the Chamber of Secrets [tmdbid-672].mp4
├── The Hobbit/
│   ├── An Unexpected Journey [tmdbid-49051].mp4
│   └── The Desolation of Smaug [tmdbid-57158].mp4
├── Hayao Miyazaki/
│   ├── Spirited Away [tmdbid-129].mp4
│   └── Princess Mononoke [tmdbid-128].mp4
├── Inception [tmdbid-27205].mp4
└── The Lion King [tmdbid-8587].mp4
```

| Item | Format |
| --- | --- |
| Movie outside a Collection | `<Title> [tmdbid-<id>].mp4`, at the Root |
| Movie of a Collection | `<Title> [tmdbid-<id>].mp4`, in the `<Collection>` folder |
| Collection folder | `<Collection name>` |

No order number before a Movie. Release order is given by the Jellyfin collections, sorted by release date.

## Collections

A Collection starts from the TMDB Collection of the Movie, then is settled as follows:

- **Name**: the TMDB name without its suffixes (`- Saga`, `Collection`) nor its details in parentheses. `Hercule Poirot (Kenneth Branagh) - Saga` becomes `Hercule Poirot`.
- **Name repeated by every Movie**: when every Movie of the Collection is called `<Name>` or starts with `<Name> - `, Jellyfin would take these Movies for versions of a single one. Each Movie then takes its subtitle alone (`The Hobbit/An Unexpected Journey [tmdbid-49051].mp4`), the identifier being enough for Jellyfin. A Movie called exactly `<Name>` keeps its name.
- **Shared universe**: the user can gather the Collections of a same universe into a single Collection, for example one folder for all the films of a studio, with the spin-off films of a saga. They decide it once, answering a question of the check.
- **User grouping**: an existing folder that gathers Movies by universe, author or theme (`Hayao Miyazaki`) stays a Collection.
- **The Root folders are the reference**: a Movie whose TMDB Collection, or a Movie of its universe, is already filed in a Root folder joins that folder. These groupings are written nowhere else.
- **Single Movie**: a Collection that would hold a single Movie has no folder, the Movie goes to the Root.
- **Movies of a Show**: the Movies that TMDB attaches to a Show (specials, TV movies, movie of the show) form the Collection `<Show> - Movies`, with the word Movies in the title language (`<Série> - Les Films` in French), so as not to take the name of the Show folder. The title of each Movie follows the pattern `<Show> - <Subtitle>` (`South Park - Post COVID`). The Movies of an Anime are an exception: they stay in the Anime Root, see [anime.md](anime.md).

## Duplicates

Between two files of the same Movie, the one in the Preferred language of `[movie]` wins, as in [videos.md](videos.md#duplicates).

## Check

The online check reports as `title` a name no TMDB Work carries, an original title instead of the Localized title, a Movie filed apart from the other Movies of its TMDB Collection. Without a TMDB key, the script says so: ask for it as in [workflow.md](workflow.md#config).

### Inventory

Each direct subfolder is a candidate Collection. Each video placed directly in the target is a candidate Movie. Identification also covers the Movies of the Collections touched by the Works to rename, since the name of a Collection folder depends on all its Movies.

### Identification

Infer a title from the file name, removing any order number, then search it on TMDB (`search/movie`, as in [tmdb.md](tmdb.md)). In a Collection, a file name can omit the name of the Collection (`The Hobbit/An Unexpected Journey`): then search `<Collection> <name>`. Accept the match without asking when the first result has exactly this title and nothing else makes it ambiguous. When the inferred title is generic (`Thor`, `Mad Max`) or the folder name places the Movie in a saga, check that the result kept is the right instalment. The TMDB identifier, added to the final name, tells homonyms apart. Also determine its Localized title, or its absence, fixed as in [videos.md](videos.md#titles), its TMDB Collection and its release date.

File it as in [Collections](#collections), looking first among the Root folders for the one that already holds a Movie of its Collection or universe. A Movie that TMDB attaches to a Show joins the Collection `<Show> - Movies`. A Movie attached to an Anime is Set aside, with the reason "Anime Movie, to file as a season 00 Episode in the Anime Root". A candidate that is an Episode is Set aside, with the reason "Episode, to move to the Show Root".

### Questions

- each ambiguous Movie, with the 3 best results (title, year, one-line synopsis), the user answering with a number or a TMDB identifier,
- each obviously wrong Localized title, with the title offered by default. A missing Localized title takes its fallback without a question,
- each new Collection, built as in [Collections](#collections) and offered once with its Movies, with the existing universe folder that could host it,
- two files for the same Movie.

In the summary, show each Collection in release order and the fixed titles (`Star Wars → Star Wars - Episode IV - A New Hope`).

## Missing

Missing items come from TMDB: the Movies already released of the TMDB Collections with a Movie in the Root. The name of a Work to ignore is the name of the Collection folder, or the name of the TMDB Collection for Movies at the Root.
