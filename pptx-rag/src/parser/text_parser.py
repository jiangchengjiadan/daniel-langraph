# src/parser/text_parser.py
"""Text document parser"""

from pathlib import Path
from typing import List, Tuple

from .base_parser import BaseParser
from ..models import SlideContent, ImageInfo
from ..logging import log


class TextParser(BaseParser):
    """Parser for text documents"""

    def __init__(self, chunk_lines: int = 50):
        """
        Initialize text parser

        Args:
            chunk_lines: Number of lines per chunk/page
        """
        self.log = log.bind(module="text_parser")
        self.chunk_lines = chunk_lines

    def get_supported_extensions(self) -> List[str]:
        return ['.txt', '.md', '.markdown', '.log', '.text']

    def parse(self, file_path: str) -> Tuple[List[SlideContent], List[ImageInfo]]:
        """
        Parse text document

        Args:
            file_path: Path to text file

        Returns:
            Tuple of (slides_content, images)
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Text file not found: {file_path}")

        self.log.info(f"Parsing text file: {file_path}")

        slides_content = []

        try:
            # Read text file with encoding detection
            text = self._read_text_file(file_path)

            # Split into chunks by lines
            lines = text.split('\n')
            total_lines = len(lines)

            page_num = 1
            for i in range(0, total_lines, self.chunk_lines):
                chunk_lines = lines[i:i + self.chunk_lines]
                chunk_text = '\n'.join(chunk_lines).strip()

                if not chunk_text:
                    continue

                # Extract title from first line of chunk
                title = self._extract_title_from_chunk(chunk_lines)

                slide = SlideContent(
                    page_number=page_num,
                    title=title,
                    text=chunk_text,
                    notes="",
                    images=[],
                )
                slides_content.append(slide)
                page_num += 1

            self.log.info(f"Extracted {len(slides_content)} chunks from text file")

        except Exception as e:
            self.log.error(f"Failed to parse text file: {e}")
            raise

        return slides_content, []

    def _read_text_file(self, file_path: Path) -> str:
        """Read text file with encoding detection"""
        # Try common encodings
        encodings = ['utf-8', 'utf-8-sig', 'gb18030', 'gbk', 'gb2312', 'latin-1']

        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    return f.read()
            except (UnicodeDecodeError, LookupError):
                continue

        # Fallback: read as binary and decode with errors='ignore'
        with open(file_path, 'rb') as f:
            return f.read().decode('utf-8', errors='ignore')

    def _extract_title_from_chunk(self, lines: List[str]) -> str:
        """Extract title from chunk (first meaningful line)"""
        for line in lines:
            line = line.strip()
            # Skip empty lines and very long lines
            if line and 2 <= len(line) <= 100:
                # Check if it looks like a heading
                if line.startswith('#'):  # Markdown heading
                    return line.lstrip('#').strip()
                elif line.isupper() and len(line.split()) <= 10:  # ALL CAPS title
                    return line
                elif len(line.split()) <= 15:  # Short line, likely title
                    return line

        return None


def parse_text(file_path: str, chunk_lines: int = 50) -> Tuple[List[SlideContent], List[ImageInfo]]:
    """
    Convenience function to parse text file

    Args:
        file_path: Path to text file
        chunk_lines: Number of lines per chunk

    Returns:
        Tuple of (slides_content, images)
    """
    parser = TextParser(chunk_lines=chunk_lines)
    return parser.parse(file_path)
