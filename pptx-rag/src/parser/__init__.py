# parser/__init__.py
"""Document Parser Package - supports PPT, PDF, Text, Image"""

from .base_parser import BaseParser
from .pptx_parser import extract_text_from_pptx, PptxParser
from .pdf_parser import PDFParser, parse_pdf
from .text_parser import TextParser, parse_text
from .image_parser import ImageParser, parse_image
from .image_handler import extract_images, ImageHandler

__all__ = [
    "BaseParser",
    "extract_text_from_pptx",
    "PptxParser",
    "PDFParser",
    "parse_pdf",
    "TextParser",
    "parse_text",
    "ImageParser",
    "parse_image",
    "extract_images",
    "ImageHandler",
]
