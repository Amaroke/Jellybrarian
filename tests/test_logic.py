import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "jb" / "scripts"))

import archives
import config
import languages
import storage
import tmdb_checks
import music_wanted
import names
import releases
import scan_readings


class Names(unittest.TestCase):
    def test_sanitize_replaces_forbidden_characters(self):
        self.assertEqual(names.sanitize("Re: Zero / Starting Life?"), "Re - Zero - Starting Life")

    def test_sanitize_removes_the_trailing_dot(self):
        self.assertEqual(names.sanitize("Agents of S.H.I.E.L.D."), "Agents of S.H.I.E.L.D")

    def test_flaws_reports_year_and_double_space(self):
        self.assertEqual(names.flaws("Dune  (2021)"), ["double space", "year in the name"])


class Spans(unittest.TestCase):
    def test_spans_groups_consecutive_episodes(self):
        self.assertEqual(tmdb_checks.spans([(1, 1), (1, 2), (1, 3), (1, 5), (2, 1)]), "S01E01 to S01E03, S01E05, S02E01")

    def test_episodes_of_reads_spans_back(self):
        self.assertEqual(releases.episodes_of("S01E01 to S01E03, S02E05"), [(1, 1), (1, 2), (1, 3), (2, 5)])

    def test_episodes_of_refuses_free_text(self):
        self.assertIsNone(releases.episodes_of("Dune : Deuxième partie"))

    def test_volume_spans_on_three_digits(self):
        self.assertEqual(scan_readings.volume_spans([110, 111, 112, 113], 3), "T110 to T113")


class Archives(unittest.TestCase):
    def test_comic_info_carries_title_series_and_number(self):
        xml = archives.comic_info({"title": "One Piece - T001", "series": "One Piece", "rank": 1})
        self.assertIn("<Series>One Piece</Series>", xml)
        self.assertIn("<Number>1</Number>", xml)

    def test_epub_named_cbz_is_a_wrong_extension(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "book.cbz"
            with zipfile.ZipFile(file, "w") as archive:
                archive.writestr("mimetype", "application/epub+zip")
            self.assertEqual(archives.wrong_extension(file), ".epub")

    def test_cbz_cleanup_writes_comic_info_and_removes_the_rest(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "volume.cbz"
            with zipfile.ZipFile(file, "w") as archive:
                archive.writestr("001.jpg", b"image")
                archive.writestr("details.json", "{}")
            archives.clean(file, {"title": "T", "series": "S", "rank": 2})
            self.assertEqual(sorted(zipfile.ZipFile(file).namelist()), ["001.jpg", "ComicInfo.xml"])

    def test_cover_found_by_identifier(self):
        opf = '<manifest><item id="cover" href="cover.jpeg" media-type="image/jpeg"/></manifest>'
        self.assertEqual(archives.cover(opf, []), "cover")


class Config(unittest.TestCase):
    def test_write_adds_then_replaces_a_value(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "config.toml"
            file.write_text("[anime]\nroot = ''\n", encoding="utf-8")
            with mock.patch.object(config, "FILE", file):
                config.write("anime", "root", r"D:\Anime")
                config.write("show", "root", "D:/Shows")
                self.assertEqual(config.value("anime", "root"), r"D:\Anime")
                self.assertEqual(config.value("show", "root"), "D:/Shows")

    def test_write_refuses_a_secret(self):
        with self.assertRaises(ValueError):
            config.write("tmdb", "key", "secret")

    def test_absent_value_raises_missing_config(self):
        with tempfile.TemporaryDirectory() as folder:
            with mock.patch.object(config, "FILE", Path(folder) / "config.toml"):
                with self.assertRaises(config.MissingConfig):
                    config.value("tmdb", "key")


class Store(unittest.TestCase):
    def test_lock_refuses_another_action_unless_forced(self):
        with tempfile.TemporaryDirectory() as folder:
            with mock.patch.object(config, "data_folder", lambda: Path(folder)):
                self.assertEqual(storage.acquire_lock("anime", ["root"], "check"), [])
                self.assertTrue(storage.acquire_lock("anime", ["root"], "rename"))
                self.assertEqual(storage.acquire_lock("anime", ["root"], "rename", force=True), [])
                storage.unlock("anime", ["root"])
                self.assertFalse(storage.lock("anime", "root").exists())


class Migration(unittest.TestCase):
    def test_merge_replaces_only_its_origin(self):
        old_values = [{"mbid": "a", "origin": "spotify"}, {"mbid": "b", "origin": "album"}]
        new_ones = [{"mbid": "c", "origin": "spotify"}]
        self.assertEqual([m["mbid"] for m in music_wanted.merge(old_values, new_ones, "spotify")], ["b", "c"])

    def test_migrate_empties_the_snapshot_of_present_tracks(self):
        with tempfile.TemporaryDirectory() as folder:
            with mock.patch.object(config, "data_folder", lambda: Path(folder)):
                storage.write_json(storage.spotify(), {"tracks": {"1": {"mbid": "a"}, "2": {"mbid": "b"}, "3": {"mbid": None}}})
                self.assertEqual(music_wanted.migrate({"a"}), 1)
                self.assertEqual(music_wanted.progress(), (1, 0, 3))
                self.assertEqual(json.loads(storage.spotify().read_text(encoding="utf-8"))["tracks"].keys(), {"2", "3"})


class Languages(unittest.TestCase):
    def setting(self, text):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        file = Path(folder.name) / "config.toml"
        file.write_text(text, encoding="utf-8")
        patch = mock.patch.object(config, "FILE", file)
        patch.start()
        self.addCleanup(patch.stop)

    def test_release_filter_follows_the_subtitle_language(self):
        self.setting("[anime]\nsubtitle_language = 'fr'\n")
        wanted = languages.release_filter("anime")
        self.assertTrue(wanted.search("[Erai-raws] Frieren - 01 [1080p][VOSTFR]"))
        self.assertTrue(wanted.search("Frieren S01 1080p French Subs"))
        self.assertFalse(wanted.search("[Erai-raws] Frieren - 01 [1080p][MultiSub]"))

    def test_no_release_filter_without_subtitle_language(self):
        self.setting("[anime]\n")
        self.assertIsNone(languages.release_filter("anime"))

    def test_release_keywords_from_the_config_replace_the_table(self):
        self.setting("[anime]\nsubtitle_language = 'fr'\nrelease_keywords = ['SUBITA']\n")
        self.assertEqual(languages.release_keywords("anime"), ["SUBITA"])

    def test_default_title_in_every_language(self):
        for title in ("Episode 3", "Épisode 3", "episode 3", "Episodio 12"):
            self.assertTrue(languages.DEFAULT_TITLE.match(title), title)
        self.assertFalse(languages.DEFAULT_TITLE.match("Episode of the Dead"))

    def test_episode_word_falls_back_to_english(self):
        self.assertEqual(languages.episode_word("fr"), "Épisode")
        self.assertEqual(languages.episode_word("ko"), "Episode")
        self.assertEqual(languages.countries("ko"), {"KO"})


if __name__ == "__main__":
    unittest.main()
