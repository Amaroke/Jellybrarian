---
name: jb-show-check
description: Checks the Incoming folder or the Root of the Shows against the convention, asks the questions and writes the Corrections that /jb-show-rename will apply. Changes nothing else on disk.
disable-model-invocation: true
argument-hint: "[incoming|root]"
---

# jb show check

Target: `$ARGUMENTS`, `incoming` when empty.

Follow [check.md](../jb/procedures/check.md) with `<type>` = `show` and `<target>` = the target, and the rules of [show.md](../jb/show.md).
