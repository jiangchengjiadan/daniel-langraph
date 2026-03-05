# src/processor/parent_builder.py
"""Build parent chunks from merged page chunks"""

import hashlib
import time
from typing import List, Dict, Tuple
from ..models import ParentChunk, PageChunk, MergeGroup
from ..logging import log


class ParentBuilder:
    """Builder for creating parent chunks from merged pages"""

    def __init__(self):
        self.log = log.bind(module="parent_builder")

    def _get_file_hash(self, file_name: str) -> str:
        """Get 8-character hash prefix for a file name"""
        hash_val = hashlib.md5(file_name.encode("utf-8")).hexdigest()[:8]
        return hash_val

    def build(
        self,
        merge_group: MergeGroup,
        page_chunks: Dict[int, PageChunk],
        file_name: str,
    ) -> Tuple[ParentChunk, Dict[str, str]]:
        """
        Build a parent chunk from a merge group.
        Only for merge groups with 2+ pages. Single-page groups return (None, {}).

        Args:
            merge_group: MergeGroup containing page numbers
            page_chunks: Dict mapping page number to PageChunk
            file_name: Name of the source file

        Returns:
            Tuple of (ParentChunk object or None, child_to_parent_map)
        """
        # Don't build parent for single page
        if len(merge_group.page_chunks) == 1:
            return None, {}

        # Collect child chunk IDs and content
        child_ids = []
        contents = []

        for page_num in merge_group.page_chunks:
            if page_num in page_chunks:
                chunk = page_chunks[page_num]
                child_ids.append(chunk.id)
                contents.append(chunk.content)

        # Build parent content (always multi-page at this point)
        # Format: # 整体主题 + --- separators
        first_chunk = page_chunks.get(merge_group.page_chunks[0])
        main_title = first_chunk.title if first_chunk else ""

        parts = [f"# 整体主题：{main_title}（第{merge_group.start_page}-{merge_group.end_page}页）\n"]

        for page_num in merge_group.page_chunks:
            if page_num in page_chunks:
                chunk = page_chunks[page_num]
                parts.append(f"---\n[第{page_num}页]\n{chunk.content}")

        parent_content = "\n".join(parts)

        file_hash = self._get_file_hash(file_name)
        parent_id = f"{file_hash}_parent_{merge_group.start_page}_{merge_group.end_page}"
        parent = ParentChunk(
            id=parent_id,
            file_name=file_name,
            start_page=merge_group.start_page,
            end_page=merge_group.end_page,
            content=parent_content,
            child_chunk_ids=child_ids,
            metadata={
                "merge_reason": merge_group.reason,
                "page_count": len(child_ids),
            },
        )

        # Build child -> parent mapping
        child_to_parent = {child_id: parent_id for child_id in child_ids}

        self.log.debug(f"Built parent chunk: {parent.id}")
        return parent, child_to_parent

    def build_all(
        self,
        merge_groups: List[MergeGroup],
        page_chunks: List[PageChunk],
        file_name: str,
    ) -> Tuple[List[ParentChunk], Dict[str, str]]:
        """
        Build parent chunks only from merge groups with multiple pages.
        Single-page groups don't need parent chunks - they use their child chunks directly.

        Args:
            merge_groups: List of MergeGroup objects
            page_chunks: List of PageChunk objects
            file_name: Name of the source file

        Returns:
            Tuple of (List of ParentChunk objects, child_to_parent_map)
        """
        # Index page chunks by page number
        chunks_by_page = {chunk.page_number: chunk for chunk in page_chunks}

        parents = []
        all_child_to_parent = {}

        for group in merge_groups:
            # Only build parent chunk if group has more than 1 page
            if len(group.page_chunks) > 1:
                parent, child_to_parent = self.build(group, chunks_by_page, file_name)
                parents.append(parent)
                all_child_to_parent.update(child_to_parent)
            else:
                self.log.debug(f"Skipping parent chunk for single page: {group.start_page}")

        skipped = len([g for g in merge_groups if len(g.page_chunks) == 1])
        self.log.info(f"Built {len(parents)} parent chunks (skipped {skipped} single-page groups)")
        return parents, all_child_to_parent


def build_parent_chunk(
    merge_group: MergeGroup,
    page_chunks: Dict[int, PageChunk],
    file_name: str,
) -> Tuple[ParentChunk, Dict[str, str]]:
    """
    Convenience function to build a parent chunk

    Args:
        merge_group: MergeGroup containing page numbers
        page_chunks: Dict mapping page number to PageChunk
        file_name: Name of the source file

    Returns:
        Tuple of (ParentChunk object, child_to_parent_map)
    """
    builder = ParentBuilder()
    return builder.build(merge_group, page_chunks, file_name)
