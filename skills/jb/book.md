# Books

Convention and check of the Book Root, on top of [common.md](common.md) and [readings.md](readings.md).

## Tree

```text
<root>/
├── The Lord of the Rings/
│   ├── The Fellowship of the Ring [gbid-AAAAAAAAAAAA].epub
│   └── The Two Towers [gbid-BBBBBBBBBBBB].epub
└── The Stranger [gbid-CCCCCCCCCCCC].epub
```

| Item | Format |
| --- | --- |
| Book outside a Series | `<Title> [gbid-<id>].<ext>`, at the root |
| Book of a Series | `<Title> [gbid-<id>].<ext>`, in the `<Series>` folder |

- `gbid` is the Google Books identifier of the Book. An ISBN changes from one edition to another, the Google Books identifier points to the edition of the file. Jellyfin does not read it in the name: rename also writes it in the OPF of an `.epub`, with the ISBN, as in [readings.md](readings.md#sidecar-files-and-metadata).
- A Series follows the rules of [Collections](movie.md#collections): name without suffix, subtitle alone when every Book repeats the name of the Series, no folder for a Series of a single Book. The split is the one of the edition of the files: a Book published in two volumes in its language gives two Books of the Series, each with its identifier.

## Check

There is no online check for Books: the script only checks the form and the metadata.

### Inventory

Each direct subfolder is a candidate Series. Each reading placed at the target is a candidate Book. Done when each reading concerned is attached to a candidate Book or Set aside with its reason.

### Identification

On Google Books (optional key `google_books.key` in the config, without it the API soon refuses repeated calls):

```
python <scripts>/books.py search "The Stranger Camus" --language en
python <scripts>/books.py volume CCCCCCCCCCCC
```

Keep the edition in the language of the file. The Series of a Book and its name come from Google Books when it gives them, otherwise from a web search. Done when each Book has a `gbid` and its Series, or a pending question.

### Questions

- each ambiguous Book, with the 3 best Google Books results (title, author, date, language), the user answering with a number or an identifier,
- each Series, with its Books in release order,
- two files for the same Book.

## Missing

`wanted.py` computes the Missing items of the Series from the Series cache of `data/cache/`, valid for a month, and lists under "To look up on the web" the Series absent or stale. For each one, search the web for the Books of the Series already released, in order, then save them with the source:

```
python <scripts>/storage.py series "<Series>" <url> "<Book 1>" "<Book 2>" ...
```

Then run `wanted.py search` again to get the Missing items.

The Follow-ups of a Book outside a Series come from the same one-month cache as the spin-off Shows of [show.md](show.md#missing): for each `Follow-up of the Book` line of `to_search`, search the web for its follow-ups already released, then save them, even when there is none:

```
python <scripts>/storage.py spin-offs "<Book>" <url> "<Follow-up>" ...
```
