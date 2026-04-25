"""Minimal deep research service built on top of the reusable knowledge service."""

from __future__ import annotations

from typing import List, Optional

from ..config import config
from langchain_openai import ChatOpenAI
from ..logging import log
from ..services import DocumentKnowledgeService
from .prompts import PLAN_PROMPT, QUESTION_PROMPT, REPORT_PROMPT
from .quality import summarize_quality
from .schemas import ResearchArtifact, ResearchResult, ResearchTodo
from .tools import list_documents_tool, search_evidence_tool
from .workspace import ResearchWorkspaceManager


class DeepResearchService:
    """Run a multi-step research flow and persist artifacts to the workspace."""

    def __init__(
        self,
        knowledge_service: Optional[DocumentKnowledgeService] = None,
    ):
        self.log = log.bind(module="deep_research_service")
        self.knowledge_service = knowledge_service or DocumentKnowledgeService()
        self.workspace = ResearchWorkspaceManager()
        self.llm = ChatOpenAI(
            model=config.llm_model,
            base_url=config.api_base_url,
            api_key=config.api_key,
            temperature=0.2,
            max_tokens=config.llm_num_predict,
        )

    def _invoke_text(self, prompt: str) -> str:
        try:
            from langchain_core.messages import HumanMessage

            response = self.llm.invoke([HumanMessage(content=prompt)])
            return response.content if hasattr(response, "content") else str(response)
        except Exception as e:
            self.log.warning(f"LLM invocation failed, fallback to deterministic output: {e}")
            return ""

    def _extract_lines(self, raw_text: str, fallback: List[str]) -> List[str]:
        lines = []
        for line in raw_text.splitlines():
            normalized = line.strip().lstrip("-").lstrip("*").strip()
            if normalized:
                lines.append(normalized)
        deduped = []
        for line in lines:
            if line not in deduped:
                deduped.append(line)
        return deduped or fallback

    def _build_document_overview(self, selected_documents: List[str]) -> str:
        all_documents = list_documents_tool(self.knowledge_service)
        documents = [
            doc for doc in all_documents if not selected_documents or doc["file_name"] in selected_documents
        ]
        if not documents:
            return "当前没有可用文档。"

        lines = ["# 文档概览"]
        for doc in documents:
            lines.append(
                f"- {doc['file_name']}: 页码 {doc['pages']}，总页数 {doc['total_pages']}，父块数量 {doc['chunks_count']}"
            )
        return "\n".join(lines)

    def _plan_todos(self, task: str, document_overview: str) -> List[ResearchTodo]:
        fallback = [
            "梳理文档范围与研究目标",
            "收集与主题相关的关键证据",
            "汇总结论并生成研究报告",
        ]
        raw = self._invoke_text(PLAN_PROMPT.format(task=task, documents=document_overview))
        steps = self._extract_lines(raw, fallback)
        todos = []
        for idx, step in enumerate(steps):
            todos.append(ResearchTodo(content=step, status="completed" if idx < len(steps) - 1 else "in_progress"))
        if todos:
            todos[-1].status = "completed"
        return todos

    def _research_questions(self, task: str) -> List[str]:
        fallback = [
            task,
            f"{task} 的关键证据是什么？",
            f"{task} 可以得出哪些结论和建议？",
        ]
        raw = self._invoke_text(QUESTION_PROMPT.format(task=task))
        return self._extract_lines(raw, fallback)[:3]

    def _search_selected_documents(self, query: str, selected_documents: List[str]) -> List[str]:
        evidence_sections = []
        if selected_documents:
            for file_name in selected_documents:
                result = search_evidence_tool(
                    self.knowledge_service,
                    query=query,
                    file_name=file_name,
                    top_k=5,
                )
                if result["hits"]:
                    evidence_sections.append(self._format_evidence_section(query, result))
        else:
            result = search_evidence_tool(self.knowledge_service, query=query, top_k=5)
            if result["hits"]:
                evidence_sections.append(self._format_evidence_section(query, result))
        return evidence_sections

    def _format_evidence_section(self, query: str, result: dict) -> str:
        lines = [f"# 研究问题", query, "", "## 命中结果"]
        for hit in result["hits"]:
            title_suffix = f" / {hit['title']}" if hit["title"] else ""
            lines.append(
                f"- {hit['file_name']} 第 {hit['page_number']} 页{title_suffix}"
            )
        lines.extend(["", "## 上下文", result["context"] or "未生成上下文"])
        return "\n".join(lines)

    def _build_report(
        self,
        task: str,
        output_mode: str,
        document_overview: str,
        evidence_text: str,
    ) -> str:
        prompt = REPORT_PROMPT.format(
            task=task,
            output_mode=output_mode,
            document_overview=document_overview,
            evidence=evidence_text,
        )
        report = self._invoke_text(prompt).strip()
        if report:
            return report

        return "\n".join(
            [
                f"# {output_mode}",
                "",
                "## 研究目标",
                task,
                "",
                "## 核心结论",
                "基于已检索证据整理出的初步结论如下。",
                "",
                "## 证据分析",
                evidence_text or "暂无证据。",
                "",
                "## 风险与不足",
                "- 当前报告为最小可运行版本，仍需补充更严格的质量校验。",
                "",
                "## 参考来源",
                "详见上方证据分析中的文档与页码。",
            ]
        )

    def run_task(
        self,
        task: str,
        selected_documents: Optional[List[str]] = None,
        output_mode: str = "研究报告",
    ) -> ResearchResult:
        selected_documents = selected_documents or []
        task_id = self.workspace.create_session()

        available_documents = list_documents_tool(self.knowledge_service)
        if not available_documents:
            raise ValueError("当前没有已处理文档，请先上传并处理文档。")

        if selected_documents:
            available_names = {doc["file_name"] for doc in available_documents}
            missing = [name for name in selected_documents if name not in available_names]
            if missing:
                raise ValueError(f"所选文档不存在或尚未处理: {', '.join(missing)}")

        artifacts: List[ResearchArtifact] = []
        self.workspace.write_text(task_id, "task.md", f"# 研究任务\n\n{task}\n")
        artifacts.append(ResearchArtifact(label="研究任务", path=f"{task_id}/task.md"))

        document_overview = self._build_document_overview(selected_documents)
        self.workspace.write_text(task_id, "documents_overview.md", document_overview)
        artifacts.append(ResearchArtifact(label="文档概览", path=f"{task_id}/documents_overview.md"))

        todos = self._plan_todos(task, document_overview)
        plan_text = "# 研究计划\n\n" + "\n".join([f"- [{todo.status}] {todo.content}" for todo in todos])
        self.workspace.write_text(task_id, "plan.md", plan_text)
        artifacts.append(ResearchArtifact(label="研究计划", path=f"{task_id}/plan.md"))

        evidence_sections: List[str] = []
        for idx, question in enumerate(self._research_questions(task), start=1):
            sections = self._search_selected_documents(question, selected_documents)
            evidence_text = "\n\n".join(sections) if sections else f"# 研究问题\n{question}\n\n未检索到直接证据。"
            self.workspace.write_text(task_id, f"evidence/q{idx}.md", evidence_text)
            artifacts.append(ResearchArtifact(label=f"证据 q{idx}", path=f"{task_id}/evidence/q{idx}.md"))
            evidence_sections.append(evidence_text)

        combined_evidence = "\n\n".join(evidence_sections)
        draft_report = self._build_report(task, output_mode, document_overview, combined_evidence)
        self.workspace.write_text(task_id, "drafts/report_v1.md", draft_report)
        artifacts.append(ResearchArtifact(label="报告初稿", path=f"{task_id}/drafts/report_v1.md"))

        quality_summary, final_report = summarize_quality(
            draft_report,
            combined_evidence,
            todo_statuses=[todo.status for todo in todos],
        )
        self.workspace.write_text(task_id, "quality_report.md", quality_summary)
        artifacts.append(ResearchArtifact(label="质量检查", path=f"{task_id}/quality_report.md"))

        self.workspace.write_text(task_id, "final/final_report.md", final_report)
        artifacts.append(ResearchArtifact(label="最终报告", path=f"{task_id}/final/final_report.md"))

        return ResearchResult(
            task_id=task_id,
            task=task,
            output_mode=output_mode,
            execution_mode="service",
            execution_note="使用本地研究协调器执行。",
            selected_documents=selected_documents,
            todos=todos,
            artifacts=artifacts,
            document_overview=document_overview,
            final_report=final_report,
            quality_summary=quality_summary,
        )
