from dataclasses import dataclass
from pathlib import Path

from models import TrackItem


@dataclass(frozen=True)
class RenameOperation:
    item: TrackItem
    destination: Path


def plan_renames(folder: Path, items: list[TrackItem]) -> list[RenameOperation]:
    existing = {path.name for path in folder.iterdir()}
    operations = []

    for item in items:
        old = item.filename
        new = item.proposed_filename
        if old == new:
            continue

        base = Path(new).stem
        ext = Path(new).suffix
        candidate = new
        suffix = 1
        while candidate in existing and candidate != old:
            candidate = f"{base} ({suffix}){ext}"
            suffix += 1

        existing.discard(old)
        existing.add(candidate)
        operations.append(RenameOperation(item=item, destination=folder / candidate))
    return operations


def execute_renames(operations: list[RenameOperation]) -> None:
    for operation in operations:
        operation.item.path.rename(operation.destination)
        operation.item.filename = operation.destination.name
        operation.item.proposed_filename = operation.destination.name
        operation.item.path = operation.destination
