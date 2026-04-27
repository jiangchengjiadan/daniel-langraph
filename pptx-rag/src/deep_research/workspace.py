"""Workspace helpers for deep research artifacts."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from tempfile import gettempdir
from uuid import uuid4

from ..logging import log
from ..config import config


class ResearchWorkspaceManager:
    """Manage session-scoped workspace directories and files."""

    def __init__(self):
        preferred_base = config.workspace_dir / "sessions"
        self.base_dir = self._ensure_base_dir(preferred_base)

    def _ensure_base_dir(self, preferred_base: Path) -> Path:
        """Create a writable workspace directory, falling back to /tmp if needed."""
        try:
            preferred_base.mkdir(parents=True, exist_ok=True)
            return preferred_base
        except Exception as e:
            fallback = Path(gettempdir()) / "pptx-rag-workspace" / "sessions"
            fallback.mkdir(parents=True, exist_ok=True)
            log.warning(f"Workspace fallback enabled: {e}; using {fallback}")
            return fallback

    def create_session(self) -> str:
        task_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:8]}"
        session_dir = self.get_session_dir(task_id)
        try:
            for relative in ["evidence", "drafts", "final"]:
                (session_dir / relative).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            fallback_base = self._ensure_base_dir(Path(gettempdir()) / "pptx-rag-workspace" / "sessions")
            self.base_dir = fallback_base
            session_dir = self.get_session_dir(task_id)
            for relative in ["evidence", "drafts", "final"]:
                (session_dir / relative).mkdir(parents=True, exist_ok=True)
            log.warning(f"Workspace session creation fallback enabled: {e}; using {session_dir}")
        return task_id

    def get_session_dir(self, task_id: str) -> Path:
        return self.base_dir / task_id

    def write_text(self, task_id: str, relative_path: str, content: str) -> Path:
        path = self.get_session_dir(task_id) / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def read_text(self, task_id: str, relative_path: str) -> str:
        path = self.get_session_dir(task_id) / relative_path
        return path.read_text(encoding="utf-8")
