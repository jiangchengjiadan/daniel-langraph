# src/models.py
"""Pydantic data models for PPTx RAG"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import uuid


class SlideContent(BaseModel):
    """Single slide content extracted from PPT"""
    page_number: int
    title: Optional[str] = None
    text: str = ""
    notes: str = ""
    images: List[Dict[str, Any]] = Field(default_factory=list)


class ImageInfo(BaseModel):
    """Image information extracted from PPT"""
    page_number: int
    image_idx: int
    path: str
    description: Optional[str] = ""
    mimetype: str = "image/png"


class PageChunk(BaseModel):
    """Single page chunk for vector storage"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    file_name: str
    page_number: int
    content: str
    title: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MergeGroup(BaseModel):
    """Group of consecutive pages to be merged"""
    start_page: int
    end_page: int
    reason: str
    page_chunks: List[int] = Field(default_factory=list)


class ParentChunk(BaseModel):
    """Parent chunk containing merged pages"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    file_name: str
    start_page: int
    end_page: int
    content: str
    child_chunk_ids: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AnswerResult(BaseModel):
    """Result from RAG question answering"""
    answer: str
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    referenced_pages: List[int] = Field(default_factory=list)


class ProcessingStatus(BaseModel):
    """Processing status for a document"""
    file_name: str
    status: str
    progress: float = 0.0
    current_step: str = ""
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
