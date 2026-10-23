# Download

Searches Releases for the Missing items and Follow-ups of the Type's Wanted list, offers them, then grabs those the user approves. Downloads arrive in the Incoming folder of the Type and stay there until `/jb-<type>-move`. Nothing changes in the Root.

Follow [workflow.md](../workflow.md) for the config, the lock on `root`, resuming and questions. Read the Download section of `<type>.md`, which gives the source, the criteria and the commands.

Without a Wanted list, the script says so: tell the user to run `/jb-<type>-find-missing`, and stop.

A Grabbed item is not offered again while its Release is in the client or its files wait in the Incoming folder. The other Grabbed items are forgotten and can be offered again.

## Approval

Show the proposals by Work, one line per Release with what `<type>.md` asks to display, then the items not found, the Works out of scope and the pending Grabbed items. Ask which ones to grab, with the default answer of `<type>.md`. Remove the declined proposals from the progress before grabbing.

## End

Give the number of Releases grabbed and the Incoming folder. Release the lock. Finish with the command to run once the downloads are done: `/jb-<type>-check`.
