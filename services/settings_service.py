import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
import os

APP_NAME = "MusicFileManager"

def get_settings_path() -> Path:
    if os.name == "nt":
        base = Path(os.getenv("APPDATA", Path.home()))
        return base / APP_NAME / "settings.json"

    return Path.home() / ".config" / APP_NAME / "settings.json"


SETTINGS_PATH = get_settings_path()


@dataclass
class RulePreset:
    remove_rules: list[str] = field(default_factory=lambda: ["SpotiDownloader.com - "])
    smart_spaces: bool = True
    remove_between_enabled: bool = False
    delimiter_pair: str = "[]"
    track_markers: str = "[]"
    tag_extract_before: str = ""
    tag_extract_after: str = ""


@dataclass
class AppSettings:
    version: int = 2
    theme: str = "Light"
    active_preset: str = "Default"
    rule_presets: dict[str, RulePreset] = field(
        default_factory=lambda: {"Default": RulePreset()}
    )

    def active_rules(self) -> RulePreset:
        return self.rule_presets.get(self.active_preset, self.rule_presets["Default"])


def load_settings(path: Path = SETTINGS_PATH) -> AppSettings:
    if not path.exists():
        return AppSettings()

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return AppSettings()
    if not isinstance(data, dict):
        return AppSettings()

    theme = data.get("theme", "Light")
    if theme not in {"Light", "Dark"}:
        theme = "Light"

    raw_presets = data.get("rule_presets")
    if isinstance(raw_presets, dict):
        presets = {
            name: _rule_preset_from_dict(value)
            for name, value in raw_presets.items()
            if isinstance(name, str) and name.strip() and isinstance(value, dict)
        }
    else:
        # Migrate the original single-rule-set format into the Default preset.
        legacy_keys = asdict(RulePreset()).keys()
        legacy_values = {key: data[key] for key in legacy_keys if key in data}
        presets = {"Default": _rule_preset_from_dict(legacy_values)}

    if "Default" not in presets:
        presets["Default"] = RulePreset()
    active_preset = data.get("active_preset", "Default")
    if active_preset not in presets:
        active_preset = "Default"
    return AppSettings(theme=theme, active_preset=active_preset, rule_presets=presets)


def save_settings(settings: AppSettings, path: Path = SETTINGS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(settings), indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )

def _rule_preset_from_dict(data: dict) -> RulePreset:
    defaults = asdict(RulePreset())
    values = {key: data.get(key, default) for key, default in defaults.items()}
    if not isinstance(values["remove_rules"], list):
        values["remove_rules"] = defaults["remove_rules"]
    return RulePreset(**values)
