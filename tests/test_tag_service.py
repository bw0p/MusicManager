import unittest
from pathlib import Path

from models import TrackItem
from tag_service import apply_pending_tags, extract_tag_value_from_filename, read_supported_tags


class FakeAudio(dict):
    pass


class TagServiceTests(unittest.TestCase):
    def make_item(self):
        return TrackItem(
            path=Path("song.mp3"),
            filename="song.mp3",
            ext=".mp3",
            proposed_filename="song.mp3",
        )

    def test_reads_all_supported_fields(self):
        audio = FakeAudio(
            artist=["Artist"],
            albumartist=["Album Artist"],
            album=["Album"],
            date=["2026"],
            genre=["Rock"],
            tracknumber=["03"],
        )

        tags = read_supported_tags(audio)

        self.assertEqual(tags["artist"], "Artist")
        self.assertEqual(tags["date"], "2026")
        self.assertEqual(tags["tracknumber"], "03")

    def test_applies_and_erases_pending_tags(self):
        audio = FakeAudio(artist=["Old Artist"], genre=["Rock"])
        item = self.make_item()
        item.set_pending_tag("artist", "New Artist")
        item.erase_tag("genre")

        apply_pending_tags(audio, item)

        self.assertEqual(audio["artist"], ["New Artist"])
        self.assertNotIn("genre", audio)

    def test_reset_edit_does_not_modify_audio(self):
        audio = FakeAudio(album=["Original"])
        item = self.make_item()
        item.set_pending_tag("album", "Replacement")
        item.reset_pending_tag("album")

        apply_pending_tags(audio, item)

        self.assertEqual(audio["album"], ["Original"])

    def test_extracts_tag_value_between_filename_boundaries(self):
        self.assertEqual(
            extract_tag_value_from_filename("My Song [Artist Name] 2026.mp3", "[", "]"),
            "Artist Name",
        )

    def test_extracts_to_end_when_after_boundary_is_empty(self):
        self.assertEqual(
            extract_tag_value_from_filename("My Song - Artist Name.flac", " - ", ""),
            "Artist Name",
        )

    def test_returns_none_when_boundary_is_missing(self):
        self.assertIsNone(
            extract_tag_value_from_filename("My Song Artist Name.mp3", "[", "]")
        )


if __name__ == "__main__":
    unittest.main()
