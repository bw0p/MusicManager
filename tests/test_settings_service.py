import tempfile
import unittest
from pathlib import Path

from services.settings_service import AppSettings, RulePreset, load_settings, save_settings


class SettingsServiceTests(unittest.TestCase):
    def test_missing_file_returns_defaults(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = load_settings(Path(temp_dir) / "missing.json")
            self.assertEqual(settings.theme, "Light")
            self.assertTrue(settings.active_rules().smart_spaces)

    def test_settings_round_trip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "settings.json"
            expected = AppSettings(
                theme="Dark",
                active_preset="Downloads",
                rule_presets={
                    "Default": RulePreset(),
                    "Downloads": RulePreset(
                        remove_rules=["Prefix -", "- Copy"],
                        delimiter_pair="()",
                        track_markers="%%",
                    ),
                },
            )

            save_settings(expected, path)
            actual = load_settings(path)

            self.assertEqual(actual, expected)

    def test_legacy_single_rule_set_migrates_to_default(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "settings.json"
            path.write_text(
                '{"theme": "Dark", "remove_rules": ["Old Prefix"], "track_markers": "%%"}',
                encoding="utf-8",
            )

            settings = load_settings(path)

            self.assertEqual(settings.theme, "Dark")
            self.assertEqual(settings.active_preset, "Default")
            self.assertEqual(settings.active_rules().remove_rules, ["Old Prefix"])
            self.assertEqual(settings.active_rules().track_markers, "%%")

    def test_missing_default_preset_is_restored(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "settings.json"
            path.write_text(
                '{"active_preset": "Custom", "rule_presets": {"Custom": {"track_markers": "()"}}}',
                encoding="utf-8",
            )

            settings = load_settings(path)

            self.assertIn("Default", settings.rule_presets)
            self.assertEqual(settings.active_preset, "Custom")

    def test_invalid_json_returns_defaults(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "settings.json"
            path.write_text("not json", encoding="utf-8")
            self.assertEqual(load_settings(path), AppSettings())

    def test_unknown_theme_falls_back_to_light(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "settings.json"
            path.write_text('{"theme": "Neon"}', encoding="utf-8")
            self.assertEqual(load_settings(path).theme, "Light")


if __name__ == "__main__":
    unittest.main()
