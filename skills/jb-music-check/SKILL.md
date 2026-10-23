---
name: jb-music-check
description: Checks the Incoming folder or the Root of Music against the convention, asks the questions and writes the Corrections that /jb-music-rename will apply. Changes nothing else on disk.
disable-model-invocation: true
argument-hint: "[incoming|root]"
---

# jb music check

Target: `$ARGUMENTS`, `incoming` when empty.

Follow [check.md](../jb/procedures/check.md) with `<type>` = `music` and `<target>` = the target, and the rules of [music.md](../jb/music.md).
