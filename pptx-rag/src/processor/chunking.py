# src/processor/chunking.py
"""Create page chunks for vector storage"""

import hashlib
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from urllib.parse import quote

from ..models import PageChunk, SlideContent, ImageInfo
from ..logging import log
from ..config import config


class ChunkingProcessor:
    """Processor for creating chunks from slide content"""

    def __init__(self):
        self.log = log.bind(module="chunking")

    def _get_file_hash(self, file_name: str) -> str:
        """Get 8-character hash prefix for a file name"""
        hash_val = hashlib.md5(file_name.encode("utf-8")).hexdigest()[:8]
        return hash_val

    def create_chunk(
        self,
        slide_content: SlideContent,
        images: List[ImageInfo] = None,
        file_name: str = "",
        title: Optional[str] = None,
        image_server_url: str = "",
    ) -> PageChunk:
        """
        Create a PageChunk from slide content

        Args:
            slide_content: Extracted slide content
            images: List of extracted images
            file_name: Name of the source file
            title: Optional generated title (overrides slide_content.title)

        Returns:
            PageChunk object
        """
        # Use provided title, fall back to slide_content.title
        effective_title = title or slide_content.title

        # Build content with images
        content_parts = []

        # Add title first
        if effective_title:
            content_parts.append(f"# {effective_title}")

        # Add main text content
        if slide_content.text:
            content_parts.append(slide_content.text)

        # Add extracted images with placeholders (after text)
        if images:
            for img in images:
                desc = img.description or f"第{slide_content.page_number}页图片"
                # Use full URL if image_server_url is provided
                if image_server_url:
                    # Convert absolute path to relative path from data/images/
                    img_path = Path(img.path)
                    # Get relative path like "filename/6_1.png"
                    try:
                        img_rel_path = img_path.relative_to(config.data_dir / "images")
                    except ValueError:
                        # Fallback: use filename from path
                        img_rel_path = f"{img_path.parent.name}/{img_path.name}"
                    # URL encode the path to handle special characters (spaces, chinese, etc.)
                    img_url = f"{image_server_url}/{quote(str(img_rel_path), safe='/')}"
                else:
                    img_url = img.path
                content_parts.append(f"![{desc}]({img_url})")

        # Add notes if present
        if slide_content.notes:
            content_parts.append(f"【备注】{slide_content.notes}")

        content = "\n\n".join(content_parts)

        file_hash = self._get_file_hash(file_name)
        chunk = PageChunk(
            id=f"{file_hash}_{slide_content.page_number}",
            file_name=file_name,
            page_number=slide_content.page_number,
            content=content,
            title=effective_title,
            metadata={
                "has_images": len(images) > 0 if images else False,
            },
        )

        self.log.debug(f"Created chunk: {chunk.id}")
        return chunk

    def create_chunks(
        self,
        slides_content: List[SlideContent],
        all_images: List[ImageInfo],
        file_name: str,
        titles: Dict[int, str] = None,
        image_server_url: str = "",
    ) -> List[PageChunk]:
        """
        Create chunks for multiple slides

        Args:
            slides_content: List of slide content
            all_images: List of all extracted images
            file_name: Name of the source file
            titles: Optional dict mapping page_number to title
            image_server_url: Base URL for image server

        Returns:
            List of PageChunk objects
        """
        # Group images by page
        images_by_page = {}
        for img in all_images:
            if img.page_number not in images_by_page:
                images_by_page[img.page_number] = []
            images_by_page[img.page_number].append(img)

        chunks = []
        for slide in slides_content:
            page_images = images_by_page.get(slide.page_number, [])
            # Get generated title if available
            slide_title = titles.get(slide.page_number) if titles else None

            chunk = self.create_chunk(
                slide, page_images, file_name, slide_title, image_server_url
            )
            chunks.append(chunk)

        self.log.info(f"Created {len(chunks)} chunks")
        return chunks


def create_page_chunk(
    slide_content: SlideContent,
    images: List[ImageInfo] = None,
    file_name: str = "",
    title: Optional[str] = None,
    image_server_url: str = "",
) -> PageChunk:
    """
    Convenience function to create a page chunk

    Args:
        slide_content: Extracted slide content
        images: List of extracted images
        file_name: Name of the source file
        title: Optional generated title
        image_server_url: Base URL for image server

    Returns:
        PageChunk object
    """
    processor = ChunkingProcessor()
    return processor.create_chunk(slide_content, images, file_name, title, image_server_url)
