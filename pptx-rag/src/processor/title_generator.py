# src/processor/title_generator.py
"""Generate or fix titles for PPT slides - text-based extraction only"""

from typing import Optional, List
import re

from ..logging import log


# Titles that indicate an invalid/ignore page
INVALID_TITLES = {
    "目录", "contents", "content",
    "感谢", "谢谢", "thank", "thanks",
    "封面", "cover", "标题", "title",
}

# Keywords that indicate an invalid page (check for partial match)
INVALID_KEYWORDS = [
    "感谢", "谢谢", "聆听", "contents", "目录",
]


def is_valid_title(title: Optional[str]) -> bool:
    """
    Check if a title is valid (not an ignored page)

    Args:
        title: The title to check

    Returns:
        True if title is valid
    """
    if not title:
        return False
    title_lower = title.lower().strip()
    # Remove spaces for keyword matching (e.g., "感 谢" -> "感谢")
    title_no_space = title_lower.replace(" ", "").replace("　", "")

    # Check exact match
    if title in INVALID_TITLES:
        return False
    # Check if title contains invalid keywords (after removing spaces)
    for keyword in INVALID_KEYWORDS:
        keyword_no_space = keyword.lower().replace(" ", "")
        if keyword_no_space in title_no_space:
            return False
    return True


class TitleGenerator:
    """Generator for creating slide titles from text content only"""

    def __init__(self):
        self.log = log.bind(module="title_generator")

    def generate(self, text: str, existing_title: Optional[str] = None) -> Optional[str]:
        """
        Generate or extract a title for slide content from text.

        Priority:
        1. Return existing_title if valid (non-empty and not placeholder)
        2. Extract from text patterns (numbered items, etc.)
        3. Return None if cannot extract (title is optional)

        Args:
            text: Slide text content
            existing_title: Existing title if available from PPT

        Returns:
            Generated title or None if cannot extract
        """
        self.log.debug(f"Generating title, existing_title: {existing_title}")

        # Step 1: Return existing valid title immediately (no LLM call)
        if existing_title and existing_title.strip():
            placeholder_titles = ["无标题", "Slide", "Slide title"]
            if existing_title not in placeholder_titles:
                self.log.info(f"Using existing title: {existing_title}")
                return existing_title.strip()
            else:
                self.log.info(f"Existing title is placeholder '{existing_title}', will try to extract from text")

        # Step 2: Extract title from text patterns
        if not text or len(text.strip()) < 5:
            self.log.debug("Text content too short, cannot extract title")
            return None

        title = self._extract_from_text(text)
        if title:
            self.log.info(f"Extracted title from text: {title}")
            return title

        # Step 3: Cannot extract title, return None
        self.log.debug("Could not extract title from text")
        return None

    def _extract_from_text(self, text: str) -> Optional[str]:
        """
        Extract title from text patterns.

        Patterns:
        - Numbered items: "1. xxx", "一、xxx", "（一）xxx"
        - Short first line (< 20 chars)
        - Lines with 、 separator
        """
        lines = text.strip().split('\n')

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Pattern 1: Numbered items
            # "1. xxx", "2. xxx"
            match = re.match(r'^[\d]+\.\s*(.+)$', line)
            if match:
                title = match.group(1).strip()
                if len(title) <= 20:
                    return title

            # Pattern 2: Chinese numbered with 、 separator
            # "一、xxx", "（一）xxx", "1、xxx"
            match = re.match(r'^[\u4e00-\u9fa5\d\uff11-\uff19（）\(\)]{1,3}[、\.]\s*(.+)$', line)
            if match:
                title = match.group(1).strip()
                if len(title) <= 20:
                    return title

            # Pattern 3: Short line as title (likely a header)
            if len(line) <= 20 and len(line) >= 2:
                return line

            # Pattern 4: Extract before first 、 if line is a list item
            if '、' in line:
                parts = line.split('、')
                first_part = parts[0].strip()
                # Check if first part looks like a short title/header
                if 2 <= len(first_part) <= 15:
                    return first_part

        return None


def generate_title(text: str, existing_title: Optional[str] = None) -> Optional[str]:
    """
    Convenience function to extract title from text.

    Args:
        text: Slide text content
        existing_title: Existing title if available

    Returns:
        Extracted title or None if cannot extract
    """
    generator = TitleGenerator()
    return generator.generate(text, existing_title)


def filter_invalid_slides(slides: List, titles: dict = None) -> list:
    """
    Filter out slides with invalid titles (目录, 感谢, etc.)

    Args:
        slides: List of slide objects with page_number and title attributes
        titles: Optional dict of page_number -> title

    Returns:
        List of valid slides
    """
    valid_slides = []
    invalid_pages = []

    for slide in slides:
        slide_title = None
        if titles and slide.page_number in titles:
            slide_title = titles[slide.page_number]
        elif hasattr(slide, 'title'):
            slide_title = slide.title

        if is_valid_title(slide_title):
            valid_slides.append(slide)
        else:
            invalid_pages.append(slide.page_number)

    if invalid_pages:
        log.info(f"Filtered out {len(invalid_pages)} invalid pages: {invalid_pages}")

    return valid_slides
