# Prowlarr and qBittorrent without Sonarr or Radarr

The Missing items and Follow-ups of Animes are downloaded by `/jb-anime-download`, which queries Prowlarr and sends the approved Releases to qBittorrent. Sonarr and Radarr are not used: they rename and file according to their own convention, competing with `check` and `move`, and would recompute the missing Episodes that `find-missing` already computes from the MAL split. The price is rewriting the choice of Releases and the tracking of Grabbed items that the *arr stack provides.
