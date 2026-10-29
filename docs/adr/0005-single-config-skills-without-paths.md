# Single config outside git, skills without paths

The skills take no path: each Type has a single Root and a single Incoming folder, read from `config.toml`, ignored by git, with the keys and URLs of the services. `check` and `rename` pick between the two with the word `incoming` or `root`, `find-missing` and `download` work on the Root, `move` goes from the Incoming folder to the Root. A missing value is asked to the user and written to the config, except a secret, which they paste themselves.

One exception: `/jb-anime-mal-download` asks for its destination folder at each run, kept in the data as the Anime target `mal` until the next one.

The repository thus holds no path nor any data of the user, and `config.toml` is the only source, without environment variables nor files in the home folder. The price is no longer being able to check an arbitrary folder, nor having several Roots for a Type.
