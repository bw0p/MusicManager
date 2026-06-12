from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TrackItem:
    path: Path
    filename: str
    ext: str
    proposed_filename: str
    audio_ok: bool = True
    read_error: str | None = None
    artist_first: str = ""
    tags: dict[str, str] = field(default_factory=dict)
    pending_tags: dict[str, str] = field(default_factory=dict)
    validation_warnings: list[str] = field(default_factory=list)

    def effective_tag(self, key: str) -> str:
        if key in self.pending_tags:
            return self.pending_tags[key]
        return self.tags.get(key, "")

    def set_pending_tag(self, key: str, value: str) -> None:
        self.pending_tags[key] = value

    def erase_tag(self, key: str) -> None:
        self.pending_tags[key] = ""

    def reset_pending_tag(self, key: str) -> None:
        self.pending_tags.pop(key, None)

    def clear_pending_tags(self) -> None:
        self.pending_tags.clear()
