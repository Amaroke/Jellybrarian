---
name: jb-movie-check
description: Checks the Incoming folder or the Root of the Movies against the convention, asks the questions and writes the Corrections that /jb-movie-rename will apply. Changes nothing else on disk.
disable-model-invocation: true
argument-hint: "[incoming|root]"
---

# jb movie check

Target: `$ARGUMENTS`, `incoming` when empty.

Follow [check.md](../jb/procedures/check.md) with `<type>` = `movie` and `<target>` = the target, and the rules of [movie.md](../jb/movie.md).
