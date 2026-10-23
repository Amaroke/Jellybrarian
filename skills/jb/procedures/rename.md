# Rename

Applies to the target of the Type the Corrections prepared by `/jb-<type>-check`, as they are. Every decision belongs to the check: if something is missing or has changed, send the user back to it.

Follow [workflow.md](../workflow.md) for the target, the config and the lock. The Corrections themselves act as progress: the script removes from them what is applied, and an interrupted run is started again as is.

## 1. List

```
python <scripts>/apply_plan.py <type> <target>
```

The script reads the Corrections and writes nothing. It refuses everything as soon as a source has disappeared or a target already exists: tell the user to run `/jb-<type>-check <target>` again and stop. Otherwise it lists:

- the files that appeared since the check, which will not be touched,
- the renames already done by an interrupted run,
- the renames by Work, and the companion files that follow their file,
- the number of sidecar files to delete,
- the Set aside files, with their reason and destination folder,
- the number of files whose metadata will be cleaned,
- the To convert files, under their final name, and the Fixed extensions.

Show this list in full.

## 2. Approval

Wait for approval. The user can exclude Works ("everything but Jujutsu Kaisen"): run step 1 again with `--exclude "<Work>"` to show them the reduced list. A Work is named by its folder.

## 3. Apply

```
python <scripts>/apply_plan.py <type> <target> --apply [--exclude "<Work>" ...]
```

The script cleans the metadata, deletes the sidecar files, renames each file with its companions, moves the Set aside files, deletes the emptied folders, then removes from the Corrections what was applied. It deletes the Corrections when nothing is left in them and no Work was excluded. It needs mutagen: if it is missing, install it with `python -m pip install --user mutagen`.

Report the failures and the folders kept because they still hold files. A locked file (open in Jellyfin or a player) does not stop the others and stays in the Corrections: ask the user to release it, then run step 3 again.

## 4. Review

```
python <scripts>/scan.py <type> <target>
```

Show the remaining Deviations. For the Root, start the Jellyfin scan as in [workflow.md](../workflow.md#jellyfin). Release the lock. Finish with the next command:

- for the Incoming folder: `/jb-<type>-move`,
- for the Root: `/jb-<type>-find-missing`.
