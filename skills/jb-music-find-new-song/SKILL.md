---
name: jb-music-find-new-song
description: Suggests new Tracks close to those of the Music Root, from Last.fm, and adds those the user accepts to the Wanted list.
disable-model-invocation: true
argument-hint: "[<Artist> | <Artist> - <Title>]"
---

# jb music find-new-song

Optional argument: `$ARGUMENTS`, an Artist or `<Artist> - <Title>` to start from, otherwise Tracks drawn at random.

Follow [suggestions.md](../jb/procedures/suggestions.md) with `<source>` = `new` and the action `find-new-song`, passing the argument to `--since` when it is given.
