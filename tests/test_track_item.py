import unittest
from pathlib import Path

from models import TrackItem
from warning_service import get_duplicate_track_ids, get_warnings, normalize_track_id


class TrackItemWarningTests(unittest.TestCase):
    def make_item(self, **overrides):
        values = {
            "path": Path("song.mp3"),
            "filename": "song.mp3",
            "ext": ".mp3",
            "proposed_filename": "song.mp3",
            "artist_first": "Artist",
            "tags": {},
        }
        values.update(overrides)
        return TrackItem(**values)

    def test_pending_tags_replace_missing_tag_warnings(self):
        item = self.make_item()
        self.assertEqual(
            get_warnings(item),
            ["Album missing", "Year missing", "Genre missing", "Track# missing"],
        )

        item.set_pending_tag("albumartist", "Artist")
        item.set_pending_tag("album", "Album")
        item.set_pending_tag("date", "2026")
        item.set_pending_tag("genre", "Rock")
        item.set_pending_tag("tracknumber", "01")

        self.assertEqual(get_warnings(item), [])

    def test_missing_contributing_artist_is_reported(self):
        item = self.make_item(
            artist_first="",
            tags={
                "album": "Album",
                "date": "2026",
                "genre": "Rock",
                "tracknumber": "01",
            },
        )

        self.assertEqual(get_warnings(item), ["Contributing Artist missing"])

        item.set_pending_tag("artist", "Artist")
        self.assertEqual(get_warnings(item), [])

    def test_album_artist_is_optional(self):
        item = self.make_item(tags={"albumartist": "Original"})
        item.erase_tag("albumartist")

        warnings = get_warnings(item)

        self.assertFalse(any("AlbumArtist" in warning for warning in warnings))

    def test_reset_pending_tag_restores_scanned_value(self):
        item = self.make_item(tags={"albumartist": "Original", "tracknumber": "02"})
        item.set_pending_tag("albumartist", "Replacement")
        self.assertEqual(item.effective_tag("albumartist"), "Replacement")

        item.reset_pending_tag("albumartist")
        self.assertEqual(item.effective_tag("albumartist"), "Original")

    def test_read_failure_keeps_error_and_validation_warnings(self):
        item = self.make_item(
            audio_ok=False,
            read_error="Unsupported data",
            validation_warnings=["Delimiter pair must be exactly 2 characters"],
        )

        self.assertEqual(
            get_warnings(item),
            [
                "Failed to read as audio file/Could not read tags",
                "Unsupported data",
                "Delimiter pair must be exactly 2 characters",
            ],
        )

    def test_duplicate_track_numbers_are_reported_for_each_track(self):
        first = self.make_item(tags={"tracknumber": "01"})
        second = self.make_item(filename="second.mp3", tags={"tracknumber": "1/10"})
        duplicates = get_duplicate_track_ids([first, second])

        self.assertEqual(duplicates, {"1"})
        self.assertIn("Duplicate Track #", get_warnings(first, duplicates))
        self.assertIn("Duplicate Track #", get_warnings(second, duplicates))

    def test_pending_track_number_updates_duplicate_detection(self):
        first = self.make_item(tags={"tracknumber": "01"})
        second = self.make_item(filename="second.mp3", tags={"tracknumber": "02"})
        self.assertEqual(get_duplicate_track_ids([first, second]), set())

        second.set_pending_tag("tracknumber", "1")
        self.assertEqual(get_duplicate_track_ids([first, second]), {"1"})

    def test_track_id_normalization_handles_padded_and_fraction_values(self):
        self.assertEqual(normalize_track_id("01"), "1")
        self.assertEqual(normalize_track_id("1/12"), "1")


if __name__ == "__main__":
    unittest.main()
