# src/retriever/parent_retriever.py
"""Parent chunk retrieval and content replacement for RAG"""

from typing import List, Dict, Set, Optional, Tuple
from ..models import PageChunk, ParentChunk
from ..storage.doc_store import DocStore
from ..logging import log


class ParentRetriever:
    """
    Handle parent chunk retrieval and content replacement.

    When child chunks are retrieved, this class:
    1. Checks if each child chunk has a parent_id in metadata
    2. Fetches parent chunk content from doc_store
    3. Deduplicates (multiple children -> same parent)
    4. Replaces child content with parent content
    """

    def __init__(self, doc_store: DocStore = None):
        """
        Initialize parent retriever

        Args:
            doc_store: Optional DocStore instance
        """
        self.log = log.bind(module="parent_retriever")
        self.doc_store = doc_store or DocStore()

    def replace_with_parents(
        self,
        chunks: List[PageChunk],
        parent_ids: Dict[str, str] = None,
    ) -> Tuple[List[PageChunk], Dict[str, ParentChunk]]:
        """
        Replace child chunks with their parent chunks.

        Args:
            chunks: List of retrieved PageChunks
            parent_ids: Optional dict mapping child_id -> parent_id

        Returns:
            Tuple of (modified_chunks, used_parents)
            - modified_chunks: Chunks with parent content where applicable
            - used_parents: Dict of parent_id -> ParentChunk for all used parents
        """
        if not chunks:
            return [], {}

        # Collect parent IDs from chunks and parent_ids dict
        child_to_parent: Dict[str, str] = {}

        # First, collect from chunk metadata
        for chunk in chunks:
            parent_id = chunk.metadata.get("parent_id")
            if parent_id:
                child_to_parent[chunk.id] = parent_id

        # Override with provided parent_ids if given
        if parent_ids:
            child_to_parent.update(parent_ids)

        if not child_to_parent:
            self.log.debug("No parent IDs found in chunks")
            return chunks, {}

        # Get unique parent IDs
        unique_parent_ids: Set[str] = set(child_to_parent.values())
        self.log.info(f"Found {len(unique_parent_ids)} unique parent IDs for {len(chunks)} chunks")

        # Fetch all parent chunks
        used_parents: Dict[str, ParentChunk] = {}
        for parent_id in unique_parent_ids:
            parent = self.doc_store.get_by_id(parent_id)
            if parent:
                used_parents[parent_id] = parent
                self.log.debug(f"Loaded parent chunk: {parent_id}")
            else:
                # Debug: show what parent IDs we're looking for
                self.log.warning(f"Parent chunk not found: {parent_id}")
                # Check if file exists
                import os
                expected_path = self.doc_store.store_dir / f"{parent_id}.json"
                self.log.warning(f"  Expected file: {expected_path}, exists: {os.path.exists(expected_path)}")

        if not used_parents:
            self.log.warning("No parent chunks found in doc_store")
            return chunks, {}

        # Replace child chunks with parent chunks
        # Group chunks by parent_id
        chunks_by_parent: Dict[str, List[PageChunk]] = {}
        for chunk in chunks:
            parent_id = child_to_parent.get(chunk.id)
            if parent_id and parent_id in used_parents:
                if parent_id not in chunks_by_parent:
                    chunks_by_parent[parent_id] = []
                chunks_by_parent[parent_id].append(chunk)

        # Build result: parent chunks + remaining single child chunks
        result_chunks: List[PageChunk] = []

        for parent_id, parent in used_parents.items():
            if parent_id in chunks_by_parent:
                # Replace multiple child chunks with one parent chunk
                # Create a new chunk that represents the parent
                parent_chunk = PageChunk(
                    id=parent.id,
                    file_name=parent.file_name,
                    page_number=parent.start_page,  # Use start page as representative
                    content=parent.content,
                    title=f"整体主题：{parent.metadata.get('page_count', 0)}页内容",
                    metadata={
                        **parent.metadata,
                        "is_parent": True,
                        "child_count": len(parent.child_chunk_ids),
                        "child_pages": list(range(parent.start_page, parent.end_page + 1)),
                    },
                )
                result_chunks.append(parent_chunk)
                self.log.debug(f"Replaced {len(chunks_by_parent[parent_id])} child chunks with parent {parent_id}")

        # Add chunks that don't have parents (single-page groups)
        for chunk in chunks:
            parent_id = child_to_parent.get(chunk.id)
            if not parent_id or parent_id not in used_parents:
                result_chunks.append(chunk)

        self.log.info(f"Returning {len(result_chunks)} chunks ({len(used_parents)} parents, {len(result_chunks) - len(used_parents)} single chunks)")
        return result_chunks, used_parents

    def get_parent_context(
        self,
        chunks: List[PageChunk],
        parent_ids: Dict[str, str] = None,
    ) -> str:
        """
        Get combined parent context for LLM.

        Args:
            chunks: List of retrieved PageChunks
            parent_ids: Optional dict mapping child_id -> parent_id

        Returns:
            Combined context string for LLM
        """
        result_chunks, used_parents = self.replace_with_parents(chunks, parent_ids)

        if not result_chunks:
            return ""

        # Build context string
        context_parts = []
        for i, chunk in enumerate(result_chunks, 1):
            is_parent = chunk.metadata.get("is_parent", False)
            if is_parent:
                page_range = chunk.metadata.get("child_pages", [])
                context_parts.append(
                    f"--- 参考来源 {i} (父块，页面 {min(page_range)}-{max(page_range)}) ---\n{chunk.content}"
                )
            else:
                context_parts.append(
                    f"--- 参考来源 {i} (页面 {chunk.page_number}) ---\n{chunk.content}"
                )

        return "\n\n".join(context_parts)


def replace_with_parents(
    chunks: List[PageChunk],
    parent_ids: Dict[str, str] = None,
    doc_store: DocStore = None,
) -> Tuple[List[PageChunk], Dict[str, ParentChunk]]:
    """
    Convenience function to replace child chunks with parent chunks.

    Args:
        chunks: List of retrieved PageChunks
        parent_ids: Optional dict mapping child_id -> parent_id
        doc_store: Optional DocStore instance

    Returns:
        Tuple of (modified_chunks, used_parents)
    """
    retriever = ParentRetriever(doc_store)
    return retriever.replace_with_parents(chunks, parent_ids)


def get_parent_context(
    chunks: List[PageChunk],
    parent_ids: Dict[str, str] = None,
    doc_store: DocStore = None,
) -> str:
    """
    Convenience function to get combined parent context for LLM.

    Args:
        chunks: List of retrieved PageChunks
        parent_ids: Optional dict mapping child_id -> parent_id
        doc_store: Optional DocStore instance

    Returns:
        Combined context string for LLM
    """
    retriever = ParentRetriever(doc_store)
    return retriever.get_parent_context(chunks, parent_ids)
