from dataclasses import dataclass
from pathlib import Path

from audio_utils import get_tag, set_tag
from models import TrackItem


@dataclass(frozen=True)
class TagField:
    label: str
    key: str


TAG_FIELDS = (
    TagField("Album Artist", "albumartist"),
    TagField("Contributing Artist", "artist"),
    TagField("Album", "album"),
    TagField("Year", "date"),
    TagField("Genre", "genre"),
)

TAG_KEY_BY_LABEL = {field.label: field.key for field in TAG_FIELDS}
SCANNED_TAG_KEYS = tuple(field.key for field in TAG_FIELDS) + ("tracknumber",)


def read_supported_tags(audio) -> dict[str, str]:
    return {key: get_tag(audio, key) or "" for key in SCANNED_TAG_KEYS}


def delete_tag(audio, key: str) -> None:
    if key in audio:
        del audio[key]


def apply_pending_tags(audio, item: TrackItem) -> None:
    for key, value in item.pending_tags.items():
        if value.strip():
            set_tag(audio, key, value.strip())
        else:
            delete_tag(audio, key)


def extract_tag_value_from_filename(
    filename: str,
    text_before: str,
    text_after: str,
) -> str | None:
    stem = Path(filename).stem
    start = 0

    if text_before:
        before_index = stem.find(text_before)
        if before_index < 0:
            return None
        start = before_index + len(text_before)

    if text_after:
        after_index = stem.find(text_after, start)
        if after_index < 0:
            return None
        value = stem[start:after_index]
    else:
        value = stem[start:]

    value = value.strip()
    return value or None
