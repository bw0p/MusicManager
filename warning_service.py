from collections import Counter

from models import TrackItem


def normalize_track_id(value: str) -> str:
    track_id = (value or "").split("/", 1)[0].strip()
    if track_id.isdigit():
        return str(int(track_id))
    return track_id.casefold()


def get_duplicate_track_ids(items: list[TrackItem]) -> set[str]:
    track_ids = [
        normalize_track_id(item.effective_tag("tracknumber"))
        for item in items
        if item.audio_ok and item.effective_tag("tracknumber").strip()
    ]
    counts = Counter(track_ids)
    return {track_id for track_id, count in counts.items() if count > 1}


def get_warnings(
    item: TrackItem,
    duplicate_track_ids: set[str] | None = None,
) -> list[str]:
    if not item.audio_ok:
        warnings = ["Failed to read as audio file/Could not read tags"]
        if item.read_error:
            warnings.append(item.read_error)
        warnings.extend(item.validation_warnings)
        return warnings

    warnings = list(item.validation_warnings)

    if not (item.effective_tag("artist") or item.artist_first):
        warnings.append("Contributing Artist missing")
    if not item.effective_tag("album"):
        warnings.append("Album missing")
    if not item.effective_tag("date"):
        warnings.append("Year missing")
    if not item.effective_tag("genre"):
        warnings.append("Genre missing")

    if not item.effective_tag("tracknumber"):
        warnings.append("Track# missing")
    elif normalize_track_id(item.effective_tag("tracknumber")) in (duplicate_track_ids or set()):
        warnings.append("Duplicate Track #")

    return warnings
