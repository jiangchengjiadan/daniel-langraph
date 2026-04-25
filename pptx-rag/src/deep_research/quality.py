"""Quality checks and repair helpers for deep research outputs."""

from __future__ import annotations

import re
from typing import Iterable, List, Tuple


def check_required_sections(report: str) -> List[str]:
    """Return missing required sections."""
    required = [
        "## 研究目标",
        "## 核心结论",
        "## 证据分析",
        "## 风险与不足",
        "## 参考来源",
    ]
    return [section for section in required if section not in report]


def check_images_preserved(report: str, evidence_text: str) -> bool:
    """Ensure report does not drop all image placeholders when evidence has them."""
    evidence_has_images = bool(re.search(r"!\[[^\]]*\]\([^)]+\)", evidence_text))
    report_has_images = bool(re.search(r"!\[[^\]]*\]\([^)]+\)", report))
    return (not evidence_has_images) or report_has_images


def check_has_citations(report: str) -> bool:
    """Best-effort check for page/document references."""
    patterns = [
        r"第\s*\d+\s*页",
        r"页面\s*\d+",
        r"\bfile_name\b",
        r"参考来源",
    ]
    return any(re.search(pattern, report) for pattern in patterns)


def check_todos_completed(todo_statuses: Iterable[str]) -> bool:
    """Verify whether all todo statuses are completed."""
    return all(status == "completed" for status in todo_statuses)


def extract_reference_lines(evidence_text: str) -> List[str]:
    """Extract compact reference lines from evidence markdown."""
    matches = []
    for line in evidence_text.splitlines():
        normalized = line.strip()
        if not normalized.startswith("- "):
            continue
        if "第 " in normalized and "页" in normalized:
            matches.append(normalized)
    return matches


def repair_report(
    report: str,
    evidence_text: str,
    missing_sections: List[str],
    citations_ok: bool,
) -> str:
    """Apply deterministic fixes so reports remain minimally deliverable."""
    repaired = report.strip()
    if not repaired:
        repaired = "# 研究报告"

    if missing_sections:
        additions = []
        for section in missing_sections:
            if section == "## 参考来源":
                references = extract_reference_lines(evidence_text)
                body = "\n".join(references) if references else "未能从证据中提取结构化来源，请回看证据文件。"
            elif section == "## 风险与不足":
                body = "- 当前报告已自动修补结构，但仍建议人工复核证据与结论的一致性。"
            elif section == "## 核心结论":
                body = "基于当前证据整理出初步结论，详见后续证据分析。"
            elif section == "## 证据分析":
                body = evidence_text or "暂无证据。"
            else:
                body = "待补充。"
            additions.extend(["", section, body])
        repaired = repaired.rstrip() + "\n" + "\n".join(additions)

    if not citations_ok:
        references = extract_reference_lines(evidence_text)
        if references:
            repaired = repaired.rstrip() + "\n\n## 自动补充来源\n" + "\n".join(references)

    return repaired


def summarize_quality(
    report: str,
    evidence_text: str,
    todo_statuses: Iterable[str] = (),
) -> Tuple[str, str]:
    """Produce a quality summary and a repaired report if needed."""
    missing_sections = check_required_sections(report)
    images_ok = check_images_preserved(report, evidence_text)
    citations_ok = check_has_citations(report)
    todos_ok = check_todos_completed(todo_statuses) if todo_statuses else True

    repaired_report = repair_report(report, evidence_text, missing_sections, citations_ok)
    repaired_missing_sections = check_required_sections(repaired_report)
    repaired_citations_ok = check_has_citations(repaired_report)

    lines = ["# 质量检查结果"]
    lines.append(f"- 缺失章节: {', '.join(missing_sections) if missing_sections else '无'}")
    lines.append(f"- 图片占位符保留: {'通过' if images_ok else '未通过'}")
    lines.append(f"- 来源引用检查: {'通过' if citations_ok else '未通过'}")
    lines.append(f"- Todo 完成情况: {'通过' if todos_ok else '未通过'}")
    if repaired_report != report:
        lines.append("- 已执行自动修补: 是")
        lines.append(
            f"- 修补后缺失章节: {', '.join(repaired_missing_sections) if repaired_missing_sections else '无'}"
        )
        lines.append(f"- 修补后来源检查: {'通过' if repaired_citations_ok else '未通过'}")
    else:
        lines.append("- 已执行自动修补: 否")

    return "\n".join(lines), repaired_report
