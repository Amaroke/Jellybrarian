# Music filed by Artist, the Album in the tags

A Track is filed as `<Artist> [mbid-<uuid>]/<Title> [mbid-<uuid>].flac`, without an Album folder. The tags carry the title, the artists, the album artist, the album, the track number, the date, the artwork and the MusicBrainz identifiers, and nothing else.

This is the opposite of videos, which carry no tag. Jellyfin builds its tracks from the embedded tags only: it has no online source for a track, and MusicBrainz only serves it for artist and album listings. The recording MBID in the name allows comparing the disk with Spotify without network, and it does not change when the Album kept changes.
