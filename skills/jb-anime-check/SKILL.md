---
name: jb-anime-check
description: Checks the Incoming folder or the Root of the Animes against the convention, asks the questions and writes the Corrections that /jb-anime-rename will apply. Changes nothing else on disk.
disable-model-invocation: true
argument-hint: "[incoming|root]"
---

# jb anime check

Target: `$ARGUMENTS`, `incoming` when empty.

Follow [check.md](../jb/procedures/check.md) with `<type>` = `anime` and `<target>` = the target, and the rules of [anime.md](../jb/anime.md).
