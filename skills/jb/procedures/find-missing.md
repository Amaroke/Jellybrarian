# Find missing

Searches for the Missing items and Follow-ups of the compliant Works of the Type's Root, asks which ones to ignore, then writes its Wanted list, which `/jb-<type>-download` reads when the Type has one. Nothing changes on disk. What is not released yet is never searched.

Follow [workflow.md](../workflow.md) for the config, the lock, resuming and questions. Read the Missing section of `<type>.md`.

## 1. Preparation

If the Missing section of `<type>.md` has a preparation, follow it.

## 2. Search through the APIs

```
python <scripts>/wanted.py search <type>
```

The script only handles compliant Works. It lists:

- the non compliant Works or Works of another Type, left aside: tell the user to run `/jb-<type>-check root` first,
- the pending Corrections, when `/jb-<type>-rename root` has not run yet,
- the Missing items and Follow-ups found through the APIs,
- the Ignored ones, apart,
- what is left to look up on the web, in `to_look_up` (Missing items) and `to_search` (Follow-ups).

It writes the progress, with `step` set to `lookup` and the draft under `wanted`: `folder`, `genre`, `type`, `missing`, `follow_ups` (each with `media`, `follow_up`, `detail`, `source`), `to_look_up`, `to_search`, plus what `<type>.md` describes.

## 3. Web search

For each line of `to_look_up` and `to_search`, search the web as `<type>.md` says. Save each result as soon as it is found, in the cache `<type>.md` points to when it has one, otherwise in the progress, then remove the line from its list in the progress. A Follow-up found goes into `follow_ups`, with the URL visited in `source`. `media` is the name of the Work without identifier, the same as for its other Follow-ups. `follow_up` is a name stable from one search to the next, the title without a date.

Done when `to_look_up` and `to_search` are empty. Set `step` to `questions`.

## 4. Questions

Show the Missing items and Follow-ups by Work, without the Ignored ones. Then ask, in batches, what to ignore from now on:

- a Work: none of its Missing items, present and future, is reported anymore. Its name is the key in `missing`,
- a Follow-up: only that one is no longer reported. Its name is `<media> : <follow_up>`,
- what `<type>.md` adds.

Apply the answers of each batch before the next. `keep`, with the same names, makes an Ignored item reported again.

```
python <scripts>/storage.py ignore <type> "<Work>" "<media> : <follow_up>" ...
```

## 5. Wanted list

```
python <scripts>/wanted.py save <type>
```

The script removes the Ignored items, writes the Wanted list of the Type and deletes the progress. Give the number of Missing items, Follow-ups and Ignored items removed. Release the lock.

Finish with the next command: `/jb-<type>-download` when the Type has one.
