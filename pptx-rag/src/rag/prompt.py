# src/rag/prompt.py
"""RAG prompt templates"""

from langchain_core.prompts import ChatPromptTemplate


# System prompt for RAG question answering
SYSTEM_PROMPT = """你是 PPT 文档智能问答助手。你的任务是基于提供的 PPT 内容回答用户的问题。

重要要求：
1. 保留 Markdown 图片链接在回答中，这些图片能帮助更好地说明内容
2. 标注参考来源，格式为：「参考: 第 X-Y 页（文件名.pptx）」
3. 如果回答中包含图片，使用 Markdown 图片语法：`![描述](图片URL)`
4. 优先使用视觉摘要和原始文本内容来回答
5. 回答要简洁、准确、图文并茂

请基于以下检索到的内容回答问题。如果你不知道答案，请如实说明。"""


# Human prompt template
HUMAN_PROMPT = """用户问题: {question}

参考内容:
{context}

请根据以上内容回答用户的问题。"""


def get_system_prompt() -> str:
    """Get the system prompt"""
    return SYSTEM_PROMPT


def get_prompt_template() -> ChatPromptTemplate:
    """Get the chat prompt template"""
    return ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", HUMAN_PROMPT),
    ])


# Answer generation prompt with structured output
ANSWER_PROMPT = """基于以下 PPT 内容回答问题。

内容:
{context}

问题: {question}

请提供包含图片的完整回答，并标注参考页码。"""
