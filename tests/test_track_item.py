import unittest
from pathlib import Path

from models import TrackItem
from warning_service import get_warnings


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
            ["AlbumArtist missing (can auto-fill)", "Track# missing"],
        )

        item.set_pending_tag("albumartist", "Artist")
        item.set_pending_tag("tracknumber", "01")

        self.assertEqual(get_warnings(item), [])

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


if __name__ == "__main__":
    unittest.main()
