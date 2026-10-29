---
name: jb-anime-mal-download
description: Downloads the Animes of a MyAnimeList list into a folder the user chooses, then checks and renames them there, outside the Root and the Wanted list.
disable-model-invocation: true
argument-hint: "<MAL list URL>"
---

# jb anime mal download

List: `$ARGUMENTS`, a URL such as `https://myanimelist.net/animelist/<user>?status=6`, optional.

Follow [workflow.md](../jb/workflow.md) with `<type>` = `anime`, `<action>` = `mal-download` and `<target>` = `mal`, and the rules of [anime.md](../jb/anime.md). The MAL Download section of [anime.md](../jb/anime.md#mal-download) says what differs from `/jb-anime-download`.

## 1. Parameters

Check the progress as in [workflow.md](../jb/workflow.md#resuming). When resuming, keep the list and the folder of the run and go to the saved step. Otherwise ask the user, in a single message and without defaults, for the URL of the MAL list when `$ARGUMENTS` is empty and for the destination folder, then:

```
python <scripts>/mal_list.py folder "<folder>"
```

Then take the lock on `mal`.

## 2. Search

```
python <scripts>/mal_list.py search "<URL>"
```

Run it in the background, as a long run. The script only reads the status of the URL and lists the other parameters it ignores: pass them on. It writes the progress with `step` set to `review`, as `/jb-anime-download` does, without `grabbed`, with `skipped` and `airing`.

Then review and approve as in the Download section of [anime.md](../jb/anime.md#download), removing the declined proposals from the progress. Not found Episodes of an Anime still airing may simply not be aired yet.

## 3. Grab

```
python <scripts>/mal_list.py grab
```

Nothing is written to the Grabbed items of the Type. `step` becomes `downloading`.

## 4. Wait

```
python <scripts>/mal_list.py wait
```

Run it in the background and give its progress line every 5 minutes, as in [workflow.md](../jb/workflow.md#long-runs). A torrent counts as done once qBittorrent has removed it. At the end `step` becomes `check`.

## 5. Check and rename

Release the lock, then follow [check.md](../jb/procedures/check.md) and [rename.md](../jb/procedures/rename.md) with `<target>` = `mal`, skipping their End: do not report the To convert files. Then give up the progress as in [workflow.md](../jb/workflow.md#resuming), release the lock and give the destination folder.
