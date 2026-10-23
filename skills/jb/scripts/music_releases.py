import argparse
import re
import sys
from datetime import date, datetime

import config
import storage
import musicbrainz
import music
import slskd

TYPE = "music"
TOLERANCE = 3
BATCH = 100
FAILURES = storage.cache("soulseek_failures")
FEAT = re.compile(r"(?i)\s*[(\[](?:feat|ft|with)\b[^)\]]*[)\]]")


def file_name(path):
    return path.replace("\\", "/").rsplit("/", 1)[-1]


def incoming():
    return config.folder(TYPE, "incoming")


def arrived():
    return {f.name for f in incoming().rglob("*") if f.is_file() and ".incomplete" not in f.parts}


def active_grabbed():
    transfers = {(t["username"], t["filename"]): t.get("state", "") for t in slskd.downloads()}
    present_ones = arrived()
    kept_elements, active = [], []
    failures = storage.read_cache(FAILURES)
    for grab in storage.grabbed(TYPE):
        state = transfers.get((grab["username"], grab["filename"]))
        in_progress = state is not None and not state.startswith("Completed")
        if file_name(grab["filename"]) in present_ones or in_progress:
            kept_elements.append(grab)
            active.append(grab)
        elif state is not None and not state.endswith("Succeeded"):
            failures.setdefault(grab["username"], []).append(grab["filename"])
    storage.write_json(FAILURES, failures)
    storage.write_grabbed(TYPE, kept_elements)
    return active


def query(track):
    title = FEAT.sub("", track["spotify_title"])
    return re.sub(r"\s+", " ", re.sub(r"[^\w']+", " ", f"{track['artists'][0]} {title}")).strip()


def matches(track, file):
    title = musicbrainz.key(FEAT.sub("", track["spotify_title"]))
    return bool(file.get("length")) and abs(file["length"] - track["duration"]) <= TOLERANCE and title in musicbrainz.key(file_name(file["filename"]))


def release(response, file):
    return {
        "username": response["username"],
        "filename": file["filename"],
        "size": file["size"],
        "length": file.get("length"),
        "bitDepth": file.get("bitDepth"),
        "sampleRate": file.get("sampleRate"),
        "bitRate": file.get("bitRate"),
        "free": response.get("hasFreeUploadSlot", False),
        "file": response.get("queueLength", 0),
        "speed": response.get("uploadSpeed", 0),
    }


def score(r):
    return (not r["free"], r["bitDepth"] not in (None, 16), r["file"], -r["speed"])


def cover_span(track, failures={}):
    try:
        responses = slskd.search(query(track))
    except OSError as error:
        return track, [], [], str(error)
    flac, mp3 = [], []
    for response in responses:
        for file in response.get("files") or []:
            extension = file_name(file["filename"]).rsplit(".", 1)[-1].lower()
            if not matches(track, file) or file["filename"] in failures.get(response["username"], ()):
                continue
            if extension == "flac":
                flac.append(release(response, file))
            elif extension == "mp3" and (file.get("bitRate") or 0) >= 320:
                mp3.append(release(response, file))
    return track, sorted(flac, key=score)[:3], sorted(mp3, key=score)[:3], None


def progress():
    return storage.in_progress(TYPE, "download")


def summary(track, result):
    _, flac, others, error = result
    entry = {k: track[k] for k in ("mbid", "artist", "title", "path", "duration") if k in track}
    if flac:
        return "proposals", entry | {"release": flac[0], "alternatives": flac[1:]}
    if others:
        return "mp3", entry | {"release": others[0], "alternatives": others[1:]}
    return "not_found", entry | ({"error": error} if error else {})


