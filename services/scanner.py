from dataclasses import dataclass, field
from pathlib import Path

from audio_utils import first_contributing_artist, load_audio
from models import TrackItem
from rename_rules import apply_remove_rules, clean_spaces, remove_between_delims, safe_filename
from tag_service import read_supported_tags


AUDIO_EXTS = {".mp3", ".m4a", ".flac", ".ogg", ".opus", ".wav", ".aiff", ".aac"}


@dataclass(frozen=True)
class ScanOptions:
    remove_rules: list[str] = field(default_factory=list)
    smart_spaces: bool = True
    remove_between_enabled: bool = False
    delimiter_pair: str = "[]"


def propose_filename(filename: str, options: ScanOptions) -> tuple[str, list[str]]:
    path = Path(filename)
    proposed_base = apply_remove_rules(
        path.stem,
        options.remove_rules,
        smart_spaces=options.smart_spaces,
    )
    warnings = []
    if options.remove_between_enabled:
        if len(options.delimiter_pair) == 2:
            proposed_base = remove_between_delims(
                proposed_base,
                options.delimiter_pair[0],
                options.delimiter_pair[1],
            )
        else:
            warnings.append("Delimiter pair must be exactly 2 characters (e.g. [] or &&).")

    proposed_base = safe_filename(clean_spaces(proposed_base))
    return proposed_base + path.suffix.lower(), warnings


def scan_folder(folder: Path, options: ScanOptions) -> list[TrackItem]:
    items = []
    for path in sorted(folder.iterdir(), key=lambda entry: entry.name.casefold()):
        ext = path.suffix.lower()
        if not path.is_file() or ext not in AUDIO_EXTS:
            continue

        audio, error = load_audio(str(path))
        tags = read_supported_tags(audio) if audio is not None else {}
        artist_first = first_contributing_artist(audio) or "" if audio is not None else ""
        proposed, validation_warnings = propose_filename(path.name, options)
        items.append(
            TrackItem(
                path=path,
                filename=path.name,
                ext=ext,
                proposed_filename=proposed,
                audio_ok=audio is not None,
                read_error=error,
                artist_first=artist_first,
                tags=tags,
                validation_warnings=validation_warnings,
            )
        )
    return items
