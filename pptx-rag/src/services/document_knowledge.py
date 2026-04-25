"""Reusable knowledge service built on top of the existing PPTX RAG modules."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import config
from ..logging import log
from ..models import PageChunk, ParentChunk, ProcessingStatus
from ..parser import ImageParser, PDFParser, PptxParser, TextParser
from ..processor import (
    ChunkingProcessor,
    Merger,
    ParentBuilder,
    filter_invalid_slides,
    generate_title,
)
from ..retriever import get_parent_context
from ..storage import DocStore, VectorStore
from ..retriever.hybrid_retriever import HybridRetriever


class DocumentKnowledgeService:
    """Document ingestion, retrieval, and context building utilities."""

    def __init__(self):
        self.log = log.bind(module="document_knowledge_service")
        self.config = config
        self.chunking_processor = ChunkingProcessor()
        self.merger = Merger()
        self.parent_builder = ParentBuilder()
        self.doc_store = DocStore()
        self.vector_store = VectorStore()
        self.hybrid_retriever = HybridRetriever(self.vector_store)
        self.config.ensure_directories()

    def _select_parser(self, file_ext: str):
        if file_ext in [".pptx", ".ppt"]:
            return PptxParser()
        if file_ext == ".pdf":
            return PDFParser()
        if file_ext in [".txt", ".md", ".markdown", ".log", ".text"]:
            return TextParser()
        if file_ext in [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff"]:
            return ImageParser()
        raise ValueError(f"Unsupported file format: {file_ext}")

    def load_document(
        self,
        file_path: str,
        on_progress: callable = None,
    ) -> Dict[str, Any]:
        """Load a document, build chunks, save parents, and update indexes."""
        file_path = Path(file_path)
        file_name = file_path.stem
        file_ext = file_path.suffix.lower()

        self.log.info(f"Loading document: {file_name} (type: {file_ext})")

        existing_docs = self.doc_store.get_by_file(file_name)
        if existing_docs:
            self.log.warning(f"File '{file_name}' already exists, clearing old data first...")
            self.clear(file_name)

        try:
            if on_progress:
                on_progress(
                    ProcessingStatus(
                        file_name=file_name,
                        status="processing",
                        progress=0.1,
                        current_step="解析文档内容",
                    )
                )

            parser = self._select_parser(file_ext)
            slides_content, images = parser.parse(str(file_path))
            self.log.info(f"Extracted {len(slides_content)} pages and {len(images)} images")

            if on_progress:
                on_progress(
                    ProcessingStatus(
                        file_name=file_name,
                        status="processing",
                        progress=0.2,
                        current_step="生成页面分块",
                    )
                )

            titles: Dict[int, str] = {}
            for slide in slides_content:
                titles[slide.page_number] = generate_title(slide.text, slide.title)

            if file_ext in [".pptx", ".ppt"]:
                valid_slides = filter_invalid_slides(slides_content, titles)
                valid_slides = [s for s in valid_slides if s.page_number != 1]
            else:
                valid_slides = slides_content

            if on_progress:
                on_progress(
                    ProcessingStatus(
                        file_name=file_name,
                        status="processing",
                        progress=0.45,
                        current_step="合并页面",
                    )
                )

            merge_groups = self.merger.merge_continuous_pages(valid_slides, titles)

            if on_progress:
                on_progress(
                    ProcessingStatus(
                        file_name=file_name,
                        status="processing",
                        progress=0.55,
                        current_step="创建分块",
                    )
                )

            page_chunks = self.chunking_processor.create_chunks(
                valid_slides,
                images,
                file_name,
                titles,
                self.config.image_server_url,
            )

            if on_progress:
                on_progress(
                    ProcessingStatus(
                        file_name=file_name,
                        status="processing",
                        progress=0.65,
                        current_step="构建父块",
                    )
                )

            parent_chunks, child_to_parent_map = self.parent_builder.build_all(
                merge_groups,
                page_chunks,
                file_name,
            )

            for chunk in page_chunks:
                if chunk.id in child_to_parent_map:
                    chunk.metadata["parent_id"] = child_to_parent_map[chunk.id]

            if on_progress:
                on_progress(
                    ProcessingStatus(
                        file_name=file_name,
                        status="processing",
                        progress=0.75,
                        current_step="保存数据",
                    )
                )

            for parent in parent_chunks:
                self.doc_store.save(parent)

            self.hybrid_retriever.add_documents(page_chunks)

            if on_progress:
                on_progress(
                    ProcessingStatus(
                        file_name=file_name,
                        status="processing",
                        progress=1.0,
                        current_step="完成",
                    )
                )

            return {
                "file_name": file_name,
                "slides_count": len(slides_content),
                "chunks_count": len(page_chunks),
                "parents_count": len(parent_chunks),
                "images_count": len(images),
            }
        except Exception as e:
            self.log.error(f"Failed to load document: {e}")
            if on_progress:
                on_progress(
                    ProcessingStatus(
                        file_name=file_name,
                        status="error",
                        error=str(e),
                    )
                )
            raise

    def list_documents(self) -> List[Dict[str, Any]]:
        """List all indexed documents."""
        file_map: Dict[str, Dict[str, Any]] = {}

        for parent_file in self.doc_store.store_dir.glob("*.json"):
            try:
                data = ParentChunk.model_validate_json(parent_file.read_text(encoding="utf-8"))
            except Exception as e:
                self.log.warning(f"Failed to parse parent file {parent_file.name}: {e}")
                continue

            if data.file_name not in file_map:
                file_map[data.file_name] = {
                    "file_name": data.file_name,
                    "pages": set(),
                    "chunks_count": 0,
                }

            file_map[data.file_name]["pages"].update(range(data.start_page, data.end_page + 1))
            file_map[data.file_name]["chunks_count"] += 1

        documents = []
        for file_name, info in file_map.items():
            sorted_pages = sorted(info["pages"])
            page_range = (
                f"{min(sorted_pages)}-{max(sorted_pages)}"
                if len(sorted_pages) > 1
                else str(sorted_pages[0])
            )
            documents.append(
                {
                    "file_name": file_name,
                    "pages": page_range,
                    "total_pages": len(sorted_pages),
                    "chunks_count": info["chunks_count"],
                }
            )

        documents.sort(key=lambda item: item["file_name"])
        return documents

    def retrieve_chunks(
        self,
        query: str,
        file_name: Optional[str] = None,
        k: Optional[int] = None,
    ) -> List[PageChunk]:
        """Retrieve page chunks with optional file filter."""
        return self.hybrid_retriever.get_relevant_documents(query, k=k, file_name=file_name)

    def build_parent_context(self, chunks: List[PageChunk]) -> str:
        """Build parent-aware context for answering or research."""
        child_to_parent = {}
        for chunk in chunks:
            parent_id = chunk.metadata.get("parent_id")
            if parent_id:
                child_to_parent[chunk.id] = parent_id
        return get_parent_context(chunks, child_to_parent, self.doc_store)

    def search_evidence(
        self,
        query: str,
        file_name: Optional[str] = None,
        k: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Retrieve evidence and return normalized payload for research workflows."""
        chunks = self.retrieve_chunks(query, file_name=file_name, k=k)
        context = self.build_parent_context(chunks) if chunks else ""

        hits = []
        for chunk in chunks:
            hits.append(
                {
                    "id": chunk.id,
                    "file_name": chunk.file_name,
                    "page_number": chunk.page_number,
                    "title": chunk.title or "",
                    "content": chunk.content,
                    "parent_id": chunk.metadata.get("parent_id"),
                }
            )

        return {
            "query": query,
            "file_name": file_name,
            "hits": hits,
            "context": context,
        }

    def get_page_content(self, file_name: str, pages: List[int]) -> List[Dict[str, Any]]:
        """Return page-level chunks for exact page inspection."""
        requested_pages = set(pages)
        page_chunks: Dict[int, PageChunk] = {}

        if self.vector_store.vector_store is None:
            return []

        for doc in self.vector_store.vector_store.docstore._dict.values():
            if doc.metadata.get("file_name") != file_name:
                continue
            page_number = doc.metadata.get("page_number", 0)
            if page_number not in requested_pages or page_number in page_chunks:
                continue
            page_chunks[page_number] = PageChunk(
                id=doc.metadata.get("id", ""),
                file_name=doc.metadata.get("file_name", ""),
                page_number=page_number,
                content=doc.page_content,
                title=doc.metadata.get("title"),
                metadata=doc.metadata,
            )

        results = []
        for page in sorted(requested_pages):
            chunk = page_chunks.get(page)
            if chunk:
                results.append(
                    {
                        "file_name": chunk.file_name,
                        "page_number": chunk.page_number,
                        "title": chunk.title or "",
                        "content": chunk.content,
                    }
                )
        return results

    def clear(self, file_name: Optional[str] = None) -> int:
        """Clear indexed data, optionally scoped to a single file."""
        if file_name:
            doc_count = self.doc_store.clear(file_name)
            vector_count = self.vector_store.delete_by_file(file_name) if self.vector_store else 0

            file_hash = hashlib.md5(file_name.encode("utf-8")).hexdigest()[:8]
            images_dir = self.config.images_dir / file_hash
            if images_dir.exists():
                shutil.rmtree(images_dir)

            deleted_uploads = 0
            for upload_file in self.config.upload_dir.glob(f"{file_name}.*"):
                upload_file.unlink()
                deleted_uploads += 1

            self.hybrid_retriever._initialize_bm25()
            self.log.info(
                f"Cleared data for {file_name}: {doc_count} parent chunks, "
                f"{vector_count} vector chunks, {deleted_uploads} uploads"
            )
            return doc_count

        doc_count = self.doc_store.clear()
        vector_count = self.vector_store.clear() if self.vector_store else 0

        if self.config.images_dir.exists():
            for item in self.config.images_dir.iterdir():
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()

        if self.config.upload_dir.exists():
            for item in self.config.upload_dir.iterdir():
                item.unlink()

        self.hybrid_retriever._initialize_bm25()
        self.log.info(f"Cleared all data: {doc_count} parent chunks, {vector_count} vector chunks")
        return doc_count
