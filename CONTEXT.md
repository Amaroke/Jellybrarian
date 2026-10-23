# Jellybrarian

Chained skills that name, file and complete a media library according to a single convention.

## Language

**Type**:
One of the six families of Works: Anime, Show, Movie, Manga, Book, Music. Each Type has its Root, its Incoming folder and its own set of `/jb-<type>-<action>` skills. A file of another Type in a Root is a Deviation to handle by hand.
_Avoid_: genre, category

**Root**:
The single folder where a Type's library lives, set by the user. Missing items and Follow-ups are only searched for in the Root.
_Avoid_: library, destination

**Work**:
One entry of the library: a Show, an Anime, a Movie, a Manga, a Book or an Artist.
_Avoid_: media, content, video

**Episode**:
A unit of a Show or an Anime, identified by its season and number in the official list.

**Collection**:
A group of at least two Movies filed in a shared folder, such as a saga or a shared universe.
_Avoid_: saga, franchise

**Manga**:
A drawn Work published in Volumes, identified on MyAnimeList. Manhwa, manhua and illustrated light novels are Mangas.
_Avoid_: comic, scan

**Volume**:
A unit of a Manga, identified by its number.
_Avoid_: tome

**Extra volume**:
A Volume filed with its Manga but outside its numbering: guide, artbook, anthology. It never counts as Missing. An official Volume 0 is not an Extra volume.
_Avoid_: special, side volume

**Book**:
A standalone written Work, possibly filed in a Series.
_Avoid_: novel, ebook

**Series**:
A group of at least two Books that form a sequence or a shared universe. It is the Books' equivalent of a Collection.
_Avoid_: saga, cycle

**Artist**:
The Work of Music: a folder that directly holds all its Tracks, identified on MusicBrainz. It is the album artist of the Track, or its first credited artist when the album is a various-artists release.
_Avoid_: band, performer

**Track**:
A unit of Music, identified by its MusicBrainz recording. A Track comes from a like or a playlist of the user on Spotify, or from an accepted Suggestion.
_Avoid_: song, title, piece

**Album**:
The MusicBrainz release a Track is attached to: the first one of type Album, never a compilation nor a single when the album exists. It exists only in tags, never as a folder.
_Avoid_: record, release

**Follow-up**:
A Work already released, linked to a Work of the library but absent from it: a spin-off Show, a sequel counted as another Work. Music has no Follow-ups, only Suggestions. A part of a Work or Collection that is present is Missing, not a Follow-up. Anything not yet released is never reported.
_Avoid_: sequel, recommendation

**Suggestion**:
A Track absent from the Music Root offered to the user: a track of a nearly complete Album, a popular Track of a well-represented Artist, or a Track close to those they have. Accepted, it becomes Missing. Declined, it becomes Ignored.
_Avoid_: recommendation, discovery

**Localized title**:
The official title of a video Work or Episode in the title language of its Type. It is always used instead of the original title. When it does not exist, the English title is used as is, otherwise the original title. A title is never translated. A Manga and a Book take the title in the language of their text. A Track and an Artist keep their original title, transliterated to Latin script when it is not.
_Avoid_: translated title, French title

**Preferred language**:
The audio and subtitle languages a video Type favours, set by the user. Between two files of the same Episode or Movie, the one in the Preferred language wins and the other is Set aside. When no Release or file in the Preferred language exists, the original audio is kept.
_Avoid_: dub, VOSTFR

**Deviation**:
A file whose name, location, metadata or title does not follow the convention. In Music, also a file that is not FLAC or has no embedded cover.
_Avoid_: error, anomaly

**Accepted deviation**:
A file the user keeps as is despite its Deviation, specific to a Type. It is never reported again, and its Work is treated as compliant. A Track in MP3 320, for lack of FLAC, is one.
_Avoid_: exception, ignored deviation

**Corrections**:
The list, specific to the Root or the Incoming folder of a Type, of the renames, items Set aside, metadata cleanups and Fixed extensions that make it compliant. Written by the check before any change, applied only after the user approves, then emptied of what was applied.
_Avoid_: summary, rename plan, preview

**Missing**:
An Episode already aired or a Movie already released that belongs to a Work or a Collection of the folder but is not in it. In Music, a Track of the Spotify snapshot, the frozen list of what remains to migrate from Spotify, absent from the Root. It is not a Deviation.
_Avoid_: gap, absent

**Wanted list**:
The list, specific to the Root of a Type, of its Missing items and Follow-ups, without the Ignored ones. Written by the search for Missing items, then read to start downloads.
_Avoid_: report, missing list

**Ignored**:
A Work or a Collection whose Missing items, present and future, the user no longer wants to see, or a specific Follow-up they no longer want to see, specific to a Type. The other Follow-ups of the same Work are still reported. In Music, also a specific Track.
_Avoid_: dismissed follow-up

**To convert**:
A video whose extension is not `.mp4`, or a reading in `.mobi` or `.azw`. It is reported to the user, who converts it themselves, and renamed and filed like the others. The skills never convert a video nor a book. A comic archive (`.cbr`, `.cb7`, `.zip`, `.rar`) is not To convert: the rename repacks it as `.cbz`, without touching the images. It is not a Deviation. Music has none: converting does not restore lost quality.

**Set aside**:
A file moved out of a Root or an Incoming folder because it has no place in the library (duplicate, interrupted download, unknown file), with its reason. It is moved to a single folder set by the user, outside the Roots, and is no longer reported.
_Avoid_: rejected, discarded

**Fixed extension**:
A reading whose extension does not match its content, such as an EPUB named `.cbz`. It is renamed with the extension of its content and reported to the user.

**Release**:
A torrent found on an indexer, or a file shared on Soulseek, candidate to fill a Missing item or a Follow-up.
_Avoid_: torrent, result

**Grabbed**:
A Missing item or a Follow-up whose Release was sent to the torrent client or to slskd, and which is not yet filed in the library. It is not offered again while its Release is in the client or its files wait in the Incoming folder.
_Avoid_: in progress, downloaded

**Incoming folder**:
The single folder outside the Root, specific to a Type and set by the user, where downloaded Releases arrive. Its Works are checked and renamed there, then filed into the Root. It is never deleted, only its emptied subfolders are.
_Avoid_: download folder, source
