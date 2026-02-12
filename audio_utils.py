import re
from mutagen import File
from mutagen.mp3 import EasyMP3
from mutagen.id3 import ID3, ID3NoHeaderError
from mutagen.mp3 import MP3



def first_contributing_artist(audio) -> str | None:
    """
    Best-effort across common tag names. Returns first entry, split on ';' (or other separators).
    """
    if audio is None:
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

def ensure_id3_header(path: str):
    try:
        try:
            ID3(path)
            return True, None
        except ID3NoHeaderError:
            tags = ID3()
            tags.save(path)
            return True, None
    except Exception as e:
        return False, f"ensure_id3_header failed: {type(e).__name__}: {e}"


def load_audio(path: str):
    ext = path.lower().rsplit(".", 1)[-1] if "." in path else ""

    if ext == "mp3":
        ok, id3_err = ensure_id3_header(path)

        # First: verify it is an MP3 audio stream (even if it has no tags)
        try:
            MP3(path)  # parses frames, proves MP3 structure
        except Exception as e:
            return None, f"MP3 parse failed: {type(e).__name__}: {e}"

        # Then: open easy tags interface
        try:
            return EasyMP3(path), id3_err
        except Exception as e:
            return None, f"EasyMP3 open failed: {type(e).__name__}: {e} | {id3_err or ''}".strip()

    # non-mp3: sniff with mutagen
    try:
        a = File(path, easy=True)
        if a:
            return a, None
        return None, "Mutagen File(easy=True) returned None (unknown/unsupported file)"
    except Exception as e:
        return None, f"Mutagen File(easy=True) exception: {type(e).__name__}: {e}"