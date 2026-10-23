import re
import struct
import sys
from pathlib import Path

import config
import tmdb

EPISODE_WORDS = {"en": "Episode", "fr": "Épisode", "de": "Episode", "es": "Episodio", "it": "Episodio", "pt": "Episódio"}
COUNTRIES = {
    "en": {"US", "GB", "CA", "AU", "NZ", "IE"},
    "fr": {"FR", "BE", "CA", "CH", "LU"},
    "de": {"DE", "AT", "CH"},
    "es": {"ES", "MX", "AR"},
    "it": {"IT", "CH"},
    "pt": {"PT", "BR"},
    "ja": {"JP"},
}
RELEASE_KEYWORDS = {"fr": ["VOSTFR", "SUBFRENCH", "FRE", "FRENCH SUB", "FRENCH SUBS", "FRENCH-SUB", "FRENCH-SUBS"]}
DEFAULT_TITLE = re.compile(r"(?i)^(?:" + "|".join(sorted({re.escape(w) for w in EPISODE_WORDS.values()} | {"[ée]pisode"})) + r") \d+$")


def title_language(type_):
    return config.value(type_, "title_language", "en")


def audio_language(type_):
    return config.value(type_, "audio_language", "original")


def subtitle_language(type_):
    return config.value(type_, "subtitle_language", "")


def use(type_):
    tmdb.LANGUAGE = title_language(type_)


def countries(language):
    return COUNTRIES.get(language, {language.upper()})


def episode_word(language):
    return EPISODE_WORDS.get(language, "Episode")


def release_keywords(type_):
    keywords = config.value(type_, "release_keywords", [])
    return keywords or RELEASE_KEYWORDS.get(subtitle_language(type_), [])


def release_filter(type_):
    keywords = release_keywords(type_)
    if not keywords:
        return None
    return re.compile(r"(?i)" + "|".join(r"\b" + re.escape(k).replace(r"\ ", r"[-\s]?") + r"\b" for k in keywords))


def boxes(f, start, end):
    pos = start
    while pos < end:
        f.seek(pos); h = f.read(8)
        if len(h) < 8: return
        size, typ = struct.unpack(">I4s", h); hl = 8
        if size == 1: size = struct.unpack(">Q", f.read(8))[0]; hl = 16
        elif size == 0: size = end - pos
        yield typ, pos + hl, pos + size
        pos += size
def languages(p):
    out = []
    with open(p, "rb") as f:
        f.seek(0, 2); n = f.tell()
        for t, s, e in boxes(f, 0, n):
            if t != b"moov": continue
            for t2, s2, e2 in boxes(f, s, e):
                if t2 != b"trak": continue
                info = {}
                for t3, s3, e3 in boxes(f, s2, e2):
                    if t3 != b"mdia": continue
                    for t4, s4, e4 in boxes(f, s3, e3):
                        f.seek(s4)
                        if t4 == b"mdhd":
                            v = f.read(1)[0]; f.seek(s4 + (20 if v == 0 else 32))
                            c = struct.unpack(">H", f.read(2))[0]
                            info["lang"] = "".join(chr(((c >> sh) & 31) + 0x60) for sh in (10, 5, 0))
                        if t4 == b"hdlr":
                            f.seek(s4 + 8); info["type"] = f.read(4).decode()
                out.append(f"{info.get('type')}:{info.get('lang')}")
    return out
def main():
    sys.stdout.reconfigure(encoding="utf-8")
    for p in sys.argv[1:]:
        print(Path(p).name, " ".join(languages(p)))


if __name__ == "__main__":
    main()
