# src/parser/pdf_parser.py
"""PDF document parser"""

import hashlib
from pathlib import Path
from typing import List, Tuple, Dict, Any
import fitz  # PyMuPDF

from .base_parser import BaseParser
from ..models import SlideContent, ImageInfo
from ..logging import log


class PDFParser(BaseParser):
    """Parser for PDF documents"""

    def __init__(self):
        self.log = log.bind(module="pdf_parser")

    def get_supported_extensions(self) -> List[str]:
        return ['.pdf']

    def parse(self, file_path: str) -> Tuple[List[SlideContent], List[ImageInfo]]:
        """
        Parse PDF document

        Args:
            file_path: Path to PDF file

        Returns:
            Tuple of (slides_content, images)
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"PDF file not found: {file_path}")

        self.log.info(f"Parsing PDF: {file_path}")

        slides_content = []
        images = []

        try:
            doc = fitz.open(str(file_path))

            for page_num in range(len(doc)):
                page = doc[page_num]

                # Extract text
                text = page.get_text("text").strip()

                # Try to extract title from first line or first heading
                title = self._extract_title_from_text(text)

                # Create slide content
                slide = SlideContent(
                    page_number=page_num + 1,
                    title=title,
                    text=text,
                    notes="",
                    images=[],
                )
                slides_content.append(slide)

            doc.close()
            self.log.info(f"Extracted {len(slides_content)} pages from PDF")

        except Exception as e:
            self.log.error(f"Failed to parse PDF: {e}")
            raise

        return slides_content, images

    def _extract_title_from_text(self, text: str) -> str:
        """Extract title from page text (first non-empty line)"""
        if not text:
            return None

        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if line and len(line) <= 100:  # Reasonable title length
                return line

        return None


def parse_pdf(file_path: str) -> Tuple[List[SlideContent], List[ImageInfo]]:
    """
    Convenience function to parse PDF

    Args:
        file_path: Path to PDF file

    Returns:
        Tuple of (slides_content, images)
    """
    parser = PDFParser()
    return parser.parse(file_path)
