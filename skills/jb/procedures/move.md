# Move

Moves into the Root of the Type the compliant Works of its Incoming folder, after `/jb-<type>-check` and `/jb-<type>-rename`, merging with the Works already there. A non compliant Work or a Work of another Type stays in the Incoming folder.

Follow [workflow.md](../workflow.md) for the config and the lock, taken on `incoming root`. An interrupted move is started again as is: what is already moved is no longer in the Incoming folder.

## 1. List

```
python <scripts>/mover.py <type>
```

The script checks the form of the Incoming folder, without network, and writes nothing. It ignores names starting with a dot and those of `ignored.names` in the config. It refuses a Root and an Incoming folder nested in each other, or a Root of another family. It refuses everything as soon as a file already exists at its place in the Root: show the collisions and stop. Otherwise it lists:

- by Work, the files moved, `merge` when the folder already exists in the Root, `new` otherwise,
- the loose files, moved into the folder of their Work when the Root has exactly one that matches, left otherwise,
- the Works and files left because they are non compliant or of another Type, with their first Deviation,
- what `<type>.md` asks to report.

Show this list in full.

## 2. Approval

Wait for approval.

## 3. Move

```
python <scripts>/mover.py <type> --apply
```

The script moves each file with its companions, then deletes the emptied subfolders of the Incoming folder. A locked file does not stop the others: ask the user to release it, then run step 3 again.

Report the folders kept and the Works left. Start the Jellyfin scan as in [workflow.md](../workflow.md#jellyfin). Release the lock. Finish with the next command: `/jb-<type>-find-missing`.
