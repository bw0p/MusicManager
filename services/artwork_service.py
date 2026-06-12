from pathlib import Path

from mutagen.flac import FLAC, Picture
from mutagen.id3 import APIC, ID3, ID3NoHeaderError
from mutagen.mp4 import MP4, MP4Cover

from models import ArtworkData, TrackItem


SUPPORTED_IMAGE_EXTS = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
SUPPORTED_AUDIO_EXTS = {".mp3", ".flac", ".m4a", ".mp4"}


class ArtworkError(Exception):
    pass


def load_artwork_file(path: Path) -> ArtworkData:
    mime = SUPPORTED_IMAGE_EXTS.get(path.suffix.lower())
    if mime is None:
        raise ArtworkError("Choose a JPG or PNG image.")
    return ArtworkData(data=path.read_bytes(), mime=mime, source_name=path.name)


def has_embedded_artwork(path: Path) -> bool:
    return extract_embedded_artwork(path) is not None


def extract_embedded_artwork(path: Path) -> ArtworkData | None:
    ext = path.suffix.lower()
    try:
        if ext == ".mp3":
            pictures = ID3(path).getall("APIC")
            if pictures:
                picture = next((frame for frame in pictures if frame.type == 3), pictures[0])
                return ArtworkData(picture.data, picture.mime or "image/jpeg", path.name)
        if ext == ".flac":
            pictures = FLAC(path).pictures
            if pictures:
                picture = next((frame for frame in pictures if frame.type == 3), pictures[0])
                return ArtworkData(picture.data, picture.mime or "image/jpeg", path.name)
        if ext in {".m4a", ".mp4"}:
            audio = MP4(path)
            covers = audio.tags.get("covr") if audio.tags else None
            if covers:
                cover = covers[0]
                mime = "image/png" if cover.imageformat == MP4Cover.FORMAT_PNG else "image/jpeg"
                return ArtworkData(bytes(cover), mime, path.name)
    except Exception:
        return None
    return None


def apply_artwork_change(item: TrackItem) -> bool:
    if not item.artwork_change_pending:
        return False

    ext = item.path.suffix.lower()
    if ext not in SUPPORTED_AUDIO_EXTS:
        raise ArtworkError(f"Artwork editing is not supported for {ext or 'this file type'}.")

    if ext == ".mp3":
        _apply_mp3_artwork(item.path, item.pending_artwork)
    elif ext == ".flac":
        _apply_flac_artwork(item.path, item.pending_artwork)
    else:
        _apply_mp4_artwork(item.path, item.pending_artwork)
    return True


def _apply_mp3_artwork(path: Path, artwork: ArtworkData | None) -> None:
    try:
        tags = ID3(path)
    except ID3NoHeaderError:
        tags = ID3()
    tags.delall("APIC")
    if artwork is not None:
        tags.add(APIC(encoding=0, mime=artwork.mime, type=3, desc="", data=artwork.data))
    # Windows Explorer is substantially more reliable with ID3v2.3 artwork.
    tags.save(path, v2_version=3)


def _apply_flac_artwork(path: Path, artwork: ArtworkData | None) -> None:
    audio = FLAC(path)
    audio.clear_pictures()
    if artwork is not None:
        picture = Picture()
        picture.type = 3
        picture.mime = artwork.mime
        picture.desc = "Cover"
        picture.data = artwork.data
        audio.add_picture(picture)
    audio.save()


def _apply_mp4_artwork(path: Path, artwork: ArtworkData | None) -> None:
    audio = MP4(path)
    if audio.tags is None:
        audio.add_tags()
    if artwork is None:
        audio.tags.pop("covr", None)
    else:
        image_format = MP4Cover.FORMAT_PNG if artwork.mime == "image/png" else MP4Cover.FORMAT_JPEG
        audio.tags["covr"] = [MP4Cover(artwork.data, imageformat=image_format)]
    audio.save()
