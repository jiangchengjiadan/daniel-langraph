# src/parser/base_parser.py
"""Base parser interface for different document types"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple
from pathlib import Path

from ..models import SlideContent, ImageInfo


class BaseParser(ABC):
    """Base class for document parsers"""

    @abstractmethod
    def parse(self, file_path: str) -> Tuple[List[SlideContent], List[ImageInfo]]:
        """
        Parse document and extract content

        Args:
            file_path: Path to the document file

        Returns:
            Tuple of (slides_content, images)
        """
        pass

    @abstractmethod
    def get_supported_extensions(self) -> List[str]:
        """
        Get list of supported file extensions

        Returns:
            List of file extensions (e.g., ['.pdf', '.txt'])
        """
        pass
