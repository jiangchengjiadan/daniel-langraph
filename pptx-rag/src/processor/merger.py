# src/processor/merger.py
"""Merge consecutive pages based on title similarity or manual marks"""

import re
from typing import List, Dict, Tuple, Optional
from ..models import SlideContent, MergeGroup
from ..logging import log


class Merger:
    """Merger for combining consecutive pages"""

    def __init__(self):
        self.log = log.bind(module="merger")

    def check_title_similarity(
        self, title1: str, title2: str, threshold: float = 0.7
    ) -> bool:
        """
        Check if two titles are similar enough to merge

        Args:
            title1: First title
            title2: Second title
            threshold: Similarity threshold (0-1)

        Returns:
            True if titles are similar
        """
        if not title1 or not title2:
            return False

        # Exact match
        if title1 == title2:
            return True

        # Check if one contains the other
        if title1 in title2 or title2 in title1:
            return True

        # Simple word-based similarity
        words1 = set(title1.lower().split())
        words2 = set(title2.lower().split())

        if not words1 or not words2:
            return False

        intersection = words1 & words2
        union = words1 | words2

        similarity = len(intersection) / len(union)
        return similarity >= threshold

    def parse_manual_marks(self, notes: str) -> Dict[str, bool]:
        """
        Parse manual merge marks from slide notes

        Marks:
        - <START_BLOCK>: Start of a merge block
        - <END_BLOCK>: End of a merge block

        Args:
            notes: Slide notes text

        Returns:
            Dict with start_block and end_block flags
        """
        return {
            "start_block": "<START_BLOCK>" in notes.upper(),
            "end_block": "<END_BLOCK>" in notes.upper(),
        }

    def merge_continuous_pages(
        self,
        slides_content: List[SlideContent],
        titles: Dict[int, str] = None,
    ) -> List[MergeGroup]:
        """
        Merge consecutive pages based on criteria

        Args:
            slides_content: List of slide content
            titles: Optional dict of page numbers to titles

        Returns:
            List of MergeGroup objects
        """
        if not slides_content:
            return []

        self.log.info(f"Merging {len(slides_content)} pages")

        merge_groups: List[MergeGroup] = []
        current_group_start = slides_content[0].page_number
        current_group_pages = [slides_content[0].page_number]
        current_title = titles.get(slides_content[0].page_number) if titles else slides_content[0].title

        for i in range(1, len(slides_content)):
            slide = slides_content[i]
            slide_title = titles.get(slide.page_number) if titles else slide.title if slide else None

            # Check for manual marks
            current_notes = slides_content[i - 1].notes if i > 0 else ""
            slide_notes = slide.notes

            current_marks = self.parse_manual_marks(current_notes)
            slide_marks = self.parse_manual_marks(slide_notes)

            # End current group if END_BLOCK found
            if current_marks.get("end_block"):
                merge_groups.append(MergeGroup(
                    start_page=current_group_start,
                    end_page=slides_content[i - 1].page_number,
                    reason="手动标记结束",
                    page_chunks=list(range(current_group_start, slides_content[i - 1].page_number + 1)),
                ))
                current_group_start = slide.page_number
                current_group_pages = [slide.page_number]
                current_title = slide_title
                continue

            # Start new group if START_BLOCK found
            if slide_marks.get("start_block"):
                if len(current_group_pages) > 1:
                    merge_groups.append(MergeGroup(
                        start_page=current_group_start,
                        end_page=slides_content[i - 1].page_number,
                        reason="手动标记开始",
                        page_chunks=list(range(current_group_start, slides_content[i - 1].page_number + 1)),
                    ))
                current_group_start = slide.page_number
                current_group_pages = [slide.page_number]
                current_title = slide_title
                continue

            # Check title similarity
            if current_title and slide_title:
                if self.check_title_similarity(current_title, slide_title):
                    current_group_pages.append(slide.page_number)
                    continue

            # No merge criteria met, end current group
            if len(current_group_pages) > 0:
                # Determine reason based on actual group size and title consistency
                if len(current_group_pages) > 1:
                    reason = "标题相同"
                else:
                    reason = "单独页面"
                merge_groups.append(MergeGroup(
                    start_page=current_group_start,
                    end_page=slides_content[i - 1].page_number,
                    reason=reason,
                    page_chunks=list(range(current_group_start, slides_content[i - 1].page_number + 1)),
                ))

            current_group_start = slide.page_number
            current_group_pages = [slide.page_number]
            current_title = slide_title

        # Don't forget the last group
        if current_group_pages:
            merge_groups.append(MergeGroup(
                start_page=current_group_start,
                end_page=slides_content[-1].page_number,
                reason="最后页面",
                page_chunks=list(range(current_group_start, slides_content[-1].page_number + 1)),
            ))

        self.log.info(f"Created {len(merge_groups)} merge groups")
        return merge_groups


def check_title_similarity(title1: str, title2: str, threshold: float = 0.7) -> bool:
    """
    Convenience function to check title similarity

    Args:
        title1: First title
        title2: Second title
        threshold: Similarity threshold

    Returns:
        True if titles are similar
    """
    merger = Merger()
    return merger.check_title_similarity(title1, title2, threshold)


def merge_continuous_pages(
    slides_content: List[SlideContent],
    titles: Dict[int, str] = None,
) -> List[MergeGroup]:
    """
    Convenience function to merge consecutive pages

    Args:
        slides_content: List of slide content
        titles: Optional dict of page numbers to titles

    Returns:
        List of MergeGroup objects
    """
    merger = Merger()
    return merger.merge_continuous_pages(slides_content, titles)
