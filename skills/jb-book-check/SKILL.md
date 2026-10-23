---
name: jb-book-check
description: Checks the Incoming folder or the Root of the Books against the convention, asks the questions and writes the Corrections that /jb-book-rename will apply. Changes nothing else on disk.
disable-model-invocation: true
argument-hint: "[incoming|root]"
---

# jb book check

Target: `$ARGUMENTS`, `incoming` when empty.

Follow [check.md](../jb/procedures/check.md) with `<type>` = `book` and `<target>` = the target, and the rules of [book.md](../jb/book.md).
