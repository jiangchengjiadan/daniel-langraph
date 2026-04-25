# src/rag/chain.py
"""RAG chain for question answering."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from langchain_openai import ChatOpenAI

from ..config import config
from ..logging import log
from ..models import AnswerResult
from ..services import DocumentKnowledgeService


class RAGChain:
    """Question-answering wrapper built on top of the reusable knowledge service."""

    _instance: Optional["RAGChain"] = None
    _initialized: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if RAGChain._initialized:
            return

        self.log = log.bind(module="rag_chain")
        self.config = config
        self.knowledge_service = DocumentKnowledgeService()
        self.llm = ChatOpenAI(
            model=config.llm_model,
            base_url=config.api_base_url,
            api_key=config.api_key,
            temperature=config.llm_temperature,
            max_tokens=config.llm_num_predict,
        )

        RAGChain._initialized = True
        self.log.info("RAGChain initialized (singleton)")

    @property
    def hybrid_retriever(self):
        """Expose the existing retriever for current UI controls."""
        return self.knowledge_service.hybrid_retriever

    def _build_qa_prompt(self, context: str, question: str) -> str:
        return f"""# 角色和要求
你是一个专业的问答助手，下面是知识库检索到的参考内容和用户的问题，请使用知识库参考内容回答用户的问题。

# 约束
1. 【必须保留图片】知识库内容中的所有图片占位符（格式：`![描述](http://localhost:8080/...)`）必须在回答中原样保留，一个都不能少，一个都不能改。如果原始内容有3张图，回答中必须有3张图。
2. 【禁止编造图片】如果知识库内容没有图片占位符，不要自己编造任何图片URL。
3. 【禁止删除内容】不要删除或修改原文中的任何内容，包括图片占位符、列表、编号等。
4. 【未检索到则回答未检索到】如果知识库中没有相关内容，回复"抱歉，未检索到相关信息"。

## 任务

知识库参考内容:
{context}

问题: {question}

请根据以上内容回答问题，必须包含知识库中的所有图片占位符，并标注参考页码。
最后你要再仔细思考检查，参考页码的正文中是否还有图片占位符遗漏了，如有遗漏要补充！"""

    def warmup(self):
        self.log.info("[WARMUP] 开始预热LLM连接...")
        try:
            from langchain_core.messages import HumanMessage

            response = self.llm.invoke([HumanMessage(content="hello")])
            self.log.info("[WARMUP] LLM连接成功，API正常")
            return response
        except Exception as e:
            self.log.warning(f"[WARMUP] LLM预热失败: {e}")
            return None

    def set_temperature(self, temperature: float):
        self.log.info(f"[UPDATE] Setting temperature: {temperature}")
        self.llm = ChatOpenAI(
            model=self.config.llm_model,
            base_url=self.config.api_base_url,
            api_key=self.config.api_key,
            temperature=temperature,
            max_tokens=self.config.llm_num_predict,
        )

    def load_document(self, file_path: str, on_progress: callable = None) -> Dict[str, Any]:
        return self.knowledge_service.load_document(file_path, on_progress=on_progress)

    def _parse_sources(
        self,
        context: str,
        results,
        file_name: Optional[str] = None,
    ) -> tuple[List[Dict[str, Any]], List[int]]:
        import re

        sources: List[Dict[str, Any]] = []
        referenced_pages: List[int] = []
        parent_pattern = r"参考来源 \d+ \(父块，页面 (\d+)-(\d+)\)"
        single_pattern = r"参考来源 \d+ \(页面 (\d+)\)"

        for line in context.split("\n"):
            match = re.search(parent_pattern, line)
            if match:
                start, end = int(match.group(1)), int(match.group(2))
                sources.append(
                    {
                        "file_name": file_name or results[0].file_name if results else "",
                        "pages": list(range(start, end + 1)),
                        "type": "parent",
                    }
                )
                referenced_pages.extend(range(start, end + 1))
                continue

            match = re.search(single_pattern, line)
            if match:
                page = int(match.group(1))
                if page not in referenced_pages:
                    sources.append(
                        {
                            "file_name": file_name or results[0].file_name if results else "",
                            "pages": [page],
                            "type": "single",
                        }
                    )
                    referenced_pages.append(page)

        referenced_pages = sorted(set(referenced_pages))
        return sources, referenced_pages

    def ask(self, question: str, file_name: str = None) -> AnswerResult:
        self.log.info(f"Answering question: {question[:100]}...")

        results = self.knowledge_service.retrieve_chunks(question, file_name=file_name)
        if not results:
            return AnswerResult(
                answer="抱歉，我没有找到相关的内容来回答您的问题。",
                sources=[],
                referenced_pages=[],
            )

        context = self.knowledge_service.build_parent_context(results)
        if not context:
            context = "\n\n---\n\n".join([r.content for r in results])

        sources, referenced_pages = self._parse_sources(context, results, file_name=file_name)
        prompt = self._build_qa_prompt(context, question)

        try:
            from langchain_core.messages import HumanMessage

            response = self.llm.invoke([HumanMessage(content=prompt)])
            answer = response.content if hasattr(response, "content") else str(response)
            return AnswerResult(
                answer=answer,
                sources=sources,
                referenced_pages=referenced_pages,
            )
        except Exception as e:
            self.log.error(f"Failed to generate answer: {e}")
            return AnswerResult(
                answer=f"生成回答时出错: {str(e)}",
                sources=sources,
                referenced_pages=referenced_pages,
            )

    def ask_stream(self, question: str, file_name: str = None):
        self.log.info(f"Answering question (streaming): {question[:100]}...")

        results = self.knowledge_service.retrieve_chunks(question, file_name=file_name)
        if not results:
            yield ("抱歉，我没有找到相关的内容来回答您的问题。", True, [], [])
            return

        context = self.knowledge_service.build_parent_context(results)
        if not context:
            context = "\n\n---\n\n".join([r.content for r in results])

        sources, referenced_pages = self._parse_sources(context, results, file_name=file_name)
        prompt = self._build_qa_prompt(context, question)

        try:
            from langchain_core.messages import HumanMessage

            full_response = ""
            for chunk in self.llm.stream([HumanMessage(content=prompt)]):
                content = chunk.content if hasattr(chunk, "content") else str(chunk)
                full_response += content
                yield (content, False, sources, referenced_pages)

            self.log.info(f"[STREAM] Completed answer with {len(full_response)} chars")
            yield ("", True, sources, referenced_pages)
        except Exception as e:
            self.log.error(f"[STREAM] Failed to generate streaming answer: {e}")
            yield (f"生成回答时出错: {str(e)}", True, sources, referenced_pages)

    def list_documents(self) -> List[Dict[str, Any]]:
        return self.knowledge_service.list_documents()

    def clear(self, file_name: str = None) -> int:
        return self.knowledge_service.clear(file_name)