def search(batch):
    root = config.folder(TYPE, "root")
    wanted = storage.wanted(TYPE)
    if not wanted:
        print("No Music Wanted list: run /jb-music-migrate-spotify or a Suggestion skill first")
        sys.exit(2)
    file = progress()
    state = storage.read_json(file) if file.is_file() else {"start": datetime.now().isoformat(timespec="seconds"), "batches": []}
    while True:
        grabbed = active_grabbed()
        already = {l["mbid"] for l in grabbed} | {m for d in (root, incoming()) for f in d.rglob("*") if f.is_file() and (m := music.from_name(f))}
        already |= {m["mbid"] for l in state["batches"] for m in l["tracks"]}
        candidates = [m for m in wanted["tracks"] if m["mbid"] not in already]
        current_batch = next((l for l in state["batches"] if l["state"] == "lookup"), None)
        if current_batch is None:
            if not candidates:
                break
            current_batch = {"number": len(state["batches"]) + 1, "state": "lookup", "tracks": candidates[:batch], "proposals": [], "mp3": [], "not_found": []}
            state["batches"].append(current_batch)
        done = {e["mbid"] for key in ("proposals", "mp3", "not_found") for e in current_batch[key]}
        remaining = [m for m in current_batch["tracks"] if m["mbid"] not in done]
        print(f"Batch {current_batch['number']}: {len(remaining)} Track(s) to search, {max(len(candidates) - len(remaining), 0)} for the next batches", flush=True)
        for n, track in enumerate(remaining, 1):
            key, entry = summary(track, cover_span(track, storage.read_cache(FAILURES)))
            current_batch[key].append(entry)
            storage.write_json(file, state)
            if n % 10 == 0:
                print(f"  {n}/{len(remaining)}", flush=True)
        current_batch["state"] = "to_approve"
        storage.write_json(file, state)
        print(f"Batch {current_batch['number']} ready to approve", flush=True)
    state["finished"] = True
    storage.write_json(file, state)
    print("Search finished.")


def launch(number):
    file = progress()
    state = storage.read_json(file)
    content = next(l for l in state["batches"] if l["number"] == number)
    grabbed = storage.grabbed(TYPE)
    refused_list = []
    for p in content["proposals"]:
        for r in [p["release"]] + p.get("alternatives", []):
            try:
                slskd.download(r["username"], [r])
                break
            except OSError:
                continue
        else:
            refused_list.append(f"{p['artist']} - {p['title']}")
            continue
        grabbed.append({
            "mbid": p["mbid"],
            "media": p["artist"],
            "username": r["username"],
            "filename": r["filename"],
            "date": date.today().isoformat(),
        })
        storage.write_grabbed(TYPE, grabbed)
    content["state"] = "grab"
    storage.write_json(file, state)
    print(f"Batch {number} grabbed: {len(content['proposals']) - len(refused_list)} Track(s) to {incoming()}")
    for refused in refused_list:
        print(f"  Refused by every source: {refused}")
    if state.get("finished") and all(l["state"] == "grab" for l in state["batches"]):
        file.unlink()
        print("Every batch is grabbed, progress deleted.")


def show_batch(content):
    print(f"Batch {content['number']} ({content['state']})")
    for title, key in (("FLAC proposals:", "proposals"), ("No FLAC, MP3 320 available:", "mp3")):
        if content[key]:
            print(title)
            for p in content[key]:
                print(f"  {line(p)}")
    if content["not_found"]:
        print("Not found on Soulseek:")
        for p in content["not_found"]:
            print(f"  {p['artist']} - {p['title']}{' (' + p['error'] + ')' if p.get('error') else ''}")


def batches():
    file = progress()
    if not file.is_file():
        print("No search in progress.")
        return
    state = storage.read_json(file)
    for l in state["batches"]:
        if l["state"] == "to_approve":
            show_batch(l)
        else:
            print(f"Batch {l['number']}: {l['state']}")
    print("Search finished." if state.get("finished") else "Search in progress.")
    print(f"Progress: {file}")


def line(p):
    r = p["release"]
    quality = f"{r['bitDepth']} bits {r['sampleRate'] // 1000} kHz" if r.get("bitDepth") and r.get("sampleRate") else f"{r.get('bitRate')} kb/s"
    return f"{p['artist']} - {p['title']} | {quality} | {r['size'] // 2**20} Mo | {'free' if r['free'] else f'file {r['file']}'} | {r['username']}"


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    p = subparsers.add_parser("search")
    p.add_argument("--batch", type=int, default=BATCH)
    subparsers.add_parser("batches")
    subparsers.add_parser("grab").add_argument("number", type=int)
    args = parser.parse_args()
    if args.command == "batches":
        batches()
        return
    if not slskd.key():
        print(slskd.key.message())
        sys.exit(config.MISSING_CONFIG)
    if not slskd.reachable():
        print(f"slskd unreachable or disconnected from Soulseek at {slskd.url()}: start slskd")
        sys.exit(2)
    if args.command == "grab":
        launch(args.number)
    else:
        search(args.batch)


if __name__ == "__main__":
    config.run_main(main)
