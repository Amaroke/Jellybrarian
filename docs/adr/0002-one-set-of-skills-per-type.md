# One set of skills per Type

Each Type has its set of `/jb-<type>-<action>` skills, with the types `anime`, `show`, `movie`, `manga`, `book` and `music`. Each Type has its Root and its Incoming folder, and a file of another Type in them is a Deviation to handle by hand. The procedures (`check`, `rename`, `move`, `find-missing`, `download`) are written once in `skills/jb/procedures/`, and each `SKILL.md` applies them with the rules of `<type>.md`. The scripts stay shared in `skills/jb/scripts/`.

Music has its own skills (`migrate-spotify` and the Suggestions): its source is Spotify and MusicBrainz, not the disk. A skill per Type only reads the rules of its Type. The price is about thirty skills, and `download` is still to write for Shows, Movies, Mangas and Books.
