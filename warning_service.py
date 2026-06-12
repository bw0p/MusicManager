from models import TrackItem


def get_warnings(item: TrackItem) -> list[str]:
    if not item.audio_ok:
        warnings = ["Failed to read as audio file/Could not read tags"]
        if item.read_error:
            warnings.append(item.read_error)
        warnings.extend(item.validation_warnings)
        return warnings

    warnings = list(item.validation_warnings)

    if not item.effective_tag("albumartist"):
        if item.artist_first:
            warnings.append("AlbumArtist missing (can auto-fill)")
        else:
            warnings.append("AlbumArtist missing + no artist found")

    if not item.effective_tag("tracknumber"):
        warnings.append("Track# missing")

    return warnings
