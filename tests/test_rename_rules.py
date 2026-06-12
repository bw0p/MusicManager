import unittest

from rename_rules import extract_index_with_pair


class ExtractIndexWithPairTests(unittest.TestCase):
    def test_extracts_selected_same_character_pair(self):
        self.assertEqual(
            extract_index_with_pair("%6% Good Morning", "%%"),
            6,
        )

    def test_extracts_markers_after_a_filename_prefix(self):
        self.assertEqual(
            extract_index_with_pair("helloExtra '10' Father", "''"),
            10,
        )

    def test_does_not_fall_back_to_another_marker_pair(self):
        self.assertIsNone(extract_index_with_pair("[03] Stronger", "%%"))

    def test_rejects_empty_or_incomplete_marker_pairs(self):
        self.assertIsNone(extract_index_with_pair("[03] Stronger", ""))
        self.assertIsNone(extract_index_with_pair("[03] Stronger", "["))


if __name__ == "__main__":
    unittest.main()
