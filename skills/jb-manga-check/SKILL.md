---
name: jb-manga-check
description: Checks the Incoming folder or the Root of the Mangas against the convention, asks the questions and writes the Corrections that /jb-manga-rename will apply. Changes nothing else on disk.
disable-model-invocation: true
argument-hint: "[incoming|root]"
---

# jb manga check

Target: `$ARGUMENTS`, `incoming` when empty.

Follow [check.md](../jb/procedures/check.md) with `<type>` = `manga` and `<target>` = the target, and the rules of [manga.md](../jb/manga.md).
