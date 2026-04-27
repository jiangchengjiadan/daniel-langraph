"""Deep research agent facade with optional Deep Agents runtime support."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import List, Optional

from langchain.tools import tool

from ..config import config
from langchain_openai import ChatOpenAI
from ..logging import log
from ..services import DocumentKnowledgeService
from .prompts import (
    DEEP_AGENT_SYSTEM_PROMPT,
    DOCUMENT_ANALYST_PROMPT,
    EVIDENCE_COLLECTOR_PROMPT,
    REPORT_WRITER_PROMPT,
)
from .schemas import ResearchArtifact, ResearchResult
from .services import DeepResearchService
from .tools import create_deep_agent_tools
from .workspace import ResearchWorkspaceManager


class DeepResearchAgent:
    """Run deep research tasks via Deep Agents when available, otherwise fallback locally."""

    def __init__(
        self,
        service: Optional[DeepResearchService] = None,
        knowledge_service: Optional[DocumentKnowledgeService] = None,
    ):
        self.log = log.bind(module="deep_research_agent")
        self.knowledge_service = knowledge_service or DocumentKnowledgeService()
        self.service = service or DeepResearchService(self.knowledge_service)
        self.workspace = ResearchWorkspaceManager()
        self.runtime_mode = "service"
        self._deep_agent = None
        self._initialize_deep_agent()

    def _initialize_deep_agent(self):
        """Best-effort Deep Agents setup. Falls back silently if dependency is unavailable."""
        try:
            from deepagents import create_deep_agent
            from deepagents.backends import FilesystemBackend
            from langgraph.checkpoint.memory import MemorySaver

            tools = self._create_orchestrator_tools()
            subagents = self._create_subagents()
            root_dir = str(self.workspace.base_dir.parent)
            model = ChatOpenAI(
                model=config.llm_model,
                base_url=config.api_base_url,
                api_key=config.api_key,
                temperature=0.2,
                max_tokens=config.llm_num_predict,
            )
            self._deep_agent = create_deep_agent(
                name="pptx-deep-research",
                model=model,
                tools=tools,
                system_prompt=DEEP_AGENT_SYSTEM_PROMPT,
                subagents=subagents,
                backend=FilesystemBackend(root_dir=root_dir, virtual_mode=True),
                checkpointer=MemorySaver(),
            )
            self.runtime_mode = "deepagents"
            self.log.info("Deep Agents runtime initialized successfully")
        except Exception as e:
            self._deep_agent = None
            self.runtime_mode = "service"
            self.log.warning(f"Deep Agents runtime unavailable, fallback to local service: {e}")

    def _create_orchestrator_tools(self):
        """Create stable high-level tools for Deep Agents orchestration."""
        helper_tools = create_deep_agent_tools(self.knowledge_service)

        @tool
        def run_research_once(task: str, selected_documents: str = "", output_mode: str = "研究报告") -> str:
            """Run the full research workflow once and return a JSON summary."""
            documents = [item.strip() for item in selected_documents.split(",") if item.strip()]
            result = self.service.run_task(
                task=task,
                selected_documents=documents,
                output_mode=output_mode,
            )
            result.execution_mode = "deepagents"
            result.execution_note = "Deep Agents 通过高层研究工具执行成功。"
            return result.model_dump_json(ensure_ascii=False)

        return [run_research_once, *helper_tools]

    def _create_subagents(self):
        """Register focused subagents without making them the default execution path."""
        helper_tools = create_deep_agent_tools(self.knowledge_service)
        helper_tools_by_name = {tool.name: tool for tool in helper_tools}

        document_analyst_tools = [
            helper_tools_by_name[name]
            for name in ("list_documents", "get_page_content")
            if name in helper_tools_by_name
        ]
        evidence_collector_tools = [
            helper_tools_by_name[name]
            for name in ("search_evidence", "get_page_content")
            if name in helper_tools_by_name
        ]
        report_writer_tools = [
            helper_tools_by_name[name]
            for name in ("list_documents", "search_evidence")
            if name in helper_tools_by_name
        ]

        return [
            {
                "name": "document_analyst",
                "description": "分析文档结构、关键章节和关键页，给出研究切入点。",
                "system_prompt": DOCUMENT_ANALYST_PROMPT,
                "tools": document_analyst_tools,
            },
            {
                "name": "evidence_collector",
                "description": "围绕具体研究问题检索证据，返回文档名、页码和上下文。",
                "system_prompt": EVIDENCE_COLLECTOR_PROMPT,
                "tools": evidence_collector_tools,
            },
            {
                "name": "report_writer",
                "description": "根据已有研究材料整理 Markdown 报告结构与结论。",
                "system_prompt": REPORT_WRITER_PROMPT,
                "tools": report_writer_tools,
            },
        ]

    def _run_with_deepagents(
        self,
        task: str,
        selected_documents: List[str],
        output_mode: str,
    ) -> ResearchResult:
        """Use Deep Agents as high-level orchestrator around one stable research tool."""
        document_scope = ", ".join(selected_documents) if selected_documents else "全部已加载文档"
        invoke_config = {
            "configurable": {"thread_id": f"deep-research-{hash((task, tuple(selected_documents), output_mode))}"},
            "recursion_limit": 20,
        }

        instruction = f"""
