import unittest

from services.scanner import ScanOptions, propose_filename


class ScannerTests(unittest.TestCase):
    def test_proposes_filename_using_cleanup_options(self):
        options = ScanOptions(remove_rules=["Downloader -"], smart_spaces=True)
        proposed, warnings = propose_filename("Downloader - Song.mp3", options)
        self.assertEqual(proposed, "Song.mp3")
        self.assertEqual(warnings, [])

    def test_invalid_delimiter_pair_adds_warning(self):
        options = ScanOptions(remove_between_enabled=True, delimiter_pair="[")
        proposed, warnings = propose_filename("[Live] Song.flac", options)
        self.assertEqual(proposed, "[Live] Song.flac")
        self.assertEqual(len(warnings), 1)


if __name__ == "__main__":
    unittest.main()
