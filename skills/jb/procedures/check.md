# Check

Checks the target of the Type against the convention and writes its Corrections, which `/jb-<type>-rename` will apply. Nothing changes on disk, except what the Preparation section of the Type allows. Missing items belong to `/jb-<type>-find-missing`.

Follow [workflow.md](../workflow.md) for the target, the config, the lock, resuming and questions. Read [common.md](../common.md), the file of the Type's family ([videos.md](../videos.md) or [readings.md](../readings.md), none for Music) and `<type>.md`, with the data files it points to.

## 1. Preparation

If `<type>.md` has a Preparation section, follow it.

## 2. Check

```
python <scripts>/scan.py <type> <target> --online --draft
```

On a large target, run it in the background: it writes its progress as it goes, one line per Work checked online (`12/75 Jujutsu Kaisen`), which you give the user if they ask where it stands. The report only comes at the end.

The script lists the Deviations by Work, with their kind:

- `name`, `location`, `file`, `metadata`: the form, without network calls,
- `file`: also a Work of another Type, to handle by hand,
- `title`: what the online check finds wrong, according to `<type>.md`.

Then the number of sidecar files to delete, the To convert files and the Fixed extensions. Online checks only cover Works without a name or location Deviation.

It writes the check progress, with `step` set to `check`, `works` empty and the Corrections draft under `corrections`: `folder`, `genre`, `type`, `files`, `deviations`, `to_convert`, `fixed_extensions`, and empty lists `operations`, `set_aside`, `responses`.

Show the report as is, then sort the Works:

- **to rename**: at least one name, location or title Deviation,
- **to clean**: only metadata Deviations, which rename handles without an operation,
- **to handle by hand**: a `file` Deviation.

Set `step` to `identification`. If no Work is to rename, go to step 4 to save Corrections without operations, which rename uses to clean. If no Work is to clean either, give up the progress as in [workflow.md](../workflow.md#resuming) and go to step 5.

## 3. Identification

In batches of at most 10 Works to rename, follow the Check section of `<type>.md`: inventory, identification, matching of files. For each Work processed, add to `works` in the progress:

```json
"Jujutsu Kaisen": {
 "operations": [{"from": "[SubsPlease] Jujutsu Kaisen - 01 (1080p).mkv", "to": "Jujutsu Kaisen [tmdbid-95479]/Jujutsu Kaisen - S01E01 - TMDB title.mkv"}],
 "set_aside": [{"from": "Jujutsu Kaisen - 01 (1).mkv", "reason": "duplicate of Jujutsu Kaisen - S01E01 - TMDB title.mkv"}],
 "questions": ["Q1: Jujutsu Kaisen from 2020 (TMDB 95479) or Jujutsu Kaisen 0 (TMDB 810693)?"],
 "responses": []
}
```

Paths are relative to the target. `operations` only lists files whose path changes, extension kept except for a Fixed extension. `set_aside` lists what leaves the library, with its reason: duplicate, interrupted download, Work of another Type, unknown file. A Work without questions is ready.

Then ask the questions of the batch as in [workflow.md](../workflow.md#questions), with the cases `<type>.md` lists. Save each answer in the Work's `responses` and fix its `operations` accordingly, before the next batch.

The user can keep a file as is despite its Deviation ("leave it like that"): it becomes an Accepted deviation, with its path relative to the target, without an operation. `restore` makes it reported again.

```
python <scripts>/storage.py accept <type> "<path>" ...
python <scripts>/storage.py restore <type> "<path>" ...
```

Done when every Work to rename has its operations and no unanswered question.

## 4. Corrections

Set `step` to `corrections`. Gather into `corrections` the `operations`, `set_aside` and `responses` of every Work, without touching the other fields. Then save:

```
python <scripts>/corrections.py <type> <target>
```

The script refuses a source not found, a duplicate target, a target that already exists or lies outside the target folder, a Set aside without a reason, an extension changed without being a Fixed extension. Fix the Work concerned in the progress and run again until it accepts. It writes the Corrections and deletes the progress.

## 5. Summary

Show, grouped by Work, without applying anything:

- the operations `old name → new name`,
- the fixed titles and what `<type>.md` asks to report,
- the To convert files, the Fixed extensions and the Set aside files, with their reason.

Release the lock. Finish with the next command: `/jb-<type>-rename <target>`.
