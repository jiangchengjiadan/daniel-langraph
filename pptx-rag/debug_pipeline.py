#!/usr/bin/env python3
"""
RAG Pipeline Debug Tool - 输出处理各个环节的详细信息到 JSON 文件

这个测试程序只调用正式的 RAGChain 接口，然后输出调试信息。

输出文件：
- data/debug/01_slides.json: 原始提取的幻灯片
- data/debug/02_titles.json: 生成的标题
- data/debug/03_chunks.json: 子块（分块结果）
- data/debug/04_merge_groups.json: 合并组（父块）
- data/debug/05_parent_chunks.json: 父块内容
- data/debug/06_vector_index.json: 向量索引信息
- data/debug/07_search_results.json: 检索结果
- data/debug/08_llm_context.json: 喂给LLM的上下文
- data/debug/09_llm_answer.json: LLM回答结果
"""

import json
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.rag.chain import RAGChain


class PipelineDebugger:
    """RAG Pipeline Debugger - 输出各个环节详情"""

    def __init__(self, pptx_path: str = None, output_dir: str = "data/debug"):
        self.pptx_path = pptx_path or "钻机电控系统培训PPT3（S120变频系统培训）ok.pptx"
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.rag = RAGChain()
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    def run_full_pipeline(self):
        """运行完整流程并输出调试信息"""
        print("=" * 80)
        print("RAG Pipeline Debugger")
        print("=" * 80)

        pptx_path = Path(self.pptx_path)
        if not pptx_path.exists():
            pptx_path = Path("data/uploads") / self.pptx_path

        if not pptx_path.exists():
            print(f"Error: File not found: {self.pptx_path}")
            return

        print(f"\nLoading document: {pptx_path}")

        # 1. 加载文档（调用正式代码）
        result = self.rag.load_document(str(pptx_path))
        print(f"  Loaded: {result}")

        # 2. 获取文档列表
        documents = self.rag.list_documents()
        print(f"  Documents: {len(documents)}")

        # 3. 输出调试文件
        print("\n[Output] 生成调试文件...")
        self._output_debug_files(result)

        print("\n" + "=" * 80)
        print(f"调试完成! 输出目录: {self.output_dir}")
        print("=" * 80)

    def run_qa_test(self, query: str):
        """
        运行问答测试并输出结果

        Args:
            query: 查询问题
        """
        print("\n" + "=" * 80)
        print(f"问答测试: {query}")
        print("=" * 80)

        # 调用正式的 ask 接口
        answer = self.rag.ask(query)

        # 保存回答结果
        self._save_json("09_llm_answer.json", {
            "timestamp": self.timestamp,
            "query": query,
            "answer": answer.answer,
            "sources": answer.sources,
            "referenced_pages": answer.referenced_pages,
        })

        print("\n" + "=" * 80)
        print("LLM回答:")
        print("=" * 80)
        print(answer.answer[:2000])
        if len(answer.answer) > 2000:
            print("\n... (截断显示)")
        print("=" * 80)
        print(f"\n参考页码: {answer.referenced_pages}")
        print(f"来源: {answer.sources}")

        return answer

    def _output_debug_files(self, load_result: dict):
        """输出调试文件 - 调用 RAGChain 的接口获取内部数据"""

        # 01_slides.json - 从 DocStore 和 chunks 获取幻灯片信息
        slides_info = self._get_slides_info()
        self._save_json("01_slides.json", {
            "timestamp": self.timestamp,
            "pptx_path": str(self.pptx_path),
            "total_pages": load_result.get("slides_count", 0),
            "slides": slides_info
        })

        # 03_chunks.json - 从 vector_store 获取分块信息
        chunks_info = self._get_chunks_info()
        self._save_json("03_chunks.json", {
            "timestamp": self.timestamp,
            "total_chunks": len(chunks_info),
            "chunks": chunks_info
        })

        # 05_parent_chunks.json - 从 DocStore 获取父块信息
        parent_info = self._get_parent_chunks_info()
        self._save_json("05_parent_chunks.json", {
            "timestamp": self.timestamp,
            "total_parent_chunks": len(parent_info),
            "parent_chunks": parent_info
        })

        # 07_images.json - 从 chunks 获取图片信息
        images_info = self._get_images_info()
        self._save_json("07_images.json", {
            "timestamp": self.timestamp,
            "total_images": len(images_info),
            "images": images_info
        })

        print(f"  已保存调试文件")

    def _get_slides_info(self) -> list:
        """从 chunks 提取幻灯片信息"""
        from src.storage.vector_store import VectorStore
        vs = VectorStore()
        info = []
        if vs.vector_store:
            for chunk_id, doc in vs.vector_store.docstore._dict.items():
                page = doc.metadata.get("page_number")
                if page and page not in [s["page_number"] for s in info]:
                    info.append({
                        "page_number": page,
                        "title": doc.metadata.get("title", ""),
                        "chunk_id": chunk_id,
                    })
        return sorted(info, key=lambda x: x["page_number"])

    def _get_chunks_info(self) -> list:
        """获取所有分块信息"""
        from src.storage.vector_store import VectorStore
        vs = VectorStore()
        info = []
        if vs.vector_store:
            for chunk_id, doc in vs.vector_store.docstore._dict.items():
                content_preview = doc.page_content[:500] + "..." if len(doc.page_content) > 500 else doc.page_content
                info.append({
                    "id": chunk_id,
                    "file_name": doc.metadata.get("file_name", ""),
                    "page_number": doc.metadata.get("page_number"),
                    "title": doc.metadata.get("title", ""),
                    "parent_id": doc.metadata.get("parent_id"),
                    "content_length": len(doc.page_content),
                    "content_preview": content_preview,
                    "has_images": doc.metadata.get("has_images", False),
                })
        return sorted(info, key=lambda x: x["page_number"])

    def _get_parent_chunks_info(self) -> list:
        """获取父块信息"""
        from src.storage.doc_store import DocStore
        ds = DocStore()
        info = []
        for parent_path in ds.store_dir.glob("*.json"):
            data = json.loads(parent_path.read_text(encoding="utf-8"))
            content_preview = data.get("content", "")[:1000] + "..." if len(data.get("content", "")) > 1000 else data.get("content", "")
            info.append({
                "id": data.get("id"),
                "file_name": data.get("file_name"),
                "start_page": data.get("start_page"),
                "end_page": data.get("end_page"),
                "page_count": data.get("end_page") - data.get("start_page") + 1,
                "child_count": len(data.get("child_chunk_ids", [])),
                "child_chunk_ids": data.get("child_chunk_ids", []),
                "merge_reason": data.get("metadata", {}).get("merge_reason", ""),
                "content_length": len(data.get("content", "")),
                "content_preview": content_preview,
            })
        return sorted(info, key=lambda x: x["start_page"])

    def _get_images_info(self) -> list:
        """获取图片信息"""
        import re
        from src.storage.vector_store import VectorStore
        vs = VectorStore()
        seen_images = set()
        info = []
        if vs.vector_store:
            for chunk_id, doc in vs.vector_store.docstore._dict.items():
                if doc.metadata.get("has_images"):
                    page = doc.metadata.get("page_number")
                    # 从 content 中提取图片路径
                    img_pattern = r'!\[.*?\]\((.*?)\)'
                    for match in re.finditer(img_pattern, doc.page_content):
                        img_path = match.group(1)
                        if img_path not in seen_images:
                            seen_images.add(img_path)
                            filename = Path(img_path).name
                            info.append({
                                "page_number": page,
                                "path": img_path,
                                "filename": filename,
                            })
        return info

    def search_and_debug(self, query: str, k: int = 5):
        """执行检索并输出调试信息"""
        print("\n" + "=" * 80)
        print(f"检索调试: {query}")
        print("=" * 80)

        # 调用正式的检索接口
        results = self.rag.hybrid_retriever.get_relevant_documents(query, k=k)

        # 保存检索结果
        self._save_json("07_search_results.json", {
            "timestamp": self.timestamp,
            "query": query,
            "k": k,
            "total_results": len(results),
            "results": [
                {
                    "id": r.id,
                    "file_name": r.file_name,
                    "page_number": r.page_number,
                    "title": r.title,
                    "parent_id": r.metadata.get("parent_id"),
                    "score": r.metadata.get("score", 0),
                    "content_preview": r.content[:300] + "..." if len(r.content) > 300 else r.content,
                }
                for r in results
            ]
        })

        print(f"\n检索到 {len(results)} 个相关分块:")
        for i, r in enumerate(results):
            parent_info = f" -> {r.metadata.get('parent_id', '无')[:30]}..." if r.metadata.get("parent_id") else ""
            print(f"  {i+1}. 页面 {r.page_number}: {r.title}{parent_info}")

        return results

    def _save_json(self, filename: str, data: dict):
        """保存 JSON 文件"""
        filepath = self.output_dir / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    """主函数"""
    import os
    import argparse

    # 设置 OpenMP 环境变量避免冲突
    os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

    parser = argparse.ArgumentParser(description="RAG Pipeline Debugger")
    parser.add_argument("pptx_path", nargs="?", default="钻机电控系统培训PPT3（S120变频系统培训）ok.pptx",
                        help="PPT 文件路径")
    parser.add_argument("-o", "--output", default="data/debug",
                        help="输出目录")
    parser.add_argument("-q", "--query", default="S120变频器的硬件组成有哪些？",
                        help="测试查询问题")
    parser.add_argument("--qa", action="store_true",
                        help="运行完整问答测试")

    args = parser.parse_args()

    # 创建调试器
    debugger = PipelineDebugger(args.pptx_path, args.output)

    # 运行完整流程
    debugger.run_full_pipeline()

    if args.qa:
        # 运行问答测试
        debugger.run_qa_test(args.query)
    else:
        # 执行测试查询
        results = debugger.search_and_debug(args.query)

        print("\n" + "=" * 80)
        print("检索结果:")
        print("=" * 80)
        for i, r in enumerate(results):
            print(f"\n[{i+1}] 页面 {r.page_number}: {r.title}")
            print(f"    内容: {r.content[:200]}...")

    print(f"\n\n所有调试文件已保存到: {debugger.output_dir}")


if __name__ == "__main__":
    main()
