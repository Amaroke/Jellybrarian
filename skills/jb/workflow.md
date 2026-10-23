# Common workflow

Rules shared by every `/jb-<type>-<action>` skill. `<jb>` is the folder `<folder of this skill>/../jb`, `<scripts>` is `<jb>/scripts`, `<type>` is the Type of the skill.

## Language

Talk to the user in the language of `conversation_language` in the config, English when it is empty:

```
python <scripts>/config.py read general.conversation_language
```

Questions, summaries and reports are in that language. Script output, file names and data stay as they are.

## Target

`check` and `rename` take an optional argument, `incoming` (default) or `root`: the Incoming folder or the Root of the Type, read from the config. `move` always goes from the Incoming folder to the Root, `find-missing` and `download` work on the Root. No skill accepts a path.

## Config

Scripts read `config.toml` at the root of the repository. A script that exits with code 3 names the missing key:

- a path, a URL or a name: ask the user for the value, write it, then run the script again,
- a secret (API key, Client ID, password): tell the user where to get it, from the comment in `config.example.toml`, and to paste it themselves into `config.toml`. Never ask for it in the conversation. Wait for their confirmation, then run again.

```
python <scripts>/config.py write <section>.<key> "<value>"
```

A script that exits with code 2 because a configured folder is not found: pass its message on and stop.

## Lock

At the start, take the lock of the Type on the target:

```
python <scripts>/storage.py lock <type> <action> <target> [<target> ...]
```

`move` locks `incoming root`. If the lock is refused (code 4), say which skill holds it and since when, and ask whether it is orphaned, for example after an interrupted session. Only on their confirmation, run again with `--force`. Release it at the end, and also when you stop before the end:

```
python <scripts>/storage.py unlock <type> <target> [<target> ...]
```

## Resuming

Every skill that asks questions or searches for a long time saves its progress in `data/<type>/in_progress/<action>-<target>.json`, as it goes. At startup, check whether one exists:

```
python <scripts>/storage.py in-progress <type> <action> <target>
```

If it exists, tell the user where they were (step, Works processed, questions answered) and ask whether to resume or start over. To start over:

```
python <scripts>/storage.py in-progress <type> <action> <target> --give-up
```

When resuming, check the disk again: a source that disappeared leaves the progress, a file that appeared is listed and left to the next `check`. Then resume at the saved step, without asking an answered question again.

In the progress, write `step` at each change of step, and what the procedure saves as it goes (a Work processed, an answer) as soon as it is done, never only at the end.

## Questions

Ask questions in batches of at most 10 Works, numbered, each with its default answer. Save the answers of a batch in the progress before moving to the next one.

## Long runs

A script run in the background (online check, search, identification) is followed by a monitor that reads its last progress line every 5 minutes. Give the user each of these points in one line (`Search: 40/97`), until the script ends or fails.

## Long lists

Beyond about a hundred lines, write the list to a file in the scratchpad, give its path and summarise by Work.

## Jellyfin

After a `rename` or a `move` that changed the Root:

```
python <scripts>/jellyfin.py scan
```

Without `jellyfin.url` in the config, the script says so: remind the user to start the library scan in Jellyfin.

## End

Release the lock and finish with the next command given by the procedure.
