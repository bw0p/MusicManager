from dataclasses import dataclass, field
from pathlib import Path

from audio_utils import ensure_id3_header, load_audio
from models import TrackItem
from services.artwork_service import apply_artwork_change
from services.rename_service import execute_renames, plan_renames
from tag_service import apply_pending_tags


@dataclass
class ApplyResult:
    renamed_files: int = 0
    tagged_files: int = 0
    skipped_files: list[str] = field(default_factory=list)
    tag_errors: list[str] = field(default_factory=list)
    artwork_files: int = 0
    artwork_errors: list[str] = field(default_factory=list)


class ApplyError(Exception):
    def __init__(self, message: str, technical_detail: str = ""):
        super().__init__(message)
        self.message = message
        self.technical_detail = technical_detail


def apply_changes(folder: Path, items: list[TrackItem]) -> ApplyResult:
    result = ApplyResult()
    operations = plan_renames(folder, items)
    try:
        execute_renames(operations)
        result.renamed_files = len(operations)
    except Exception as error:
        raise ApplyError(
            "A file could not be renamed. A file with that name may already exist, "
            "or it may be open in another program.",
            str(error),
        ) from error

    for item in items:
        if item.path.suffix.lower() == ".mp3":
            ensure_id3_header(str(item.path))

        audio, error = load_audio(str(item.path))
        if audio is None:
            result.skipped_files.append(item.filename)
            if error:
                print(f"[apply load_audio] {item.filename}: {error}")
            continue

        try:
            apply_pending_tags(audio, item)
            audio.save()
            result.tagged_files += 1
        except Exception as error:
            result.tag_errors.append(item.filename)
            print(f"[tag save failed] {item.filename}: {type(error).__name__}: {error}")

        try:
            if apply_artwork_change(item):
                result.artwork_files += 1
        except Exception as error:
            result.artwork_errors.append(item.filename)
            print(f"[artwork save failed] {item.filename}: {type(error).__name__}: {error}")
    return result
