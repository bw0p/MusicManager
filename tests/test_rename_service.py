import tempfile
import unittest
from pathlib import Path

from models import TrackItem
from services.rename_service import execute_renames, plan_renames


class RenameServiceTests(unittest.TestCase):
    def make_item(self, folder: Path, filename: str, proposed: str):
        path = folder / filename
        path.write_bytes(b"audio")
        return TrackItem(path=path, filename=filename, ext=path.suffix, proposed_filename=proposed)

    def test_collision_gets_numbered_filename(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            item = self.make_item(folder, "old.mp3", "song.mp3")
            (folder / "song.mp3").write_bytes(b"existing")
            operations = plan_renames(folder, [item])
            self.assertEqual(operations[0].destination.name, "song (1).mp3")

    def test_execute_updates_file_and_item(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            item = self.make_item(folder, "old.mp3", "new.mp3")
            execute_renames(plan_renames(folder, [item]))
            self.assertFalse((folder / "old.mp3").exists())
            self.assertTrue((folder / "new.mp3").exists())
            self.assertEqual(item.filename, "new.mp3")


if __name__ == "__main__":
    unittest.main()
