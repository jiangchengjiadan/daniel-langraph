"""Tool-like wrappers used by the deep research service and Deep Agents runtime."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from ..services import DocumentKnowledgeService


def list_documents_tool(knowledge_service: DocumentKnowledgeService) -> List[Dict[str, Any]]:
    """List indexed documents."""
    return knowledge_service.list_documents()


def search_evidence_tool(
    knowledge_service: DocumentKnowledgeService,
    query: str,
    file_name: Optional[str] = None,
    top_k: int = 5,
) -> Dict[str, Any]:
    """Search for evidence with an optional file filter."""
    return knowledge_service.search_evidence(query, file_name=file_name, k=top_k)


def get_page_content_tool(
    knowledge_service: DocumentKnowledgeService,
    file_name: str,
    pages: List[int],
) -> List[Dict[str, Any]]:
    """Get exact page content for inspection."""
    return knowledge_service.get_page_content(file_name, pages)


def create_deep_agent_tools(knowledge_service: DocumentKnowledgeService):
    """Create LangChain-compatible tools for a future Deep Agents runtime."""
    try:
        from langchain.tools import tool
    except Exception:
        return []

    @tool
    def list_documents() -> str:
        """List currently indexed documents available for research."""
        return json.dumps(list_documents_tool(knowledge_service), ensure_ascii=False, indent=2)

    @tool
    def search_evidence(query: str, file_name: str = "", top_k: int = 5) -> str:
        """Search indexed documents for evidence related to a research query."""
        target_file = file_name or None
        result = search_evidence_tool(
            knowledge_service,
            query=query,
            file_name=target_file,
            top_k=top_k,
        )
        return json.dumps(result, ensure_ascii=False, indent=2)

    @tool
    def get_page_content(file_name: str, pages: str) -> str:
        """Get exact page content. `pages` accepts comma-separated numbers like '3,4,5'."""
        page_numbers = []
        for item in pages.split(","):
            item = item.strip()
            if item.isdigit():
                page_numbers.append(int(item))
        result = get_page_content_tool(knowledge_service, file_name=file_name, pages=page_numbers)
        return json.dumps(result, ensure_ascii=False, indent=2)

    return [list_documents, search_evidence, get_page_content]
