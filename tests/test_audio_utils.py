import unittest

from audio_utils import first_contributing_artist


class FirstContributingArtistTests(unittest.TestCase):
    def test_does_not_use_album_artist_as_contributing_artist(self):
        audio = {"albumartist": ["Album Artist"]}
        self.assertIsNone(first_contributing_artist(audio))

    def test_reads_artist_even_when_album_artist_exists(self):
        audio = {
            "artist": ["Contributing Artist"],
            "albumartist": ["Album Artist"],
        }
        self.assertEqual(first_contributing_artist(audio), "Contributing Artist")


if __name__ == "__main__":
    unittest.main()
