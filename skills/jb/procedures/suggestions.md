# Suggestions

Offers Tracks absent from the Music Root, then adds those the user accepts to the Wanted list, which `/jb-music-download` will download. Those declined become Ignored and are never offered again. Nothing changes on disk.

`<source>` is `albums`, `artists` or `new`, depending on the skill. Follow [workflow.md](../workflow.md) for the config, the lock on `root`, resuming and questions, with the action of the skill. Read the Suggestions section of [music.md](../music.md).

## 1. Search

```
python <scripts>/suggestions.py search <source> [--count 50] [--since "<Artist>" | "<Artist> - <Title>"]
```

Run it in the background: it writes one progress line per Album, Artist or seed, and saves each Suggestion in the progress as soon as it is found. Run again, it resumes where it stopped. It leaves out what is in the Root, in the Incoming folder, in the Wanted list, among the Grabbed or the Ignored items. `--count` and `--since` only apply to `new`.

At the end, it shows the numbered Suggestions, by Artist, each with its reason.

## 2. Questions

Show the Suggestions in batches, with the default answer: accepted. The user answers by numbers, by Artist or all at once ("all", "none but 3 and 7"). In the progress, set `"accepted": true` or `false` on each Suggestion decided, as soon as the batch is answered. To see where things stand:

```
python <scripts>/suggestions.py show <source>
```

## 3. Wanted list

```
python <scripts>/suggestions.py save <source>
```

The script adds the accepted ones to the Wanted list, with their origin, ignores the declined ones and deletes the progress. A Suggestion left unanswered is forgotten: it will come back next time. Release the lock. Finish with the next command: `/jb-music-download`.
