# src/rag/chain.py
"""RAG chain for question answering"""

import hashlib
import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser

from ..config import config
from ..models import (
    SlideContent, PageChunk, ParentChunk, AnswerResult, ProcessingStatus
)
from ..parser import (
    extract_text_from_pptx,
    extract_images,
    PptxParser,
    ImageHandler,
    PDFParser,
    TextParser,
    ImageParser,
)
from ..processor import (
    TitleGenerator,
    ChunkingProcessor,
    Merger,
    ParentBuilder,
    generate_title,
    filter_invalid_slides,
)
from ..storage import DocStore, VectorStore
from ..retriever import HybridRetriever, ParentRetriever, replace_with_parents, get_parent_context
from ..logging import log


class RAGChain:
    """RAG Chain for PPT question answering - Singleton Pattern"""

    _instance: Optional['RAGChain'] = None
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

        # Initialize components with performance optimization
        self.llm = ChatOpenAI(
            model=config.llm_model,
            base_url=config.api_base_url,
            api_key=config.api_key,
            temperature=config.llm_temperature,
            max_tokens=config.llm_num_predict,
        )

        self.title_generator = TitleGenerator()
        self.chunking_processor = ChunkingProcessor()
        self.merger = Merger()
        self.parent_builder = ParentBuilder()

        # Storage
        self.doc_store = DocStore()
        self.vector_store = VectorStore()

        # Retriever
        self.hybrid_retriever = HybridRetriever(self.vector_store)

        # Ensure directories exist
        config.ensure_directories()

        RAGChain._initialized = True
        self.log.info("RAGChain initialized (singleton)")

    def _build_qa_prompt(self, context: str, question: str) -> str:
        """Build the QA prompt for LLM (shared by ask and ask_stream)"""
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
        """预热LLM连接 - 应用启动时调用，触发API连接测试"""
        self.log.info("[WARMUP] 开始预热LLM连接...")
        try:
            # 发送简单消息测试连接
            from langchain_core.messages import HumanMessage
            test_message = HumanMessage(content="hello")
            response = self.llm.invoke([test_message])
            self.log.info(f"[WARMUP] LLM连接成功，API正常")
        except Exception as e:
            self.log.warning(f"[WARMUP] LLM预热失败: {e}")

    def set_temperature(self, temperature: float):
        """动态设置 LLM temperature（需要重新创建 LLM 实例）"""
        self.log.info(f"[UPDATE] Setting temperature: {temperature}")
        self._create_llm()

    def _create_llm(self):
        """创建/重新创建 LLM 实例"""
        self.llm = ChatOpenAI(
            model=self.config.llm_model,
            base_url=self.config.api_base_url,
            api_key=self.config.api_key,
            temperature=self.config.llm_temperature,
            max_tokens=self.config.llm_num_predict,
        )
        self.log.info(f"[UPDATE] LLM recreated with max_tokens={self.config.llm_num_predict}")

    def load_document(
        self,
        file_path: str,
        on_progress: callable = None,
    ) -> Dict[str, Any]:
        """
        Load and process a document (supports PPTX, PDF, text files, and images)

        Args:
            file_path: Path to the document file
            on_progress: Optional callback for progress updates

        Returns:
            Dict with processing results
        """
        file_path = Path(file_path)
        file_name = file_path.stem
        file_ext = file_path.suffix.lower()

        self.log.info(f"Loading document: {file_name} (type: {file_ext})")

        # 检查文件是否已存在，如果存在则先删除旧数据
        existing_docs = self.doc_store.get_by_file(file_name)
        if existing_docs:
            self.log.warning(f"File '{file_name}' already exists, clearing old data first...")
            self.clear(file_name)

        try:
            if on_progress:
                on_progress(ProcessingStatus(
                    file_name=file_name,
                    status="processing",
                    progress=0.1,
                    current_step="解析文档内容",
                ))

            # Step 1: Select appropriate parser based on file extension
            parser = None
            if file_ext in ['.pptx', '.ppt']:
                parser = PptxParser()
            elif file_ext == '.pdf':
                parser = PDFParser()
            elif file_ext in ['.txt', '.md', '.markdown', '.log', '.text']:
                parser = TextParser()
            elif file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff']:
                parser = ImageParser()
            else:
                raise ValueError(f"Unsupported file format: {file_ext}")

            # Step 2: Parse document to extract content and images
            slides_content, images = parser.parse(str(file_path))
            self.log.info(f"Extracted {len(slides_content)} pages and {len(images)} images")

            if on_progress:
                on_progress(ProcessingStatus(
                    file_name=file_name,
                    status="processing",
                    progress=0.2,
                    current_step="生成页面分块",
                ))

            # Step 3: Generate titles for slides
            titles: Dict[int, str] = {}
            for slide in slides_content:
                title = generate_title(slide.text, slide.title)
                titles[slide.page_number] = title

            # Step 4: Filter out invalid pages (only for PPTX files)
            # For PPTX: filter out cover page, table of contents, thank you pages, etc.
            # For other formats: keep all pages
            if file_ext in ['.pptx', '.ppt']:
                valid_slides = filter_invalid_slides(slides_content, titles)
                # Filter out first page (cover page)
                valid_slides = [s for s in valid_slides if s.page_number != 1]
                self.log.info(f"Filtered to {len(valid_slides)} valid slides (after removing cover and invalid pages)")
            else:
                valid_slides = slides_content
                self.log.info(f"Using all {len(valid_slides)} pages (no filtering for {file_ext} files)")

            if on_progress:
                on_progress(ProcessingStatus(
                    file_name=file_name,
                    status="processing",
                    progress=0.45,
                    current_step="合并页面",
                ))

            # Step 5: Merge consecutive pages
            merge_groups = self.merger.merge_continuous_pages(valid_slides, titles)

            if on_progress:
                on_progress(ProcessingStatus(
                    file_name=file_name,
                    status="processing",
                    progress=0.55,
                    current_step="创建分块",
                ))

            # Step 6: Create page chunks (with generated titles)
            page_chunks = self.chunking_processor.create_chunks(
                valid_slides,
                images,
                file_name,
                titles,
                self.config.image_server_url,
            )
            self.log.info(f"Created {len(page_chunks)} page chunks")

            if on_progress:
                on_progress(ProcessingStatus(
                    file_name=file_name,
                    status="processing",
                    progress=0.65,
                    current_step="构建父块",
                ))

            # Step 7: Build parent chunks and get child->parent mapping
            parent_chunks, child_to_parent_map = self.parent_builder.build_all(
                merge_groups,
                page_chunks,
                file_name,
            )
            self.log.info(f"Created {len(parent_chunks)} parent chunks, {len(child_to_parent_map)} child->parent mappings")

            # Step 8: Update chunk metadata with parent_id
            for chunk in page_chunks:
                if chunk.id in child_to_parent_map:
                    chunk.metadata["parent_id"] = child_to_parent_map[chunk.id]

            if on_progress:
                on_progress(ProcessingStatus(
                    file_name=file_name,
                    status="processing",
                    progress=0.75,
                    current_step="保存数据",
                ))

            # Step 9: Save parent chunks to DocStore
            for parent in parent_chunks:
                self.doc_store.save(parent)

            # Step 10: Add page chunks to vector store
            self.hybrid_retriever.add_documents(page_chunks)

            if on_progress:
                on_progress(ProcessingStatus(
                    file_name=file_name,
                    status="processing",
                    progress=1.0,
                    current_step="完成",
                ))

            return {
                "file_name": file_name,
                "slides_count": len(slides_content),
                "chunks_count": len(page_chunks),
                "parents_count": len(parent_chunks),
                "images_count": len(images),
            }

        except Exception as e:
            self.log.error(f"Failed to load document: {e}")
            if on_progress:
                on_progress(ProcessingStatus(
                    file_name=file_name,
                    status="error",
                    error=str(e),
                ))
            raise

    def ask(
        self,
        question: str,
        file_name: str = None,
    ) -> AnswerResult:
        """
        Answer a question about the documents

        Args:
            question: User question
            file_name: Optional file name filter

        Returns:
            AnswerResult with answer and sources
        """
        import time
        self.log.info(f"Answering question: {question[:100]}...")

        # Step 1: Hybrid retrieval
        t0 = time.time()
        results = self.hybrid_retriever.get_relevant_documents(
            question, file_name=file_name
        )
        t1 = time.time()
        self.log.info(f"[TIMING] Retrieval: {t1-t0:.2f}s, found {len(results)} results")

        if not results:
            return AnswerResult(
                answer="抱歉，我没有找到相关的内容来回答您的问题。",
                sources=[],
                referenced_pages=[],
            )

        # Step 2: Build child_to_parent map
        t2 = time.time()
        child_to_parent = {}
        chunks_with_parent = 0
        for chunk in results:
            parent_id = chunk.metadata.get("parent_id")
            if parent_id:
                child_to_parent[chunk.id] = parent_id
                chunks_with_parent += 1
        t3 = time.time()
        self.log.info(f"[TIMING] Build parent map: {t3-t2:.2f}s, {chunks_with_parent}/{len(results)} chunks have parent_id")

        # Debug: log all parent_ids
        if child_to_parent:
            self.log.debug(f"Child->Parent mappings: {child_to_parent}")

        # Step 3: Get parent context
        t4 = time.time()
        context = get_parent_context(results, child_to_parent, self.doc_store)
        t5 = time.time()
        self.log.info(f"[TIMING] Get parent context: {t5-t4:.2f}s, context length: {len(context)} chars")

        # Debug: log context preview
        if context:
            self.log.debug(f"Context preview (first 500 chars): {context[:500]}")
        else:
            self.log.warning("Context is empty!")

        if not context:
            # Fall back to raw results if no parent context
            context = "\n\n---\n\n".join([r.content for r in results])
            self.log.info("Using fallback context (no parent chunks)")

        # Step 4: Collect source information
        t6 = time.time()
        sources: List[Dict[str, Any]] = []
        referenced_pages: List[int] = []

        # Parse context to extract page ranges (from the --- markers)
        import re
        parent_pattern = r"参考来源 \d+ \(父块，页面 (\d+)-(\d+)\)"
        single_pattern = r"参考来源 \d+ \(页面 (\d+)\)"

        for line in context.split("\n"):
            match = re.search(parent_pattern, line)
            if match:
                start, end = int(match.group(1)), int(match.group(2))
                sources.append({
                    "file_name": file_name or results[0].file_name if results else "",
                    "pages": list(range(start, end + 1)),
                    "type": "parent",
                })
                referenced_pages.extend(range(start, end + 1))
            else:
                match = re.search(single_pattern, line)
                if match:
                    page = int(match.group(1))
                    if page not in referenced_pages:
                        sources.append({
                            "file_name": file_name or results[0].file_name if results else "",
                            "pages": [page],
                            "type": "single",
                        })
                        referenced_pages.append(page)

        # Deduplicate pages
        referenced_pages = list(set(referenced_pages))
        referenced_pages.sort()
        t7 = time.time()
        self.log.info(f"[TIMING] Parse sources: {t7-t6:.2f}s")

        # Step 5: Generate answer
        t8 = time.time()
        from langchain_core.messages import HumanMessage

        prompt = self._build_qa_prompt(context, question)

        # Log the full prompt for debugging (preview first 500 chars)
        self.log.info(f"[PROMPT] LLM prompt preview (context={len(context)} chars):\n{prompt[:500]}...")

        try:
            message = HumanMessage(content=prompt)
            self.log.info(f"[TIMING] Calling LLM...")
            response = self.llm.invoke([message])
            t9 = time.time()
            self.log.info(f"[TIMING] LLM response: {t9-t8:.2f}s")

            # Debug: log response details
            self.log.info(f"[LLM_RESPONSE] response type: {type(response)}")
            self.log.info(f"[LLM_RESPONSE] response: {response}")

            answer = response.content if hasattr(response, 'content') else str(response)
            self.log.info(f"[LLM_RESPONSE] answer length: {len(answer)} chars, answer: '{answer[:200]}...'")

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

    def ask_stream(
        self,
        question: str,
        file_name: str = None,
    ):
        """
        Answer a question with streaming output.

        Args:
            question: User question
            file_name: Optional file name filter

        Yields:
            tuple: (chunk content, is_complete, sources, referenced_pages)
        """
        self.log.info(f"Answering question (streaming): {question[:100]}...")

        # Step 1: Hybrid retrieval
        results = self.hybrid_retriever.get_relevant_documents(
            question, file_name=file_name
        )
        self.log.info(f"[STREAM] Retrieval: found {len(results)} results")

        if not results:
            yield ("抱歉，我没有找到相关的内容来回答您的问题。", True, [], [])
            return

        # Step 2: Build child_to_parent map
        child_to_parent = {}
        for chunk in results:
            parent_id = chunk.metadata.get("parent_id")
            if parent_id:
                child_to_parent[chunk.id] = parent_id

        # Step 3: Get parent context
        import time
        t_context = time.time()
        context = get_parent_context(results, child_to_parent, self.doc_store)
        t_context_end = time.time()
        self.log.info(f"[STREAM] Get context: {t_context_end-t_context:.2f}s, {len(context)} chars")

        # Debug: check for images in context
        import re
        img_count = len(re.findall(r'!\[', context))
        self.log.info(f"[STREAM] Context contains {img_count} image placeholders")

        if not context:
            context = "\n\n---\n\n".join([r.content for r in results])
            fallback_img_count = len(re.findall(r'!\[', context))
            self.log.info(f"[STREAM] Using fallback context: {len(context)} chars, {fallback_img_count} images")

        # Debug: log context preview
        self.log.debug(f"[STREAM] Context preview (first 500 chars):\n{context[:500]}")

        # Step 4: Collect source information
        sources: List[Dict[str, Any]] = []
        referenced_pages: List[int] = []

        import re
        parent_pattern = r"参考来源 \d+ \(父块，页面 (\d+)-(\d+)\)"
        single_pattern = r"参考来源 \d+ \(页面 (\d+)\)"

        for line in context.split("\n"):
            match = re.search(parent_pattern, line)
            if match:
                start, end = int(match.group(1)), int(match.group(2))
                sources.append({
                    "file_name": file_name or results[0].file_name if results else "",
                    "pages": list(range(start, end + 1)),
                    "type": "parent",
                })
                referenced_pages.extend(range(start, end + 1))
            else:
                match = re.search(single_pattern, line)
                if match:
                    page = int(match.group(1))
                    if page not in referenced_pages:
                        sources.append({
                            "file_name": file_name or results[0].file_name if results else "",
                            "pages": [page],
                            "type": "single",
                        })
                        referenced_pages.append(page)

        referenced_pages = list(set(referenced_pages))
        referenced_pages.sort()

        # Step 5: Generate streaming answer
        from langchain_core.messages import HumanMessage

        prompt = self._build_qa_prompt(context, question)

        message = HumanMessage(content=prompt)

        import time
        t0 = time.time()
        self.log.info(f"[STREAM] Calling LLM...")

        try:
            full_response = ""
            chunk_count = 0
            for chunk in self.llm.stream([message]):
                content = chunk.content if hasattr(chunk, 'content') else str(chunk)
                full_response += content
                chunk_count += 1
                yield (content, False, sources, referenced_pages)

            t1 = time.time()
            self.log.info(f"[STREAM] LLM completed: {t1-t0:.2f}s, {chunk_count} chunks, {len(full_response)} chars")

            # Yield completion signal (no content, just mark complete)
            yield ("", True, sources, referenced_pages)
        except Exception as e:
            self.log.error(f"[STREAM] Failed to generate streaming answer: {e}")
            yield (f"生成回答时出错: {str(e)}", True, sources, referenced_pages)

    def list_documents(self) -> List[Dict[str, Any]]:
        """List all loaded documents (by source file, not parent chunks)"""
        file_map: Dict[str, Dict[str, Any]] = {}

        # 遍历所有父块，收集每个文件的页码范围
        for parent_file in self.doc_store.store_dir.glob("*.json"):
            data = json.loads(parent_file.read_text(encoding="utf-8"))
            file_name = data["file_name"]
            start_page = data["start_page"]
            end_page = data["end_page"]

            if file_name not in file_map:
                file_map[file_name] = {
                    "file_name": file_name,
                    "pages": set(),  # 使用 set 收集所有页码
                    "chunks_count": 0,
                }
            file_map[file_name]["pages"].add(start_page)
            file_map[file_name]["pages"].add(end_page)
            file_map[file_name]["chunks_count"] += 1

        # 转换为列表格式
        documents = []
        for file_name, info in file_map.items():
            sorted_pages = sorted(info["pages"])
            page_range = f"{min(sorted_pages)}-{max(sorted_pages)}" if len(sorted_pages) > 1 else str(sorted_pages[0])
            documents.append({
                "file_name": file_name,
                "pages": page_range,
                "total_pages": len(sorted_pages),
                "chunks_count": info["chunks_count"],
            })

        return documents

    def clear(self, file_name: str = None) -> int:
        """Clear all documents, optionally for a specific file"""
        import shutil

        if file_name:
            # Clear specific file from all stores
            doc_count = self.doc_store.clear(file_name)
            vector_count = self.vector_store.delete_by_file(file_name) if self.vector_store else 0

            # Delete images for this file (images/{hash}/)
            file_hash = hashlib.md5(file_name.encode("utf-8")).hexdigest()[:8]
            images_dir = self.config.images_dir / file_hash
            if images_dir.exists():
                shutil.rmtree(images_dir)
                self.log.info(f"Deleted images directory: {images_dir}")

            # Delete uploaded file
            upload_file = self.config.upload_dir / f"{file_name}.pptx"
            if upload_file.exists():
                upload_file.unlink()
                self.log.info(f"Deleted uploaded file: {upload_file}")

            self.log.info(f"Cleared all data for {file_name}: {doc_count} docs, {vector_count} vector chunks")
            return doc_count
        else:
            # Clear all
            doc_count = self.doc_store.clear()
            vector_count = self.vector_store.clear() if self.vector_store else 0

            # Clear images directory (keep the dir itself)
            images_dir = self.config.images_dir
            if images_dir.exists():
                for item in images_dir.iterdir():
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
                self.log.info("Cleared images directory")

            # Clear uploads directory
            uploads_dir = self.config.upload_dir
            if uploads_dir.exists():
                deleted = 0
                for item in uploads_dir.iterdir():
                    try:
                        item.unlink()
                        deleted += 1
                    except Exception as e:
                        self.log.warning(f"Failed to delete {item}: {e}")
                self.log.info(f"Cleared uploads directory: {deleted} files deleted")
            else:
                self.log.info("Uploads directory does not exist, nothing to clear")

            self.log.info(f"Cleared all data: {doc_count} doc chunks, {vector_count} vector chunks")
            return doc_count
