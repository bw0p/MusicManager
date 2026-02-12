import re


def first_contributing_artist(audio) -> str | None:
    """
    Best-effort across common tag names. Returns first entry, split on ';' (or other separators).
    """
    if not audio:
        return None

    candidate_keys = [
        "contributingartists",
        "contributing artists",
        "artists",
        "artist",       # most common
        "albumartist",
    ]

    for key in candidate_keys:
        val = audio.get(key)
        if not val:
            continue
        text = val[0] if isinstance(val, list) and val else str(val)
        text = text.strip()
        if not text:
            continue

        # primary split on semicolon
        first = re.split(r"\s*;\s*", text, maxsplit=1)[0]
        if first == text:
            # optional fallback split for multi-artist strings
            first = re.split(r"\s*/\s*|\s*,\s*|\s*&\s*", text, maxsplit=1)[0]

        first = first.strip()
        return first if first else None

    return None


def get_tag(audio, key: str) -> str | None:
    val = audio.get(key)
    if not val:
        return None
    if isinstance(val, list) and val:
        s = str(val[0]).strip()
        return s if s else None
    s = str(val).strip()
    return s if s else None


def set_tag(audio, key: str, value: str):
    # mutagen easy tags expect list values
    audio[key] = [value]
