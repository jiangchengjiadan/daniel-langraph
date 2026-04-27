"""节点辅助函数"""


def extract_text_content(content) -> str:
    """
    从消息 content 中提取纯文本。

    Agent Chat UI / LangGraph Server 可能发送 list 格式的 content（OpenAI 多模态格式），
    例如 [{"type": "text", "text": "你好"}]，需要将其转换为纯字符串。
    """
    if isinstance(content, list):
        return " ".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        )
    return content if isinstance(content, str) else str(content)