请完成一个文档研究任务。

要求：
1. 先简要制定 todo 计划
2. 文档范围：{document_scope}
3. 制定 todo 后必须立即调用 `run_research_once`
4. 调用参数必须包含：
   - task: 原始研究任务
   - selected_documents: 使用逗号连接的文档名，如果为空则表示全部文档
   - output_mode: {output_mode}
5. 除非 `run_research_once` 调用失败，否则不要调用 `task` 或其他辅助工具
6. 工具返回后，简要说明任务编号和关键产物路径

研究任务：
{task}
"""

        timed_out = False
        result = None
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(
            self._deep_agent.invoke,
            {"messages": [{"role": "user", "content": instruction}]},
            invoke_config,
        )
        try:
            result = future.result(timeout=120)
        except FuturesTimeoutError:
            timed_out = True
            future.cancel()
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        tool_payload = None
        if result and isinstance(result, dict):
            for message in result.get("messages", []):
                name = getattr(message, "name", "")
                if name == "run_research_once":
                    tool_payload = getattr(message, "content", None)

        if not tool_payload:
            raise ValueError(
                f"Deep Agents runtime未返回 run_research_once 的结果。最后返回内容: "
                f"{json.dumps(result, ensure_ascii=False, default=str)[:500]}"
            )

        parsed = ResearchResult.model_validate_json(tool_payload)
        runtime_note = "Deep Agents 通过高层研究工具执行成功。"
        if timed_out:
            runtime_note += " invoke 在超时前已返回工具结果，因此按成功处理。"
        parsed.execution_mode = "deepagents"
        parsed.execution_note = runtime_note
        return parsed

    def run(
        self,
        task: str,
        selected_documents: Optional[List[str]] = None,
        output_mode: str = "研究报告",
    ) -> ResearchResult:
        selected_documents = selected_documents or []

        if self._deep_agent is not None:
            try:
                return self._run_with_deepagents(task, selected_documents, output_mode)
            except Exception as e:
                self.log.warning(f"Deep Agents execution failed, fallback to local service: {e}")
                fallback_result = self.service.run_task(
                    task=task,
                    selected_documents=selected_documents,
                    output_mode=output_mode,
                )
                fallback_result.execution_mode = "service_fallback"
                fallback_result.execution_note = f"Deep Agents 初始化成功，但执行失败后回退到本地协调器。原因: {e}"
                return fallback_result

        return self.service.run_task(
            task=task,
            selected_documents=selected_documents,
            output_mode=output_mode,
        )
