# src/processor/visual_summary.py
"""Generate visual summaries for PPT slides using Vision API"""

from pathlib import Path

from ..config import config
from langchain_openai import ChatOpenAI
from ..logging import log


# System prompt for visual summary generation
VISUAL_SUMMARY_SYSTEM_PROMPT = """你是视觉理解专家。你的任务是根据PPT页面的图片，生成简洁的视觉摘要。

请分析图片中的：
1. 页面标题和主要标题
2. 关键内容点（文字、图表、数据等）
3. 视觉元素（图片、图表、表格等）

请用简洁的中文描述页面内容，不要超过100字。"""


class VisualSummaryGenerator:
    """Generator for creating visual summaries of slides"""

    def __init__(self):
        self.log = log.bind(module="visual_summary")
        self.llm = ChatOpenAI(
            model=config.llm_model,
            base_url=config.api_base_url,
            api_key=config.api_key,
            temperature=0.1,
        )

    def generate(self, image_path: str) -> str:
        """
        Generate visual summary for an image

        Args:
            image_path: Path to the slide image

        Returns:
            Visual summary text
        """
        self.log.info(f"Generating visual summary for: {image_path}")

        from langchain_core.messages import HumanMessage

        image_path = Path(image_path)
        if not image_path.exists():
            self.log.warning(f"Image not found: {image_path}")
            return ""

        try:
            message = HumanMessage(
                content=[
                    {"type": "text", "text": VISUAL_SUMMARY_SYSTEM_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": str(image_path.absolute())},
                    },
                ]
            )

            response = self.llm.invoke([message])
            summary = response.content.strip()

            # Remove thinking tags if present
            import re
            summary = re.sub(r"<thinking>.*?</thinking>", "", summary, flags=re.DOTALL)
            summary = re.sub(r"<think>.*?</think>", "", summary, flags=re.DOTALL)

            self.log.debug(f"Visual summary: {summary[:100]}...")
            return summary

        except Exception as e:
            self.log.error(f"Failed to generate visual summary: {e}")
            return ""


def generate_visual_summary(image_path: str) -> str:
    """
    Convenience function to generate visual summary

    Args:
        image_path: Path to the slide image

    Returns:
        Visual summary text
    """
    generator = VisualSummaryGenerator()
    return generator.generate(image_path)
