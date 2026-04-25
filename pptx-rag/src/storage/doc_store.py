# src/storage/doc_store.py
"""Document store for parent chunks using local files"""

import json
from pathlib import Path
from typing import Optional, Dict, Any
from ..models import ParentChunk
from ..config import config
from ..logging import log


class DocStore:
    """File-based document store for parent chunks"""

    def __init__(self, store_dir: str = None):
        """
        Initialize document store

        Args:
            store_dir: Directory for storing documents (defaults to chunks_dir)
        """
        self.log = log.bind(module="doc_store")
        self.store_dir = Path(store_dir) if store_dir else config.chunks_dir
        self.store_dir.mkdir(parents=True, exist_ok=True)

    def save(self, parent_chunk: ParentChunk) -> bool:
        """
        Save a parent chunk to the store

        Args:
            parent_chunk: ParentChunk to save

        Returns:
            True if successful
        """
        try:
            file_path = self.store_dir / f"{parent_chunk.id}.json"
            data = {
                "id": parent_chunk.id,
                "file_name": parent_chunk.file_name,
                "start_page": parent_chunk.start_page,
                "end_page": parent_chunk.end_page,
                "content": parent_chunk.content,
                "child_chunk_ids": parent_chunk.child_chunk_ids,
                "metadata": parent_chunk.metadata,
            }

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            self.log.debug(f"Saved parent chunk: {parent_chunk.id}")
            return True

        except Exception as e:
            self.log.error(f"Failed to save parent chunk: {e}")
            return False

    def get_by_id(self, chunk_id: str) -> Optional[ParentChunk]:
        """
        Get a parent chunk by ID

        Args:
            chunk_id: ID of the chunk

        Returns:
            ParentChunk or None if not found
        """
        import time
        t0 = time.time()

        try:
            file_path = self.store_dir / f"{chunk_id}.json"
            if not file_path.exists():
                return None

            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            t1 = time.time()
            if t1 - t0 > 0.1:  # Log if slow
                self.log.warning(f"[DOCSTORE] Slow read {chunk_id}: {t1-t0:.2f}s")

            return ParentChunk(**data)

        except Exception as e:
            self.log.error(f"Failed to get parent chunk {chunk_id}: {e}")
            return None

    def get_by_file(self, file_name: str) -> list:
        """
        Get all parent chunks for a file

        Args:
            file_name: Name of the source file

        Returns:
            List of ParentChunk objects
        """
        chunks = []
        for file_path in self.store_dir.glob("*.json"):
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
            except Exception as e:
                self.log.warning(f"Failed to read parent chunk {file_path.name}: {e}")
                continue

            if data.get("file_name") == file_name:
                chunks.append(ParentChunk(**data))
        return chunks

    def delete(self, chunk_id: str) -> bool:
        """
        Delete a parent chunk

        Args:
            chunk_id: ID of the chunk to delete

        Returns:
            True if successful
        """
        try:
            file_path = self.store_dir / f"{chunk_id}.json"
            if file_path.exists():
                file_path.unlink()
                self.log.debug(f"Deleted parent chunk: {chunk_id}")
                return True
            return False

        except Exception as e:
            self.log.error(f"Failed to delete parent chunk {chunk_id}: {e}")
            return False

    def clear(self, file_name: str = None) -> int:
        """
        Clear all chunks, optionally for a specific file

        Args:
            file_name: Optional file name filter

        Returns:
            Number of deleted files
        """
        count = 0
        for file_path in self.store_dir.glob("*.json"):
            should_delete = file_name is None
            if file_name is not None:
                try:
                    data = json.loads(file_path.read_text(encoding="utf-8"))
                    should_delete = data.get("file_name") == file_name
                except Exception as e:
                    self.log.warning(f"Failed to inspect {file_path.name} during clear: {e}")
                    should_delete = False

            if should_delete:
                file_path.unlink()
                count += 1

        self.log.info(f"Cleared {count} chunks")
        return count
