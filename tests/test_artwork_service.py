import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from mutagen.id3 import ID3

from models import ArtworkData, TrackItem
from services.artwork_service import (
    ArtworkError,
    apply_artwork_change,
    extract_embedded_artwork,
    has_embedded_artwork,
    load_artwork_file,
)


class ArtworkServiceTests(unittest.TestCase):
    def make_item(self, path: Path):
        return TrackItem(
            path=path,
            filename=path.name,
            ext=path.suffix,
            proposed_filename=path.name,
        )

    def test_loads_jpg_and_rejects_unsupported_image(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            jpg = folder / "cover.jpg"
            jpg.write_bytes(b"image")
            artwork = load_artwork_file(jpg)
            self.assertEqual(artwork.mime, "image/jpeg")

            unsupported = folder / "cover.bmp"
            unsupported.write_bytes(b"image")
            with self.assertRaises(ArtworkError):
                load_artwork_file(unsupported)

    def test_mp3_artwork_can_be_added_and_removed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "song.mp3"
            ID3().save(path)
            item = self.make_item(path)
            item.set_pending_artwork(ArtworkData(b"cover", "image/jpeg", "cover.jpg"))

            self.assertTrue(apply_artwork_change(item))
            self.assertTrue(has_embedded_artwork(path))
            self.assertEqual(ID3(path).version, (2, 3, 0))
            picture = ID3(path).getall("APIC")[0]
            self.assertEqual(picture.type, 3)
            self.assertEqual(picture.desc, "")
            extracted = extract_embedded_artwork(path)
            self.assertEqual(extracted.data, b"cover")
            self.assertEqual(extracted.mime, "image/jpeg")

            item.erase_artwork()
            self.assertTrue(apply_artwork_change(item))
            self.assertFalse(has_embedded_artwork(path))

    @patch("services.artwork_service.FLAC")
    def test_flac_artwork_uses_picture_api(self, flac_class):
        audio = MagicMock()
        flac_class.return_value = audio
        item = self.make_item(Path("song.flac"))
        item.set_pending_artwork(ArtworkData(b"cover", "image/png"))

        self.assertTrue(apply_artwork_change(item))

        audio.clear_pictures.assert_called_once()
        audio.add_picture.assert_called_once()
        audio.save.assert_called_once()

    @patch("services.artwork_service.MP4")
    def test_m4a_artwork_uses_cover_tag(self, mp4_class):
        audio = MagicMock()
        audio.tags = {}
        mp4_class.return_value = audio
        item = self.make_item(Path("song.m4a"))
        item.set_pending_artwork(ArtworkData(b"cover", "image/jpeg"))

        self.assertTrue(apply_artwork_change(item))

        self.assertIn("covr", audio.tags)
        audio.save.assert_called_once()

    def test_unsupported_audio_type_reports_error(self):
        item = self.make_item(Path("song.ogg"))
        item.erase_artwork()
        with self.assertRaises(ArtworkError):
            apply_artwork_change(item)


if __name__ == "__main__":
    unittest.main()
