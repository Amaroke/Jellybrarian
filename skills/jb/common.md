# Common rules

Naming rules shared by every Type. How to run the skills is in [workflow.md](workflow.md). Each Type has its own rules in `<type>.md`, and videos and readings share theirs in [videos.md](videos.md) and [readings.md](readings.md).

## Roots

Each Type has a Root and an Incoming folder, set in the config. A Root only holds Works of its Type: a Movie in the Show Root, an Anime in the Show Root, a Book in the Manga Root are `file` Deviations, to handle by hand. `scan.py` reports them without checking the rest of their name.

Names starting with a dot and those of `ignored.names` in the config are ignored everywhere.

## Characters and spaces

- Replacements: ` : ` and `:` become ` - `, `/` and `\` become ` - `, `?`, `*`, `"`, `<`, `>`, `|` are removed. Accents are kept.
- No double space, no space or dot at the end of a name, including a Work title: Windows strips the trailing dot of a folder name, so `Agents of S.H.I.E.L.D.` becomes `Agents of S.H.I.E.L.D` everywhere, folder and files.
- Never a year, neither in a file name nor in a folder name. Two Works that would get the same name in the same place are asked to the user.
