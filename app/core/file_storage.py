from pathlib import Path
from uuid import UUID


class FileStorage:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, storage_name: str) -> Path:
        return self.root / storage_name

    def path_for_id(self, file_id: UUID) -> Path:
        return self.root / str(file_id)
