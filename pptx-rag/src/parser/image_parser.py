# src/parser/image_parser.py
"""Image document parser - uses Vision API to understand image content"""

import hashlib
import shutil
from pathlib import Path
from typing import List, Tuple

from langchain_core.messages import HumanMessage

from .base_parser import BaseParser
from ..models import SlideContent, ImageInfo
from ..config import config
from ..logging import log


class ImageParser(BaseParser):
    """Parser for image files using Vision API"""

    def __init__(self):
        self.log = log.bind(module="image_parser")

    def get_supported_extensions(self) -> List[str]:
        return ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff']

    def parse(self, file_path: str) -> Tuple[List[SlideContent], List[ImageInfo]]:
        """
        Parse image file using Vision API

        Args:
            file_path: Path to image file

        Returns:
            Tuple of (slides_content, images)
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Image file not found: {file_path}")

        self.log.info(f"Parsing image: {file_path}")

        slides_content = []
        images = []

        try:
            # Extract text from image using Vision API
            description = self._analyze_image_with_vision(file_path)

            # Save image to images directory
            file_name = file_path.stem
            file_hash = hashlib.md5(file_name.encode("utf-8")).hexdigest()[:8]
            images_dir = config.images_dir / file_hash
            images_dir.mkdir(parents=True, exist_ok=True)

            # Copy image to storage
            image_filename = f"1_0{file_path.suffix}"
            saved_path = images_dir / image_filename
            shutil.copy2(file_path, saved_path)

            # Create image info
            image_url = f"{config.image_server_url}/{file_hash}/{image_filename}"
            image_info = ImageInfo(
                page_number=1,
                image_idx=0,
                path=str(saved_path),
                description=description,
                mimetype=self._get_mimetype(file_path.suffix),
            )
            images.append(image_info)

            # Create slide content with image
            slide = SlideContent(
                page_number=1,
                title=file_path.stem,
                text=f"{description}\n\n![{file_path.stem}]({image_url})",
                notes="",
                images=[image_info.model_dump()],
            )
            slides_content.append(slide)

            self.log.info(f"Analyzed image: {file_path.name}")

        except Exception as e:
            self.log.error(f"Failed to parse image: {e}")
            raise

        return slides_content, images

    def _analyze_image_with_vision(self, image_path: Path) -> str:
        """Use Vision API to analyze image content"""
        try:
            from langchain_openai import ChatOpenAI

            llm = ChatOpenAI(
                model=config.llm_model,
                base_url=config.api_base_url,
                api_key=config.api_key,
                temperature=0.1,
            )

            message = HumanMessage(
                content=[
                    {
                        "type": "text",
                        "text": "请详细描述这张图片的内容，包括：1. 图片主题 2. 关键信息 3. 文字内容（如有）。用中文回答，不超过200字。"
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"file://{image_path.absolute()}"},
                    },
                ]
            )

            response = llm.invoke([message])
            description = response.content.strip()
            self.log.debug(f"Vision analysis: {description[:100]}...")
            return description

        except Exception as e:
            self.log.warning(f"Vision API failed, using filename as description: {e}")
            return f"图片：{image_path.stem}"

    def _get_mimetype(self, extension: str) -> str:
        """Get MIME type from file extension"""
        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.bmp': 'image/bmp',
            '.webp': 'image/webp',
            '.tiff': 'image/tiff',
        }
        return mime_types.get(extension.lower(), 'image/jpeg')


def parse_image(file_path: str) -> Tuple[List[SlideContent], List[ImageInfo]]:
    """
    Convenience function to parse image file

    Args:
        file_path: Path to image file

    Returns:
        Tuple of (slides_content, images)
    """
    parser = ImageParser()
    return parser.parse(file_path)
