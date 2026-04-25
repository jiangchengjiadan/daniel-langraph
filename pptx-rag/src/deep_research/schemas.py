"""Schemas for the deep research workflow."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ResearchTodo(BaseModel):
    """A planned research task item."""

    content: str
    status: str = "pending"


class ResearchArtifact(BaseModel):
    """A generated artifact in the research workspace."""

    label: str
    path: str


class ResearchEvidence(BaseModel):
    """Normalized evidence hit used in the research workflow."""

    file_name: str
    page_number: int
    title: str = ""
    content: str
    parent_id: Optional[str] = None


class ResearchResult(BaseModel):
    """Result of a deep research task execution."""

    task_id: str
    task: str
    output_mode: str
    execution_mode: str = "service"
    execution_note: str = ""
    selected_documents: List[str] = Field(default_factory=list)
    todos: List[ResearchTodo] = Field(default_factory=list)
    artifacts: List[ResearchArtifact] = Field(default_factory=list)
    document_overview: str = ""
    final_report: str = ""
    quality_summary: str = ""
    created_at: datetime = Field(default_factory=datetime.now)
